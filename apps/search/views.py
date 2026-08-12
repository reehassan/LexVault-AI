# apps/search/views.py

from django.http import JsonResponse
from django.views.decorators.http import require_POST

from apps.search.services.search import (
    InvalidSearchQueryError,
    search_documents,
)


@require_POST
def search_documents_view(request):
    """
    Semantic document search endpoint.

    POST /search/

    Expected JSON:
        {
            "question": "What are the termination clauses?"
        }
    """

    if not request.user.is_authenticated:
        return JsonResponse(
            {
                "detail": "Authentication required."
            },
            status=401,
        )

    if request.user.firm_id is None:
        return JsonResponse(
            {
                "detail": "User is not associated with a firm."
            },
            status=403,
        )

    try:
        import json

        body = json.loads(request.body)

    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse(
            {
                "detail": "Request body must contain valid JSON."
            },
            status=400,
        )

    question = body.get("question")

    try:
        results = search_documents(
            question=question,
            firm_id=request.user.firm_id,
            top_k=5,
        )

    except InvalidSearchQueryError as exc:
        return JsonResponse(
            {
                "detail": str(exc)
            },
            status=400,
        )

    return JsonResponse(
        {
            "results": results,
            "count": len(results),
        },
        status=200,
    )