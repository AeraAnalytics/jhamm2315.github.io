from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field, HttpUrl


class Evidence(BaseModel):
    url: HttpUrl
    title: str
    excerpt: str = ""
    verified: bool = False


class OpportunityIn(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    category: Literal["development", "service", "product", "government", "fulfillment"]
    summary: str = Field(min_length=1, max_length=5000)
    source_url: HttpUrl
    evidence: list[Evidence] = []


class PublicProfile(BaseModel):
    legal_name: str | None = None
    business_state: str | None = None
    public_business_address: str | None = None
    website: HttpUrl | None = None
    verified_fields: list[str] = []


class ResearchRequest(BaseModel):
    query: str = Field(min_length=3, max_length=2000)
    model: str = Field(min_length=1, max_length=100)
    max_turns: int = Field(ge=1, le=10)
    reservation_cents: int = Field(ge=1)


class Decision(BaseModel):
    decision: Literal["approved", "denied"]
    payload_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class PolicyIn(BaseModel):
    cash_buffer_cents: int = Field(ge=0)
    daily_limit_cents: int = Field(ge=0)
    total_limit_cents: int = Field(ge=0)
    spending_paused: bool = False


class LedgerIn(BaseModel):
    amount_cents: int
    receipt_reference: str = Field(min_length=1, max_length=300)
    event_key: str = Field(min_length=1, max_length=200)


class OutcomeIn(BaseModel):
    observation: str = Field(min_length=1, max_length=4000)
    revenue_cents: int = 0
    cost_cents: int = 0


class ReconcileIn(BaseModel):
    actual_cents: int = Field(ge=0)
    receipt_reference: str = Field(min_length=1, max_length=300)


class ResolveIn(BaseModel):
    evidence_reference: str = Field(min_length=1, max_length=1000)


class Record(BaseModel):
    id: str
    data: dict[str, Any]
