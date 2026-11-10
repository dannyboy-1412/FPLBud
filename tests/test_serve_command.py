import sys
from pathlib import Path

import pytest

from api.serve import build_serve_command, restart_after_request_limit

BIN = "/app/.venv/bin/uvicorn"


def test_default_command_trusts_proxy_and_binds_fallback_port() -> None:
    command, limit = build_serve_command({}, BIN)
    assert limit is None
    assert command == [
        BIN,
        "api.main:app",
        "--host",
        "0.0.0.0",
        "--port",
        "8000",
        "--proxy-headers",
        "--forwarded-allow-ips",
        "*",
        "--timeout-graceful-shutdown",
        "25",
    ]


def test_port_and_proxy_settings_come_from_the_environment() -> None:
    command, limit = build_serve_command(
        {
            "PORT": "10000",
            "FORWARDED_ALLOW_IPS": "10.0.0.0/8",
            "UVICORN_GRACEFUL_SHUTDOWN": "10",
        },
        BIN,
    )
    assert limit is None
    assert "--port" in command
    assert command[command.index("--port") + 1] == "10000"
    assert command[command.index("--forwarded-allow-ips") + 1] == "10.0.0.0/8"
    assert command[command.index("--timeout-graceful-shutdown") + 1] == "10"


def test_blank_port_uses_the_local_fallback() -> None:
    command, _limit = build_serve_command({"PORT": ""}, BIN)
    assert command[command.index("--port") + 1] == "8000"


def test_request_cap_is_off_unless_set() -> None:
    for raw in ("", "0"):
        command, limit = build_serve_command({"UVICORN_LIMIT_MAX_REQUESTS": raw}, BIN)
        assert limit is None
        assert "--limit-max-requests" not in command


def test_request_cap_recycles_and_can_jitter() -> None:
    command, limit = build_serve_command(
        {
            "UVICORN_LIMIT_MAX_REQUESTS": "1000",
            "UVICORN_LIMIT_MAX_REQUESTS_JITTER": "50",
        },
        BIN,
    )
    assert limit == 1000
    assert command[command.index("--limit-max-requests") + 1] == "1000"
    assert command[command.index("--limit-max-requests-jitter") + 1] == "50"


def test_jitter_without_a_cap_is_ignored() -> None:
    command, limit = build_serve_command({"UVICORN_LIMIT_MAX_REQUESTS_JITTER": "50"}, BIN)
    assert limit is None
    assert "--limit-max-requests-jitter" not in command


@pytest.mark.parametrize(
    ("env", "name"),
    [
        ({"PORT": "nope"}, "PORT"),
        ({"PORT": "0"}, "PORT"),
        ({"UVICORN_GRACEFUL_SHUTDOWN": "-1"}, "UVICORN_GRACEFUL_SHUTDOWN"),
        ({"UVICORN_LIMIT_MAX_REQUESTS": "many"}, "UVICORN_LIMIT_MAX_REQUESTS"),
    ],
)
def test_bad_numbers_are_rejected(env: dict[str, str], name: str) -> None:
    with pytest.raises(SystemExit, match=name):
        build_serve_command(env, BIN)


def test_clean_exit_restarts_until_the_child_fails(tmp_path: Path) -> None:
    counter = tmp_path / "starts"
    code = (
        "import pathlib,sys; p=pathlib.Path(sys.argv[1]); "
        "n=int(p.read_text()) if p.exists() else 0; n+=1; p.write_text(str(n)); "
        "sys.exit(0 if n < 3 else 4)"
    )
    with pytest.raises(SystemExit) as raised:
        restart_after_request_limit([sys.executable, "-c", code, str(counter)])
    assert raised.value.code == 4
    assert counter.read_text() == "3"
