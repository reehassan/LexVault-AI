"""
PDF text extraction service.

Deliberately Django-free: no models, no settings, no ORM imports.
Takes a file path, returns plain data structures. This keeps it fast to
test (plain pytest, no test database) and reusable outside the Celery
task that will eventually call it.
"""

import fitz  # PyMuPDF


class ExtractionError(Exception):
    """
    Raised when a PDF cannot be extracted — encrypted or corrupted.

    A dedicated exception type (rather than a bare ValueError) lets
    callers catch extraction failures specifically, without accidentally
    swallowing unrelated bugs that happen to also raise ValueError.
    """
    pass


def extract_pages(file_path: str) -> list[dict]:
    """
    Extract text from a PDF, page by page.

    Returns a list of dicts, one per non-empty page:
        [{"page_number": 1, "text": "..."}, {"page_number": 2, "text": "..."}]

    Empty pages are silently skipped, not treated as errors — a blank
    page in a real document is normal, not a failure.

    Raises:
        ExtractionError: if the file is encrypted, or if it's corrupted /
            not a valid PDF at all.
    """
    try:
        doc = fitz.open(file_path)
    except Exception as exc:
        raise ExtractionError(
            f"Could not open PDF — file may be corrupted or invalid: {file_path}"
        ) from exc

    if doc.needs_pass:
        doc.close()
        raise ExtractionError(
            f"PDF is password-protected and cannot be processed: {file_path}"
        )

    pages = []
    for page_number in range(len(doc)):
        page = doc[page_number]
        text = page.get_text().strip()

        if not text:
            continue  # skip empty pages, do not error

        pages.append({"page_number": page_number + 1, "text": text})

    doc.close()
    return pages