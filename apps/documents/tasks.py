import logging

import fitz
from celery import shared_task
from django.core.files.storage import default_storage
from django.db import transaction

from apps.documents.models import Chunk, Document
from apps.documents.services.chunker import chunk_pages
from apps.documents.services.embedder import embed_chunks
from apps.documents.services.extractor import CorruptedPDFError, ExtractionError, extract_pages

logger = logging.getLogger(__name__)


class EmptyDocumentError(Exception):
    """Raised when chunking produces zero chunks for a document."""
    pass


@shared_task
def process_document(document_id):
    document = Document.objects.get(id=document_id)
    document.status = Document.ProcessingStatus.PROCESSING
    document.save(update_fields=["status", "updated_at"])

    try:
        path = default_storage.path(document.storage_path)

        try:
            with fitz.open(path) as doc:
                total_pages = doc.page_count
        except Exception as exc:
            raise CorruptedPDFError("Unable to open PDF.") from exc

        pages = extract_pages(path)
        chunks = chunk_pages(pages)

        if not chunks:
            raise EmptyDocumentError(
                "No chunks were produced from this document."
            )

        embeddings = embed_chunks(chunks)

        # sanity check before writing anything to the DB
        assert len(chunks) == len(embeddings), (
            f"chunk/embedding count mismatch: {len(chunks)} vs {len(embeddings)}"
        )

        logger.info(
            "process_document: document_id=%s extracted %d pages, "
            "produced %d chunks, generated %d embeddings",
            document_id, len(pages), len(chunks), len(embeddings),
        )

        chunk_objects = [
            Chunk(
                document=document,
                firm=document.firm,
                page_number=c["page_number"],
                chunk_index=c["chunk_index"],
                content=c["chunk_text"],
                token_count=c["token_count"],
                embedding=embedding,
            )
            for c, embedding in zip(chunks, embeddings)
        ]

        with transaction.atomic():
            Chunk.objects.bulk_create(chunk_objects)
            document.page_count = total_pages
            document.status = Document.ProcessingStatus.READY
            document.save(update_fields=["page_count", "status", "updated_at"])

    except ExtractionError as exc:
        logger.warning(
            "process_document: document_id=%s failed with %s: %s",
            document_id, type(exc).__name__, exc,
        )
        document.status = Document.ProcessingStatus.FAILED
        document.error_message = str(exc)
        document.save(update_fields=["status", "error_message", "updated_at"])

    except EmptyDocumentError as exc:
        logger.warning(
            "process_document: document_id=%s produced no chunks: %s",
            document_id, exc,
        )
        document.status = Document.ProcessingStatus.FAILED
        document.error_message = str(exc)
        document.save(update_fields=["status", "error_message", "updated_at"])

    except Exception as exc:
        logger.error(
            "process_document: document_id=%s unexpected failure: %s",
            document_id, exc, exc_info=True,
        )
        document.status = Document.ProcessingStatus.FAILED
        document.error_message = "Unexpected processing error."
        document.save(update_fields=["status", "error_message", "updated_at"])