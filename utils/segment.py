from __future__ import annotations

from typing import List, Dict, Any
import re


def _split_sentences(text: str) -> List[str]:
	# Very simple splitter for MVP; can be replaced by spaCy
	parts = re.split(r"(?<=[.!?])\s+", text.strip())
	return [p.strip() for p in parts if p.strip()]


def segment_clauses(pages: List[Dict[str, Any]], merge_short: bool = True) -> List[Dict[str, Any]]:
	clauses: List[Dict[str, Any]] = []
	clause_id = 0
	for page in pages:
		page_num = page.get("page_number", 1)
		sentences = _split_sentences(page.get("text", ""))
		buffer: List[str] = []
		for sent in sentences:
			if merge_short and (len(sent) < 80):
				buffer.append(sent)
				continue
			if buffer:
				merged = " ".join(buffer + [sent]).strip()
				buffer = []
				text = merged
			else:
				text = sent
			clause_id += 1
			clauses.append({
				"clause_id": f"c_{clause_id:04d}",
				"page": page_num,
				"text": text,
			})
		if buffer:
			clause_id += 1
			clauses.append({
				"clause_id": f"c_{clause_id:04d}",
				"page": page_num,
				"text": " ".join(buffer).strip(),
			})
	return clauses
