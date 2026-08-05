from django.db import transaction
from django.core.files.storage import default_storage

from apps.documents.models import Document
from apps.documents.services.storage import save_document_file
from apps.documents.tasks import process_document


def upload_document_file(
    *,
    file_obj,
    user,
):
    """
    Complete document upload workflow:

    1. Save file to storage
    2. Create Document record
    3. Queue Celery processing

    Returns:
        Document instance
    """

    with transaction.atomic():

        storage_path = save_document_file(
            file_obj=file_obj,
            firm_id=user.firm_id,
        )

        document = Document.objects.create(
            firm=user.firm,
            uploaded_by=user,
            filename=file_obj.name,
            file_size_bytes=file_obj.size,
            storage_path=storage_path,
            status=Document.ProcessingStatus.UPLOADED,
        )

        transaction.on_commit(
            lambda: process_document.delay(
                str(document.id)
            )
        )

    return document