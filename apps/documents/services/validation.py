from django.conf import settings

import magic


class InvalidFileTypeError(Exception):
    """Raised when the uploaded file is not a PDF."""
    pass


class FileTooLargeError(Exception):
    """Raised when the uploaded file exceeds the maximum allowed size."""
    pass


class EmptyFileError(Exception):
    """Raised when the uploaded file has zero bytes."""
    pass


def validate_document_file(file_obj):
    """
    Validate:
    - File is not empty
    - File size is within the allowed maximum
    - MIME type is really application/pdf

    Raises:
        EmptyFileError
        FileTooLargeError
        InvalidFileTypeError
    """
    max_size = settings.MAX_DOCUMENT_UPLOAD_SIZE

    if file_obj.size == 0:
        raise EmptyFileError("Uploaded file is empty.")

    if file_obj.size > max_size:
        raise FileTooLargeError(
            f"Maximum allowed file size is {max_size} bytes."
        )

    header = file_obj.read(2048)
    detected_mime = magic.from_buffer(header, mime=True)
    file_obj.seek(0)

    if detected_mime != "application/pdf":
        raise InvalidFileTypeError("Only PDF files are allowed.")
