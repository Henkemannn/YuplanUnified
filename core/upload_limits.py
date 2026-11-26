"""Shared upload limits and bounded parsing helpers."""

from __future__ import annotations

import io
import csv
import zipfile
from dataclasses import dataclass
from typing import BinaryIO

from flask import current_app, has_app_context, request

KIB = 1024
MIB = 1024 * KIB


class UploadTooLarge(ValueError):
    """Raised when an upload exceeds a configured resource limit."""


class InvalidUpload(ValueError):
    """Raised when an upload is structurally invalid or exceeds parser limits."""


@dataclass(frozen=True)
class UploadPolicy:
    request_bytes: int = 8 * MIB
    multipart_memory_bytes: int = 1 * MIB
    csv_bytes: int = 5 * MIB
    txt_bytes: int = 1 * MIB
    document_bytes: int = 5 * MIB
    zip_total_bytes: int = 50 * MIB
    zip_entry_bytes: int = 25 * MIB
    zip_entries: int = 1000
    multipart_parts: int = 10
    xlsx_sheets: int = 50
    rows_total: int = 50_000
    columns_per_row: int = 256
    cells_total: int = 250_000
    text_bytes: int = 8 * MIB
    cell_text_bytes: int = 64 * KIB
    docx_tables: int = 100


def get_upload_policy() -> UploadPolicy:
    policy = UploadPolicy()
    if not has_app_context():
        return policy
    overrides = current_app.config.get("UPLOAD_POLICY_OVERRIDES") or {}
    if not isinstance(overrides, dict):
        return policy
    values = {
        field: int(overrides[field])
        for field in policy.__dataclass_fields__
        if field in overrides
    }
    return UploadPolicy(**{**policy.__dict__, **values})


def is_upload_request(path: str | None = None) -> bool:
    route_path = path if path is not None else request.path
    return (
        route_path.startswith("/import/")
        or route_path.startswith("/ui/admin/menu-import/upload")
        or route_path.startswith("/api/builder/import/")
    )


def apply_request_limits() -> None:
    """Set Flask/Werkzeug limits before any form or body access."""
    if not is_upload_request():
        return
    policy = get_upload_policy()
    request.max_content_length = policy.request_bytes
    request.max_form_memory_size = policy.multipart_memory_bytes
    request.max_form_parts = policy.multipart_parts


def bounded_read(stream: BinaryIO, limit: int) -> bytes:
    """Read at most limit plus one byte, rejecting oversized streams."""
    if limit <= 0:
        raise ValueError("upload limit must be positive")
    chunks: list[bytes] = []
    total = 0

    while True:
        chunk = stream.read(min(64 * KIB, limit + 1 - total))
        if not chunk:
            break
        if not isinstance(chunk, bytes):
            chunk = bytes(chunk)
        total += len(chunk)
        if total > limit:
            raise UploadTooLarge("upload exceeds the allowed size")
        chunks.append(chunk)
    if total == 0:
        raise InvalidUpload("file is empty")
    return b"".join(chunks)


def validate_text_bytes(data: bytes, *, policy: UploadPolicy | None = None) -> str:
    active = policy or get_upload_policy()
    if len(data) > active.text_bytes:
        raise UploadTooLarge("text content exceeds the allowed size")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise InvalidUpload("file must be UTF-8 encoded") from exc
    if len(text.encode("utf-8")) > active.text_bytes:
        raise UploadTooLarge("text content exceeds the allowed size")
    return text


def validate_text_lines(data: bytes, *, policy: UploadPolicy | None = None) -> list[str]:
    active = policy or get_upload_policy()
    text = validate_text_bytes(data, policy=active)
    lines = text.splitlines()
    if len(lines) > active.rows_total:
        raise UploadTooLarge("text document contains too many rows")
    total = 0
    for line in lines:
        encoded = line.encode("utf-8")
        if len(encoded) > active.cell_text_bytes:
            raise UploadTooLarge("text line exceeds the allowed size")
        total += len(encoded)
        if total > active.text_bytes:
            raise UploadTooLarge("text content exceeds the allowed size")
    return lines


def validate_csv_bytes(data: bytes, *, policy: UploadPolicy | None = None) -> None:
    active = policy or get_upload_policy()
    text = validate_text_bytes(data, policy=active)
    try:
        rows = csv.reader(io.StringIO(text, newline=""))
        row_count = 0
        cell_count = 0
        for row in rows:
            row_count += 1
            if row_count > active.rows_total:
                raise UploadTooLarge("CSV contains too many rows")
            if len(row) > active.columns_per_row:
                raise UploadTooLarge("CSV row contains too many columns")
            cell_count += len(row)
            if cell_count > active.cells_total:
                raise UploadTooLarge("CSV contains too many cells")
            for value in row:
                validate_cell_text(value, policy=active)
    except csv.Error as exc:
        raise InvalidUpload("invalid CSV file") from exc


def validate_zip_payload(data: bytes, *, policy: UploadPolicy | None = None) -> None:
    """Validate ZIP metadata and actual decompressed bytes without disk extraction."""
    active = policy or get_upload_policy()
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        raise InvalidUpload("invalid document archive") from exc

    total = 0
    actual_total = 0
    try:
        entries = archive.infolist()
        if len(entries) > active.zip_entries:
            raise UploadTooLarge("document contains too many archive entries")
        for entry in entries:
            if entry.is_dir():
                continue
            if entry.file_size > active.zip_entry_bytes:
                raise UploadTooLarge("document archive entry is too large")
            total += entry.file_size
            if total > active.zip_total_bytes:
                raise UploadTooLarge("document archive expands beyond the allowed size")
            try:
                with archive.open(entry) as member:
                    actual = 0
                    while True:
                        chunk = member.read(min(64 * KIB, active.zip_entry_bytes + 1 - actual))
                        if not chunk:
                            break
                        actual += len(chunk)
                        actual_total += len(chunk)
                        if actual > active.zip_entry_bytes:
                            raise UploadTooLarge("document archive entry is too large")
                        if actual_total > active.zip_total_bytes:
                            raise UploadTooLarge(
                                "document archive expands beyond the allowed size"
                            )
            except UploadTooLarge:
                raise
            except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
                raise InvalidUpload("invalid document archive") from exc
    finally:
        archive.close()


def validate_cell_text(value: object, *, policy: UploadPolicy | None = None) -> str:
    active = policy or get_upload_policy()
    text = "" if value is None else str(value)
    if len(text.encode("utf-8")) > active.cell_text_bytes:
        raise UploadTooLarge("cell or paragraph exceeds the allowed size")
    return text


__all__ = [
    "InvalidUpload",
    "KIB",
    "MIB",
    "UploadPolicy",
    "UploadTooLarge",
    "apply_request_limits",
    "bounded_read",
    "get_upload_policy",
    "is_upload_request",
    "validate_cell_text",
    "validate_csv_bytes",
    "validate_text_bytes",
    "validate_text_lines",
    "validate_zip_payload",
]
