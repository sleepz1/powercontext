# Copyright (c) 2026 OceanBase.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Capture one CSV row as a stable Source and a text-evidence projection.

Identity is ``csv:{quoted document_id}:{quoted primary_key_value}``. Field text is
preserved exactly: no trimming and no numeric, boolean, or date coercion.
"""

from __future__ import annotations

import csv
import io
import json
from urllib.parse import quote

from pydantic import BaseModel

from powercontext.limits import MAX_SOURCE_ID_LENGTH
from powercontext.sources.definitions import AdapterSourceDefinition
from powercontext.sources.models import Source, SourceMaterialization
from powercontext.sources.projections import TEXT_EVIDENCE_PROJECTION_KEY, TextEvidence

CSV_ROW_SOURCE_NAME = "csv-row"
CSV_ROW_SOURCE_VERSION = "1"

_DOCUMENT_ID = "document_id must be a non-empty string without surrounding whitespace"
_PRIMARY_KEY = "primary_key must be a non-empty string"
_PRIMARY_KEY_VALUE = "primary_key_value must contain a non-whitespace character"
_PRIMARY_KEY_MATCH = "primary_key must match a header field exactly"
_HEADER_EMPTY = "CSV header must not be empty"
_HEADER_FIELD = "CSV header fields must be non-empty and not whitespace"
_HEADER_UNIQUE = "CSV header fields must be unique"
_RECORD_WIDTH = "CSV record width must match the header"
_DUPLICATE_KEY = "primary key values must be unique within the document"
_UTF8 = "CSV content must be strict UTF-8"
_MALFORMED = "CSV document is malformed"
_MISSING_HEADER = "CSV document must include a header"
_SOURCE_ID_LENGTH = "csv row source_id must not exceed 256 characters"
_ROW_IDENTITY = "primary_key_value must match the primary key field"
_CAPTURED = "csv row sources must be captured"


class CSVDocumentInput(BaseModel):
    """Complete offline CSV document addressed by a stable document id."""

    document_id: str
    primary_key: str
    content: bytes


class CSVRowInput(BaseModel):
    """One validated CSV record addressed by its document and primary key."""

    document_id: str
    primary_key: str
    primary_key_value: str
    columns: tuple[str, ...]
    values: tuple[str, ...]


class CSVRowSource(Source):
    """Captured CSV row whose identity does not depend on physical order."""

    source_id: str
    document_id: str
    primary_key: str
    primary_key_value: str
    columns: tuple[str, ...]
    values: tuple[str, ...]


def csv_row_source_id(document_id: str, primary_key_value: str) -> str:
    """Return the bounded row identity for a document and primary-key value."""

    _require_document_id(document_id)
    _require_primary_key_value(primary_key_value)
    source_id = f"csv:{quote(document_id, safe='')}:{quote(primary_key_value, safe='')}"
    if len(source_id) > MAX_SOURCE_ID_LENGTH:
        raise ValueError(_SOURCE_ID_LENGTH)
    return source_id


def parse_csv_document(value: CSVDocumentInput) -> tuple[CSVRowInput, ...]:
    """Parse and validate a whole CSV document before returning any row."""

    _require_document_id(value.document_id)
    _require_primary_key_name(value.primary_key)
    records = _read_records(_decode_csv(value.content))
    if not records:
        raise ValueError(_MISSING_HEADER)
    columns, key_index = _validate_header(records[0], value.primary_key)
    rows: list[CSVRowInput] = []
    seen_keys: set[str] = set()
    for record in records[1:]:
        if not record:
            continue
        if len(record) != len(columns):
            raise ValueError(_RECORD_WIDTH)
        primary_key_value = record[key_index]
        _require_primary_key_value(primary_key_value)
        if primary_key_value in seen_keys:
            raise ValueError(_DUPLICATE_KEY)
        seen_keys.add(primary_key_value)
        csv_row_source_id(value.document_id, primary_key_value)
        rows.append(
            CSVRowInput(
                document_id=value.document_id,
                primary_key=value.primary_key,
                primary_key_value=primary_key_value,
                columns=columns,
                values=tuple(record),
            )
        )
    return tuple(rows)


class CSVRowSourceAdapter:
    """Resolve a validated row into a captured Source and read that row back."""

    input_class = CSVRowInput
    name = CSV_ROW_SOURCE_NAME
    source_class = CSVRowSource

    async def resolve(self, value: CSVRowInput, /) -> CSVRowSource:
        source_id = _validated_source_id(value)
        return CSVRowSource(
            name=source_id,
            definition_version=CSV_ROW_SOURCE_VERSION,
            materialization=SourceMaterialization.CAPTURED,
            source_id=source_id,
            document_id=value.document_id,
            primary_key=value.primary_key,
            primary_key_value=value.primary_key_value,
            columns=value.columns,
            values=value.values,
        )

    async def read(self, source: CSVRowSource, /) -> CSVRowInput:
        row = CSVRowInput(
            document_id=source.document_id,
            primary_key=source.primary_key,
            primary_key_value=source.primary_key_value,
            columns=tuple(source.columns),
            values=tuple(source.values),
        )
        if source.name != source.source_id or _validated_source_id(row) != source.source_id:
            raise ValueError(_ROW_IDENTITY)
        if source.materialization is not SourceMaterialization.CAPTURED:
            raise ValueError(_CAPTURED)
        return row


class CSVRowTextEvidenceProjection:
    """Project one captured row through the standard text-evidence capability."""

    name = TEXT_EVIDENCE_PROJECTION_KEY.name
    version = TEXT_EVIDENCE_PROJECTION_KEY.version
    source_class = CSVRowSource
    output_class: type[BaseModel] = TextEvidence

    def project(self, source: CSVRowSource, /) -> TextEvidence:
        row = _row_object(source.columns, source.values)
        return TextEvidence(
            source_type=CSV_ROW_SOURCE_NAME,
            source_id=source.source_id,
            content=json.dumps(row, ensure_ascii=False, separators=(",", ":")),
            metadata={
                "document_id": source.document_id,
                "primary_key": source.primary_key,
                "primary_key_value": source.primary_key_value,
                "columns": list(source.columns),
                "row": row,
            },
        )


CSV_ROW_SOURCE_DEFINITION = AdapterSourceDefinition(
    CSVRowSourceAdapter(),
    version=CSV_ROW_SOURCE_VERSION,
    projections=(CSVRowTextEvidenceProjection(),),
)


def _require_document_id(document_id: object) -> None:
    if not isinstance(document_id, str) or document_id == "" or document_id != document_id.strip():
        raise ValueError(_DOCUMENT_ID)


def _require_primary_key_name(primary_key: object) -> None:
    if not isinstance(primary_key, str) or primary_key == "":
        raise ValueError(_PRIMARY_KEY)


def _require_primary_key_value(primary_key_value: object) -> None:
    if not isinstance(primary_key_value, str) or primary_key_value.strip() == "":
        raise ValueError(_PRIMARY_KEY_VALUE)


def _decode_csv(content: bytes) -> str:
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError(_UTF8) from error


def _read_records(text: str) -> list[list[str]]:
    reader = csv.reader(
        io.StringIO(text, newline=""),
        delimiter=",",
        quotechar='"',
        doublequote=True,
        escapechar=None,
        strict=True,
        skipinitialspace=False,
    )
    try:
        return [list(record) for record in reader]
    except csv.Error as error:
        raise ValueError(_MALFORMED) from error


def _validate_header(header: list[str], primary_key: str) -> tuple[tuple[str, ...], int]:
    if not header:
        raise ValueError(_HEADER_EMPTY)
    indexes: dict[str, int] = {}
    for index, column in enumerate(header):
        if column.strip() == "":
            raise ValueError(_HEADER_FIELD)
        if column in indexes:
            raise ValueError(_HEADER_UNIQUE)
        indexes[column] = index
    try:
        key_index = indexes[primary_key]
    except KeyError:
        raise ValueError(_PRIMARY_KEY_MATCH) from None
    return tuple(header), key_index


def _validated_source_id(value: CSVRowInput) -> str:
    _require_document_id(value.document_id)
    _require_primary_key_name(value.primary_key)
    columns = tuple(value.columns)
    values = tuple(value.values)
    if len(columns) != len(values):
        raise ValueError(_RECORD_WIDTH)
    _, key_index = _validate_header(list(columns), value.primary_key)
    if values[key_index] != value.primary_key_value:
        raise ValueError(_ROW_IDENTITY)
    return csv_row_source_id(value.document_id, value.primary_key_value)


def _row_object(columns: tuple[str, ...], values: tuple[str, ...]) -> dict[str, str]:
    return dict(zip(columns, values, strict=True))


__all__ = [
    "CSV_ROW_SOURCE_DEFINITION",
    "CSVDocumentInput",
    "CSVRowInput",
    "CSVRowSource",
    "csv_row_source_id",
    "parse_csv_document",
]
