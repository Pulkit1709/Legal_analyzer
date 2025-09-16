from __future__ import annotations

from typing import List, Dict, Any
import json
from pathlib import Path
from collections import Counter
import numpy as np
from scipy.stats import ks_2samp

BASELINE_PATH = Path("storage/drift_baseline_unigrams.json")


def _tokenize(text: str) -> List[str]:
	return [t.lower() for t in (text or "").split() if t.strip()]


def build_unigram_dist(texts: List[str], top_k: int = 5000) -> Dict[str, float]:
	cnt = Counter()
	for t in texts:
		cnt.update(_tokenize(t))
	total = sum(cnt.values()) or 1
	most = cnt.most_common(top_k)
	return {w: c / total for w, c in most}


def save_baseline(dist: Dict[str, float]):
	BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
	with open(BASELINE_PATH, 'w', encoding='utf-8') as f:
		json.dump(dist, f, ensure_ascii=False)


def load_baseline() -> Dict[str, float] | None:
	if not BASELINE_PATH.exists():
		return None
	with open(BASELINE_PATH, 'r', encoding='utf-8') as f:
		return json.load(f)


def psi(current: Dict[str, float], baseline: Dict[str, float], epsilon: float = 1e-8) -> float:
	# Population Stability Index across shared and missing bins
	keys = set(baseline.keys()) | set(current.keys())
	val = 0.0
	for k in keys:
		p = baseline.get(k, epsilon)
		q = current.get(k, epsilon)
		val += (q - p) * np.log(q / p)
	return float(val)


def ks_score(current_samples: List[float], baseline_samples: List[float]) -> float:
	stat, _ = ks_2samp(current_samples, baseline_samples)
	return float(stat)


def detect_drift(texts: List[str]) -> Dict[str, Any]:
	base = load_baseline()
	curr = build_unigram_dist(texts)
	if base is None:
		save_baseline(curr)
		return {"psi": 0.0, "ks": 0.0, "baseline_created": True}
	# build aligned samples for KS by probabilities
	common = list((set(base.keys()) | set(curr.keys())))
	base_probs = [base.get(k, 0.0) for k in common]
	curr_probs = [curr.get(k, 0.0) for k in common]
	return {
		"psi": psi(curr, base),
		"ks": ks_score(curr_probs, base_probs),
		"baseline_created": False,
	}
