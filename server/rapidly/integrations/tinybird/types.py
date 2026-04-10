"""TypedDict schemas for Tinybird event ingestion payloads."""

from typing import TypedDict


class TinybirdEvent(TypedDict):
    id: str
    ingested_at: str
    timestamp: str
    name: str
    source: str
    organization_id: str
    customer_id: str | None
    external_customer_id: str | None
    member_id: str | None
    external_member_id: str | None
    external_id: str | None
    parent_id: str | None
    root_id: str | None
    event_type_id: str | None
    # Meter fields
    meter_id: str | None
    units: int | None
    rollover: bool | None
    # Core entity IDs
    share_id: str | None
    transaction_id: str | None
    # Financial fields
    amount: int | None
    currency: str | None
    # Customer fields
    customer_email: str | None
    customer_name: str | None
    # User event fields (_cost, _llm)
    cost_amount: int | None
    cost_currency: str | None
    llm_vendor: str | None
    llm_model: str | None
    llm_input_tokens: int | None
    llm_output_tokens: int | None
    # Remaining metadata as JSON string
    user_metadata: str
