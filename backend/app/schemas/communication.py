"""Communication memory requests and grounded model output."""
from typing import Literal

from pydantic import Field

from app.schemas.base import StrictModel
from app.schemas.dossier import DossierImport

MemoryType = Literal["communication_request", "boundary", "support_need", "situated_trait",
                     "shared_understanding", "stage_context", "event", "useful_preference",
                     "relationship_position", "interaction_signal", "personal_view", "emotional_state"]


class Evidence(StrictModel):
    message_id: int = Field(ge=0)
    quote: str = Field(min_length=2, max_length=300)


class Candidate(StrictModel):
    memory_type: MemoryType
    scene: Literal["romance", "everyday", "interests", "intergenerational", "coordination"] = "everyday"
    subject: Literal["self", "other", "relation"] = "other"
    topic: str = Field(min_length=1, max_length=40)
    fact: str = Field(min_length=1, max_length=200)
    scope: str = Field(min_length=1, max_length=160)
    retention: Literal["conditional", "temporary", "episode", "pending"]
    source_level: Literal["direct", "interaction"] = "direct"
    interpretation: str = Field(default="", max_length=140)
    method: str = Field(default="", max_length=180)
    example: str = Field(default="", max_length=180)
    limitation: str = Field(default="", max_length=140)
    claim_basis: Literal["stated", "observed", "inferred"] = "stated"
    alternative: str = Field(default="", max_length=160)
    verification_reason: str = Field(default="", max_length=180)
    review_required: bool = False
    target_id: str | None = Field(default=None, max_length=64)
    operation: Literal["add", "evidence", "refine", "branch", "change", "conflict", "end"] = "add"
    event_identity: str = Field(default="", max_length=100)
    event_status: Literal["unknown", "planned", "completed", "cancelled", "result_unknown", "offer_received"] = "unknown"
    evidence: list[Evidence] = Field(min_length=1, max_length=6)


class MemoryImport(DossierImport):
    save_consent: bool = False
    role_reliability: Literal["confirmed", "unverified"] = "confirmed"
    time_reliability: Literal["confirmed", "unknown", "ocr_uncertain"] = "confirmed"
    source_kind: Literal["chat", "ocr", "corrected_transcript", "ai_summary"] = "chat"


class MemoryCommit(StrictModel):
    token: str = Field(min_length=1, max_length=500_000)
    save_consent: bool = False


class MemoryNote(StrictModel):
    revision: int = Field(ge=0)
    fact_id: str | None = Field(default=None, max_length=64)
    text: str = Field(min_length=1, max_length=200)
    use_in_ai: bool = False


class MemoryResolution(StrictModel):
    revision: int = Field(ge=0)
    decision: Literal["accept", "keep"]
