import asyncio
import json
from datetime import datetime

from .verifier import AgentVerifier

def load_mock_scan_results():
    # This should be replaced with actual security scan results
    return {
        "passed": True,
        "issuesFound": 0,
        "securityScore": 0.85,
        "hasSecurityUpdates": True,
        "files": [
            {"path": "main.py", "content": "import openai\ndef run():\n    print('Hello')\n"}
        ]
    }

def load_mock_github_context():
    # Simulated GitHub repository metadata (normally from GitHub Action context)
    return {
        "stargazers_count": 12,
        "forks_count": 3,
        "watchers_count": 5,
        "updated_at": datetime.utcnow().isoformat() + "Z",
        "size": 1234,
        "language": "Python",
        "private": False
    }

async def main():
    print("Running agent verification GitHub Action entrypoint...")
    scan_results = load_mock_scan_results()
    github_context = load_mock_github_context()
    repo_url = "https://github.com/example/repo"

    verifier = AgentVerifier()
    result = await verifier.verify_agent(repo_url, scan_results, github_context)

    if result["success"]:
        print(f"✅ Agent Verified: {result['agent']['id']}")
        print(f"🔒 Trust Score: {result['agent']['trustScore']}")
        print(f"🏷️ Badge URL: {result['badge']['verificationUrl']}")
    else:
        print("❌ Verification failed")
        print(f"Error: {result['error']['message']}")

if __name__ == "__main__":
    asyncio.run(main())
