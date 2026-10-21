from fastapi import APIRouter, Depends

from api.auth import require_internal
from api.deps import get_settings_dep
from api.worker import process_one
from fplcore.settings import Settings
from ingest.run import drain_queue

router = APIRouter()


@router.post("/internal/agent/drain")
async def drain(_: None = Depends(require_internal), settings: Settings = Depends(get_settings_dep)) -> dict:
    n = await drain_queue(limit=25)
    extra = await process_one(settings)
    return {"drained": n, "processed_one": extra}
