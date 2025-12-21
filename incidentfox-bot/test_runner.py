#!/usr/bin/env python3
"""
Test runner for IncidentFox - Simulates Coolify deployment failures without needing real Coolify.

Usage:
    python test_runner.py --scenario missing-env-var
    python test_runner.py --scenario port-mismatch
    python test_runner.py --scenario build-failure
"""

import argparse
import json
import sys
from pathlib import Path

import httpx

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.analyzer import FailureAnalyzer

# Sample failure logs for different scenarios
SCENARIOS = {
    "missing-env-var": {
        "name": "Missing DATABASE_URL",
        "logs": """
[2025-12-15T10:30:15Z] Building Docker image...
[2025-12-15T10:30:45Z] Build completed successfully
[2025-12-15T10:30:46Z] Starting container...
[2025-12-15T10:30:47Z] backend-1  | Error: DATABASE_URL environment variable is not set
[2025-12-15T10:30:47Z] backend-1  | at /app/src/db.js:12:15
[2025-12-15T10:30:47Z] backend-1 exited with code 1
[2025-12-15T10:30:48Z] Deployment failed
""",
        "pr": 123,
        "branch": "feat/add-user-auth",
    },
    "port-mismatch": {
        "name": "Port Mismatch (Healthcheck Failure)",
        "logs": """
[2025-12-15T11:15:20Z] Building Docker image...
[2025-12-15T11:15:50Z] Build completed successfully
[2025-12-15T11:15:51Z] Starting container...
[2025-12-15T11:15:52Z] backend-1  | Server listening on port 5001
[2025-12-15T11:16:02Z] Health check failed: GET http://localhost:3000/health - Connection refused
[2025-12-15T11:16:12Z] Health check failed: GET http://localhost:3000/health - Connection refused
[2025-12-15T11:16:22Z] Health check failed: GET http://localhost:3000/health - Connection refused
[2025-12-15T11:16:22Z] Container failed health checks after 30s
[2025-12-15T11:16:23Z] Deployment failed
""",
        "pr": 124,
        "branch": "fix/update-api-port",
    },
    "build-failure": {
        "name": "Build Failure (Missing Dependency)",
        "logs": """
[2025-12-15T12:00:10Z] Building Docker image...
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
        "pr": 125,
        "branch": "feat/upgrade-dependencies",
    },
    "runtime-crash": {
        "name": "Runtime Crash (Unhandled Exception)",
        "logs": """
[2025-12-15T14:20:30Z] Building Docker image...
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
        "pr": 126,
        "branch": "fix/database-connection",
    },
}


def analyze_scenario(scenario_name: str):
    """Analyze a failure scenario and print the results."""

    if scenario_name not in SCENARIOS:
        print(f"❌ Unknown scenario: {scenario_name}")
        print(f"Available scenarios: {', '.join(SCENARIOS.keys())}")
        return 1

    scenario = SCENARIOS[scenario_name]
    print(f"\n🔍 Testing Scenario: {scenario['name']}")
    print("=" * 80)

    # Initialize analyzer
    analyzer = FailureAnalyzer()

    # Run analysis
    print("\n📊 Running Analysis Engine...")
    result = analyzer.analyze(
        logs=scenario["logs"],
        repo_name="extend/enterprise-fullstack-assignment",
        pr_number=scenario["pr"],
        branch_name=scenario["branch"],
    )

    # Display results
    print("\n" + "=" * 80)
    print("📋 ANALYSIS RESULTS")
    print("=" * 80)

    print(f"\n🏷️  Failure Category: {result.failure_category}")
    print(f"💯 Confidence: {result.confidence:.1%}")
    print(f"\n📝 Summary:\n{result.summary}")
    print(f"\n🔎 Root Cause:\n{result.root_cause}")

    if result.evidence:
        print(f"\n📄 Evidence ({len(result.evidence)} items):")
        for i, ev in enumerate(result.evidence, 1):
            print(f"  {i}. {ev.type}: {ev.description}")
            if ev.snippet:
                print(f"     Snippet: {ev.snippet[:100]}...")

    if result.recommendations:
        print(f"\n💡 Recommendations:")
        for i, rec in enumerate(result.recommendations, 1):
            print(f"  {i}. {rec}")

    if result.suggested_files:
        print(f"\n📁 Files to Check:")
        for f in result.suggested_files:
            print(f"  - {f}")

    print("\n" + "=" * 80)

    # Generate formatted PR comment
    from src.comment_formatter import format_analysis_comment

    comment = format_analysis_comment(
        analysis=result,
        pr_number=scenario["pr"],
        deployment_url=f"https://coolify.example.com/deployment/test-{scenario['pr']}",
        repo_name="extend/enterprise-fullstack-assignment",
    )

    print("\n💬 Generated PR Comment:")
    print("=" * 80)
    print(comment)
    print("=" * 80)

    return 0


def list_scenarios():
    """List all available test scenarios."""
    print("\n📚 Available Test Scenarios:\n")
    for name, scenario in SCENARIOS.items():
        print(f"  • {name:25} - {scenario['name']}")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Test IncidentFox failure analysis without needing Coolify",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--scenario",
        "-s",
        help="Scenario to test (use --list to see available scenarios)",
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

    if not args.scenario:
        parser.print_help()
        print()
        list_scenarios()
        return 1

    return analyze_scenario(args.scenario)


if __name__ == "__main__":
    sys.exit(main())
