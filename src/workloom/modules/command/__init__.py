"""Command-based modules for WORKLOOM.

Command modules use Function Calling to parse user intent
and execute actions on PostgreSQL.
"""

from workloom.modules.command.base import BaseCommandService

__all__ = ["BaseCommandService"]
