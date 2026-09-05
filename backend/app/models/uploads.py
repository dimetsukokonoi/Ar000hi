"""Framework-neutral uploaded document passed into the driver model."""
from dataclasses import dataclass


@dataclass(frozen=True)
class UploadedDocument:
    filename: str | None
    content_type: str | None
    content: bytes
