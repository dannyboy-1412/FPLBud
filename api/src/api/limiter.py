from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address


def limiter_key(request: Request) -> str:
    auth = request.headers.get("authorization") or ""
    if auth.lower().startswith("bearer ") and len(auth) > 20:
        return "user:" + auth[-24:]
    return get_remote_address(request)


limiter = Limiter(key_func=limiter_key, default_limits=[])
