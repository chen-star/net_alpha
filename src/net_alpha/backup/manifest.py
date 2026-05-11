"""Pydantic Manifest model for a backup bundle."""

from __future__ import annotations

from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, ValidationError

MANIFEST_FORMAT_VERSION = 1


class Manifest(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    format_version: int
    app_version: str
    schema_version: int
    created_at: datetime
    reason: str
    hostname: str
    db_sha256: str
    db_size_bytes: int
    row_counts: dict[str, int]
    account_labels: list[str]
    encrypted: bool

    def to_json_bytes(self) -> bytes:
        return self.model_dump_json(indent=2).encode("utf-8")

    @classmethod
    def from_json_bytes(cls, blob: bytes) -> Self:
        try:
            return cls.model_validate_json(blob)
        except ValidationError as e:
            raise ValueError(f"invalid manifest: {e}") from e
