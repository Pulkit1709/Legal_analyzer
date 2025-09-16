from __future__ import annotations

from typing import List, Dict, Any
import math

KEYWORDS = {
	"Liability": [
		"indemnify", "indemnification", "hold harmless", "liable", "liability", "consequential damages",
		"not be liable", "shall not be liable", "limitation of liability",
	],
	"Financial": [
		"payment", "fee", "penalty", "interest", "late fee", "invoice", "refund", "charges",
	],
	"Compliance": [
		"comply", "compliance", "law", "regulation", "sanction", "privacy", "gdpr", "hipaa",
	],
	"Operational": [
		"service level", "uptime", "availability", "maintenance", "support", "response time", "sla",
	],
}

SEVERITY_WEIGHTS = {
	"Safe": 0.1,
	"Financial": 0.8,
	"Compliance": 0.9,
	"Liability": 1.0,
	"Operational": 0.6,
}


def _severity_bucket(score: float) -> str:
	if score < 0.5:
		return "Low"
	if score < 0.75:
		return "Medium"
	return "High"


def classify_clauses(clauses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
	results: List[Dict[str, Any]] = []
	for cl in clauses:
		text = cl.get("text", "").lower()
		best_category = "Safe"
		best_conf = 0.0
		matched_terms: List[str] = []
		for cat, terms in KEYWORDS.items():
			count = sum(1 for t in terms if t in text)
			if count > 0:
				conf = min(0.95, 0.4 + 0.2 * count)
				if conf > best_conf:
					best_conf = conf
					best_category = cat
					matched_terms = [t for t in terms if t in text]

		length_factor = min(1.0, max(0.6, len(text) / 600.0))
		severity_score = best_conf * SEVERITY_WEIGHTS.get(best_category, 0.1) * length_factor
		severity = _severity_bucket(severity_score)
		explanation = ""
		if best_category != "Safe":
			explanation = f"{best_category} signals: " + ", ".join(sorted(set(matched_terms)))

		results.append({
			"clause_id": cl["clause_id"],
			"page": cl["page"],
			"text": cl["text"],
			"predictions": [{"category": best_category, "confidence": round(best_conf, 3)}] if best_category != "Safe" else [],
			"severity_score": round(severity_score, 3),
			"severity": severity,
			"explanation": explanation,
		})
	return results
