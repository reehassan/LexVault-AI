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

_model = None


class InvalidChunkInputError(Exception):
    """Raised when chunk input isn't in the expected shape."""
    pass


def _get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME, device="cpu")
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
            raise InvalidChunkInputError("chunk_text must be a non-empty string")
        texts.append(text)

    model = _get_model()
    embeddings = model.encode(texts, batch_size=32, show_progress_bar=False)

    return [embedding.tolist() for embedding in embeddings]