#!/usr/bin/env python3
"""
Helper script to get GitHub App Installation ID.

Run this after installing your GitHub App to a repository.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.config import settings
from github import GithubIntegration, Auth


def get_installation_id():
    """Get the installation ID for the GitHub App."""

    print("\n🔍 Finding GitHub App Installation ID...\n")

    try:
        # Read private key
        with open(settings.github_app_private_key_path) as f:
            private_key = f.read()

        # Create GitHub Integration
        auth = Auth.AppAuth(settings.github_app_id, private_key)
        gi = GithubIntegration(auth=auth)

        # Get all installations
        installations = gi.get_installations()

        if not installations:
            print("❌ No installations found!")
            print("\nYou need to install the GitHub App to a repository first:")
            print(f"   https://github.com/apps/YOUR_APP_NAME/installations/new\n")
            return

        print("✅ Found installations:\n")

        for install in installations:
            print(f"📦 Installation ID: {install.id}")
            print(f"   Account: {install.account.login}")
            print(f"   Type: {install.account.type}")
            print(f"   Repos: {install.repository_selection}")

            if install.repository_selection == "selected":
                # Get selected repositories
                repos = install.get_repos()
                print(f"   Selected Repositories:")
                for repo in repos:
                    print(f"      - {repo.full_name}")

            print()

        if len(list(installations)) == 1:
            install_id = list(installations)[0].id
            print(f"✨ Add this to your .env file:\n")
            print(f"GITHUB_INSTALLATION_ID={install_id}")
            print()
        else:
            print("Multiple installations found. Choose the one for your target repository.")
            print()

    except FileNotFoundError:
        print(f"❌ Private key not found at: {settings.github_app_private_key_path}")
        print("\nMake sure GITHUB_APP_PRIVATE_KEY_PATH in .env points to your private-key.pem file.\n")
    except Exception as e:
        print(f"❌ Error: {e}\n")
        if "401" in str(e):
            print("This usually means:")
            print("  - Wrong GitHub App ID")
            print("  - Wrong private key")
            print("  - Private key format issue\n")


if __name__ == "__main__":
    get_installation_id()
