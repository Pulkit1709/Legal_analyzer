from __future__ import annotations

from typing import List, Dict, Any
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException
import sqlite3
from pathlib import Path
from datetime import datetime

router = APIRouter()

DB_PATH = Path("storage/metadata.db")


def db_init():
	with sqlite3.connect(DB_PATH) as con:
		con.execute(
			"""
			CREATE TABLE IF NOT EXISTS feedback (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				job_id TEXT NOT NULL,
				clause_id TEXT NOT NULL,
				user_id TEXT NOT NULL,
				original_prediction TEXT,
				new_labels TEXT,
				new_severity TEXT,
				comment TEXT,
				created_at TEXT NOT NULL
			)
			"""
		)

db_init()


class ClauseFeedback(BaseModel):
	clause_id: str
	original_prediction: Dict[str, Any] | None = None
	new_labels: List[str] | None = None
	new_severity: str | None = None
	comment: str | None = None


class FeedbackRequest(BaseModel):
	user_id: str
	items: List[ClauseFeedback]


@router.post("/api/feedback/{job_id}")
def submit_feedback(job_id: str, payload: FeedbackRequest):
	if not payload.items:
		raise HTTPException(400, detail="No items provided")
	with sqlite3.connect(DB_PATH) as con:
		for it in payload.items:
			con.execute(
				"""
				INSERT INTO feedback (job_id, clause_id, user_id, original_prediction, new_labels, new_severity, comment, created_at)
				VALUES (?, ?, ?, ?, ?, ?, ?, ?)
				""",
				(
					job_id,
					it.clause_id,
					payload.user_id,
					json_dumps(it.original_prediction),
					json_dumps(it.new_labels),
					it.new_severity,
					it.comment,
					datetime.utcnow().isoformat() + "Z",
				),
			)
	return {"job_id": job_id, "saved": len(payload.items)}


def json_dumps(obj) -> str:
	import json
	return json.dumps(obj, ensure_ascii=False) if obj is not None else None
