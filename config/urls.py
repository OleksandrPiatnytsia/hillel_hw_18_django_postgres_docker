from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from config.views import health

urlpatterns = [
    path("admin/", admin.site.urls),
    # 200 / 503: are PostgreSQL and Redis reachable (docker-compose healthcheck)
    path("health/", health, name="health"),
    # Login / logout / sign up: /accounts/login/, ... (namespace "users")
    path("accounts/", include("users.urls")),
    # Bookstore catalog lives at the site root; namespace "books" comes
    # from app_name in books/urls.py
    path("", include("books.urls")),
]

if settings.DEBUG:
    # Uploaded files (covers) in development. runserver serves static files
    # by itself, but not media. In production nginx / storage does this.
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.ENABLE_DEBUG_TOOLBAR:
    # Imported here: without requirements-dev.txt the package doesn't exist.
    # /__debug__/... — the toolbar loads its panels from these URLs.
    from debug_toolbar.toolbar import debug_toolbar_urls

    urlpatterns += debug_toolbar_urls()
