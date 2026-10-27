from __future__ import annotations

import json
import time
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def invoke(endpoint: str, body: dict, timeout: float) -> dict:
    started = time.monotonic()
    response = {"body": body}
    try:
        request = Request(endpoint, data=json.dumps(body).encode(),
                          headers={"Content-Type": "application/json"}, method="POST")
        with build_opener(ProxyHandler({}), NoRedirect).open(request, timeout=timeout) as stream:
            response.update(status=stream.status, raw=stream.read().decode())
    except Exception as exc:
        response.update(error=type(exc).__name__, reason=str(exc))
    response["seconds"] = time.monotonic() - started
    return response
