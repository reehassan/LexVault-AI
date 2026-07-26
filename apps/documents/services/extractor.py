# apps/documents/services/extractor.py
import fitz  # PyMuPDF


class ExtractionError(Exception):
    """Base exception for all extraction errors."""
    pass


class CorruptedPDFError(ExtractionError):
    """Raised when the PDF cannot be opened or parsed."""
    pass


class EncryptedPDFError(ExtractionError):
    """Raised when the PDF is password protected."""
    pass


class EmptyPDFError(ExtractionError):
    """Raised when no text could be extracted from any page."""
    pass


def extract_pages(path):
    """
    Extract text from each non-empty page of a PDF.

    Args:
        path (str): Path to the PDF file.

    Returns:
        list[dict]:
        [
            {"page": 1, "text": "..."},
            ...
        ]

    Raises:
        CorruptedPDFError
        EncryptedPDFError
        EmptyPDFError
    """
    try:
        document = fitz.open(path)
    except Exception as exc:
        raise CorruptedPDFError("Unable to open PDF.") from exc

    try:
        if document.is_encrypted:
            raise EncryptedPDFError("PDF is encrypted.")

        extracted_pages = []
        for page_number, page in enumerate(document, start=1):
            text = page.get_text().strip()
            if not text:
                continue
            extracted_pages.append({"page": page_number, "text": text})

        if not extracted_pages:
            raise EmptyPDFError("PDF contains no extractable text.")

        return extracted_pages
    finally:
        document.close()