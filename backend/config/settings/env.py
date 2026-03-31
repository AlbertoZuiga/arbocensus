"""Environment helpers for Django settings modules."""

import os


def get_required_env(name: str) -> str:
    """Return an environment variable or fail fast with a clear error."""
    value = os.environ.get(name)
    if not value:
        raise ValueError(f"The {name} environment variable is not set.")
    return value
