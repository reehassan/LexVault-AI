import uuid
from django.core.files.storage import default_storage


def save_document_file(file_obj, firm_id):
    """
    Save the uploaded file using django-storages.

    The stored filename is fully server-generated — the client's
    original filename never touches disk I/O. This is deliberate:
    validate_document_file() already confirmed the file is really a
    PDF via MIME sniffing, so ".pdf" here reflects a verified fact,
    not a client claim.

    Returns:
        storage path (string)
    """
    filename = f"firms/{firm_id}/{uuid.uuid4()}.pdf"
    storage_path = default_storage.save(filename, file_obj)
    return storage_path
