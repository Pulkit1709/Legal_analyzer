from __future__ import annotations

import os
import json
from dataclasses import dataclass
from typing import List, Dict, Any

import numpy as np
import pandas as pd
from datasets import Dataset, DatasetDict
from transformers import (
	AutoTokenizer, AutoModelForSequenceClassification,
	Trainer, TrainingArguments, DataCollatorWithPadding
)
import evaluate
from sklearn.metrics import classification_report


@dataclass
class TrainConfig:
	model_name: str = "roberta-base"  # replace with legal-bert when available
	labels: List[str] = None
	multi_label: bool = True
	max_length: int = 256
	lr: float = 2e-5
	batch_size: int = 16
	epochs: int = 3
	weight_decay: float = 0.01
	warmup_ratio: float = 0.1
	output_dir: str = "artifacts/model_roberta"


def prepare_datasets(train_df: pd.DataFrame, val_df: pd.DataFrame, test_df: pd.DataFrame, labels: List[str], tokenizer, max_length: int, multi_label: bool):
	label2id = {l: i for i, l in enumerate(labels)}
	id2label = {i: l for l, i in label2id.items()}

	def encode(example):
		t = tokenizer(example["text"], truncation=True, max_length=max_length)
		if multi_label:
			vec = [0] * len(labels)
			for l in example.get("labels", []):
				if l in label2id:
					vec[label2id[l]] = 1
			return {**t, "labels": vec}
		else:
			return {**t, "labels": label2id[example["label"]]}

	ds = DatasetDict({
		"train": Dataset.from_pandas(train_df.reset_index(drop=True)),
		"validation": Dataset.from_pandas(val_df.reset_index(drop=True)),
		"test": Dataset.from_pandas(test_df.reset_index(drop=True)),
	})
	ds = ds.map(encode, batched=False)
	return ds, label2id, id2label


def compute_metrics_builder(multi_label: bool):
	metric_f1 = evaluate.load("f1")
	metric_precision = evaluate.load("precision")
	metric_recall = evaluate.load("recall")
	def compute_metrics(eval_pred):
		logits, labels = eval_pred
		if multi_label:
			preds = (1 / (1 + np.exp(-logits)) >= 0.5).astype(int)
			micro_f1 = metric_f1.compute(predictions=preds, references=labels, average="micro")["f1"]
			macro_f1 = metric_f1.compute(predictions=preds, references=labels, average="macro")["f1"]
			micro_p = metric_precision.compute(predictions=preds, references=labels, average="micro")["precision"]
			micro_r = metric_recall.compute(predictions=preds, references=labels, average="micro")["recall"]
			return {"micro_f1": micro_f1, "macro_f1": macro_f1, "micro_p": micro_p, "micro_r": micro_r}
		else:
			preds = np.argmax(logits, axis=-1)
			f1 = metric_f1.compute(predictions=preds, references=labels, average="macro")["f1"]
			return {"macro_f1": f1}
	return compute_metrics


def train_and_export(train_df: pd.DataFrame, val_df: pd.DataFrame, test_df: pd.DataFrame, config: TrainConfig):
	os.makedirs(config.output_dir, exist_ok=True)
	labels = config.labels or ["Financial", "Compliance", "Liability", "Operational", "Safe"]
	tokenizer = AutoTokenizer.from_pretrained(config.model_name)
	model = AutoModelForSequenceClassification.from_pretrained(
		config.model_name,
		num_labels=len(labels),
		problem_type=("multi_label_classification" if config.multi_label else None),
	)

	ds, label2id, id2label = prepare_datasets(train_df, val_df, test_df, labels, tokenizer, config.max_length, config.multi_label)

	args = TrainingArguments(
		output_dir=config.output_dir,
		learning_rate=config.lr,
		per_device_train_batch_size=config.batch_size,
		per_device_eval_batch_size=config.batch_size,
		num_train_epochs=config.epochs,
		weight_decay=config.weight_decay,
		evaluation_strategy="epoch",
		save_strategy="epoch",
		warmup_ratio=config.warmup_ratio,
		load_best_model_at_end=True,
		metric_for_best_model="macro_f1",
	)

	trainer = Trainer(
		model=model,
		args=args,
		train_dataset=ds["train"],
		eval_dataset=ds["validation"],
		data_collator=DataCollatorWithPadding(tokenizer),
		compute_metrics=compute_metrics_builder(config.multi_label),
	)

	trainer.train()
	metrics = trainer.evaluate(ds["test"])
	with open(os.path.join(config.output_dir, "metrics.json"), "w", encoding="utf-8") as f:
		json.dump(metrics, f, indent=2)

	model.save_pretrained(config.output_dir)
	tokenizer.save_pretrained(config.output_dir)
	with open(os.path.join(config.output_dir, "labels.json"), "w", encoding="utf-8") as f:
		json.dump({"labels": labels, "label2id": label2id, "id2label": id2label}, f, indent=2)

	return metrics
