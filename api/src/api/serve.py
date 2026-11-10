"""Container entrypoint. One uvicorn process, bound to Render's port."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path


def uvicorn_executable() -> str:
    filename = "uvicorn.exe" if os.name == "nt" else "uvicorn"
    return str(Path(sys.executable).with_name(filename))


def build_serve_command(env: Mapping[str, str], uvicorn_bin: str) -> tuple[list[str], int | None]:
    """Argv for the image, and a request cap when recycling is enabled.

    A missing cap means the process should be replaced by uvicorn. A single
    uvicorn process exits once it hits the cap, so the parent has to start it again.
    """
    port = _positive_int(env.get("PORT") or "8000", "PORT")
    grace = _non_negative_int(
        env.get("UVICORN_GRACEFUL_SHUTDOWN") or "25",
        "UVICORN_GRACEFUL_SHUTDOWN",
    )
    command = [
        uvicorn_bin,
        "api.main:app",
        "--host",
        "0.0.0.0",
        "--port",
        str(port),
        "--proxy-headers",
        "--forwarded-allow-ips",
        env.get("FORWARDED_ALLOW_IPS") or "*",
        "--timeout-graceful-shutdown",
        str(grace),
    ]
    raw_limit = (env.get("UVICORN_LIMIT_MAX_REQUESTS") or "").strip()
    if raw_limit in ("", "0"):
        return command, None
    limit = _positive_int(raw_limit, "UVICORN_LIMIT_MAX_REQUESTS")
    command.extend(["--limit-max-requests", str(limit)])
    raw_jitter = (env.get("UVICORN_LIMIT_MAX_REQUESTS_JITTER") or "").strip()
    if raw_jitter not in ("", "0"):
        jitter = _non_negative_int(raw_jitter, "UVICORN_LIMIT_MAX_REQUESTS_JITTER")
        command.extend(["--limit-max-requests-jitter", str(jitter)])
    return command, limit


def serve() -> None:
    command, limit = build_serve_command(os.environ, uvicorn_executable())
    if limit is None:
        os.execv(command[0], command)
    restart_after_request_limit(command)


def restart_after_request_limit(command: list[str]) -> None:
    stopping = False
    child: subprocess.Popen[bytes] | None = None

    def stop(_signum: int, _frame: object) -> None:
        nonlocal stopping
        stopping = True
        if child is not None and child.poll() is None:
            child.terminate()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    while True:
        child = subprocess.Popen(command)
        status = _wait(child)
        child = None
        if stopping:
            raise SystemExit(0)
        if status != 0:
            raise SystemExit(status)
        print("request limit reached; restarting uvicorn", file=sys.stderr, flush=True)


def _wait(child: subprocess.Popen[bytes]) -> int:
    while True:
        try:
            return child.wait()
        except InterruptedError:
            continue


def _positive_int(raw: str, name: str) -> int:
    if not raw.isdigit() or int(raw) == 0:
        raise SystemExit(f"{name} must be a positive integer")
    return int(raw)


def _non_negative_int(raw: str, name: str) -> int:
    if not raw.isdigit():
        raise SystemExit(f"{name} must be a non-negative integer")
    return int(raw)


if __name__ == "__main__":
    serve()
