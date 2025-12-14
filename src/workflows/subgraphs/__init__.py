"""
Система динамических подграфов для переиспользования компонентов workflow.
"""

from .registry import SubgraphRegistry, get_registry
from .base import BaseSubgraph
from .common import *

__all__ = [
    "SubgraphRegistry",
    "BaseSubgraph", 
    "get_registry",
    "CodeAnalysisSubgraph",
    "TestingSubgraph", 
    "DeploymentSubgraph",
    "SecurityReviewSubgraph"
]
