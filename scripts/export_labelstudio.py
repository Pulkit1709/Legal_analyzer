import json
import sys
from datetime import datetime

"""
Usage:
  python scripts/export_labelstudio.py input.json > output.jsonl

Input: Label Studio JSON export with tasks containing 'data': {'text': ...}
and 'annotations' list with 'result' entries for labels, severity, and notes.
"""


def to_jsonl_objects(payload):
	for task in payload:
		text = task.get('data', {}).get('text', '')
		clause_id = task.get('data', {}).get('clause_id') or task.get('id')
		annos = task.get('annotations', [])
		if not annos:
			continue
		ann = annos[0]
		labels = []
		severity = None
		notes = None
		for r in ann.get('result', []):
			if r.get('type') == 'choices' and r.get('from_name') == 'labels':
				labels = r.get('value', {}).get('choices', [])
			if r.get('type') == 'choices' and r.get('from_name') == 'severity':
				sv = r.get('value', {}).get('choices', [])
				severity = sv[0] if sv else None
			if r.get('type') == 'textarea' and r.get('from_name') == 'notes':
				vals = r.get('value', {}).get('text', [])
				notes = vals[0] if vals else None
		yield {
			"clause_id": clause_id,
			"text": text,
			"labels": labels,
			"severity": severity,
			"notes": notes,
			"annotator_id": ann.get('completed_by'),
			"timestamp": ann.get('created_at') or datetime.utcnow().isoformat() + 'Z'
		}


def main():
	data = json.load(sys.stdin if len(sys.argv) < 2 else open(sys.argv[1], 'r', encoding='utf-8'))
	for obj in to_jsonl_objects(data):
		print(json.dumps(obj, ensure_ascii=False))


if __name__ == '__main__':
	main()
