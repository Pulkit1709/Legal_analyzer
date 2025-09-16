from __future__ import annotations

from typing import List, Dict, Any, Union
import io
import os

import pdfplumber
from docx import Document
from pypdf import PdfReader


def _extract_pdf(file_bytes: bytes) -> List[Dict[str, Any]]:
	pages: List[Dict[str, Any]] = []
	with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
		for i, page in enumerate(pdf.pages, start=1):
			text = page.extract_text() or ""
			pages.append({"page_number": i, "text": text})
	return pages


def _extract_docx(file_bytes: bytes) -> List[Dict[str, Any]]:
	doc = Document(io.BytesIO(file_bytes))
	text = []
	for p in doc.paragraphs:
		text.append(p.text)
	joined = "\n".join(text)
	return [{"page_number": 1, "text": joined}]


def extract_document(file_or_bytes: Union[bytes, io.BytesIO, Any], name: str | None = None) -> List[Dict[str, Any]]:
	"""
	Accepts raw bytes or a file-like object (with optional .name) and returns page dicts.
	"""
	# Normalize to bytes
	data: bytes
	fname = name
	if hasattr(file_or_bytes, "read") and callable(getattr(file_or_bytes, "read")):
		# file-like
		try:
			data = file_or_bytes.read()
		except TypeError:
			# Some buffers require .getvalue()
			data = file_or_bytes.getvalue()
		if fname is None and hasattr(file_or_bytes, "name"):
			fname = str(getattr(file_or_bytes, "name"))
	elif isinstance(file_or_bytes, (bytes, bytearray)):
		data = bytes(file_or_bytes)
	else:
		raise ValueError("Unsupported input type for extract_document")

	fname = (fname or "uploaded").lower()
	if fname.endswith(".pdf"):
		try:
			PdfReader(io.BytesIO(data))
		except Exception:
			pass
		return _extract_pdf(data)
	elif fname.endswith(".docx"):
		return _extract_docx(data)
	else:
		# Guess by magic: naive fallback uses PDF first
		try:
			return _extract_pdf(data)
		except Exception:
			return _extract_docx(data)
