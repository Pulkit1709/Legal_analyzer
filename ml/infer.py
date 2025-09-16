from __future__ import annotations

from typing import List, Dict, Any
import os
import json
import numpy as np
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch

FALLBACK_KEYWORDS = {
	"Liability": ["indemnify", "liable", "limitation", "consequential damages"],
	"Financial": ["payment", "fee", "penalty", "interest"],
	"Compliance": ["comply", "gdpr", "hipaa", "regulation"],
	"Operational": ["uptime", "service level", "sla", "support"],
	"Safe": [],
}


class RiskClassifier:
	def __init__(self, model_dir: str):
		self.model_dir = model_dir
		self.use_fallback = not (os.path.isdir(model_dir) and os.path.isfile(os.path.join(model_dir, "config.json")))
		if not self.use_fallback:
			with open(os.path.join(model_dir, "labels.json"), "r", encoding="utf-8") as f:
				m = json.load(f)
			self.labels = m["labels"]
			self.tokenizer = AutoTokenizer.from_pretrained(model_dir)
			self.model = AutoModelForSequenceClassification.from_pretrained(model_dir)
			self.model.eval()
		else:
			self.labels = list(FALLBACK_KEYWORDS.keys())

	@torch.no_grad()
	def predict_clause(self, text: str) -> List[Dict[str, Any]]:
		if self.use_fallback:
			low = text.lower()
			out = []
			for label in self.labels:
				terms = FALLBACK_KEYWORDS[label]
				score = 0.0
				if terms:
					matches = sum(1 for t in terms if t in low)
					score = min(0.95, 0.4 + 0.2 * matches) if matches else 0.0
				out.append({"label": label, "score": float(score)})
			return sorted(out, key=lambda x: x["score"], reverse=True)
		inputs = self.tokenizer(text, truncation=True, max_length=256, return_tensors="pt")
		outputs = self.model(**inputs)
		logits = outputs.logits.squeeze(0).detach().cpu().numpy()
		if logits.ndim == 0:
			logits = np.array([logits])
		probs = 1.0 / (1.0 + np.exp(-logits))
		out: List[Dict[str, Any]] = []
		for i, label in enumerate(self.labels):
			out.append({"label": label, "score": float(probs[i])})
		out.sort(key=lambda x: x["score"], reverse=True)
		return out


def predict_clause(text: str, model_dir: str) -> List[Dict[str, Any]]:
	return RiskClassifier(model_dir).predict_clause(text)
