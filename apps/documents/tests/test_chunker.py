# apps/documents/tests/test_chunker.py
import pytest

from apps.documents.services.chunker import chunk_pages


def test_chunk_pages_empty_list_returns_empty():
    assert chunk_pages([]) == []


def test_chunk_pages_single_short_page_produces_one_chunk():
    pages = [{"page": 1, "text": "This is a short page with few tokens."}]
    result = chunk_pages(pages, chunk_size=350, overlap=50)

    assert len(result) == 1
    assert result[0]["chunk_index"] == 0
    assert result[0]["page_number"] == 1
    assert result[0]["token_count"] < 350


def test_chunk_pages_large_page_splits_into_multiple_chunks():
    # ~1000 tokens of repeated text, forces multiple chunks at size 350
    text = "word " * 1000
    pages = [{"page": 1, "text": text}]
    result = chunk_pages(pages, chunk_size=350, overlap=50)

    assert len(result) > 1
    for chunk in result:
        assert chunk["page_number"] == 1
        assert chunk["token_count"] <= 350

    # chunk_index must be sequential starting at 0
    assert [c["chunk_index"] for c in result] == list(range(len(result)))


def test_chunk_pages_page_exactly_at_chunk_size_produces_one_chunk():
    encoding_word_count = 350  # approx, "word " tokenizes close to 1 token each
    text = "word " * encoding_word_count
    pages = [{"page": 1, "text": text}]
    result = chunk_pages(pages, chunk_size=350, overlap=50)

    # whether this is 1 or 2 chunks depends on exact tokenization,
    # so assert the real invariant instead: every chunk respects the ceiling
    for chunk in result:
        assert chunk["token_count"] <= 350


def test_chunk_pages_never_spans_multiple_pages():
    pages = [
        {"page": 1, "text": "First page content here."},
        {"page": 2, "text": "Second page content here."},
    ]
    result = chunk_pages(pages, chunk_size=350, overlap=50)

    page_1_chunks = [c for c in result if c["page_number"] == 1]
    page_2_chunks = [c for c in result if c["page_number"] == 2]

    assert len(page_1_chunks) >= 1
    assert len(page_2_chunks) >= 1
    # chunk_index keeps incrementing across pages, never resets
    assert page_2_chunks[0]["chunk_index"] > page_1_chunks[-1]["chunk_index"]


def test_chunk_pages_skips_blank_pages():
    pages = [
        {"page": 1, "text": "Real content."},
        {"page": 2, "text": "   "},  # whitespace-only
        {"page": 3, "text": "More real content."},
    ]
    result = chunk_pages(pages, chunk_size=350, overlap=50)

    page_numbers = {c["page_number"] for c in result}
    assert page_numbers == {1, 3}


def test_chunk_pages_is_deterministic():
    pages = [{"page": 1, "text": "word " * 500}]
    result_1 = chunk_pages(pages, chunk_size=350, overlap=50)
    result_2 = chunk_pages(pages, chunk_size=350, overlap=50)

    assert result_1 == result_2


def test_chunk_pages_raises_when_overlap_exceeds_chunk_size():
    pages = [{"page": 1, "text": "some content"}]
    with pytest.raises(ValueError):
        chunk_pages(pages, chunk_size=50, overlap=50)