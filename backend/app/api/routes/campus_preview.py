"""Opt-in local preview controls; absent in normal project operation."""
import os

from fastapi import APIRouter, HTTPException
from pydantic import Field

from app.api.deps import get_store
from app.core.errors import call
from app.schemas.base import StrictModel
from app.services import campus_demo

router = APIRouter(prefix="/api/campus-preview", tags=["虚构案例预览"])


def enabled():
    if os.environ.get("JOKER_CAMPUS_PREVIEW") != "1":
        raise HTTPException(404, "预览案例入口未开启")


class Start(StrictModel):
    case_id: str = Field(max_length=10)


class Advance(StrictModel):
    contact_id: str = Field(max_length=64)
    revision: int = Field(ge=0)


@router.get("/cases")
def catalog():
    enabled()
    return {"cases": campus_demo.catalog(), "mode": "recorded_fictional_replay"}


@router.post("/start")
def start(body: Start):
    enabled()
    return call(campus_demo.start, get_store(), body.case_id)


@router.post("/next")
def advance(body: Advance):
    enabled()
    return call(campus_demo.advance, get_store(), body.contact_id, body.revision)
