"""Kenyan continuous learning pipeline."""

from api.services.kenyan_continuous_learning.service import (
    KenyanContinuousLearningService,
    get_kenyan_continuous_learning_service,
)

__all__ = ["KenyanContinuousLearningService", "get_kenyan_continuous_learning_service"]
