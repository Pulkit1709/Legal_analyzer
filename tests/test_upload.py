import io
from fastapi.testclient import TestClient
from app_api.main import app, STORAGE_DIR

client = TestClient(app)


def test_upload_pdf_ok(tmp_path):
	content = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF"
	files = {"file": ("test.pdf", content, "application/pdf")}
	r = client.post("/api/upload", files=files)
	assert r.status_code == 200, r.text
	data = r.json()
	assert data["status"] == "queued"
	assert (STORAGE_DIR / f"{data['job_id']}.bin").exists()


def test_reject_invalid_type():
	files = {"file": ("test.txt", b"hello", "text/plain")}
	r = client.post("/api/upload", files=files)
	assert r.status_code in (400, 415)


def test_reject_oversize():
	big = b"a" * (26 * 1024 * 1024)  # 26MB
	files = {"file": ("big.pdf", big, "application/pdf")}
	r = client.post("/api/upload", files=files)
	assert r.status_code in (400, 413)
