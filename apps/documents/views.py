from django.http import JsonResponse
from django.views.decorators.http import require_POST

from apps.documents.models import Document
from apps.documents.services.storage import save_document_file
from apps.documents.services.validation import (
    validate_document_file,
    EmptyFileError,
    FileTooLargeError,
    InvalidFileTypeError,
)
from apps.documents.tasks import process_document


@require_POST
def upload_document(request):
    if not request.user.is_authenticated:
        return JsonResponse(
            {"detail": "Authentication required."},
            status=401,
        )

    if "file" not in request.FILES:
        return JsonResponse(
            {"detail": "No file uploaded."},
            status=400,
        )

    file_obj = request.FILES["file"]

    try:
        validate_document_file(file_obj)

    except EmptyFileError:
        return JsonResponse(
            {"detail": "Uploaded file is empty."},
            status=400,
        )

    except FileTooLargeError:
        return JsonResponse(
            {"detail": "File exceeds maximum size."},
            status=413,
        )

    except InvalidFileTypeError:
        return JsonResponse(
            {"detail": "Only PDF files are allowed."},
            status=422,
        )

    storage_path = save_document_file(
        file_obj=file_obj,
        firm_id=request.user.firm_id,
    )

    document = Document.objects.create(
        firm=request.user.firm,
        uploaded_by=request.user,
        filename=file_obj.name,
        file_size_bytes=file_obj.size,
        storage_path=storage_path,
        status=Document.ProcessingStatus.UPLOADED,
    )

    process_document.delay(str(document.id))

    return JsonResponse(
        {
            "document_id": str(document.id),
            "filename": document.filename,
            "status": document.status,
            "created_at": document.created_at.isoformat(),
        },
        status=201,
    )