from __future__ import annotations

from typing import List, Dict, Any, Tuple
import io
import unicodedata

import fitz  # PyMuPDF
import pdfplumber
from pdf2image import convert_from_bytes
import pytesseract
from pytesseract import Output
from docx import Document


def _normalize_text(s: str) -> str:
	s = s.replace("\u0000", " ")
	s = unicodedata.normalize("NFC", s)
	return " ".join(s.split())


def _join_hyphenated(lines: List[str]) -> List[str]:
	joined: List[str] = []
	buf = ""
	for line in lines:
		line = line.rstrip()
		if line.endswith("-"):
			buf += line[:-1]
			continue
		else:
			buf += line
			joined.append(buf)
			buf = ""
	if buf:
		joined.append(buf)
	return joined


def detect_pdf_has_text(pdf_bytes: bytes) -> bool:
	try:
		with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
			for page in pdf.pages:
				if (page.extract_text() or "").strip():
					return True
	except Exception:
		pass
	try:
		doc = fitz.open(stream=pdf_bytes, filetype="pdf")
		for page in doc:
			blocks = page.get_text("blocks") or []
			if any((b[4] or "").strip() for b in blocks):
				return True
	finally:
		try:
			doc.close()
		except Exception:
			pass
	return False


def extract_pdf_text_layout(pdf_bytes: bytes) -> Dict[str, Any]:
	doc = fitz.open(stream=pdf_bytes, filetype="pdf")
	pages_out: List[Dict[str, Any]] = []
	for i, page in enumerate(doc, start=1):
		blocks_out: List[Dict[str, Any]] = []
		blocks = page.get_text("blocks") or []
		char_offset = 0
		for b in blocks:
			x0, y0, x1, y1, text, block_no, block_type = b[0], b[1], b[2], b[3], b[4], b[5], (b[6] if len(b) > 6 else 0)
			if not (text or "").strip():
				continue
			norm = _normalize_text(text)
			lines = _join_hyphenated(norm.splitlines())
			norm = "\n".join(lines)
			length = len(norm)
			blocks_out.append({
				"text": norm,
				"bbox": {"x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0},
				"char_start": char_offset,
				"char_end": char_offset + length,
				"block_no": block_no,
				"type": block_type,
			})
			char_offset += length + 1
		pages_out.append({
			"page_number": i,
			"blocks": blocks_out,
		})
	doc.close()
	return {"type": "pdf_text", "page_count": len(pages_out), "pages": pages_out}


def ocr_scanned_pdf(pdf_bytes: bytes, language: str = "eng", psm: int = 3) -> Dict[str, Any]:
	images = convert_from_bytes(pdf_bytes, fmt="png", dpi=300)
	pages_out: List[Dict[str, Any]] = []
	for i, img in enumerate(images, start=1):
		conf_accum = 0.0
		conf_count = 0
		data = pytesseract.image_to_data(img, lang=language, config=f"--psm {psm}", output_type=Output.DICT)
		blocks_out: List[Dict[str, Any]] = []
		char_offset = 0
		for j in range(len(data["text"])):
			text = (data["text"][j] or "").strip()
			if not text:
				continue
			x, y, w, h = data["left"][j], data["top"][j], data["width"][j], data["height"][j]
			conf = float(data.get("conf", [0])[j] or 0)
			conf_accum += max(conf, 0)
			conf_count += 1
			norm = _normalize_text(text)
			length = len(norm)
			blocks_out.append({
				"text": norm,
				"bbox": {"x": x, "y": y, "w": w, "h": h},
				"char_start": char_offset,
				"char_end": char_offset + length,
				"ocr_conf": conf,
			})
			char_offset += length + 1
		avg_conf = (conf_accum / conf_count) if conf_count else 0.0
		pages_out.append({
			"page_number": i,
			"blocks": blocks_out,
			"ocr_avg_conf": avg_conf,
			"needs_review": avg_conf < 60.0,
		})
	return {"type": "pdf_scanned", "page_count": len(pages_out), "pages": pages_out}


def parse_docx_with_styles(docx_bytes: bytes) -> Dict[str, Any]:
	doc = Document(io.BytesIO(docx_bytes))
	pages_out: List[Dict[str, Any]] = []
	blocks_out: List[Dict[str, Any]] = []
	char_offset = 0
	for p in doc.paragraphs:
		text = _normalize_text(p.text or "")
		if not text:
			continue
		length = len(text)
		blocks_out.append({
			"text": text,
			"bbox": None,
			"char_start": char_offset,
			"char_end": char_offset + length,
			"style": getattr(p.style, 'name', None),
			"num": getattr(p._p.pPr.numPr, 'numId', None) if hasattr(p._p, 'pPr') and getattr(p._p.pPr, 'numPr', None) else None,
		})
		char_offset += length + 1
	pages_out.append({"page_number": 1, "blocks": blocks_out})
	return {"type": "docx", "page_count": 1, "pages": pages_out}


def preprocess_file(file_bytes: bytes, filename: str) -> Dict[str, Any]:
	if filename.lower().endswith(".pdf"):
		has_text = detect_pdf_has_text(file_bytes)
		if has_text:
			return extract_pdf_text_layout(file_bytes)
		else:
			# try both PSM 6 then 3 for layout text
			try:
				return ocr_scanned_pdf(file_bytes, psm=6)
			except Exception:
				return ocr_scanned_pdf(file_bytes, psm=3)
	elif filename.lower().endswith(".docx"):
		return parse_docx_with_styles(file_bytes)
	else:
		raise ValueError("Unsupported file type")
