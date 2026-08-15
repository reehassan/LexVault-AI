from django.http import JsonResponse
from django.views.decorators.http import require_POST
from apps.documents.services.validation import (
    validate_document_file,
    EmptyFileError,
    FileTooLargeError,
    InvalidFileTypeError,
)
from apps.documents.services.uploader import upload_document_file


@require_POST
def upload_document(request):
    if not request.user.is_authenticated:
        return JsonResponse(
            {
                "error": "authentication_required",
                "detail": "Authentication required.",
            },
            status=401,
        )

    if "file" not in request.FILES:
        return JsonResponse(
            {
                "error": "validation_error",
                "detail": "No file uploaded.",
            },
            status=400,
        )

    file_obj = request.FILES["file"]

    try:
        validate_document_file(file_obj)
    except EmptyFileError:
        return JsonResponse(
            {
                "error": "validation_error",
                "detail": "Uploaded file is empty.",
            },
            status=400,
        )
    except FileTooLargeError:
        return JsonResponse(
            {
                "error": "file_too_large",
                "detail": "File exceeds maximum size.",
            },
            status=413,
        )
    except InvalidFileTypeError:
        return JsonResponse(
            {
                "error": "unsupported_file_type",
                "detail": "Only PDF files are allowed.",
            },
            status=422,
        )

    document = upload_document_file(
        file_obj=file_obj,
        user=request.user,
    )

    return JsonResponse(
        {
            "document_id": str(document.id),
            "filename": document.filename,
            "status": document.status,
            "created_at": document.created_at.isoformat(),
        },
        status=201,
    )