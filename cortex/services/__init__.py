"""Go gRPC service client and management for Cortex."""

from .client import CortexServiceClient
from .manager import ServiceManager

__all__ = ["CortexServiceClient", "ServiceManager"]
