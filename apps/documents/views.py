# apps/documents/views.py

import magic

from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.core.files.storage import default_storage

from apps.documents.models import Document
from apps.documents.tasks import process_document

ALLOWED_MIME_TYPES = ("application/pdf",)


@require_POST
def upload_document(request):
    uploaded_file = request.FILES.get("document")
    if not uploaded_file:
        return JsonResponse({"error": "Please upload a document."}, status=400)

    file_bytes = uploaded_file.read(2048)
    uploaded_file.seek(0)

    detected_mime = magic.from_buffer(file_bytes, mime=True)

    if detected_mime not in ALLOWED_MIME_TYPES:
        return JsonResponse(
            {"error": f"Invalid file type ({detected_mime}). Only PDF is allowed."},
            status=400,
        )
    
    saved_path = default_storage.save(
        f"firms/{request.user.firm.id}/docs/{uploaded_file.name}",
        uploaded_file,
    )

    document_row = Document.objects.create(
    firm=request.user.firm,
    uploaded_by=request.user,
    filename=uploaded_file.name,
    file_size_bytes=uploaded_file.size,
    storage_path=saved_path,
    status=Document.ProcessingStatus.UPLOADED,
    )

    process_document.delay(str(document_row.id))

    return JsonResponse(
        {
            "status": "success",
            "message": "Document uploaded successfully and queued for processing.",
            "document_id": str(document_row.id),
            "processing_status": document_row.status,
        },
        status=201,
    )