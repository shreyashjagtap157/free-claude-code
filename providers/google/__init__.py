"""Google AI Studio (Gemini) provider exports."""

from providers.defaults import GOOGLE_DEFAULT_BASE

from .client import GoogleProvider

__all__ = [
    "GOOGLE_DEFAULT_BASE",
    "GoogleProvider",
]
