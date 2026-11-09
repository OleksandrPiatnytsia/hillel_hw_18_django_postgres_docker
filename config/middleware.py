import logging
import time

from django.conf import settings

logger = logging.getLogger(__name__)  # "config.middleware"


class RequestTimingMiddleware:
    """Measures how long each request takes, logs it and returns it in headers.

    Log line:  GET /authors/?page=2 200 12.3ms user=ann
    Headers:   X-Request-Duration: 12.3ms
               Server-Timing: app;dur=12.3   (shown in DevTools -> Network -> Timing)

    Placed FIRST in MIDDLEWARE, so the measured time includes all other
    middleware (sessions, auth, CSRF, ...) plus the view and the template.
    It can still log the user: AuthenticationMiddleware, further down the
    chain, sets request.user on the same request object, so it is there by
    the time get_response() returns.
    """

    # Requests that are not worth a log line (the header is still added):
    # the toolbar's own AJAX calls, book covers (up to 10 per catalog page)
    # and /health/ (Docker calls it every few seconds; a failed check is
    # logged by the health view itself, with the reason)
    SKIP_LOG_PREFIXES = (
        "/__debug__/",
        "/" + settings.MEDIA_URL.lstrip("/"),
        "/health/",
    )

    def __init__(self, get_response):
        # Called ONCE, when the server starts. get_response is the next
        # middleware in the chain (or the view itself for the last one).
        self.get_response = get_response
        # Slower requests are logged as WARNING instead of INFO
        self.slow_ms = getattr(settings, "REQUEST_SLOW_MS", 500)

    def __call__(self, request):
        # Called for EVERY request.
        # perf_counter(): a monotonic high-resolution clock for measuring
        # intervals (time.time() can jump when the system clock is adjusted)
        start = time.perf_counter()

        # ---- everything before this line runs on the way IN ----
        response = self.get_response(request)
        # ---- everything after it runs on the way OUT ----

        duration_ms = (time.perf_counter() - start) * 1000
        response["X-Request-Duration"] = f"{duration_ms:.1f}ms"
        response["Server-Timing"] = f"app;dur={duration_ms:.1f}"

        if not request.path.startswith(self.SKIP_LOG_PREFIXES):
            level = logging.WARNING if duration_ms >= self.slow_ms else logging.INFO
            logger.log(
                level,
                "%s %s %s %.1fms user=%s",
                request.method,
                request.get_full_path(),  # path + query string (?page=2)
                response.status_code,
                duration_ms,
                self.get_username(request),
            )
        return response

    @staticmethod
    def get_username(request):
        # request.user may be missing if a middleware above AuthenticationMiddleware
        # returned a response early (e.g. SecurityMiddleware's HTTPS redirect)
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            return "anonymous"
        return user.username
