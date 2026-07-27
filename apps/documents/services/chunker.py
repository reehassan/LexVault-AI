# apps/documents/services/chunker.py
import tiktoken


def chunk_pages(pages, chunk_size=350, overlap=50):
    """
    Split extracted PDF pages into overlapping token chunks.

    Pure function — no Django imports, no database access. Chunks
    never span page boundaries: each chunk belongs to exactly one
    page, so a chunk's page_number is always unambiguous for citation
    purposes.

    Args:
        pages (list[dict]):
            [{"page": 1, "text": "..."}] — output of extract_pages()
        chunk_size (int):
            Maximum tokens per chunk.
        overlap (int):
            Number of tokens shared between consecutive chunks.

    Returns:
        list[dict]:
            [
                {
                    "chunk_index": 0,
                    "page_number": 1,
                    "chunk_text": "...",
                    "token_count": 350,
                }
            ]

    Raises:
        ValueError: if overlap >= chunk_size, which would either loop
        forever or produce chunks that never advance.
    """
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    encoding = tiktoken.get_encoding("cl100k_base")
    chunks = []
    chunk_index = 0

    for page in pages:
        page_number = page["page"]
        text = page["text"]

        # Defensive: extract_pages() already filters blanks, but
        # chunk_pages() should be safe to call directly with
        # hand-built input too.
        if not text.strip():
            continue

        tokens = encoding.encode(text)
        start = 0

        while start < len(tokens):
            end = start + chunk_size
            chunk_tokens = tokens[start:end]
            chunk_text = encoding.decode(chunk_tokens)

            chunks.append(
                {
                    "chunk_index": chunk_index,
                    "page_number": page_number,
                    "chunk_text": chunk_text,
                    "token_count": len(chunk_tokens),
                }
            )
            chunk_index += 1

            if end >= len(tokens):
                break

            start += chunk_size - overlap

    return chunks