import logging
import os

import fitz
from celery import shared_task
from django.core.files.storage import default_storage
from django.db import transaction

from apps.documents.models import Chunk, Document
from apps.documents.services.chunker import chunk_pages
from apps.documents.services.embedder import embed_chunks
from apps.documents.services.extractor import (
    CorruptedPDFError,
    ExtractionError,
    extract_pages,
)


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

        logger.info("CELERY PATH: %s", path)
        logger.info(
            "CELERY FILE EXISTS: %s",
            os.path.exists(path)
        )
        logger.info(
            "CELERY STORAGE PATH: %s",
            document.storage_path
        )

        if not os.path.exists(path):
            raise CorruptedPDFError(
                f"File missing inside worker container: {path}"
            )

        try:
            with fitz.open(path) as pdf:
                total_pages = pdf.page_count

        except Exception as exc:
            raise CorruptedPDFError(
                f"Unable to open PDF: {path} | {exc}"
            ) from exc


        pages = extract_pages(path)

        chunks = chunk_pages(pages)

        if not chunks:
            raise EmptyDocumentError(
                "No chunks were produced from this document."
            )


        embeddings = embed_chunks(chunks)


        assert len(chunks) == len(embeddings), (
            f"chunk/embedding count mismatch: "
            f"{len(chunks)} vs {len(embeddings)}"
        )


        logger.info(
            "Document %s: pages=%s chunks=%s embeddings=%s",
            document_id,
            len(pages),
            len(chunks),
            len(embeddings),
        )


        chunk_objects = [
            Chunk(
                document=document,
                firm=document.firm,
                page_number=item["page_number"],
                chunk_index=item["chunk_index"],
                content=item["chunk_text"],
                token_count=item["token_count"],
                embedding=embedding,
            )
            for item, embedding in zip(chunks, embeddings)
        ]


        with transaction.atomic():

            Chunk.objects.bulk_create(chunk_objects)

            document.page_count = total_pages
            document.status = Document.ProcessingStatus.READY
            document.error_message = None

            document.save(
                update_fields=[
                    "page_count",
                    "status",
                    "error_message",
                    "updated_at",
                ]
            )


    except ExtractionError as exc:

        logger.warning(
            "Extraction failed for %s: %s",
            document_id,
            exc,
        )

        document.status = Document.ProcessingStatus.FAILED
        document.error_message = str(exc)

        document.save(
            update_fields=[
                "status",
                "error_message",
                "updated_at",
            ]
        )


    except EmptyDocumentError as exc:

        logger.warning(
            "Empty document %s: %s",
            document_id,
            exc,
        )

        document.status = Document.ProcessingStatus.FAILED
        document.error_message = str(exc)

        document.save(
            update_fields=[
                "status",
                "error_message",
                "updated_at",
            ]
        )


    except Exception as exc:

        logger.error(
            "Unexpected failure for %s: %s",
            document_id,
            exc,
            exc_info=True,
        )

        document.status = Document.ProcessingStatus.FAILED
        document.error_message = "Unexpected processing error."

        document.save(
            update_fields=[
                "status",
                "error_message",
                "updated_at",
            ]
        )