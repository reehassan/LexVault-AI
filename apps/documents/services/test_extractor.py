"""
Plain pytest tests for the extraction service.

No @pytest.mark.django_db, no Django settings needed — proves this
module truly has no Django dependency, per its own design goal.
"""

import fitz
import pytest

from apps.documents.services.extractor import ExtractionError, extract_pages


def make_pdf(tmp_path, pages_text: list[str], filename: str = "test.pdf") -> str:
    """
    Build a real PDF on disk with one page per string in pages_text.
    Returns the file path as a string, matching extract_pages' signature.
    """
    doc = fitz.open()
    for text in pages_text:
        page = doc.new_page()
        if text:
            page.insert_text((72, 72), text)
    path = tmp_path / filename
    doc.save(str(path))
    doc.close()
    return str(path)


def test_extract_pages_returns_correct_count_and_page_numbers(tmp_path):
    pdf_path = make_pdf(
        tmp_path,
        ["First page content", "Second page content", "Third page content"],
    )

    result = extract_pages(pdf_path)

    assert len(result) == 3
    assert [p["page_number"] for p in result] == [1, 2, 3]


def test_extract_pages_returns_correct_text_per_page(tmp_path):
    pdf_path = make_pdf(tmp_path, ["Alpha content", "Beta content"])

    result = extract_pages(pdf_path)

    assert "Alpha" in result[0]["text"]
    assert "Beta" in result[1]["text"]


def test_extract_pages_skips_empty_pages_without_error(tmp_path):
    pdf_path = make_pdf(tmp_path, ["Real content here", "", "More real content"])

    result = extract_pages(pdf_path)

    # Only the two non-empty pages should be returned — empty page skipped,
    # not present as an empty-string entry and not raising an error.
    assert len(result) == 2
    assert result[0]["page_number"] == 1
    assert result[1]["page_number"] == 3  # original page 2 was skipped


def test_extract_pages_raises_extraction_error_for_corrupted_file(tmp_path):
    bad_path = tmp_path / "corrupted.pdf"
    bad_path.write_bytes(b"this is not a real pdf, just garbage bytes")

    with pytest.raises(ExtractionError, match="corrupted or invalid"):
        extract_pages(str(bad_path))


def test_extract_pages_raises_extraction_error_for_encrypted_pdf(tmp_path):
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Secret content")

    encrypted_path = tmp_path / "encrypted.pdf"
    doc.save(
        str(encrypted_path),
        encryption=fitz.PDF_ENCRYPT_AES_256,
        owner_pw="ownerpass",
        user_pw="userpass",
    )
    doc.close()

    with pytest.raises(ExtractionError, match="password-protected"):
        extract_pages(str(encrypted_path))


def test_extract_pages_raises_extraction_error_for_nonexistent_file():
    with pytest.raises(ExtractionError, match="corrupted or invalid"):
        extract_pages("/path/does/not/exist.pdf")