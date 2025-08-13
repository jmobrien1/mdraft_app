"""
Services package for mdraft.

This package contains service layer components that provide business logic
and external integrations for the mdraft application.
"""

from .storage import Storage

__all__ = ['Storage']
