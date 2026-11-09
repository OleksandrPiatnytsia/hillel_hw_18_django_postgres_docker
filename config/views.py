"""Project-level views that don't belong to the books or users apps."""

import logging
import uuid

from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

logger = logging.getLogger(__name__)  # "config.views"


def check_database():
    """Run the simplest possible query: proves PostgreSQL accepts queries."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        cursor.fetchone()


def check_cache():
    """Write a value to the cache (Redis) and read it back.

    A random value, so an old value left by another request (another
    gunicorn worker) can't make a broken cache look working.
    """
    value = uuid.uuid4().hex
    cache.set("health_check", value, timeout=10)
    if cache.get("health_check") != value:
        raise RuntimeError("the value read back differs from the value written")


CHECKS = {
    "database": check_database,
    "cache": check_cache,
}


@never_cache  # Cache-Control: no-cache..., so no proxy or browser keeps an old answer
@require_GET  # other methods -> 405
def health(request):
    """GET /health/ - is the app able to work right now?

    Used by the healthcheck of the web service in docker-compose.yml (and
    could be used by a load balancer or monitoring). Checks the services
    the app can't work without: PostgreSQL and Redis.

    200 {"status": "ok", "database": "ok", "cache": "ok"}
    503 {"status": "error", "database": "ok", "cache": "error"}

    503 Service Unavailable, not 500: the app itself works, a service it
    depends on doesn't. No login needed, so no session is read: the check
    works even when the session storage (Redis) is down.
    The error details go only to the log, not to the response: the URL is
    public, and an error message may reveal host names or settings.
    """
    results = {}
    for name, check in CHECKS.items():
        try:
            check()
        except Exception:
            # Any error counts: connection refused, timeout, wrong password...
            # logger.exception = ERROR level + the traceback
            logger.exception("Health check failed: %s", name)
            results[name] = "error"
        else:
            results[name] = "ok"

    healthy = all(result == "ok" for result in results.values())
    return JsonResponse(
        {"status": "ok" if healthy else "error", **results},
        status=200 if healthy else 503,
    )
