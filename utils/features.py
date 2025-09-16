from __future__ import annotations

from typing import Dict, Any
import re
import unicodedata

try:
	import spacy
	try:
		NLP = spacy.load("en_core_web_sm")
	except Exception:
		NLP = spacy.blank("en")
		if "sentencizer" not in NLP.pipe_names:
			NLP.add_pipe("sentencizer")
except Exception:
	NLP = None

RE_NUM = re.compile(r"\b\d{4,}\b")
RE_MONEY = re.compile(r"\b(?:\$|€|£)\s?\d{1,3}(?:[\,\.]\d{3})*(?:\.\d+)?\b", re.I)
RE_PERCENT = re.compile(r"\b\d{1,3}\s?%\b")
RE_DATE = re.compile(r"\b(?:\d{1,2}[\-/]\d{1,2}[\-/]\d{2,4}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{2,4})\b", re.I)
RE_DURATION = re.compile(r"\b\d+\s+(?:day|days|month|months|year|years|quarter|quarters)\b", re.I)
RE_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
RE_URL = re.compile(r"https?://\S+|www\.\S+", re.I)

KEYWORDS = [
	"indemnify", "indemnity", "limitation", "penalty", "interest", "termination",
	"confidentiality", "compliance", "regulatory", "warranty",
]
MODALS = {"shall", "must", "may", "should", "will"}
NEGATIONS = {"not", "no", "never", "without", "except"}


def _normalize(text: str) -> str:
	text = (text or "").replace("\u0000", " ")
	text = unicodedata.normalize("NFC", text)
	text = " ".join(text.split())
	return text


def _placeholderize(text: str) -> str:
	text = RE_MONEY.sub(" [MONEY] ", text)
	text = RE_DATE.sub(" [DATE] ", text)
	text = RE_NUM.sub(" [NUM] ", text)
	return " ".join(text.split())


def _readability_flesch(text: str) -> float:
	# Very rough heuristic to avoid heavy deps
	words = re.findall(r"[A-Za-z]+", text)
	sentences = max(1, len(re.findall(r"[.!?]", text)) or 1)
	syllables = 0
	for w in words:
		# naive syllable count
		syllables += max(1, len(re.findall(r"[aeiouyAEIOUY]+", w)))
	num_words = max(1, len(words))
	return round(206.835 - 1.015 * (num_words / sentences) - 84.6 * (syllables / num_words), 2)


def extract_features_for_clause(clause: Dict[str, Any]) -> Dict[str, Any]:
	original_text = clause.get("text", "")
	orig = _normalize(original_text)
	normalized = _placeholderize(orig)

	features: Dict[str, Any] = {}
	features["has_money"] = bool(RE_MONEY.search(orig))
	features["has_percent"] = bool(RE_PERCENT.search(orig))
	features["has_date"] = bool(RE_DATE.search(orig))
	features["has_duration"] = bool(RE_DURATION.search(orig))
	features["has_email"] = bool(RE_EMAIL.search(orig))
	features["has_url"] = bool(RE_URL.search(orig))

	# spaCy-based
	tokens = []
	lemmas = []
	pos_tags = []
	modals = False
	negation_present = False
	passive_voice = False
	uppercase_ratio = 0.0
	avg_token_len = 0.0
	length_tokens = 0

	if NLP:
		doc = NLP(orig)
		length_tokens = len([t for t in doc if not t.is_space])
		if length_tokens:
			avg_token_len = sum(len(t.text) for t in doc if not t.is_space) / length_tokens
			uppercase_words = sum(1 for t in doc if t.text.isupper() and len(t.text) > 1)
			uppercase_ratio = uppercase_words / max(1, length_tokens)
		for t in doc:
			if t.is_space:
				continue
			tokens.append(t.text)
			lemmas.append(t.lemma_ if t.lemma_ else t.text.lower())
			pos_tags.append(t.pos_)
			if t.lemma_.lower() in MODALS or t.text.lower() in MODALS:
				modals = True
			if t.dep_.lower() == "neg" or t.text.lower() in NEGATIONS:
				negation_present = True
		# Passive voice heuristic: presence of auxpass + VERB in past participle
		# In blank models dep_ is unavailable; fallback to regex
		if NLP and any(getattr(t, "tag_", "") == "VBN" for t in doc) and any(getattr(t, "dep_", "") == "auxpass" for t in doc):
			passive_voice = True
		elif re.search(r"\b(be|is|are|was|were|been|being)\b\s+\w+ed\b", orig, re.I):
			passive_voice = True
	else:
		words = orig.split()
		length_tokens = len(words)
		avg_token_len = sum(len(w) for w in words) / max(1, length_tokens)
		uppercase_ratio = sum(1 for w in words if w.isupper() and len(w) > 1) / max(1, length_tokens)
		modals = any(w.lower() in MODALS for w in words)
		negation_present = any(w.lower() in NEGATIONS for w in words)
		passive_voice = bool(re.search(r"\b(be|is|are|was|were|been|being)\b\s+\w+ed\b", orig, re.I))

	readability = _readability_flesch(orig)
	keyword_flags = {kw: (kw in orig.lower()) for kw in KEYWORDS}

	features.update({
		"length_tokens": length_tokens,
		"avg_token_length": round(avg_token_len, 3),
		"uppercase_ratio": round(uppercase_ratio, 3),
		"readability_flesch": readability,
		"has_modals": modals,
		"has_negation": negation_present,
		"passive_voice": passive_voice,
		"keywords": keyword_flags,
		"tokens": tokens,
		"lemmas": lemmas,
		"pos": pos_tags,
	})

	return {
		**clause,
		"original_text": original_text,
		"normalized_text": normalized,
		"features": features,
	}
