"""Requests for independent dossier editing and reviewed imports."""
from datetime import date
from typing import Literal

from pydantic import Field

from app.core import config
from app.schemas.base import StrictModel
from app.schemas.profiles import Message

Category = Literal["trait", "style", "boundary", "value", "event", "preference"]


class ContactDetails(StrictModel):
    revision: int = Field(ge=0)
    name: str = Field(min_length=1, max_length=60)
    relationship_tags: list[str] = Field(default_factory=list, max_length=10)
    background: str = Field(default="", max_length=500)


class ManualFact(StrictModel):
    revision: int = Field(ge=0)
    category: Category
    topic: str = Field(min_length=1, max_length=40)
    text: str = Field(min_length=1, max_length=200)
    context: str = Field(default="", max_length=100)
    event_date: date | None = None
    event_status: Literal["planned", "completed", "cancelled", "unknown"] = "unknown"


class DossierImport(StrictModel):
    revision: int = Field(ge=0)
    messages: list[Message] = Field(min_length=2, max_length=config.MAX_ROWS)
    self_speaker: str = Field(min_length=1, max_length=100)
    other_speaker: str = Field(min_length=1, max_length=100)
    chat_date: date | None = None
    scene: str = Field(default="", max_length=100)
    use_ai: bool = False
    cloud_consent: bool = False


class ImportCommit(StrictModel):
    token: str = Field(min_length=1, max_length=500_000)
    selected_ids: list[str] = Field(max_length=20)
    save_consent: bool = False
