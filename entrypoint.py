import os, sys, yaml, json, pathlib, asyncio

# Add the current directory to Python path to help with imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from llm_policy.api_key_scanner import scan_api_keys
from llm_policy.rate_limit_scanner import scan_rate_limits
from llm_policy.telemetry import emit_metrics
from llm_policy.input_sanitize_scanner import scan_input_sanitization

# Try to import agent verification engine with error handling
try:
    from agent_verification_engine.verifier import AgentVerifier

    AGENT_VERIFICATION_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ Agent verification engine not available: {e}")
    print("🔄 Falling back to V0 security scanning only")
    AGENT_VERIFICATION_AVAILABLE = False

ROOT = pathlib.Path(".")
CONFIG_FILE = os.getenv("INPUT_CONFIG", "llm-policy.yml")


def load_cfg():
    if pathlib.Path(CONFIG_FILE).exists():
        with open(CONFIG_FILE, "r") as f:
            return yaml.safe_load(f) or {}
    return {}


def set_github_outputs(v0_results, agent_results, v0_failed):
    """Set GitHub Action outputs for both V0 security and Agent Verification"""
    output_file = os.getenv('GITHUB_OUTPUT')
    if not output_file:
        return

    # V0 Security outputs (existing)
    api_violations = v0_results.get("api_key_security", {}).get("violations", 0)
    rate_warnings = v0_results.get("rate_limit", {}).get("total", 0)
    sanitize_warnings = v0_results.get("input_sanitize", {}).get("total", 0)

    if v0_failed:
        security_status = "failed"
        security_badge_status = "❌ Failed"
    elif api_violations > 0 or rate_warnings > 0 or sanitize_warnings > 0:
        security_status = "warning"
        security_badge_status = "⚠️ Warnings"
    else:
        security_status = "passed"
        security_badge_status = "✅ Secured"

    # Agent Verification outputs (new)
    agent_status = "unknown"
    agent_badge_status = "❓ Unknown"
    trust_score = 0
    agent_id = "unknown"
    verification_url = ""

    if agent_results and agent_results.get("success"):
        agent_data = agent_results.get("agent", {})
        trust_score = agent_data.get("trustScore", 0)
        agent_id = agent_data.get("id", "unknown")
        verification_url = agent_results.get("badge", {}).get("verificationUrl", "")

        # Determine agent status based on trust score
        if trust_score >= 0.9:
            agent_status = "verified"
            agent_badge_status = "✅ Verified"
        elif trust_score >= 0.75:
            agent_status = "trusted"
            agent_badge_status = "🔷 Trusted"
        elif trust_score >= 0.6:
            agent_status = "validated"
            agent_badge_status = "🟡 Validated"
        elif trust_score >= 0.4:
            agent_status = "basic"
            agent_badge_status = "🟠 Basic"
        else:
            agent_status = "unverified"
            agent_badge_status = "⚪ Unverified"
    elif agent_results and not agent_results.get("success"):
        agent_status = "error"
        agent_badge_status = "❌ Error"

    # Write all outputs
    with open(output_file, 'a') as f:
        # V0 Security outputs
        f.write(f"security-status={security_status}\n")
        f.write(f"api-key-violations={api_violations}\n")
        f.write(f"rate-limit-warnings={rate_warnings}\n")
        f.write(f"input-sanitize-warnings={sanitize_warnings}\n")
        f.write(f"security-badge-status={security_badge_status}\n")

        # Agent Verification outputs
        f.write(f"agent-status={agent_status}\n")
        f.write(f"agent-trust-score={trust_score:.2f}\n")
        f.write(f"agent-id={agent_id}\n")
        f.write(f"agent-badge-status={agent_badge_status}\n")
        f.write(f"agent-verification-url={verification_url}\n")

    # GitHub Actions annotations
    print(f"::notice title=LLM Security Status::{security_badge_status}")
    print(f"::notice title=Agent Verification::{agent_badge_status} (Trust: {trust_score:.2f})")


def collect_file_contents():
    """Collect file contents for Agent Verification Engine"""
    files = []
    exclude_patterns = [".git", "__pycache__", "node_modules", ".github"]

    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(pattern in str(path) for pattern in exclude_patterns):
            continue
        if path.suffix not in [".py", ".js", ".ts", ".go", ".md", ".yml", ".yaml"]:
            continue

        try:
            content = path.read_text("utf-8", "ignore")
            files.append({
                "path": str(path),
                "content": content
            })
        except Exception:
            continue

    return files


def get_github_context():
    """Extract GitHub repository context from environment"""
    return {
        "stargazers_count": 0,  # Would need GitHub API to get real values
        "forks_count": 0,
        "watchers_count": 0,
        "updated_at": os.getenv("GITHUB_SHA_TIMESTAMP", ""),
        "size": 0,
        "language": "Python",  # Could be detected from files
        "private": os.getenv("GITHUB_REPOSITORY", "").startswith("private/"),
        "repository": os.getenv("GITHUB_REPOSITORY", ""),
        "sha": os.getenv("GITHUB_SHA", ""),
        "ref": os.getenv("GITHUB_REF", ""),
        "workflow": os.getenv("GITHUB_WORKFLOW", ""),
        "run_id": os.getenv("GITHUB_RUN_ID", ""),
        "run_number": os.getenv("GITHUB_RUN_NUMBER", "")
    }


async def run_agent_verification(v0_results):
    """Run Agent Verification Engine with real data"""
    if not AGENT_VERIFICATION_AVAILABLE:
        print("⚠️ Agent verification engine not available, skipping...")
        return {
            "success": False,
            "error": {"message": "Agent verification engine not available"},
            "agent": None,
            "verification": None,
            "badge": None
        }

    try:
        print("\n" + "=" * 50)
        print("AGENT VERIFICATION ENGINE - V1")
        print("=" * 50)

        # Prepare scan results in expected format
        scan_results = {
            "passed": v0_results.get("api_key_security", {}).get("violations", 0) == 0,
            "issuesFound": (
                    v0_results.get("api_key_security", {}).get("violations", 0) +
                    v0_results.get("rate_limit", {}).get("total", 0) +
                    v0_results.get("input_sanitize", {}).get("total", 0)
            ),
            "securityScore": max(0.1, 1.0 - (
                    v0_results.get("api_key_security", {}).get("violations", 0) * 0.3 +
                    v0_results.get("rate_limit", {}).get("total", 0) * 0.1 +
                    v0_results.get("input_sanitize", {}).get("total", 0) * 0.1
            )),
            "hasSecurityUpdates": v0_results.get("api_key_security", {}).get("violations", 0) == 0,
            "files": collect_file_contents()
        }

        github_context = get_github_context()
        repo_url = f"https://github.com/{github_context['repository']}"

        # Initialize verifier with cache path
        cache_path = os.getenv("GITHUB_WORKSPACE", ".") + "/.agent-cache/registry.json"
        verifier = AgentVerifier({
            "registry_path": cache_path,
            "badge_base_url": "https://agentproof.dev",  # Placeholder
            "enable_cache": True
        })

        result = await verifier.verify_agent(repo_url, scan_results, github_context)

        if result["success"]:
            agent = result["agent"]
            print(f"✅ Agent Verified: {agent['id']}")
            print(f"🔒 Trust Score: {agent['trustScore']:.2f}")
            print(f"🏷️ Badge URL: {result['badge']['verificationUrl']}")
            print(f"📊 Repositories: {len(agent['repositories'])}")
            print(f"🔄 Verification Count: {agent['metadata']['verificationCount']}")
        else:
            print("❌ Agent verification failed")
            print(f"Error: {result['error']['message']}")

        return result

    except Exception as e:
        print(f"❌ Agent verification error: {e}")
        return {
            "success": False,
            "error": {"message": str(e)},
            "agent": None,
            "verification": None,
            "badge": None
        }


def main():
    print("LLM AGENT TRUST VERIFICATION - V1")
    if AGENT_VERIFICATION_AVAILABLE:
        print("Running V0 Security Scan + Agent Verification Engine")
    else:
        print("Running V0 Security Scan Only (Agent verification unavailable)")
    print("=" * 60)

    cfg = load_cfg()
    policies = cfg.get("policies", {"api-key-security": True, "rate-limit": True})
    v0_failed = False
    v0_results = {}

    # ===============================
    # V0 SECURITY SCAN (EXISTING)
    # ===============================
    print("\n📋 PHASE 1: V0 SECURITY ANALYSIS")
    print("-" * 30)

    # API Key Security Scanner
    if policies.get("api-key-security"):
        res = scan_api_keys(ROOT, cfg)
        v0_results["api_key_security"] = res

        if res["violations"] > 0:
            print(f"::warning title=API Key Violations::Found {res['violations']} potential API keys or tokens")
            for detail in res.get("details", [])[:5]:
                print(f"::warning file={detail.split(':')[0]}::{detail}")

    # Input Sanitization Scanner
    if policies.get("input-sanitize", True):
        res = scan_input_sanitization(ROOT, cfg)
        v0_results["input_sanitize"] = res

        if res.get("total", 0) > 0:
            print(f"::warning title=Input Sanitization::Found {res['total']} potential unsanitized inputs")
            for warning in res.get("warnings", [])[:5]:
                if ":" in warning:
                    parts = warning.split(":", 2)
                    print(
                        f"::warning file={parts[0]},line={parts[1]}::{parts[2] if len(parts) > 2 else 'Unsanitized input'}")

    # Rate Limit Scanner
    if policies.get("rate-limit"):
        res = scan_rate_limits(ROOT, cfg)
        v0_results["rate_limit"] = res

        if res.get("total", 0) > 0:
            print(f"::warning title=Rate Limiting::Found {res['total']} LLM calls without rate limiting")
            for warning in res.get("warnings", [])[:5]:
                if ":" in warning:
                    parts = warning.split(":", 2)
                    print(
                        f"::warning file={parts[0]},line={parts[1]}::{parts[2] if len(parts) > 2 else 'Missing rate limit'}")

    # V0 Results Summary
    print("\n📊 V0 SECURITY SCAN RESULTS:")
    print(json.dumps(v0_results, indent=2))

    # ===============================
    # AGENT VERIFICATION (NEW)
    # ===============================
    if AGENT_VERIFICATION_AVAILABLE:
        print("\n🤖 PHASE 2: AGENT VERIFICATION ENGINE")
        print("-" * 30)

        # Run agent verification
        agent_results = asyncio.run(run_agent_verification(v0_results))
    else:
        print("\n⚠️ PHASE 2: AGENT VERIFICATION SKIPPED")
        print("-" * 30)
        print("Agent verification engine not available")
        agent_results = None

    # ===============================
    # FINALIZATION
    # ===============================
    # Emit telemetry
    emit_metrics(v0_results, cfg)

    # Set GitHub Action outputs for both systems
    set_github_outputs(v0_results, agent_results, v0_failed)

    # Final status
    print("\n" + "=" * 60)
    if AGENT_VERIFICATION_AVAILABLE:
        print("✅ V1 VERIFICATION COMPLETE")
    else:
        print("✅ V0 SECURITY SCAN COMPLETE")

    if v0_failed:
        print("❌ V0 Security scan failed")

    if AGENT_VERIFICATION_AVAILABLE and agent_results and agent_results.get("success"):
        trust_score = agent_results["agent"]["trustScore"]
        print(f"🤖 Agent Trust Score: {trust_score:.2f}")
    elif AGENT_VERIFICATION_AVAILABLE and agent_results:
        print("⚠️ Agent verification had issues")
    else:
        print("ℹ️ Agent verification skipped")

    print("=" * 60)

    if v0_failed:
        sys.exit("❌ V0 Policy enforcement failed")

    if AGENT_VERIFICATION_AVAILABLE:
        print("✅ All verification steps completed")
    else:
        print("✅ Security verification completed (Agent verification unavailable)")


if __name__ == "__main__":
    main()