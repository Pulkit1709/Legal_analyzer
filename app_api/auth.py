from __future__ import annotations

from typing import Optional, List
from datetime import datetime, timedelta
import sqlite3
from pathlib import Path
import jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

DB_PATH = Path("storage/metadata.db")
JWT_SECRET = "dev_secret_change_me"  # replace with env var in prod
JWT_ALG = "HS256"
ACCESS_TTL_MIN = 60 * 8

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
auth_scheme = HTTPBearer()


def db_init():
	with sqlite3.connect(DB_PATH) as con:
		con.execute("""
		CREATE TABLE IF NOT EXISTS users (
			id TEXT PRIMARY KEY,
			email TEXT UNIQUE NOT NULL,
			name TEXT,
			password_hash TEXT,
			role TEXT NOT NULL,
			workspace_id TEXT NOT NULL
		)
		""")
		con.execute("""
		CREATE TABLE IF NOT EXISTS workspaces (
			id TEXT PRIMARY KEY,
			name TEXT NOT NULL
		)
		""")
		con.execute("""
		CREATE TABLE IF NOT EXISTS audit (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			user_id TEXT,
			action TEXT,
			resource TEXT,
			created_at TEXT
		)
		""")
		con.execute("""
		CREATE TABLE IF NOT EXISTS doc_acl (
			job_id TEXT PRIMARY KEY,
			workspace_id TEXT NOT NULL,
			owner_user_id TEXT NOT NULL
		)
		""")

db_init()


def hash_password(p: str) -> str:
	return pwd_context.hash(p)


def verify_password(p: str, h: str) -> bool:
	return pwd_context.verify(p, h)


def create_token(user_id: str, role: str, workspace_id: str) -> str:
	payload = {
		"sub": user_id,
		"role": role,
		"ws": workspace_id,
		"exp": datetime.utcnow() + timedelta(minutes=ACCESS_TTL_MIN),
	}
	return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def decode_token(token: str):
	try:
		return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
	except Exception:
		raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


def require_auth(credentials: HTTPAuthorizationCredentials = Depends(auth_scheme)):
	payload = decode_token(credentials.credentials)
	return payload


def require_role(roles: List[str]):
	def _dep(payload = Depends(require_auth)):
		if payload.get("role") not in roles:
			raise HTTPException(403, "Forbidden")
		return payload
	return _dep


def audit_log(user_id: str, action: str, resource: str):
	with sqlite3.connect(DB_PATH) as con:
		con.execute("INSERT INTO audit (user_id, action, resource, created_at) VALUES (?,?,?,?)",
				 (user_id, action, resource, datetime.utcnow().isoformat() + 'Z'))


def set_doc_acl(job_id: str, workspace_id: str, owner_user_id: str):
	with sqlite3.connect(DB_PATH) as con:
		con.execute("INSERT OR REPLACE INTO doc_acl (job_id, workspace_id, owner_user_id) VALUES (?,?,?)",
				 (job_id, workspace_id, owner_user_id))


def enforce_doc_access(job_id: str, requester_payload: dict):
	ws = requester_payload.get('ws')
	role = requester_payload.get('role')
	if not ws:
		raise HTTPException(403, "No workspace context")
	with sqlite3.connect(DB_PATH) as con:
		cur = con.execute("SELECT workspace_id FROM doc_acl WHERE job_id = ?", (job_id,))
		row = cur.fetchone()
		if not row:
			raise HTTPException(404, "Job not found")
		(doc_ws,) = row
		if doc_ws != ws and role != 'Admin':
			raise HTTPException(403, "Forbidden: cross-workspace access")
