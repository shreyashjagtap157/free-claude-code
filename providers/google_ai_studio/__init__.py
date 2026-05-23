"""Google AI Studio (Gemini) provider package."""

from providers.defaults import GEMINI_DEFAULT_BASE

from .client import GoogleAIStudioProvider

__all__ = [
    "GEMINI_DEFAULT_BASE",
    "GoogleAIStudioProvider",
]
