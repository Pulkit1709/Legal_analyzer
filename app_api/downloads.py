from __future__ import annotations

from typing import Dict, Any
import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from utils.report import build_json_report, build_csv_report, build_pdf_report

router = APIRouter()


@router.get("/api/download/{job_id}")
def download(job_id: str, format: str = "json", redact_pii: bool = False):
	from app_api.serving import JOBS
	state = JOBS.get(job_id)
	if not state or not state.get("future") or not state["future"].done():
		raise HTTPException(404, detail="Results not ready")
	out = state["future"].result()
	results = out.get("clauses", [])
	summary = out.get("summary", {})
	doc_name = out.get("document_name", job_id)

	fmt = (format or "json").lower()
	if fmt == "json":
		return JSONResponse(build_json_report(doc_name, results, summary, redact_pii=redact_pii))
	elif fmt == "csv":
		import pandas as pd
		df = pd.DataFrame([
			{
				"clause_id": r.get("clause_id"),
				"page": r.get("page"),
				"category": (r.get("predictions") or [{}])[0].get("category") or (r.get("predictions") or [{}])[0].get("label"),
				"severity": r.get("severity"),
				"confidence": (r.get("predictions") or [{}])[0].get("confidence") or (r.get("predictions") or [{}])[0].get("score"),
				"text": r.get("text"),
				"explanation": r.get("explanation"),
			}
			for r in results
		])
		bio = build_csv_report(df, redact_pii=redact_pii)
		return StreamingResponse(iter([bio.getvalue()]), media_type="text/csv", headers={"Content-Disposition": f"attachment; filename={doc_name}_clauses.csv"})
	elif fmt == "pdf":
		pdf_bytes = build_pdf_report(doc_name, results, summary, redact_pii_flag=redact_pii)
		return StreamingResponse(iter([pdf_bytes]), media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename={doc_name}_report.pdf"})
	else:
		raise HTTPException(400, detail="Unsupported format")
