from __future__ import annotations

from typing import List, Dict, Any
import io

import fitz  # PyMuPDF

CATEGORY_COLORS = {
	"Safe": (46/255, 125/255, 50/255),
	"Financial": (21/255, 101/255, 192/255),
	"Compliance": (106/255, 27/255, 154/255),
	"Liability": (198/255, 40/255, 40/255),
	"Operational": (239/255, 108/255, 0/255),
}


def _pick_color(category: str) -> tuple:
	return CATEGORY_COLORS.get(category, (1.0, 0.8, 0.0))


def _candidate_snippets(text: str, max_len: int = 80) -> List[str]:
	text = (text or "").strip()
	if not text:
		return []
	# Prefer a few snippets to increase chance of hits
	snips = []
	if len(text) <= max_len:
		snips.append(text)
	else:
		snips.append(text[:max_len])
		# Also include tail to catch end phrases
		snips.append(text[-max_len:])
	return list(dict.fromkeys([s for s in snips if len(s) >= 12]))


def generate_annotated_pdf(pdf_bytes: bytes, results: List[Dict[str, Any]]) -> bytes:
	"""
	Generate an annotated PDF by highlighting clause text matches on their pages.
	This uses text search; if multiple matches, all will be highlighted.
	"""
	doc = fitz.open(stream=pdf_bytes, filetype="pdf")
	for item in results:
		preds = item.get("predictions", [])
		if not preds:
			continue
		category = preds[0].get("category", "Safe")
		if category == "Safe":
			continue
		page_index = max(0, int(item.get("page", 1)) - 1)
		if page_index >= len(doc):
			continue
		page = doc[page_index]
		color = _pick_color(category)
		for snippet in _candidate_snippets(item.get("text", "")):
			try:
				rects = page.search_for(snippet, quads=False)
			except Exception:
				rects = []
			for r in rects:
				annot = page.add_highlight_annot(r)
				annot.set_colors(stroke=color, fill=color)
				annot.set_opacity(0.25)
				annot.update()
	buf = io.BytesIO()
	doc.save(buf)
	doc.close()
	return buf.getvalue()
