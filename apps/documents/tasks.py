from celery import shared_task

from apps.documents.models import Document


@shared_task
def process_document(document_id):
    """
    Day 14 stub.

    Real pipeline (Days 15–17):

    Extract
    -> Chunk
    -> Embed
    -> Store
    """

    document = Document.objects.get(
        id=document_id,
    )

    document.status = (
        Document.ProcessingStatus.PROCESSING
    )

    document.save(
        update_fields=["status"],
    )