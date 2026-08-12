"""API models for dataset query endpoints."""

from typing import Any

from pydantic import BaseModel


class DatasetQueryRequest(BaseModel):
    """Request payload used to execute SQL against a registered dataset."""

    sql: str


class DatasetQueryResponse(BaseModel):
    """JSON representation of one materialized dataset query result."""

    sql: str
    rows: list[dict[str, Any]]
    row_count: int
    column_count: int
    execution_time_ms: float
