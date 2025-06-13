# agent_verification_engine/__init__.py

# Import main classes for external use
from .verifier import AgentVerifier
from .fingerprinter import AgentFingerprinter
from .registry import AgentRegistry
from .badge import AgentBadgeGenerator
from .registry_adapter import RegistryAdapter

# Make cache manager available if needed
try:
    from .cache_manager import CachedAgentRegistry, GitHubActionsCache
except ImportError:
    # Graceful fallback if cache dependencies aren't available
    CachedAgentRegistry = None
    GitHubActionsCache = None

__version__ = "1.0.0"
__all__ = [
    "AgentVerifier",
    "AgentFingerprinter",
    "AgentRegistry",
    "AgentBadgeGenerator",
    "RegistryAdapter",
    "CachedAgentRegistry",
    "GitHubActionsCache"
]