import logging

from celery import shared_task
from django.core.files.storage import default_storage

from apps.documents.models import Document
from apps.documents.services.extractor import ExtractionError, extract_pages

logger = logging.getLogger(__name__)


@shared_task
def process_document(document_id):
    logger.info(f"process_document started for Document id={document_id}")

    try:
        document = Document.objects.get(id=document_id)
    except Document.DoesNotExist:
        logger.error(f"process_document: Document id={document_id} does not exist")
        return

    document.status = Document.ProcessingStatus.PROCESSING
    document.save(update_fields=["status"])

    # NOTE: .path() only works with local FileSystemStorage. Once switched
    # to R2 in production, this needs to read bytes via
    # default_storage.open(document.storage_path) and pass them to
    # extract_pages as a stream instead of a filesystem path.
    file_path = default_storage.path(document.storage_path)

    try:
        pages = extract_pages(file_path)
    except ExtractionError as exc:
        document.status = Document.ProcessingStatus.FAILED
        document.error_message = str(exc)
        document.save(update_fields=["status", "error_message"])
        logger.error(
            f"process_document: extraction failed for Document id={document_id}: {exc}"
        )
        return

    document.page_count = len(pages)
    document.save(update_fields=["page_count"])

    logger.info(
        f"process_document: extracted {len(pages)} pages for Document "
        f"id={document_id}. Chunking/embedding not yet implemented — "
        f"status remains PROCESSING until those stages exist."
    )

    # TODO: chunking + embedding stages go here once built.
    # Only once both are done should status become READY.