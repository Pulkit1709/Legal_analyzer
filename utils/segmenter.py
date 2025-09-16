from __future__ import annotations

from typing import List, Dict, Any, Optional, Tuple
import re

try:
	import spacy
	NLP = spacy.blank("en")
	# Enable sentencizer tuned for legal abbreviations
	rule = NLP.add_pipe("sentencizer")
except Exception:
	NLP = None

HEADING_PATTERNS = [
	re.compile(r"^(section\s+)?\d+(\.\d+)*[\).\-]\s+", re.I),
	re.compile(r"^(article\s+)?[ivxlc]+[\).\-]\s+", re.I),
	re.compile(r"^(schedule|annex|appendix)\s+\w+", re.I),
	re.compile(r"^(confidentiality|termination|liability|payment|indemnity|governing law|definitions)\b", re.I),
	re.compile(r"^[\-\*\u2022]\s+"),  # bullets
]


def _is_heading(line: str) -> bool:
	line = line.strip()
	for pat in HEADING_PATTERNS:
		if pat.search(line):
			return True
	return False


def _split_lines_keep_offsets(text: str) -> List[Tuple[str, int, int]]:
	out = []
	pos = 0
	for part in re.split(r"(\r?\n)", text):
		if part == "\n" or part == "\r\n":
			pos += len(part)
			continue
		if part:
			start = pos
			end = pos + len(part)
			out.append((part, start, end))
			pos = end
	return out


def _spacy_sentences(text: str) -> List[Tuple[str, int, int]]:
	if not NLP:
		return [(text, 0, len(text))] if text else []
	doc = NLP(text)
	return [(sent.text, sent.start_char, sent.end_char) for sent in doc.sents]


def _merge_short(sentences: List[Tuple[str, int, int]], headings_map: Dict[int, str]) -> List[Tuple[str, int, int]]:
	merged: List[Tuple[str, int, int]] = []
	buf: Optional[Tuple[str, int, int]] = None
	for text, s, e in sentences:
		length = len(text.strip())
		is_heading_here = any(s >= hs and s < he for hs, he in headings_map.keys())
		if is_heading_here:
			if buf:
				merged.append(buf)
				buf = None
			merged.append((text, s, e))
			continue
		if length < 80:
			if not buf:
				buf = (text, s, e)
			else:
				buf = (buf[0] + " " + text, buf[1], e)
			continue
		if buf:
			merged.append(buf)
			buf = None
		merged.append((text, s, e))
	if buf:
		merged.append(buf)
	return merged


def _collect_headings(text: str) -> Dict[Tuple[int, int], str]:
	headings: Dict[Tuple[int, int], str] = {}
	for line, s, e in _split_lines_keep_offsets(text):
		if _is_heading(line):
			headings[(s, e)] = line.strip()
	return headings


def _chunk_long(text: str, max_tokens: int = 512, overlap: int = 50) -> List[str]:
	# heuristic tokenization by whitespace
	tokens = text.split()
	if len(tokens) <= max_tokens:
		return [text]
	parts: List[str] = []
	start = 0
	while start < len(tokens):
		end = min(len(tokens), start + max_tokens)
		parts.append(" ".join(tokens[start:end]))
		if end == len(tokens):
			break
		start = end - overlap
		if start < 0:
			start = 0
	return parts


def segment_pages_to_clauses(pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
	clauses: List[Dict[str, Any]] = []
	clause_idx = 0
	current_section: Optional[str] = None
	for page in pages:
		page_num = int(page.get("page_number", 1))
		# If using preprocess output, join block texts with newlines and keep bboxes map
		blocks = page.get("blocks", [])
		offset_map: List[Tuple[int, int, Dict[str, Any]]] = []
		text_accum = []
		pos = 0
		for b in blocks:
			bt = b.get("text", "")
			start = pos
			text_accum.append(bt)
			pos += len(bt) + 1
			offset_map.append((start, start + len(bt), b.get("bbox")))
		full_text = "\n".join(text_accum)

		headings = _collect_headings(full_text)
		sents = _spacy_sentences(full_text)
		merged = _merge_short(sents, headings)

		for text, start_char, end_char in merged:
			line_is_heading = any(start_char >= hs and start_char < he for hs, he in headings.keys())
			if line_is_heading:
				current_section = text.strip()
				continue
			# collect bboxes intersecting this span
			bboxes = []
			for s, e, bb in offset_map:
				if e <= start_char or s >= end_char:
					continue
				if bb:
					bboxes.append(bb)
			clause_idx += 1
			clause_id = f"c_{clause_idx:04d}"
			chunks = _chunk_long(text)
			if len(chunks) == 1:
				clauses.append({
					"clause_id": clause_id,
					"text": text.strip(),
					"start_char": start_char,
					"end_char": end_char,
					"page": page_num,
					"bounding_boxes": bboxes,
					"parent_section_title": current_section,
				})
			else:
				for part_idx, chunk_text in enumerate(chunks, start=1):
					clauses.append({
						"clause_id": f"{clause_id}_part{part_idx}",
						"parent_clause_id": clause_id,
						"text": chunk_text.strip(),
						"start_char": start_char,
						"end_char": end_char,
						"page": page_num,
						"bounding_boxes": bboxes,
						"parent_section_title": current_section,
					})
	return clauses


def segment_document(job_id: str, preprocessed: Dict[str, Any]) -> List[Dict[str, Any]]:
	# For now we ignore job_id, but keep signature for integration with pipeline
	return segment_pages_to_clauses(preprocessed.get("pages", []))
