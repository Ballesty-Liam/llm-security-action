import hashlib
import json
from datetime import datetime

from .registry import AgentRegistry
from .fingerprinter import AgentFingerprinter
from .badge import AgentBadgeGenerator


class AgentVerifier:
    def __init__(self, options=None):
        self.options = {
            "registry_path": "./data/agent-registry.json",
            "badge_base_url": "https://agentproof.dev",
            "enable_cache": True,
        }
        if options:
            self.options.update(options)

        self.registry = AgentRegistry(storage_path=self.options["registry_path"])
        self.fingerprinter = None
        self.cache = {}

    async def verify_agent(self, repo_url, scan_results, github_context=None):
        github_context = github_context or {}
        try:
            print(f"Starting agent verification for: {repo_url}")

            cache_key = self.create_cache_key(repo_url, scan_results)
            if self.options["enable_cache"] and cache_key in self.cache:
                print("Returning cached verification result")
                return self.cache[cache_key]

            self.fingerprinter = AgentFingerprinter(scan_results)
            fingerprint = self.fingerprinter.generate_fingerprint()

            if not fingerprint or fingerprint.get("metadata", {}).get("error"):
                raise ValueError("Failed to generate valid fingerprint")

            consistency_result = await self.registry.verify_agent_consistency(fingerprint, repo_url)
            enriched_metadata = self.enrich_metadata(scan_results, github_context)

            if consistency_result["consistent"]:
                agent_record = await self.registry.update_agent(
                    consistency_result["agentId"], repo_url, fingerprint, enriched_metadata
                )
            else:
                agent_record = await self.registry.register_agent(
                    repo_url, fingerprint, enriched_metadata
                )

            badge_generator = AgentBadgeGenerator(agent_record, consistency_result, {
                "base_url": self.options["badge_base_url"]
            })
            badge = badge_generator.generate_badge()

            result = {
                "success": True,
                "agent": agent_record,
                "verification": consistency_result,
                "badge": badge,
                "fingerprint": {
                    "composite": fingerprint["composite"],
                    "generated": fingerprint["metadata"]["generated"]
                },
                "metadata": {
                    "verificationTime": datetime.utcnow().isoformat() + "Z",
                    "version": "1.0"
                }
            }

            if self.options["enable_cache"]:
                self.cache[cache_key] = result

            print(f"Agent verification completed successfully for: {repo_url}")
            return result

        except Exception as e:
            print("Agent verification failed:", e)
            return self.create_error_result(e, repo_url)

    def enrich_metadata(self, scan_results, github_context):
        return {
            "securityScore": scan_results.get("securityScore", 0.5),
            "securityIssuesFound": scan_results.get("issuesFound", 0),
            "hasSecurityUpdates": scan_results.get("hasSecurityUpdates", False),
            "hasTests": self.detect_tests(scan_results),
            "hasDocumentation": self.detect_documentation(scan_results),
            "hasLicense": self.detect_license(scan_results),
            "complexity": self.assess_complexity(scan_results),
            "githubStars": github_context.get("stargazers_count", 0),
            "githubForks": github_context.get("forks_count", 0),
            "githubWatchers": github_context.get("watchers_count", 0),
            "lastCommit": github_context.get("updated_at"),
            "repoSize": github_context.get("size", 0),
            "language": github_context.get("language", "unknown"),
            "isPublic": not github_context.get("private", True),
            "scannerVersion": "1.0",
            "verificationSource": "github_action"
        }

    def detect_tests(self, scan_results):
        files = scan_results.get("files", [])
        return any("test" in f["path"] or "spec" in f["path"] or "test(" in f.get("content", "") for f in files)

    def detect_documentation(self, scan_results):
        files = scan_results.get("files", [])
        return any(f["path"].lower().endswith(".md") or "readme" in f["path"].lower() or "doc" in f["path"].lower() for f in files)

    def detect_license(self, scan_results):
        files = scan_results.get("files", [])
        return any("license" in f["path"].lower() or "licence" in f["path"].lower() for f in files)

    def assess_complexity(self, scan_results):
        files = scan_results.get("files", [])
        total_lines = sum(len(f.get("content", "").splitlines()) for f in files)
        if total_lines < 500:
            return "low"
        elif total_lines < 2000:
            return "medium"
        else:
            return "high"

    def create_cache_key(self, repo_url, scan_results):
        files_json = json.dumps(scan_results.get("files", []), sort_keys=True)
        files_hash = hashlib.sha256(files_json.encode()).hexdigest()[:16]
        return json.dumps({"repoUrl": repo_url, "filesHash": files_hash})

    def create_error_result(self, error, repo_url):
        return {
            "success": False,
            "error": {
                "message": str(error),
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "repoUrl": repo_url
            },
            "agent": None,
            "verification": None,
            "badge": None,
            "fingerprint": None
        }

    async def get_agent_by_id(self, agent_id):
        return await self.registry.get_agent(agent_id)

    async def get_all_agents(self):
        return await self.registry.get_all_agents()

    def clear_cache(self):
        self.cache.clear()
