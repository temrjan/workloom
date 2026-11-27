"""Department modules for WORKLOOM.

This package contains module configurations and services for each department.
Modules are divided into two types:

- Command-based (Dashboard): Use Function Calling to execute actions
- RAG-based (CallCenter, Marketing, HR): Use knowledge retrieval for answers

Usage:
    >>> from workloom.modules import module_registry, ModuleType
    >>> from workloom.modules.command.dashboard import DashboardConfig
    >>>
    >>> # Register module at startup
    >>> module_registry.register(DashboardConfig())
    >>>
    >>> # Get module by department_id
    >>> config = module_registry.get("dashboard")
"""

from workloom.modules.base import (
    BaseModuleConfig,
    CommandModuleConfig,
    ModuleType,
    RAGModuleConfig,
)
from workloom.modules.registry import ModuleRegistry, module_registry

__all__ = [
    "BaseModuleConfig",
    "CommandModuleConfig",
    "ModuleRegistry",
    "ModuleType",
    "RAGModuleConfig",
    "module_registry",
]
