# apps/documents/tests/test_embedder.py

import pytest

from apps.documents.services import embedder
from apps.documents.services.embedder import (
    EMBEDDING_DIM,
    InvalidChunkInputError,
    QUERY_PREFIX,
    embed_chunks,
    embed_query,
)


def test_embed_chunks_single_chunk_returns_correct_dimension():
    chunks = [
        {"chunk_text": "This is a test sentence about contracts."}
    ]

    result = embed_chunks(chunks)

    assert len(result) == 1
    assert len(result[0]) == EMBEDDING_DIM
    assert all(isinstance(x, float) for x in result[0])


def test_embed_chunks_multiple_chunks_preserves_order_and_count():
    chunks = [
        {"chunk_text": "First chunk about termination clauses."},
        {"chunk_text": "Second chunk about payment terms."},
        {"chunk_text": "Third chunk about liability."},
    ]

    result = embed_chunks(chunks)

    assert len(result) == 3

    for embedding in result:
        assert len(embedding) == EMBEDDING_DIM


def test_embed_chunks_empty_list_returns_empty():
    assert embed_chunks([]) == []


def test_embed_chunks_raises_on_non_list_input():
    with pytest.raises(InvalidChunkInputError):
        embed_chunks("not a list")


def test_embed_chunks_raises_on_missing_chunk_text_key():
    with pytest.raises(InvalidChunkInputError):
        embed_chunks([{"wrong_key": "some text"}])


def test_embed_chunks_raises_on_empty_chunk_text():
    with pytest.raises(InvalidChunkInputError):
        embed_chunks([{"chunk_text": "   "}])


def test_embed_chunks_reuses_model_instance():
    embed_chunks([{"chunk_text": "warm up the model"}])
    model_after_first_call = embedder._model

    embed_chunks([{"chunk_text": "second call"}])
    model_after_second_call = embedder._model

    assert model_after_first_call is model_after_second_call


def test_embed_query_returns_correct_dimension():
    result = embed_query(
        "What are the termination clauses?"
    )

    assert isinstance(result, list)
    assert len(result) == EMBEDDING_DIM
    assert all(isinstance(x, float) for x in result)


def test_embed_query_raises_on_non_string_input():
    with pytest.raises(InvalidChunkInputError):
        embed_query(None)


def test_embed_query_raises_on_empty_query():
    with pytest.raises(InvalidChunkInputError):
        embed_query("")


def test_embed_query_raises_on_whitespace_query():
    with pytest.raises(InvalidChunkInputError):
        embed_query("   ")


def test_embed_query_strips_surrounding_whitespace():
    result_with_spaces = embed_query(
        "   What are the payment terms?   "
    )

    result_without_spaces = embed_query(
        "What are the payment terms?"
    )

    assert result_with_spaces == result_without_spaces


def test_embed_query_uses_query_prefix(monkeypatch):
    captured = {}

    class FakeEmbedding:
        def tolist(self):
            return [0.0] * EMBEDDING_DIM

    class FakeModel:
        def encode(self, text, show_progress_bar=False):
            captured["text"] = text
            return FakeEmbedding()

    monkeypatch.setattr(embedder, "_model", FakeModel())

    result = embed_query("What are the payment terms?")

    assert captured["text"] == (
        QUERY_PREFIX + "What are the payment terms?"
    )

    assert len(result) == EMBEDDING_DIM


def test_embed_query_reuses_model_instance():
    embed_query("first search query")
    model_after_first_call = embedder._model

    embed_query("second search query")
    model_after_second_call = embedder._model

    assert model_after_first_call is model_after_second_call