"""PII anonymization web demo package."""

from .app import anonymization_bp, create_anonymization_app

__all__ = ["anonymization_bp", "create_anonymization_app"]
