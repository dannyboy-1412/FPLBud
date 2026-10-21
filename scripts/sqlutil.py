"""Split SQL scripts into statements, respecting dollar-quoted function bodies."""

from __future__ import annotations

import re

_DOLLAR = re.compile(r"\$[A-Za-z0-9_]*\$")


def split_sql(script: str) -> list[str]:
    statements: list[str] = []
    buf: list[str] = []
    i = 0
    n = len(script)
    in_single = False
    dollar_tag: str | None = None

    while i < n:
        ch = script[i]
        nxt = script[i + 1] if i + 1 < n else ""

        if dollar_tag is not None:
            if script.startswith(dollar_tag, i):
                buf.append(dollar_tag)
                i += len(dollar_tag)
                dollar_tag = None
                continue
            buf.append(ch)
            i += 1
            continue

        if in_single:
            buf.append(ch)
            if ch == "'" and nxt == "'":
                buf.append(nxt)
                i += 2
                continue
            if ch == "'":
                in_single = False
            i += 1
            continue

        if ch == "-" and nxt == "-":
            while i < n and script[i] != "\n":
                buf.append(script[i])
                i += 1
            continue

        if ch == "/" and nxt == "*":
            buf.append(ch)
            buf.append(nxt)
            i += 2
            while i < n - 1 and not (script[i] == "*" and script[i + 1] == "/"):
                buf.append(script[i])
                i += 1
            if i < n:
                buf.append(script[i])
                i += 1
            if i < n:
                buf.append(script[i])
                i += 1
            continue

        if ch == "'":
            in_single = True
            buf.append(ch)
            i += 1
            continue

        if ch == "$":
            match = _DOLLAR.match(script, i)
            if match:
                dollar_tag = match.group(0)
                buf.append(dollar_tag)
                i += len(dollar_tag)
                continue

        if ch == ";":
            statement = "".join(buf).strip()
            if statement:
                statements.append(statement)
            buf = []
            i += 1
            continue

        buf.append(ch)
        i += 1

    tail = "".join(buf).strip()
    if tail:
        statements.append(tail)
    return statements
