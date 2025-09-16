from __future__ import annotations

import time
from typing import Dict, Any
from fastapi import APIRouter, Request, Response
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from starlette.middleware.base import BaseHTTPMiddleware

router = APIRouter()

REQUEST_LATENCY = Histogram('api_request_latency_seconds', 'API request latency', ['path', 'method'])
REQUEST_COUNT = Counter('api_request_total', 'API request count', ['path', 'method', 'status'])
JOB_DURATION = Histogram('job_duration_seconds', 'Document job end-to-end duration')
QUEUE_DEPTH = Gauge('queue_depth', 'Jobs waiting in queue')
ERROR_COUNT = Counter('api_errors_total', 'API errors total', ['path'])
MODEL_LABEL_DIST = Counter('model_pred_labels_total', 'Predicted labels count', ['label'])
MODEL_CONFIDENCE = Histogram('model_confidence', 'Model probability scores')
FEEDBACK_ACCEPT_RATE = Gauge('feedback_accept_rate', 'Share of accepted model suggestions')


class MetricsMiddleware(BaseHTTPMiddleware):
	async def dispatch(self, request: Request, call_next):
		start = time.time()
		try:
			response = await call_next(request)
			status = str(response.status_code)
		except Exception:
			status = '500'
			ERROR_COUNT.labels(path=request.url.path).inc()
			raise
		finally:
			elapsed = time.time() - start
			REQUEST_LATENCY.labels(path=request.url.path, method=request.method).observe(elapsed)
			REQUEST_COUNT.labels(path=request.url.path, method=request.method, status=status).inc()
		return response


@router.get('/metrics')
def metrics():
	return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
