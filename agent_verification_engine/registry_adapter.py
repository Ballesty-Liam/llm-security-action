import asyncio
from typing import Union


class RegistryAdapter:
    """
    Adapter to make synchronous registry work with async code
    """

    def __init__(self, registry):
        self.registry = registry
        self._is_async_registry = hasattr(registry, 'initialize') and asyncio.iscoroutinefunction(
            getattr(registry, 'initialize', None))

    async def verify_agent_consistency(self, fingerprint, current_repo):
        """Async wrapper for verify_agent_consistency"""
        if self._is_async_registry:
            return await self.registry.verify_agent_consistency(fingerprint, current_repo)
        else:
            # For sync registry, call directly
            return self.registry.verify_agent_consistency(fingerprint, current_repo)

    async def register_agent(self, repo_url, fingerprint, metadata=None):
        """Async wrapper for register_agent"""
        if self._is_async_registry:
            return await self.registry.register_agent(repo_url, fingerprint, metadata)
        else:
            return self.registry.register_agent(repo_url, fingerprint, metadata)

    async def update_agent(self, agent_id, repo_url, fingerprint, metadata=None):
        """Async wrapper for update_agent"""
        if self._is_async_registry:
            return await self.registry.update_agent(agent_id, repo_url, fingerprint, metadata)
        else:
            return self.registry.update_agent(agent_id, repo_url, fingerprint, metadata)

    async def get_agent(self, agent_id):
        """Async wrapper for get_agent"""
        if self._is_async_registry:
            return await self.registry.get_agent(agent_id)
        else:
            return self.registry.get_agent(agent_id)

    async def get_all_agents(self):
        """Async wrapper for get_all_agents"""
        if self._is_async_registry:
            return await self.registry.get_all_agents()
        else:
            return self.registry.get_all_agents()

    async def initialize(self):
        """Initialize the registry if it's async"""
        if self._is_async_registry and hasattr(self.registry, 'initialize'):
            await self.registry.initialize()

    def __getattr__(self, name):
        """Delegate any other method calls to the underlying registry"""
        return getattr(self.registry, name)