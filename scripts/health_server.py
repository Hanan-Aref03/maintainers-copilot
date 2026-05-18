#!/usr/bin/env python3
"""Tiny HTTP server used by scaffold containers until real app code lands."""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class HealthHandler(BaseHTTPRequestHandler):
    service_name = "service"

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return

    def _send(self, status: int, body: str, content_type: str) -> None:
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            payload = json.dumps({"service": self.service_name, "status": "ok"})
            self._send(200, payload, "application/json; charset=utf-8")
            return

        if self.path == "/":
            self._send(200, f"{self.service_name} is running\n", "text/plain; charset=utf-8")
            return

        payload = json.dumps({"service": self.service_name, "error": "not found"})
        self._send(404, payload, "application/json; charset=utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--name", required=True)
    args = parser.parse_args()

    handler = type(f"{args.name.title()}Handler", (HealthHandler,), {"service_name": args.name})
    server = ThreadingHTTPServer(("0.0.0.0", args.port), handler)
    print(f"{args.name} listening on port {args.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
