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

"""Capture every physical PDF page and retrieve evidence pages from Memory.

Identity is ``pdf:{quoted document_id}:{document_sha256}:{page_number}``. Page
numbers start at 1. A later byte revision is a different identity.
"""

from __future__ import annotations

import hashlib
import io
from typing import Protocol
from urllib.parse import quote

from pydantic import BaseModel
from pypdf import PdfReader
from pypdf.errors import PyPdfError

from powercontext.artifacts import MemoryCitation
from powercontext.limits import MAX_SOURCE_ID_LENGTH
from powercontext.sources.definitions import AdapterSourceDefinition
from powercontext.sources.models import Source, SourceMaterialization
from powercontext.sources.pdf_retrieval import rank_page_texts
from powercontext.sources.projections import TEXT_EVIDENCE_PROJECTION_KEY, TextEvidence

PDF_PAGE_SOURCE_NAME = "pdf-page"
PDF_PAGE_SOURCE_VERSION = "1"

_DOCUMENT_ID = "document_id must contain a non-whitespace character"
_UNREADABLE = "PDF document is empty, corrupt, or cannot be read completely"
_SHA = "document_sha256 must be a lowercase SHA-256 hex digest"
_PAGE = "page_number must be a positive integer"
_SOURCE_ID_LENGTH = "pdf page source_id must not exceed 256 characters"
_PAGE_IDENTITY = "pdf page fields must match the source identity"
_CAPTURED = "pdf page sources must be captured"


class PDFDocumentInput(BaseModel):
    """Complete original PDF addressed by a stable document id."""

    document_id: str
    content: bytes


class PDFPageInput(BaseModel):
    """One physical page, including a page whose extractable text is empty."""

    document_id: str
    document_sha256: str
    page_number: int
    text: str


class PDFPageSource(Source):
    """Captured page. Identity follows the document bytes and physical page."""

    source_id: str
    document_id: str
    document_sha256: str
    page_number: int
    text: str


class _ScopedMemory(Protocol):
    """Scoped Memory head used to read stored page entries."""

    async def list(self, *, include_inactive: bool = False) -> object: ...


def pdf_page_source_id(document_id: str, document_sha256: str, page_number: int) -> str:
    """Return the bounded page identity for one document revision and physical page."""

    _require_document_id(document_id)
    digest = _require_sha256(document_sha256)
    number = _require_page_number(page_number)
    quoted = quote(document_id, safe="")
    source_id = f"pdf:{quoted}:{digest}:{number}"
    if len(source_id) <= MAX_SOURCE_ID_LENGTH:
        return source_id
    document_key = hashlib.sha256(document_id.encode("utf-8")).hexdigest()
    source_id = f"pdf-id:{document_key}:{digest}:{number}"
    if len(source_id) > MAX_SOURCE_ID_LENGTH:
        raise ValueError(_SOURCE_ID_LENGTH)
    return source_id


def parse_pdf_document(value: PDFDocumentInput) -> tuple[PDFPageInput, ...]:
    """Parse every physical page, or fail without returning a partial document."""

    _require_document_id(value.document_id)
    digest = hashlib.sha256(value.content).hexdigest()
    try:
        texts = _extract_page_texts(value.content)
    except PyPdfError as error:
        raise ValueError(_UNREADABLE) from error
    return tuple(
        PDFPageInput(
            document_id=value.document_id,
            document_sha256=digest,
            page_number=page_number,
            text=text,
        )
        for page_number, text in enumerate(texts, start=1)
    )


class PDFPageSourceAdapter:
    """Resolve one validated page into a captured Source and read that page back."""

    input_class = PDFPageInput
    name = PDF_PAGE_SOURCE_NAME
    source_class = PDFPageSource

    async def resolve(self, value: PDFPageInput, /) -> PDFPageSource:
        source_id = _validated_source_id(value)
        return PDFPageSource(
            name=source_id,
            definition_version=PDF_PAGE_SOURCE_VERSION,
            materialization=SourceMaterialization.CAPTURED,
            source_id=source_id,
            document_id=value.document_id,
            document_sha256=value.document_sha256,
            page_number=value.page_number,
            text=value.text,
        )

    async def read(self, source: PDFPageSource, /) -> PDFPageInput:
        page = PDFPageInput(
            document_id=source.document_id,
            document_sha256=source.document_sha256,
            page_number=source.page_number,
            text=source.text,
        )
        if source.name != source.source_id or _validated_source_id(page) != source.source_id:
            raise ValueError(_PAGE_IDENTITY)
        if source.materialization is not SourceMaterialization.CAPTURED:
            raise ValueError(_CAPTURED)
        return page


class PDFPageTextEvidenceProjection:
    """Project one captured page through the standard text-evidence capability."""

    name = TEXT_EVIDENCE_PROJECTION_KEY.name
    version = TEXT_EVIDENCE_PROJECTION_KEY.version
    source_class = PDFPageSource
    output_class: type[BaseModel] = TextEvidence

    def project(self, source: PDFPageSource, /) -> TextEvidence:
        return TextEvidence(
            source_type=PDF_PAGE_SOURCE_NAME,
            source_id=source.source_id,
            content=f"{source.document_id}\n{source.text}",
            metadata={
                "document_id": source.document_id,
                "document_sha256": source.document_sha256,
                "page_number": source.page_number,
            },
        )


PDF_PAGE_SOURCE_DEFINITION = AdapterSourceDefinition(
    PDFPageSourceAdapter(),
    version=PDF_PAGE_SOURCE_VERSION,
    projections=(PDFPageTextEvidenceProjection(),),
)


async def search_pdf_pages(memory: _ScopedMemory, question: str, limit: int = 10) -> tuple[MemoryCitation, ...]:
    """Return at most ``limit`` distinct stored pages for one natural-language question.

    Ranking reads the scoped Memory head. Full-text admission alone drops statement
    pages that do not repeat the question, so the stored entries are reranked offline.
    Every returned citation is an entry already stored in Memory.
    """

    if limit < 1:
        return ()
    stored = await _active_entries(memory)
    indexes = rank_page_texts(question, tuple(text for text, _citation in stored), limit)
    chosen: list[MemoryCitation] = []
    seen: set[tuple[str, str, str, str, str]] = set()
    for index in indexes:
        citation = stored[index][1]
        identity = _citation_identity(citation)
        if identity in seen:
            continue
        seen.add(identity)
        chosen.append(citation)
        if len(chosen) >= limit:
            break
    return tuple(chosen)


def _extract_page_texts(content: bytes) -> tuple[str, ...]:
    reader = PdfReader(io.BytesIO(content))
    if reader.is_encrypted and reader.decrypt("") == 0:
        raise ValueError(_UNREADABLE)
    texts: list[str] = []
    for page in reader.pages:
        extracted = page.extract_text() or ""
        texts.append("" if extracted.strip() == "" else extracted)
    if not texts:
        raise ValueError(_UNREADABLE)
    return tuple(texts)


async def _active_entries(memory: _ScopedMemory) -> tuple[tuple[str, MemoryCitation], ...]:
    page = await memory.list()
    entries = getattr(page, "entries", ())
    stored: list[tuple[str, MemoryCitation]] = []
    for entry in entries:
        if getattr(entry, "state", "active") != "active":
            continue
        text = _entry_text(entry)
        citation = getattr(entry, "citation", None)
        if text is None or not isinstance(citation, MemoryCitation):
            continue
        stored.append((text, citation))
    return tuple(stored)


def _entry_text(entry: object) -> str | None:
    body = getattr(entry, "entry", None)
    text = getattr(body, "text", None)
    if isinstance(text, str):
        return text
    return None


def _citation_identity(citation: MemoryCitation) -> tuple[str, str, str, str, str]:
    ref = citation.memory_ref
    return (ref.family, ref.artifact_id, str(ref.revision), citation.entry_id, citation.entry_version_id)


def _validated_source_id(value: PDFPageInput) -> str:
    return pdf_page_source_id(value.document_id, value.document_sha256, value.page_number)


def _require_document_id(document_id: object) -> None:
    if not isinstance(document_id, str) or document_id.strip() == "":
        raise ValueError(_DOCUMENT_ID)


def _require_sha256(document_sha256: object) -> str:
    if not isinstance(document_sha256, str) or len(document_sha256) != 64:
        raise ValueError(_SHA)
    if any(character not in "0123456789abcdef" for character in document_sha256):
        raise ValueError(_SHA)
    return document_sha256


def _require_page_number(page_number: object) -> int:
    if isinstance(page_number, bool) or not isinstance(page_number, int) or page_number < 1:
        raise ValueError(_PAGE)
    return page_number


__all__ = [
    "PDF_PAGE_SOURCE_DEFINITION",
    "PDFDocumentInput",
    "PDFPageInput",
    "PDFPageSource",
    "parse_pdf_document",
    "pdf_page_source_id",
    "search_pdf_pages",
]
