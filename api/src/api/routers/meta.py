from fastapi import APIRouter, Depends
from psycopg import Connection

from api.deps import db_conn
from api.services import meta_payload

router = APIRouter()


@router.get("/meta")
def meta(conn: Connection = Depends(db_conn)) -> dict:
    return meta_payload(conn)
