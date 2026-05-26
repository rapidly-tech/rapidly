"""Chunkers — turn a source document's bytes into ordered text chunks.

Each chunk gets one VectorChunk row when the indexer flushes. The
chunker's job is to produce *self-contained* slices: a downstream
retriever should be able to surface a single chunk to the LLM and
have it carry enough context to be useful.

v1 supports text/markdown only via paragraph-aware splitting. PDF +
DOCX dispatch lands in a follow-up that pulls in pdfplumber +
python-docx as optional deps.

Why paragraph-first, not fixed-size:
    A blind 1500-char window will slice mid-sentence and mid-list,
    which makes retrieved chunks read like garbage. Paragraph
    boundaries (one blank line) match the document's authored
    structure, so we keep them whenever each paragraph fits inside
    the size cap. We only fall back to character-level splitting
    when a single paragraph blows past the cap.

The overlap parameter exists to soften the boundary: when one
chunk ends mid-thought because the *next* paragraph would have
made it too long, the next chunk repeats the last ``overlap``
characters so a retriever query that hits the boundary still
surfaces the right context.
"""

from __future__ import annotations

import re

# Default chunk-size cap. Calibrated for the OpenAI 3-small
# embedding model (8K-token context limit) with headroom — at ~4
# chars/token a 1500-char chunk is ~375 tokens, comfortably below
# the limit and big enough that one chunk typically holds a full
# paragraph or short section.
DEFAULT_MAX_CHARS = 1500

# How much trailing context to repeat at the start of the next
# chunk when we have to split inside a paragraph. 200 chars ≈
# 50 tokens — enough to carry an antecedent ("it", "this") into
# the next chunk without doubling storage.
DEFAULT_OVERLAP = 200


class UnsupportedMimeError(ValueError):
    """Raised when the indexer is asked to chunk a mime we don't handle yet."""


# Single blank-line paragraph break (\n\n, possibly with whitespace).
_PARAGRAPH_BREAK = re.compile(r"\n\s*\n")


def chunk_text(
    text: str,
    *,
    max_chars: int = DEFAULT_MAX_CHARS,
    overlap: int = DEFAULT_OVERLAP,
) -> list[str]:
    """Split ``text`` into ordered chunks no larger than ``max_chars``.

    Paragraph-aware: groups whole paragraphs into chunks up to
    ``max_chars``. A single paragraph that exceeds ``max_chars`` is
    split at character boundaries with ``overlap`` chars repeated.

    Returns an empty list for empty/whitespace-only input. Callers
    should treat an empty result as "nothing to index" rather than
    an error — a zero-byte source document is valid input.
    """
    if not text or not text.strip():
        return []
    if max_chars < 1:
        raise ValueError("max_chars must be >= 1")
    if overlap < 0:
        raise ValueError("overlap must be >= 0")
    if overlap >= max_chars:
        # Overlap >= chunk size would make the splitter loop forever.
        raise ValueError("overlap must be < max_chars")

    paragraphs = [p.strip() for p in _PARAGRAPH_BREAK.split(text) if p.strip()]

    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        if len(para) > max_chars:
            # Flush whatever is pending, then character-split the
            # oversize paragraph with overlap.
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(_split_long(para, max_chars=max_chars, overlap=overlap))
            continue

        # Does adding this paragraph (with separator) blow the cap?
        sep = "\n\n" if current else ""
        if len(current) + len(sep) + len(para) > max_chars:
            chunks.append(current)
            current = para
        else:
            current = f"{current}{sep}{para}"

    if current:
        chunks.append(current)

    return chunks


def _split_long(text: str, *, max_chars: int, overlap: int) -> list[str]:
    """Character-level split for a paragraph that exceeds max_chars.

    Stops once a window covers the end of the text so we don't
    emit a trailing sliver that the previous chunk's overlap
    already contains.
    """
    out: list[str] = []
    i = 0
    n = len(text)
    step = max_chars - overlap
    while i < n:
        end = i + max_chars
        out.append(text[i:end])
        if end >= n:
            break
        i += step
    return out


def chunk_for_mime(mime: str, raw: bytes, **kwargs: int) -> list[str]:
    """Dispatch by mime type. Raises UnsupportedMimeError for non-text.

    PDF (``application/pdf``) and DOCX (``application/vnd.openxmlformats-
    officedocument.wordprocessingml.document``) are explicitly rejected
    so the caller can surface a clear message — the supporting libs
    aren't in the dep tree yet and we'd rather fail fast than do a
    silent best-effort utf-8 decode of binary content.

    All ``text/*`` mimes route to ``chunk_text``. Markdown gets no
    special handling beyond paragraph-aware splitting because the
    blank-line paragraph break already aligns with markdown's section
    structure.
    """
    if mime.startswith("text/") or mime in (
        "application/json",
        "application/x-yaml",
        "application/yaml",
    ):
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise UnsupportedMimeError(
                f"non-utf-8 bytes for mime={mime!r}; only utf-8 text is supported"
            ) from exc
        return chunk_text(text, **kwargs)
    raise UnsupportedMimeError(
        f"indexing for mime {mime!r} is not supported yet "
        "(v1 supports text/* and application/json + application/yaml)"
    )
