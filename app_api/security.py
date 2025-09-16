from __future__ import annotations

import os
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

ENFORCE_HTTPS = os.environ.get("ENFORCE_HTTPS", "false").lower() == "true"


class HTTPSRedirectMiddleware(BaseHTTPMiddleware):
	async def dispatch(self, request: Request, call_next):
		if ENFORCE_HTTPS:
			xfp = request.headers.get('x-forwarded-proto')
			if xfp != 'https' and request.url.scheme != 'https':
				# redirect to https
				url = request.url.replace(scheme='https')
				return Response(status_code=307, headers={'Location': str(url)})
		return await call_next(request)
