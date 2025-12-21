#!/usr/bin/env python3
"""
Webhook simulator for testing IncidentFox locally.

Usage:
    python simulate_webhook.py --scenario missing-env-var --pr 123
    python simulate_webhook.py --list
"""

import argparse
import hashlib
import hmac
import json
import sys
from datetime import datetime

import httpx

# Sample failure logs for different scenarios
SCENARIOS = {
    "missing-env-var": {
        "name": "Missing DATABASE_URL",
        "logs": """[2025-12-15T10:30:15Z] Building Docker image...
[2025-12-15T10:30:45Z] Build completed successfully
[2025-12-15T10:30:46Z] Starting container...
[2025-12-15T10:30:47Z] backend-1  | Error: DATABASE_URL environment variable is not set
[2025-12-15T10:30:47Z] backend-1  | at /app/src/db.js:12:15
[2025-12-15T10:30:47Z] backend-1 exited with code 1
[2025-12-15T10:30:48Z] Deployment failed
""",
    },
    "port-mismatch": {
        "name": "Port Mismatch (Healthcheck Failure)",
        "logs": """[2025-12-15T11:15:20Z] Building Docker image...
[2025-12-15T11:15:50Z] Build completed successfully
[2025-12-15T11:15:51Z] Starting container...
[2025-12-15T11:15:52Z] backend-1  | Server listening on port 5001
[2025-12-15T11:16:02Z] Health check failed: GET http://localhost:3000/health - Connection refused
[2025-12-15T11:16:12Z] Health check failed: GET http://localhost:3000/health - Connection refused
[2025-12-15T11:16:22Z] Health check failed: GET http://localhost:3000/health - Connection refused
[2025-12-15T11:16:22Z] Container failed health checks after 30s
[2025-12-15T11:16:23Z] Deployment failed
""",
    },
    "build-failure": {
        "name": "Build Failure (Missing Dependency)",
        "logs": """[2025-12-15T12:00:10Z] Building Docker image...
[2025-12-15T12:00:15Z] Step 5/10 : RUN npm install
[2025-12-15T12:00:45Z] npm ERR! code ERESOLVE
[2025-12-15T12:00:45Z] npm ERR! ERESOLVE unable to resolve dependency tree
[2025-12-15T12:00:45Z] npm ERR! While resolving: extend-app@1.0.0
[2025-12-15T12:00:45Z] npm ERR! Found: react@18.2.0
[2025-12-15T12:00:45Z] npm ERR! node_modules/react
[2025-12-15T12:00:45Z] npm ERR!   react@"^18.2.0" from the root project
[2025-12-15T12:00:45Z] npm ERR! Could not resolve dependency:
[2025-12-15T12:00:45Z] npm ERR! peer react@"^17.0.0" from some-package@1.2.3
[2025-12-15T12:00:45Z] Build failed
""",
    },
    "runtime-crash": {
        "name": "Runtime Crash (Unhandled Exception)",
        "logs": """[2025-12-15T14:20:30Z] Building Docker image...
[2025-12-15T14:21:00Z] Build completed successfully
[2025-12-15T14:21:01Z] Starting container...
[2025-12-15T14:21:02Z] backend-1  | Server starting...
[2025-12-15T14:21:03Z] backend-1  | Connecting to database...
[2025-12-15T14:21:04Z] backend-1  | TypeError: Cannot read properties of undefined (reading 'query')
[2025-12-15T14:21:04Z] backend-1  |     at Database.connect (/app/src/db.js:45:18)
[2025-12-15T14:21:04Z] backend-1  |     at Server.start (/app/src/server.js:12:22)
[2025-12-15T14:21:04Z] backend-1 exited with code 1
[2025-12-15T14:21:05Z] Container restarted (1/3)
[2025-12-15T14:21:06Z] backend-1 exited with code 1
[2025-12-15T14:21:07Z] Container restarted (2/3)
[2025-12-15T14:21:08Z] backend-1 exited with code 1
[2025-12-15T14:21:09Z] Deployment failed - Container crash loop
""",
    },
}


def send_coolify_webhook(
    scenario_name: str,
    pr_number: int,
    bot_url: str = "http://localhost:8000",
    webhook_secret: str = "test_secret",
):
    """Send a simulated Coolify deployment webhook."""

    if scenario_name not in SCENARIOS:
        print(f"❌ Unknown scenario: {scenario_name}")
        print(f"Available: {', '.join(SCENARIOS.keys())}")
        return False

    scenario = SCENARIOS[scenario_name]

    # Construct webhook payload (matches Coolify's format)
    payload = {
        "event": "deployment.failed",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "deployment": {
            "id": f"deployment-{pr_number}-{datetime.utcnow().timestamp()}",
            "status": "failed",
            "application_id": "app-extend-preview",
            "environment": f"preview-pr-{pr_number}",
            "logs": scenario["logs"],
            "started_at": "2025-12-15T10:30:00Z",
            "finished_at": datetime.utcnow().isoformat() + "Z",
            "exit_code": 1,
        },
        "application": {
            "id": "app-extend-preview",
            "name": "extend-preview",
            "repository": {
                "url": "https://github.com/extend/enterprise-fullstack-assignment",
                "branch": f"pr-{pr_number}",
                "full_name": "extend/enterprise-fullstack-assignment",
            },
        },
        "pull_request": {
            "number": pr_number,
            "url": f"https://github.com/extend/enterprise-fullstack-assignment/pull/{pr_number}",
        },
    }

    # Sign the webhook
    payload_bytes = json.dumps(payload).encode()
    signature = hmac.new(
        webhook_secret.encode(), payload_bytes, hashlib.sha256
    ).hexdigest()

    # Send the webhook
    print(f"\n🚀 Sending webhook to {bot_url}/webhooks/coolify")
    print(f"📦 Scenario: {scenario['name']}")
    print(f"🔢 PR Number: {pr_number}")
    print()

    try:
        response = httpx.post(
            f"{bot_url}/webhooks/coolify",
            json=payload,
            headers={
                "X-Signature": f"sha256={signature}",
                "Content-Type": "application/json",
                "User-Agent": "Coolify-Webhook/1.0",
            },
            timeout=30.0,
        )

        print(f"✅ Response Status: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            print(f"📝 Response: {json.dumps(result, indent=2)}")
            print()
            print("🎉 Webhook processed successfully!")
            print()
            print("Next steps:")
            print(f"  1. Check PR #{pr_number} for a new comment from IncidentFox")
            print("  2. Try interactive commands: /incidentfox apply fix")
            print("  3. Check bot logs: make logs")
            return True
        else:
            print(f"❌ Error: {response.text}")
            return False

    except httpx.ConnectError:
        print("❌ Connection failed!")
        print()
        print("Is the bot running? Start it with:")
        print("  cd incidentfox-bot && make dev")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def list_scenarios():
    """List all available scenarios."""
    print("\n📚 Available Scenarios:\n")
    for name, scenario in SCENARIOS.items():
        print(f"  • {name:25} - {scenario['name']}")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Simulate Coolify webhooks for testing IncidentFox",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Send a missing env var failure for PR #123
  python simulate_webhook.py --scenario missing-env-var --pr 123

  # Send a port mismatch failure for PR #456
  python simulate_webhook.py --scenario port-mismatch --pr 456

  # List available scenarios
  python simulate_webhook.py --list
        """,
    )

    parser.add_argument(
        "--scenario",
        "-s",
        help="Scenario to simulate",
    )
    parser.add_argument(
        "--pr",
        "-p",
        type=int,
        help="PR number",
    )
    parser.add_argument(
        "--url",
        "-u",
        default="http://localhost:8000",
        help="IncidentFox bot URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--secret",
        default="test_secret",
        help="Webhook secret (default: test_secret)",
    )
    parser.add_argument(
        "--list",
        "-l",
        action="store_true",
        help="List available scenarios",
    )

    args = parser.parse_args()

    if args.list:
        list_scenarios()
        return 0

    if not args.scenario or not args.pr:
        parser.print_help()
        print()
        list_scenarios()
        return 1

    success = send_coolify_webhook(
        scenario_name=args.scenario,
        pr_number=args.pr,
        bot_url=args.url,
        webhook_secret=args.secret,
    )

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
