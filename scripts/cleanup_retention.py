import os
from datetime import datetime, timedelta
from pathlib import Path

RETENTION_DAYS = int(os.environ.get("RETENTION_DAYS", "7"))
STORAGE_DIR = Path("storage/ephemeral")


def main():
	cutoff = datetime.utcnow() - timedelta(days=RETENTION_DAYS)
	for p in STORAGE_DIR.glob("*.bin"):
		try:
			mtime = datetime.utcfromtimestamp(p.stat().st_mtime)
			if mtime < cutoff:
				p.unlink(missing_ok=True)
				print(f"Deleted {p}")
		except Exception as e:
			print(f"Skip {p}: {e}")

if __name__ == '__main__':
	main()
