from __future__ import annotations

from typing import Dict, Any, List, Tuple
import os
import numpy as np
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from captum.attr import IntegratedGradients


def _token_importances_ig(model, inputs, target_idx: int) -> np.ndarray:
	model.zero_grad()
	ig = IntegratedGradients(lambda inp: model(**inp).logits)
	attributions = ig.attribute(inputs=inputs, target=target_idx, n_steps=32)
	# sum over hidden size if present
	if isinstance(attributions, tuple):
		attributions = attributions[0]
	att = attributions.sum(dim=-1).squeeze(0).detach().cpu().numpy()
	return att


def _token_importances_attention(model, inputs) -> np.ndarray:
	# Not all models return attentions by default; enable via config if needed
	outputs = model(**inputs, output_attentions=True)
	attentions = outputs.attentions  # list of layers, each (batch, heads, seq, seq)
	if not attentions:
		return np.zeros(inputs["input_ids"].shape[1])
	# Average heads and layers, focus on [CLS] attention to tokens
	avg = np.mean([a.detach().cpu().numpy() for a in attentions], axis=0)  # (batch, heads, seq, seq)
	avg_heads = avg.mean(axis=1)[0]  # (seq, seq)
	cls_attn = avg_heads[0]  # attention from CLS to tokens
	return cls_attn


def _map_tokens_to_chars(tokenizer, text: str, inputs) -> List[Tuple[int, int]]:
	offsets = []
	# Use fast tokenizers for offsets
	enc = tokenizer(text, return_offsets_mapping=True, truncation=True, max_length=256)
	for off in enc["offset_mapping"]:
		offsets.append((int(off[0]), int(off[1])))
	return offsets


def explain_text(model_dir: str, text: str, method: str = "ig", top_k: int = 8) -> Dict[str, Any]:
	tokenizer = AutoTokenizer.from_pretrained(model_dir, use_fast=True)
	model = AutoModelForSequenceClassification.from_pretrained(model_dir)
	model.eval()
	inputs = tokenizer(text, truncation=True, max_length=256, return_tensors="pt")
	# choose target as argmax of logits for single-label; for multi-label, use each label independently
	with torch.no_grad():
		logits = model(**inputs).logits
		probs = torch.sigmoid(logits).squeeze(0).cpu().numpy()
		target_idx = int(np.argmax(probs))

	if method == "ig":
		scores = _token_importances_ig(model, inputs, target_idx)
	elif method == "attention":
		scores = _token_importances_attention(model, inputs)
	else:
		scores = _token_importances_ig(model, inputs, target_idx)

	scores = (scores - scores.min()) / (scores.ptp() + 1e-9)
	offsets = _map_tokens_to_chars(tokenizer, text, inputs)
	tokens = tokenizer.convert_ids_to_tokens(inputs["input_ids"].squeeze(0))

	pairs = []
	for tok, (s, e), sc in zip(tokens, offsets, scores):
		if s == e:
			continue
		pairs.append({"token": tok, "start": int(s), "end": int(e), "importance": float(sc)})

	pairs.sort(key=lambda x: x["importance"], reverse=True)
	expl_tokens = pairs[:top_k]
	explanation_text = "Tokens: " + ", ".join(f"{p['token']} ({p['importance']:.2f})" for p in expl_tokens)

	return {
		"token_importances": pairs,
		"explanation_text": explanation_text,
	}


def map_tokens_to_bboxes(token_importances: List[Dict[str, Any]], bboxes: List[Dict[str, Any]], clause_start_char: int = 0) -> List[Dict[str, Any]]:
	# Simplistic mapping: if token char span falls within block span, attach that bbox
	# Here bboxes are page-level block boxes; this function will replicate bbox for tokens within the clause
	return [
		{
			"token": t["token"],
			"importance": t["importance"],
			"bbox": bboxes[0] if bboxes else None,
		}
		for t in token_importances
	]
