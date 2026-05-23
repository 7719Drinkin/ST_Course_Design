"""Requirement request / response schemas."""

from pydantic import BaseModel, Field


class IngestRequest(BaseModel):
    content: str = ""


class IngestResponse(BaseModel):
    text: str
    length: int
