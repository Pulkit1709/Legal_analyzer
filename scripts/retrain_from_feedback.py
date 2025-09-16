import sqlite3
import json
from pathlib import Path
from datetime import datetime

DB_PATH = Path("storage/metadata.db")


def export_feedback_jsonl(out_path: str):
	rows = []
	with sqlite3.connect(DB_PATH) as con:
		cur = con.execute("SELECT job_id, clause_id, user_id, original_prediction, new_labels, new_severity, comment, created_at FROM feedback ORDER BY created_at DESC")
		for (job_id, clause_id, user_id, orig_pred, new_labels, new_severity, comment, created_at) in cur.fetchall():
			rows.append({
				"job_id": job_id,
				"clause_id": clause_id,
				"user_id": user_id,
				"original_prediction": json.loads(orig_pred) if orig_pred else None,
				"labels": json.loads(new_labels) if new_labels else None,
				"severity": new_severity,
				"comment": comment,
				"timestamp": created_at,
			})
	with open(out_path, 'w', encoding='utf-8') as f:
		for r in rows:
			f.write(json.dumps(r, ensure_ascii=False) + "\n")


def main():
	out = f"storage/feedback_{datetime.utcnow().strftime('%Y%m%d')}.jsonl"
	export_feedback_jsonl(out)
	print(f"Exported {out}")


if __name__ == '__main__':
	main()
