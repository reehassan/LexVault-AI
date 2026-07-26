import fitz
import pytest

from apps.documents.services.extractor import (
    extract_pages,
    CorruptedPDFError,
    EncryptedPDFError,
    EmptyPDFError,
)


def make_valid_pdf(path, pages_with_text):
    """
    Create a real PDF at `path` with one page per entry in
    `pages_with_text`. Empty string means a genuinely blank page.
    """
    doc = fitz.open()
    for text in pages_with_text:
        page = doc.new_page()
        if text:
            page.insert_text((50, 50), text)
    doc.save(str(path))
    doc.close()


def make_encrypted_pdf(path):
    doc = fitz.open()
    doc.new_page()
    doc.save(
        str(path),
        encryption=fitz.PDF_ENCRYPT_AES_256,
        owner_pw="ownerpass",
        user_pw="userpass",
    )
    doc.close()


def make_corrupted_pdf(path):
    path.write_bytes(b"%PDF-1.4\nthis is not a real pdf body, just garbage")


def test_extract_pages_returns_correct_count_and_text(tmp_path):
    pdf_path = tmp_path / "valid.pdf"
    make_valid_pdf(pdf_path, ["Hello page one", "Hello page two"])

    result = extract_pages(str(pdf_path))

    assert len(result) == 2
    assert result[0]["page"] == 1
    assert "Hello page one" in result[0]["text"]
    assert result[1]["page"] == 2
    assert "Hello page two" in result[1]["text"]


def test_extract_pages_skips_blank_pages_without_error(tmp_path):
    pdf_path = tmp_path / "mixed.pdf"
    make_valid_pdf(pdf_path, ["Real content here", "", ""])

    result = extract_pages(str(pdf_path))

    assert len(result) == 1
    assert result[0]["page"] == 1
    assert "Real content here" in result[0]["text"]


def test_extract_pages_raises_empty_pdf_error_when_all_pages_blank(tmp_path):
    pdf_path = tmp_path / "blank.pdf"
    make_valid_pdf(pdf_path, ["", "", ""])

    with pytest.raises(EmptyPDFError):
        extract_pages(str(pdf_path))


def test_extract_pages_raises_encrypted_pdf_error(tmp_path):
    pdf_path = tmp_path / "encrypted.pdf"
    make_encrypted_pdf(pdf_path)

    with pytest.raises(EncryptedPDFError):
        extract_pages(str(pdf_path))


def test_extract_pages_raises_corrupted_pdf_error(tmp_path):
    pdf_path = tmp_path / "corrupted.pdf"
    make_corrupted_pdf(pdf_path)

    with pytest.raises(CorruptedPDFError):
        extract_pages(str(pdf_path))


def test_extract_pages_raises_corrupted_pdf_error_for_nonexistent_file(tmp_path):
    missing_path = tmp_path / "does_not_exist.pdf"

    with pytest.raises(CorruptedPDFError):
        extract_pages(str(missing_path))


def test_extract_pages_preserves_page_numbers_across_blank_gaps(tmp_path):
    pdf_path = tmp_path / "gaps.pdf"
    make_valid_pdf(pdf_path, ["First", "", "Third"])

    result = extract_pages(str(pdf_path))

    assert len(result) == 2
    assert result[0]["page"] == 1
    assert result[1]["page"] == 3
