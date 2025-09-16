from __future__ import annotations

from typing import Dict, Any, List
import json
import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from utils.preprocess import preprocess_file
from utils.segmenter import segment_document
from utils.features import extract_features_for_clause
from ml.infer import RiskClassifier
from app_api.metrics import MODEL_LABEL_DIST, MODEL_CONFIDENCE, JOB_DURATION
from utils.drift import detect_drift
from app_api.auth import enforce_doc_access, require_auth

router = APIRouter()

ARTIFACT_DIR = Path("artifacts/model_roberta")
MODEL_VERSION = os.environ.get("MODEL_VERSION", "roberta-base@local")

# Simple in-memory job store (MVP); replace with Redis/DB in production
JOBS: Dict[str, Dict[str, Any]] = {}
EXECUTOR = ThreadPoolExecutor(max_workers=2)


class AnalyzeResponse(BaseModel):
	job_id: str
	status: str
	model_version: str


def _run_pipeline(job_id: str, file_bytes: bytes, filename: str) -> Dict[str, Any]:
	start = datetime.utcnow()
	JOBS[job_id]["status"] = "preprocessing"
	pre = preprocess_file(file_bytes, filename)

	JOBS[job_id]["status"] = "segmenting"
	clauses = segment_document(job_id, pre)

	JOBS[job_id]["status"] = "featurizing"
	aug = [extract_features_for_clause(c) for c in clauses]

	JOBS[job_id]["status"] = "loading_model"
	model = RiskClassifier(str(ARTIFACT_DIR))

	JOBS[job_id]["status"] = "inference"
	results = []
	texts_for_drift = []
	for c in aug:
		preds = model.predict_clause(c["normalized_text"])  # multi-label probs
		texts_for_drift.append(c["normalized_text"])
		for p in preds:
			MODEL_LABEL_DIST.labels(label=p["label"]).inc()
			MODEL_CONFIDENCE.observe(p["score"])
		top = [p for p in preds if p["score"] >= 0.5]
		results.append({
			"clause_id": c.get("clause_id"),
			"page": c.get("page"),
			"text": c.get("original_text", c.get("text")),
			"predictions": top,
			"severity_score": max((p["score"] for p in top), default=0.0),
			"severity": ("High" if any(p["score"] >= 0.75 for p in top) else ("Medium" if any(p["score"] >= 0.5 for p in top) else "Low")),
			"explanation": "Heuristic features: modals={}; negation={}".format(
				c["features"].get("has_modals"), c["features"].get("has_negation")
			),
			"important_tokens": [],
		})

	JOBS[job_id]["status"] = "drift_check"
	drift = detect_drift(texts_for_drift)

	JOBS[job_id]["status"] = "packaging"
	flagged = sum(1 for r in results if r["predictions"])
	summary = {
		"total_clauses": len(results),
		"flagged": flagged,
		"by_category": {},
		"drift": drift,
	}

	out = {
		"job_id": job_id,
		"document_name": filename,
		"model_version": MODEL_VERSION,
		"summary": summary,
		"clauses": results,
		"created_at": datetime.utcnow().isoformat() + "Z",
	}
	JOB_DURATION.observe((datetime.utcnow() - start).total_seconds())
	return out


@router.post("/api/analyze/{job_id}", response_model=AnalyzeResponse)
def analyze(job_id: str, payload = Depends(require_auth)):
	enforce_doc_access(job_id, payload)
	from app_api.main import STORAGE_DIR, FERNET
	enc_path = STORAGE_DIR / f"{job_id}.bin"
	if not enc_path.exists():
		raise HTTPException(404, detail="Job not found or file missing")
	file_bytes = FERNET.decrypt(enc_path.read_bytes())
	filename = f"{job_id}.pdf"

	JOBS[job_id] = {"status": "queued"}
	future = EXECUTOR.submit(_run_pipeline, job_id, file_bytes, filename)
	JOBS[job_id]["future"] = future
	return AnalyzeResponse(job_id=job_id, status="queued", model_version=MODEL_VERSION)


@router.get("/api/status/{job_id}")
def status(job_id: str, payload = Depends(require_auth)):
	enforce_doc_access(job_id, payload)
	state = JOBS.get(job_id)
	if not state:
		return {"job_id": job_id, "status": "unknown"}
	st = state.get("status", "queued")
	done = state.get("future").done() if state.get("future") else False
	return {"job_id": job_id, "status": ("completed" if done and st == "packaging" else st)}


@router.get("/api/results/{job_id}")
def results(job_id: str, payload = Depends(require_auth)):
	enforce_doc_access(job_id, payload)
	state = JOBS.get(job_id)
	if not state:
		raise HTTPException(404, detail="Job not found")
	fut = state.get("future")
	if not fut:
		raise HTTPException(400, detail="Job not started")
	if not fut.done():
		raise HTTPException(202, detail="Job not completed")
	try:
		out = fut.result()
		return out
	except Exception as e:
		raise HTTPException(500, detail=str(e))
