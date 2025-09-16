import io
import pytest

from utils.preprocess import preprocess_file, detect_pdf_has_text


def test_text_pdf_minimal():
	# Minimal PDF with text block might be too small; we still ensure function runs
	pdf_bytes = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF"
	out = preprocess_file(pdf_bytes, "sample.pdf")
	assert out["type"] in ("pdf_text", "pdf_scanned")
	assert "pages" in out


def test_docx_minimal(tmp_path):
	pytest.importorskip("docx")
	# Construct a docx via python-docx for realistic bytes if available
	from docx import Document
	doc = Document()
	doc.add_paragraph("Hello World")
	buf = io.BytesIO()
	doc.save(buf)
	out = preprocess_file(buf.getvalue(), "x.docx")
	assert out["type"] == "docx"
	assert out["page_count"] == 1
