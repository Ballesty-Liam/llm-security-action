import json
import hashlib
import os
from datetime import datetime
from pathlib import Path


class AgentRegistry:
    def __init__(self, storage_path="./data/agent-registry.json", auto_save=True):
        self.storage_path = Path(storage_path)
        self.auto_save = auto_save
        self.registry = {}
        self.initialized = False

    async def initialize(self):
        if self.initialized:
            return
        try:
            await self.load_registry()
            self.initialized = True
        except Exception as e:
            print(f"Failed to load registry, starting fresh: {e}")
            self.registry = {}
            self.initialized = True

    async def register_agent(self, repo_url, fingerprint, metadata=None):
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

        return agent_record

    async def update_agent(self, agent_id, repo_url, fingerprint, metadata=None):
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

        return agent

    async def verify_agent_consistency(self, fingerprint, current_repo):
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
            return f"did:agentproof:{repo_hash}-{fingerprint_hash}"
        except Exception:
            random_id = os.urandom(8).hex()
            return f"did:agentproof:fallback-{random_id}"

    def calculate_initial_trust_score(self, fingerprint, metadata):
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
        metadata = metadata or {}
        try:
            base_score = agent.get("trustScore", 0.5)
            adjusted_score = base_score

            verification_bonus = min(0.2, agent["metadata"].get("verificationCount", 1) * 0.02)
            adjusted_score += verification_bonus

            cross_repo_bonus = min(0.15, (len(agent["repositories"]) - 1) * 0.05)
            adjusted_score += cross_repo_bonus

            days_since = self.get_days_since(agent["metadata"].get("lastVerified"))
            if days_since < 7:
                adjusted_score += 0.05

            if metadata.get("securityIssuesFound", 1) == 0:
                adjusted_score += 0.05
            if metadata.get("hasSecurityUpdates"):
                adjusted_score += 0.03

            return max(0.1, min(1.0, adjusted_score))
        except Exception as e:
            print("Trust score update error:", e)
            return agent.get("trustScore", 0.5)

    def get_days_since(self, date_str):
        try:
            dt = datetime.fromisoformat(date_str.replace("Z", ""))
            return (datetime.utcnow() - dt).days
        except Exception:
            return 999

    async def get_agent(self, agent_id):
        await self.initialize()
        return self.registry.get(agent_id)

    async def get_all_agents(self):
        await self.initialize()
        return list(self.registry.values())

    async def save_registry(self):
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            with self.storage_path.open("w", encoding="utf-8") as f:
                json.dump(self.registry, f, indent=2)
        except Exception as e:
            print(f"Failed to save registry: {e}")

    async def load_registry(self):
        try:
            if self.storage_path.exists():
                with self.storage_path.open("r", encoding="utf-8") as f:
                    self.registry = json.load(f)
        except Exception as e:
            print(f"Failed to load registry: {e}")
            self.registry = {}
