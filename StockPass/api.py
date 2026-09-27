import logging

from django.conf import settings
from django.http import Http404, JsonResponse
from ninja import NinjaAPI
from ninja.errors import HttpError, ValidationError

from StockPassCore.api.auth import router as auth_router
from StockPassCore.api.users import router as users_router
from SalesAndTransport.api.master import router as master_router
from SalesAndTransport.api.order import router as order_router
from SalesAndTransport.api.transport import router as transport_router
from SalesAndTransport.api.bulk_transport import router as bulk_transport_router
from SalesAndTransport.api.dashboard import router as dashboard_router


api = NinjaAPI(
    title="StockPass API",
    version="1.0.0",
)


logger = logging.getLogger("ninja")


@api.exception_handler(Exception)
@api.exception_handler(Http404)
@api.exception_handler(ValidationError)
@api.exception_handler(HttpError)
def handle_api_exception(request, exc):
    if isinstance(exc, HttpError):
        status = exc.status_code
        error = str(exc)
    elif isinstance(exc, ValidationError):
        status = 422
        error = "; ".join(
            f"{'.'.join(str(part) for part in item.get('loc', ())) }: {item.get('msg', 'Invalid value')}"
            for item in exc.errors
        )
    elif isinstance(exc, Http404):
        status = 404
        error = "Not found."
    else:
        status = 500
        logger.exception("Unhandled API exception")
        error = str(exc) if settings.DEBUG else "An unexpected error occurred."

    return JsonResponse({"error": error}, status=status)


api.add_router("/auth/", auth_router)
api.add_router("/users/", users_router)
api.add_router("/master/", master_router)
api.add_router("/orders/", order_router)
api.add_router("/transports/", transport_router)
api.add_router("/bulk-transports/", bulk_transport_router)
api.add_router("/dashboard/", dashboard_router)

