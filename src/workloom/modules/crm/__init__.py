"""CRM module for managing Telegram customer profiles."""

from workloom.modules.crm.models import TelegramCustomer
from workloom.modules.crm.router import router
from workloom.modules.crm.service import CRMService

__all__ = ["CRMService", "TelegramCustomer", "router"]
