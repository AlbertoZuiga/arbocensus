"""Utilities to inspect and expose public API URL routes."""

from django.urls import URLPattern, URLResolver, get_resolver


def list_public_routes() -> list[str]:
    """Return every non-admin route registered in the project."""
    return _extract_public_patterns(get_resolver().url_patterns)


def _extract_public_patterns(
    patterns: list[URLPattern | URLResolver], prefix: str = ""
) -> list[str]:
    routes: list[str] = []

    for pattern in patterns:
        current = f"{prefix}{pattern.pattern}"
        if isinstance(pattern, URLResolver):
            routes.extend(_extract_public_patterns(pattern.url_patterns, current))
            continue

        current_path = str(current)
        if not current_path.startswith("admin/"):
            routes.append(current_path)

    return routes
