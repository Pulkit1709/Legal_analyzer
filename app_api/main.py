import os, uuid, hashlib, tempfile, mimetypes
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, UploadFile, File, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from cryptography.fernet import Fernet
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
import magic
import sqlite3
import boto3
import clamd
import io

from app_api.serving import router as serving_router
from app_api.downloads import router as download_router
from app_api.feedback import router as feedback_router
from app_api.auth import require_role, set_doc_acl, require_auth
from app_api.metrics import router as metrics_router, MetricsMiddleware
from app_api.security import HTTPSRedirectMiddleware

S3_BUCKET = os.environ.get("S3_BUCKET")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
s3 = boto3.client("s3", region_name=AWS_REGION) if S3_BUCKET else None

CLAMD_HOST = os.environ.get("CLAMD_HOST")
CLAMD_PORT = int(os.environ.get("CLAMD_PORT", "3310"))
clam = clamd.ClamdNetworkSocket(host=CLAMD_HOST, port=CLAMD_PORT) if CLAMD_HOST else None

ALLOWED_MIME = {
	"application/pdf",
	"application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
MAX_BYTES = 25 * 1024 * 1024
STORAGE_DIR = Path("storage/ephemeral"); STORAGE_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = Path("storage/metadata.db")
FERNET_KEY_PATH = Path("storage/fernet.key")

if not FERNET_KEY_PATH.exists():
	FERNET_KEY_PATH.write_bytes(Fernet.generate_key())
FERNET = Fernet(FERNET_KEY_PATH.read_bytes())

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="Upload & Analyze API", version="1.0.0")
app.add_middleware(HTTPSRedirectMiddleware)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(MetricsMiddleware)
app.state.limiter = limiter
app.add_middleware(
	CORSMiddleware,
	allow_origins=["http://localhost:3000", "http://localhost:8501"],
	allow_credentials=True,
	allow_methods=["GET", "POST", "OPTIONS"],
	allow_headers=["*"]
)

class UploadResponse(BaseModel):
	job_id: str
	status: str
	filename: str
	size_bytes: int
	mime: str
	sha256: str

class PresignResponse(BaseModel):
	job_id: str
	url: str
	fields: dict

@app.exception_handler(RateLimitExceeded)
def rl_handler(request: Request, exc: RateLimitExceeded):
	return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})

def db_init():
	with sqlite3.connect(DB_PATH) as con:
		con.execute(
			"""
			CREATE TABLE IF NOT EXISTS uploads (
				job_id TEXT PRIMARY KEY,
				filename TEXT NOT NULL,
				size_bytes INTEGER NOT NULL,
				mime TEXT NOT NULL,
				sha256 TEXT NOT NULL,
				storage_path TEXT NOT NULL,
				created_at TEXT NOT NULL,
				status TEXT NOT NULL
			)
			"""
		)

def db_insert(meta: dict):
	with sqlite3.connect(DB_PATH) as con:
		con.execute(
			"""
			INSERT INTO uploads (job_id, filename, size_bytes, mime, sha256, storage_path, created_at, status)
			VALUES (:job_id, :filename, :size_bytes, :mime, :sha256, :storage_path, :created_at, :status)
			""",
			meta,
		)

db_init()

def validate_mime_and_size(filename: str, sniffed_mime: str, size_bytes: int):
	if size_bytes > MAX_BYTES:
		raise HTTPException(413, detail="File too large.")
	if sniffed_mime not in ALLOWED_MIME:
		if sniffed_mime == "application/zip" and filename.lower().endswith(".docx"):
			return
		raise HTTPException(400, detail=f"Unsupported type: {sniffed_mime}")

def compute_sha256(fp) -> str:
	fp.seek(0)
	h = hashlib.sha256()
	for chunk in iter(lambda: fp.read(8192), b""):
		h.update(chunk)
	fp.seek(0)
	return h.hexdigest()

def encrypt_and_store(fp, job_id: str) -> Path:
	fp.seek(0)
	# Optional AV scan
	if clam:
		pos = fp.tell()
		fp.seek(0)
		data = fp.read()
		resp = clam.instream(io.BytesIO(data))
		fp.seek(pos)
		if resp and resp.get('stream', ['OK'])[0] != 'OK':
			raise HTTPException(400, detail="Malware detected")
	ciphertext = FERNET.encrypt(fp.read())
	out_path = STORAGE_DIR / f"{job_id}.bin"
	out_path.write_bytes(ciphertext)
	return out_path

@app.post("/api/upload/presign", response_model=PresignResponse, dependencies=[Depends(require_role(["Admin","Reviewer"]))])
async def presign_upload(filename: str, payload=Depends(require_auth)):
	if not s3:
		raise HTTPException(400, "S3 not configured")
	key = f"uploads/{payload.get('ws')}/{uuid.uuid4().hex}/{filename}"
	conditions = [["content-length-range", 1, MAX_BYTES]]
	fields = {"acl": "private"}
	post = s3.generate_presigned_post(Bucket=S3_BUCKET, Key=key, Fields=fields, Conditions=conditions, ExpiresIn=600)
	job_id = "job_" + uuid.uuid4().hex
	set_doc_acl(job_id, payload.get('ws'), payload.get('sub'))
	return PresignResponse(job_id=job_id, url=post['url'], fields=post['fields'])

@app.post("/api/upload", response_model=UploadResponse, dependencies=[Depends(require_role(["Admin","Reviewer"]))])
@limiter.limit("10/minute")
async def upload(file: UploadFile = File(...), payload=Depends(require_auth)):
	spooled = tempfile.SpooledTemporaryFile(max_size=MAX_BYTES + 1)
	total = 0
	while True:
		block = await file.read(1024 * 1024)
		if not block:
			break
		total += len(block)
		if total > MAX_BYTES:
			spooled.close()
			raise HTTPException(413, detail="File too large.")
		spooled.write(block)

	spooled.seek(0)
	head = spooled.read(4096)
	spooled.seek(0)
	sniffed_mime = magic.from_buffer(head, mime=True) or mimetypes.guess_type(file.filename)[0] or "application/octet-stream"

	validate_mime_and_size(file.filename, sniffed_mime, total)
	sha256 = compute_sha256(spooled)

	job_id = "job_" + uuid.uuid4().hex
	storage_path = encrypt_and_store(spooled, job_id)
	spooled.close()

	meta = {
		"job_id": job_id,
		"filename": file.filename,
		"size_bytes": total,
		"mime": sniffed_mime,
		"sha256": sha256,
		"storage_path": str(storage_path),
		"created_at": datetime.utcnow().isoformat() + "Z",
		"status": "uploaded",
	}
	db_insert(meta)
	set_doc_acl(job_id, payload.get('ws'), payload.get('sub'))

	return UploadResponse(
		job_id=job_id,
		status="queued",
		filename=file.filename,
		size_bytes=total,
		mime=sniffed_mime,
		sha256=sha256,
	)

app.include_router(serving_router, dependencies=[Depends(require_role(["Admin","Reviewer","Viewer"]))])
app.include_router(download_router, dependencies=[Depends(require_role(["Admin","Reviewer","Viewer"]))])
app.include_router(feedback_router, dependencies=[Depends(require_role(["Admin","Reviewer"]))])
app.include_router(metrics_router)
