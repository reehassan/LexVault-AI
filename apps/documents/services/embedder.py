# apps/documents/services/embedder.py

"""
Local sentence-embedding service using bge-small-en-v1.5.

Model loads once per process (lazy singleton) and is reused across
calls — reloading a transformer model on every call would be slow and
pointless. No Django imports; pure service, same design as extractor
and chunker.
"""

from sentence_transformers import SentenceTransformer


MODEL_NAME = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIM = 384

QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

_model = None


class InvalidChunkInputError(Exception):
    """Raised when embedding input isn't in the expected shape."""

    pass


def _get_model():
    global _model

    if _model is None:
        _model = SentenceTransformer(
            MODEL_NAME,
            device="cpu",
        )

    return _model


def embed_chunks(chunks):
    """
    Generate embeddings for a list of chunk dicts (as produced by
    chunk_pages()).

    Args:
        chunks (list[dict]): each dict must have a "chunk_text" key
            with a non-empty string value.

    Returns:
        list[list[float]]: one 384-dim embedding per chunk, same
        order as the input.

    Raises:
        InvalidChunkInputError: if chunks isn't a list, or any entry
        isn't a dict with a valid "chunk_text".
    """
    if not isinstance(chunks, list):
        raise InvalidChunkInputError("chunks must be a list")

    if not chunks:
        return []

    texts = []

    for chunk in chunks:
        if not isinstance(chunk, dict) or "chunk_text" not in chunk:
            raise InvalidChunkInputError(
                "each chunk must be a dict with a 'chunk_text' key"
            )

        text = chunk["chunk_text"]

        if not isinstance(text, str) or not text.strip():
            raise InvalidChunkInputError(
                "chunk_text must be a non-empty string"
            )

        texts.append(text)

    model = _get_model()

    embeddings = model.encode(
        texts,
        batch_size=32,
        show_progress_bar=False,
    )

    return [embedding.tolist() for embedding in embeddings]


def embed_query(query_text):
    """
    Generate an embedding for a search query.

    The BGE model uses a retrieval-specific instruction for queries.
    Document chunk embeddings remain unchanged.

    Args:
        query_text (str): non-empty search query.

    Returns:
        list[float]: one 384-dimensional embedding.

    Raises:
        InvalidChunkInputError: if query_text is not a non-empty string.
    """
    if not isinstance(query_text, str):
        raise InvalidChunkInputError(
            "query_text must be a string"
        )

    if not query_text.strip():
        raise InvalidChunkInputError(
            "query_text must be a non-empty string"
        )

    query = QUERY_PREFIX + query_text.strip()

    model = _get_model()

    embedding = model.encode(
        query,
        show_progress_bar=False,
    )

    return embedding.tolist()