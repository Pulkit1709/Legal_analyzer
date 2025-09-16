from __future__ import annotations

from typing import Dict, Any
import re

try:
	import spacy
	try:
		NLP = spacy.load("en_core_web_sm")
	except Exception:
		NLP = spacy.blank("en")
except Exception:
	NLP = None

RE_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
RE_SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
RE_PHONE = re.compile(r"\b\+?\d[\d\-\s]{7,}\d\b")


def detect_pii(text: str) -> Dict[str, Any]:
	found = {"emails": [], "ssn": [], "phones": [], "persons": [], "orgs": []}
	for m in RE_EMAIL.finditer(text or ""):
		found["emails"].append(m.group())
	for m in RE_SSN.finditer(text or ""):
		found["ssn"].append(m.group())
	for m in RE_PHONE.finditer(text or ""):
		found["phones"].append(m.group())
	if NLP:
		doc = NLP(text or "")
		for ent in getattr(doc, "ents", []):
			if ent.label_ == "PERSON":
				found["persons"].append(ent.text)
			elif ent.label_ == "ORG":
				found["orgs"].append(ent.text)
	return found


def redact(text: str, mask: str = "█") -> str:
	red = RE_EMAIL.sub(mask*8, text)
	red = RE_SSN.sub(mask*11, red)
	red = RE_PHONE.sub(mask*8, red)
	return red
