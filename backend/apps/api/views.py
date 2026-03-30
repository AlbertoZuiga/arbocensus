"""API views placeholder."""

from django.http import JsonResponse

from .services.route_discovery import list_public_routes


def api(_request):
    """API root endpoint."""
    payload = {
        "message": "Welcome to the ArboCensus API!",
        "available_routes": list_public_routes(),
    }
    return JsonResponse(payload)


def health(_request):
    """Health check endpoint."""
    return JsonResponse({"status": "ok"})
