import os
import json
import hashlib
import subprocess
import asyncio
from pathlib import Path
from datetime import datetime


class GitHubActionsCache:
    """
    Manages GitHub Actions cache for agent registry persistence
    """

    def __init__(self, cache_key_prefix="agent-registry"):
        self.cache_key_prefix = cache_key_prefix
        self.cache_dir = Path(os.getenv("GITHUB_WORKSPACE", ".")) / ".agent-cache"
        self.cache_dir.mkdir(exist_ok=True)

    def generate_cache_key(self, repo_url=None):
        """Generate a cache key for the agent registry"""
        if not repo_url:
            repo_url = os.getenv("GITHUB_REPOSITORY", "unknown")

        # Create a hash of repo for shorter cache key
        repo_hash = hashlib.sha256(repo_url.encode()).hexdigest()[:8]

        # Include date to allow cache rotation weekly
        week = datetime.now().strftime("%Y-W%W")

        return f"{self.cache_key_prefix}-{repo_hash}-{week}"

    async def restore_cache(self, registry_path):
        """Restore agent registry from GitHub Actions cache"""
        if not self._is_github_actions():
            print("ℹ️ Not in GitHub Actions, skipping cache restore")
            return False

        try:
            cache_key = self.generate_cache_key()
            cache_file = self.cache_dir / "registry.json"

            print(f"🔍 Attempting to restore cache with key: {cache_key}")

            # Simple file-based cache for now (GitHub CLI might not be available)
            # In a real implementation, you'd use actions/cache@v3
            if cache_file.exists():
                target_path = Path(registry_path)
                target_path.parent.mkdir(parents=True, exist_ok=True)

                with cache_file.open("r") as src, target_path.open("w") as dst:
                    dst.write(src.read())

                print(f"✅ Cache restored from: {cache_file}")
                return True

            print(f"ℹ️ No cache file found at: {cache_file}")
            return False

        except Exception as e:
            print(f"⚠️ Cache restore failed: {e}")
            return False

    async def save_cache(self, registry_path):
        """Save agent registry to GitHub Actions cache"""
        if not self._is_github_actions():
            print("ℹ️ Not in GitHub Actions, skipping cache save")
            return False

        try:
            source_path = Path(registry_path)
            if not source_path.exists():
                print("⚠️ No registry file to cache")
                return False

            cache_file = self.cache_dir / "registry.json"

            # Copy file to cache directory
            with source_path.open("r") as src, cache_file.open("w") as dst:
                dst.write(src.read())

            print(f"✅ Registry cached to: {cache_file}")
            return True

        except Exception as e:
            print(f"⚠️ Cache save failed: {e}")
            return False

    def _is_github_actions(self):
        """Check if running in GitHub Actions environment"""
        return bool(os.getenv("GITHUB_ACTIONS"))


class CachedAgentRegistry:
    """
    Agent Registry with GitHub Actions cache support
    """

    def __init__(self, storage_path="./data/agent-registry.json", auto_save=True):
        self.storage_path = Path(storage_path)
        self.auto_save = auto_save
        self.registry = {}
        self.initialized = False
        self.cache_manager = GitHubActionsCache()

    async def initialize(self):
        """Initialize registry with cache restore"""
        if self.initialized:
            return

        try:
            # Try to restore from cache first
            cache_restored = await self.cache_manager.restore_cache(self.storage_path)

            if not cache_restored:
                # Fall back to local file
                await self.load_registry()

            self.initialized = True
            print(f"📁 Registry initialized from {'cache' if cache_restored else 'local file'}")

        except Exception as e:
            print(f"Failed to initialize registry: {e}")
            self.registry = {}
            self.initialized = True

    async def save_registry(self):
        """Save registry to local file and cache"""
        try:
            # Save to local file first
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            with self.storage_path.open("w", encoding="utf-8") as f:
                json.dump(self.registry, f, indent=2)

            # Save to cache for next run
            await self.cache_manager.save_cache(self.storage_path)

        except Exception as e:
            print(f"Failed to save registry: {e}")

    async def load_registry(self):
        """Load registry from local file"""
        try:
            if self.storage_path.exists():
                with self.storage_path.open("r", encoding="utf-8") as f:
                    self.registry = json.load(f)
                print(f"📁 Loaded {len(self.registry)} agents from local registry")
            else:
                self.registry = {}
                print("📁 Starting with empty registry")
        except Exception as e:
            print(f"Failed to load registry: {e}")
            self.registry = {}

    async def register_agent(self, repo_url, fingerprint, metadata=None):
        """Register a new agent"""
        metadata = metadata or {}
        await self.initialize()

        agent_id = self.generate_agent_did(repo_url, fingerprint)
        existing = self.registry.get(agent_id)
        if existing:
            return await self.update_agent(agent_id, repo_url, fingerprint, metadata)

        agent_record = {
            "id": agent_id,
            "fingerprint": fingerprint["composite"],
            "fingerprintDetails": {
                "behavioral": fingerprint["behavioral"],
                "structural": fingerprint["structural"],
            },
            "repositories": [repo_url],
            "trustScore": self.calculate_initial_trust_score(fingerprint, metadata),
            "metadata": {
                "created": datetime.utcnow().isoformat() + "Z",
                "lastVerified": datetime.utcnow().isoformat() + "Z",
                "verificationCount": 1,
                "version": "1.0",
                **metadata
            },
        }

        self.registry[agent_id] = agent_record
        if self.auto_save:
            await self.save_registry()

        print(f"🆕 Registered new agent: {agent_id}")
        return agent_record

    async def update_agent(self, agent_id, repo_url, fingerprint, metadata=None):
        """Update existing agent"""
        metadata = metadata or {}
        agent = self.registry.get(agent_id)
        if not agent:
            raise ValueError(f"Agent {agent_id} not found")

        if repo_url not in agent["repositories"]:
            agent["repositories"].append(repo_url)

        agent["metadata"]["lastVerified"] = datetime.utcnow().isoformat() + "Z"
        agent["metadata"]["verificationCount"] = agent["metadata"].get("verificationCount", 0) + 1
        agent["trustScore"] = self.update_trust_score(agent, metadata)
        agent["metadata"].update(metadata)

        self.registry[agent_id] = agent
        if self.auto_save:
            await self.save_registry()

        print(f"🔄 Updated agent: {agent_id}")
        return agent

    async def verify_agent_consistency(self, fingerprint, current_repo):
        """Verify agent consistency across repositories"""
        await self.initialize()
        for agent in self.registry.values():
            if agent["fingerprint"] == fingerprint["composite"]:
                return {
                    "consistent": True,
                    "agentId": agent["id"],
                    "trustScore": agent["trustScore"],
                    "repositories": agent["repositories"],
                    "crossRepoCount": len(agent["repositories"]),
                    "verificationHistory": agent["metadata"].get("verificationCount", 1)
                }

        return {
            "consistent": False,
            "agentId": None,
            "trustScore": 0,
            "repositories": [],
            "crossRepoCount": 0,
            "verificationHistory": 0
        }

    def generate_agent_did(self, repo_url, fingerprint):
        try:
            repo_hash = hashlib.sha256(repo_url.encode()).hexdigest()[:12]
            fingerprint_hash = fingerprint["composite"][:12]
            return f"agentproof:{repo_hash}-{fingerprint_hash}"  # Remove "did:" prefix FOR NOW
        except Exception:
            random_id = os.urandom(8).hex()
            return f"agentproof:fallback-{random_id}"  # Remove "did:" prefix FOR NOW

    def calculate_initial_trust_score(self, fingerprint, metadata):
        """Calculate initial trust score for new agent"""
        score = 0.5
        try:
            if metadata.get("securityScore", 0) > 0.8:
                score += 0.2
            if metadata.get("hasTests"):
                score += 0.1
            if metadata.get("hasDocumentation"):
                score += 0.1
            if metadata.get("hasLicense"):
                score += 0.05
            if metadata.get("complexity") == "low":
                score += 0.05
            elif metadata.get("complexity") == "high":
                score -= 0.05
            if metadata.get("githubStars", 0) > 10:
                score += min(0.1, metadata["githubStars"] / 1000)
            return max(0.1, min(1.0, score))
        except Exception as e:
            print("Trust score calculation error:", e)
            return 0.5

    def update_trust_score(self, agent, metadata=None):
        """Update trust score for existing agent"""
        metadata = metadata or {}
        try:
            base_score = agent.get("trustScore", 0.5)
            adjusted_score = base_score

            # Verification history bonus
            verification_bonus = min(0.2, agent["metadata"].get("verificationCount", 1) * 0.02)
            adjusted_score += verification_bonus

            # Cross-repository consistency bonus
            cross_repo_bonus = min(0.15, (len(agent["repositories"]) - 1) * 0.05)
            adjusted_score += cross_repo_bonus

            # Recent verification bonus
            days_since = self.get_days_since(agent["metadata"].get("lastVerified"))
            if days_since < 7:
                adjusted_score += 0.05

            # Security status bonuses
            if metadata.get("securityIssuesFound", 1) == 0:
                adjusted_score += 0.05
            if metadata.get("hasSecurityUpdates"):
                adjusted_score += 0.03

            return max(0.1, min(1.0, adjusted_score))
        except Exception as e:
            print("Trust score update error:", e)
            return agent.get("trustScore", 0.5)

    def get_days_since(self, date_str):
        """Calculate days since a given date"""
        try:
            dt = datetime.fromisoformat(date_str.replace("Z", ""))
            return (datetime.utcnow() - dt).days
        except Exception:
            return 999

    async def get_agent(self, agent_id):
        """Get agent by ID"""
        await self.initialize()
        return self.registry.get(agent_id)

    async def get_all_agents(self):
        """Get all agents"""
        await self.initialize()
        return list(self.registry.values())