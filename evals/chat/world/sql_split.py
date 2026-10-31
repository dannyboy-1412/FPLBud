"""Split a Postgres script on semicolons that are not inside strings or dollar quotes."""

from __future__ import annotations


def split_sql(script: str) -> list[str]:
    statements: list[str] = []
    buf: list[str] = []
    i = 0
    dollar: str | None = None
    while i < len(script):
        if dollar is None and script.startswith("--", i):
            newline = script.find("\n", i)
            i = len(script) if newline < 0 else newline + 1
            continue
        if dollar is None and script[i] == "'":
            buf.append(script[i])
            i += 1
            while i < len(script):
                buf.append(script[i])
                if script[i] == "'" and i + 1 < len(script) and script[i + 1] == "'":
                    buf.append(script[i + 1])
                    i += 2
                    continue
                if script[i] == "'":
                    i += 1
                    break
                i += 1
            continue
        if script[i] == "$":
            tag = _dollar_tag(script, i)
            if tag is not None:
                if dollar is None:
                    dollar = tag
                elif dollar == tag:
                    dollar = None
                buf.append(tag)
                i += len(tag)
                continue
        if script[i] == ";" and dollar is None:
            statement = "".join(buf).strip()
            if statement:
                statements.append(statement)
            buf = []
            i += 1
            continue
        buf.append(script[i])
        i += 1
    tail = "".join(buf).strip()
    if tail:
        statements.append(tail)
    return statements


def _dollar_tag(script: str, start: int) -> str | None:
    if not script.startswith("$", start):
        return None
    end = script.find("$", start + 1)
    if end < 0:
        return None
    tag = script[start : end + 1]
    if tag == "$$" or tag[1:-1].isidentifier():
        return tag
    return None
