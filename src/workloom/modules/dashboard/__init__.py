"""Dashboard module for financial tracking."""

from workloom.modules.dashboard.config import dashboard_config
from workloom.modules.dashboard.service import DashboardService

__all__ = [
    "DashboardService",
    "dashboard_config",
]
