"""Production-grade admin dashboard for AI call operations."""

from api.services.admin_operations.service import (
    AdminOperationsService,
    get_admin_operations_service,
)

__all__ = ["AdminOperationsService", "get_admin_operations_service"]
