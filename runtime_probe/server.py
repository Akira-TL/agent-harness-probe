#!/usr/bin/env python3
"""Controlled, read-only HTTP runtime fingerprint endpoint.

This tool intentionally offers no arbitrary URL fetching, code execution,
filesystem access, uploads, credentials, or public log-reading endpoint.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import secrets
import threading
import time
from urllib.parse import parse_qs, urlsplit

REPO_ROOT = Path(__file__).resolve().parents[1]
LOCAL_DIR = REPO_ROOT / ".local"
LOCAL_DIR.mkdir(mode=0o700, exist_ok=True)
LOCAL_DIR.chmod(0o700)
SECRET_FILE = LOCAL_DIR / "probe-secret.txt"
EVENTS_FILE = LOCAL_DIR / "probe-events.jsonl"
LOCK = threading.RLock()
COUNTS: dict[str, int] = defaultdict(int)
ALLOWED_CASE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def get_or_create_secret() -> str:
    if SECRET_FILE.exists():
        token = SECRET_FILE.read_text(encoding="utf-8").strip()
        if re.fullmatch(r"[0-9a-f]{32}", token):
            return token
        raise RuntimeError("Existing probe token has invalid format; refuse to overwrite")
    token = secrets.token_hex(16)
    fd = os.open(SECRET_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(token + "\n")
    return token


class ProbeHandler(BaseHTTPRequestHandler):
    server_version = "HarnessProbe/1.0"
    sys_version = ""

    def log_message(self, fmt: str, *args: object) -> None:
        # Never log raw request paths into the process stderr.
        return

    def do_GET(self) -> None:
        self._handle(send_body=True)

    def do_HEAD(self) -> None:
        self._handle(send_body=False)

    def do_POST(self) -> None:
        self._respond(405, {"error": "read-only test service"})

    def _respond(self, status: int, payload: dict, *, extra: dict[str, str] | None = None,
                 send_body: bool = True) -> None:
        body = (json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n").encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", (extra or {}).get("Cache-Control", "no-store"))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'none'")
        for key, val in (extra or {}).items():
            if key != "Cache-Control":
                self.send_header(key, val)
        self.end_headers()
        if send_body:
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

    def _handle(self, *, send_body: bool) -> None:
        if len(self.path) > 1024:
            self._respond(414, {"error": "request path too long"}, send_body=send_body)
            return
        parts = urlsplit(self.path)
        path = parts.path
        prefix = f"/{self.server.probe_secret}/"  # type: ignore[attr-defined]
        if not path.startswith(prefix):
            self._respond(404, {"error": "not found"}, send_body=send_body)
            return
        route = path[len(prefix):]
        if route not in ("health", "echo", "redirect", "flaky", "delay", "cache", "status"):
            self._respond(404, {"error": "unknown probe"}, send_body=send_body)
            return
        query = parse_qs(parts.query, keep_blank_values=False, max_num_fields=12)
        case = query.get("case", ["default"])[0]
        if not ALLOWED_CASE.fullmatch(case):
            self._respond(400, {"error": "invalid case id"}, send_body=send_body)
            return
        event_time = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
        key = f"{route}:{case}"
        with LOCK:
            COUNTS[key] += 1
            attempt = COUNTS[key]
        payload = {
            "probe": route,
            "case": case,
            "attempt": attempt,
            "received_at_utc": event_time,
            "server_nonce": secrets.token_hex(6),
        }
        extra: dict[str, str] = {}
        code = 200
        delay_s = 0.0
        if route == "health":
            payload.update({"ok": True, "description": "controlled testing only"})
        elif route == "echo":
            payload["marker"] = "ECHO_PROBE_OK"
        elif route == "redirect":
            code = 302
            location = f"echo?case=redirect_{case}"
            extra["Location"] = location
            payload.update({"redirect_to": location, "marker": "REDIRECT_SOURCE"})
        elif route == "flaky":
            try:
                fail_count = max(0, min(3, int(query.get("fails", ["1"])[0])))
                error_code = int(query.get("code", ["503"])[0])
                if error_code not in (429, 500, 503):
                    raise ValueError
            except ValueError:
                self._respond(400, {"error": "invalid flaky settings"}, send_body=send_body)
                return
            if attempt <= fail_count:
                code = error_code
                extra["Retry-After"] = "1"
                payload["status"] = "retry_later"
            else:
                payload["status"] = "recovered"
            payload["fails_configured"] = fail_count
        elif route == "delay":
            try:
                delay_s = max(0.0, min(6.0, float(query.get("seconds", ["2"])[0])))
                if not (delay_s == delay_s):
                    raise ValueError
            except ValueError:
                self._respond(400, {"error": "invalid delay"}, send_body=send_body)
                return
            payload["delayed_seconds"] = delay_s
        elif route == "cache":
            policy = query.get("policy", ["no-store"])[0]
            if policy not in ("no-store", "public"):
                self._respond(400, {"error": "invalid cache policy"}, send_body=send_body)
                return
            if policy == "public":
                extra["Cache-Control"] = "public, max-age=60"
            payload["cache_policy"] = policy
        elif route == "status":
            try:
                code = int(query.get("code", ["429"])[0])
            except ValueError:
                code = 400
            if code not in (403, 404, 429, 500, 503):
                self._respond(400, {"error": "unsupported code"}, send_body=send_body)
                return
            if code == 429:
                extra["Retry-After"] = "1"
            payload["status"] = "controlled_error"

        # Only allowlisted headers are retained locally. Never capture cookies,
        # authorization, request body, or unbounded user-supplied content.
        safe_headers = ("User-Agent", "Accept", "Accept-Language", "Via",
                        "CF-Connecting-IP", "CF-Ray", "X-Forwarded-For")
        event = {
            "time": event_time,
            "method": self.command,
            "route": route,
            "case": case,
            "attempt": attempt,
            "response_status": code,
            "delay_seconds": delay_s,
            "client_ip": self.client_address[0],
            "headers": {h.lower(): self.headers[h][:250] for h in safe_headers if self.headers.get(h)},
        }
        with LOCK:
            fd = os.open(EVENTS_FILE, os.O_CREAT | os.O_WRONLY | os.O_APPEND, 0o600)
            with os.fdopen(fd, "a", encoding="utf-8") as f:
                f.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")
        if delay_s:
            time.sleep(delay_s)
        self._respond(code, payload, extra=extra, send_body=send_body)


class ProbeServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def main() -> None:
    parser = argparse.ArgumentParser(description="Bounded read-only HTTP probe")
    parser.add_argument("--port", type=int, default=18768)
    args = parser.parse_args()
    if not (1024 <= args.port <= 65535):
        parser.error("port must be >= 1024 and <= 65535")
    secret = get_or_create_secret()
    server = ProbeServer(("127.0.0.1", args.port), ProbeHandler)
    server.probe_secret = secret  # type: ignore[attr-defined]
    print(f"READY localhost:{args.port} /<private-token>/health", flush=True)
    try:
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
