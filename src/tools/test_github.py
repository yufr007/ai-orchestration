"""Test GitHub integration."""

import asyncio

from src.tools.github import get_github_client


async def test_github() -> None:
    """Test GitHub API connection."""
    print("\n=== Testing GitHub Integration ===")

    client = get_github_client()
    test_repo = "yufr007/ai-orchestration"  # This repo

    # Test authentication
    print("\n1. Testing authentication...")
    try:
        user = client.gh.get_user()
        print(f"  ✅ Authenticated as: {user.login}")
        print(f"  Name: {user.name}")
        print(f"  Email: {user.email}")
    except Exception as e:
        print(f"  ❌ Authentication failed: {e}")
        return

    # Test repo access
    print(f"\n2. Testing repo access ({test_repo})...")
    try:
        owner, repo_name = test_repo.split("/")
        repo = client.gh.get_repo(test_repo)
        print(f"  ✅ Repo accessible: {repo.name}")
        print(f"  Description: {repo.description}")
        print(f"  Default branch: {repo.default_branch}")
    except Exception as e:
        print(f"  ❌ Repo access failed: {e}")

    # Test file reading
    print("\n3. Testing file reading...")
    try:
        content = await client.get_file(test_repo, "README.md")
        print(f"  ✅ File read successful")
        print(f"  Length: {len(content)} characters")
        print(f"  First line: {content.split(chr(10))[0][:80]}...")
    except Exception as e:
        print(f"  ❌ File read failed: {e}")


if __name__ == "__main__":
    asyncio.run(test_github())
