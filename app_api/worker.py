from __future__ import annotations

import time
from app_api.serving import JOBS


def main():
	print("Worker placeholder started. Polling for jobs...")
	while True:
		# In real deployment, use Celery/RQ. Here just idle.
		time.sleep(5)


if __name__ == '__main__':
	main()
