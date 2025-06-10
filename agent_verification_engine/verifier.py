import hashlib
import json
from datetime import datetime
from pathlib import Path

from fingerprinter import AgentFingerprinter
from badge import AgentBadgeGenerator
from github_actions_cache import CachedAgentRegistry


class AgentVerifier:
    def __init__(self, options=None):
        self.options = {
            "registry_path": "./data/agent-registry.json",
            "badge_base_url": "https://agentproof.dev",
            "enable_cache": True,
        }
        if options:
            self.options.update(options)

        # Import CachedAgentRegistry here to avoid circular imports
        self.registry = CachedAgentRegistry(
            storage_path=self.options["registry_path"],
            auto_save=True
        )
        self.fingerprinter = None
        self.cache = {}

    async def verify_agent(self, repo_url, scan_results, github_context=None):
        github_context = github_context or {}
        try:
            print(f"🔍 Starting agent verification for: {repo_url}")

            cache_key = self.create_cache_key(repo_url, scan_results)
            if self.options["enable_cache"] and cache_key in self.cache:
                print("💾 Returning cached verification result")
                return self.cache[cache_key]

            self.fingerprinter = AgentFingerprinter(scan_results)
            fingerprint = self.fingerprinter.generate_fingerprint()

            if not fingerprint or fingerprint.get("metadata", {}).get("error"):
                raise ValueError("Failed to generate valid fingerprint")

            print(f"🔑 Generated fingerprint: {fingerprint['composite'][:16]}...")

            consistency_result = await self.registry.verify_agent_consistency(fingerprint, repo_url)
            enriched_metadata = self.enrich_metadata(scan_results, github_context)

            if consistency_result["consistent"]:
                print(f"🔄 Updating existing agent: {consistency_result['agentId']}")
                agent_record = await self.registry.update_agent(
                    consistency_result["agentId"], repo_url, fingerprint, enriched_metadata
                )
            else:
                print("🆕 Registering new agent")
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

            print(f"✅ Agent verification completed successfully")
            print(f"   Agent ID: {agent_record['id']}")
            print(f"   Trust Score: {agent_record['trustScore']:.2f}")
            print(f"   Repositories: {len(agent_record['repositories'])}")

            return result

        except Exception as e:
            print(f"❌ Agent verification failed: {e}")
            return self.create_error_result(e, repo_url)

    def enrich_metadata(self, scan_results, github_context):
        """Enrich metadata with graceful degradation for missing fields"""
        # Basic security metrics from scan results
        metadata = {
            "securityScore": scan_results.get("securityScore", 0.5),
            "securityIssuesFound": scan_results.get("issuesFound", 0),
            "hasSecurityUpdates": scan_results.get("hasSecurityUpdates", False),
            "scannerVersion": "1.0",
            "verificationSource": "github_action"
        }

        # File analysis with graceful degradation
        try:
            metadata.update({
                "hasTests": self.detect_tests(scan_results),
                "hasDocumentation": self.detect_documentation(scan_results),
                "hasLicense": self.detect_license(scan_results),
                "complexity": self.assess_complexity(scan_results),
            })
        except Exception as e:
            print(f"⚠️ File analysis failed, using defaults: {e}")
            metadata.update({
                "hasTests": False,
                "hasDocumentation": False,
                "hasLicense": False,
                "complexity": "medium",
            })

        # GitHub context with graceful degradation
        try:
            metadata.update({
                "githubStars": github_context.get("stargazers_count", 0),
                "githubForks": github_context.get("forks_count", 0),
                "githubWatchers": github_context.get("watchers_count", 0),
                "lastCommit": github_context.get("updated_at", ""),
                "repoSize": github_context.get("size", 0),
                "language": github_context.get("language", "unknown"),
                "isPublic": not github_context.get("private", True),
                "repository": github_context.get("repository", ""),
                "sha": github_context.get("sha", ""),
                "ref": github_context.get("ref", ""),
                "workflow": github_context.get("workflow", ""),
                "run_id": github_context.get("run_id", ""),
                "run_number": github_context.get("run_number", "")
            })
        except Exception as e:
            print(f"⚠️ GitHub context enrichment failed: {e}")

        return metadata

    def detect_tests(self, scan_results):
        """Detect if repository has tests"""
        try:
            files = scan_results.get("files", [])
            return any(
                "test" in f.get("path", "").lower() or
                "spec" in f.get("path", "").lower() or
                "test(" in f.get("content", "") or
                "describe(" in f.get("content", "") or
                "unittest" in f.get("content", "") or
                "pytest" in f.get("content", "")
                for f in files
            )
        except Exception:
            return False

    def detect_documentation(self, scan_results):
        """Detect if repository has documentation"""
        try:
            files = scan_results.get("files", [])
            return any(
                f.get("path", "").lower().endswith((".md", ".rst", ".txt")) or
                "readme" in f.get("path", "").lower() or
                "doc" in f.get("path", "").lower() or
                "documentation" in f.get("path", "").lower()
                for f in files
            )
        except Exception:
            return False

    def detect_license(self, scan_results):
        """Detect if repository has a license file"""
        try:
            files = scan_results.get("files", [])
            return any(
                "license" in f.get("path", "").lower() or
                "licence" in f.get("path", "").lower() or
                "copying" in f.get("path", "").lower()
                for f in files
            )
        except Exception:
            return False

    def assess_complexity(self, scan_results):
        """Assess code complexity based on file count and content"""
        try:
            files = scan_results.get("files", [])
            total_lines = sum(
                len(f.get("content", "").splitlines())
                for f in files
                if f.get("content")
            )

            if total_lines < 500:
                return "low"
            elif total_lines < 2000:
                return "medium"
            else:
                return "high"
        except Exception:
            return "medium"

    def create_cache_key(self, repo_url, scan_results):
        """Create cache key for verification results"""
        try:
            files_json = json.dumps(scan_results.get("files", []), sort_keys=True)
            files_hash = hashlib.sha256(files_json.encode()).hexdigest()[:16]
            return json.dumps({"repoUrl": repo_url, "filesHash": files_hash})
        except Exception:
            return f"fallback-{hash(repo_url)}"

    def create_error_result(self, error, repo_url):
        """Create error result structure"""
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
        """Get agent by ID"""
        return await self.registry.get_agent(agent_id)

    async def get_all_agents(self):
        """Get all agents"""
        return await self.registry.get_all_agents()

    def clear_cache(self):
        """Clear verification cache"""
        self.cache.clear()