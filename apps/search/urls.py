from django.urls import path

from . import views


urlpatterns = [
    path(
        "",
        views.search_documents_view,
        name="search_documents",
    ),
]