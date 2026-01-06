"""GitHub API integration tools."""

import base64
from typing import Any

import httpx
from github import Github, GithubException
from github.Repository import Repository

from src.config import get_settings


class GitHubClient:
    """GitHub API client wrapper."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.client = Github(self.settings.github_token)
        self._repo_cache: dict[str, Repository] = {}

    def get_repo(self, repo_name: str) -> Repository:
        """Get repository object with caching."""
        if repo_name not in self._repo_cache:
            self._repo_cache[repo_name] = self.client.get_repo(repo_name)
        return self._repo_cache[repo_name]

    async def get_issue_details(self, repo_name: str, issue_number: int) -> str:
        """Get issue details including title, body, and comments."""
        try:
            repo = self.get_repo(repo_name)
            issue = repo.get_issue(issue_number)

            details = f"""# Issue #{issue_number}: {issue.title}

**State**: {issue.state}
**Author**: {issue.user.login}
**Created**: {issue.created_at}

## Description
{issue.body or 'No description provided'}

## Comments
"""
            comments = issue.get_comments()
            for comment in comments:
                details += f"\n---\n**{comment.user.login}** ({comment.created_at}):\n{comment.body}\n"

            return details
        except GithubException as e:
            return f"Error fetching issue: {e.data.get('message', str(e))}"

    async def get_file_contents(self, repo_name: str, path: str, ref: str = "main") -> str:
        """Get file contents from repository."""
        try:
            repo = self.get_repo(repo_name)
            content = repo.get_contents(path, ref=ref)

            if isinstance(content, list):
                # Directory - return file list
                return "\n".join(f.path for f in content)

            # File - decode content
            return content.decoded_content.decode("utf-8")
        except GithubException as e:
            raise FileNotFoundError(f"File not found: {path}")

    async def get_file_tree(self, repo_name: str, path: str = "", max_depth: int = 3) -> str:
        """Get repository file tree structure."""
        try:
            repo = self.get_repo(repo_name)
            tree = repo.get_git_tree(repo.default_branch, recursive=True)

            # Build tree structure
            lines = []
            for item in tree.tree[:100]:  # Limit to avoid huge outputs
                depth = item.path.count("/")
                if depth <= max_depth:
                    indent = "  " * depth
                    lines.append(f"{indent}{item.path.split('/')[-1]}")

            return "\n".join(lines)
        except GithubException:
            return "Unable to fetch file tree"

    async def create_branch(self, repo_name: str, branch_name: str, from_branch: str = "main") -> str:
        """Create a new branch."""
        try:
            repo = self.get_repo(repo_name)
            source = repo.get_branch(from_branch)
            repo.create_git_ref(ref=f"refs/heads/{branch_name}", sha=source.commit.sha)
            return branch_name
        except GithubException as e:
            raise RuntimeError(f"Failed to create branch: {e.data.get('message', str(e))}")

    async def create_or_update_file(
        self,
        repo_name: str,
        path: str,
        content: str,
        branch: str,
        message: str,
    ) -> dict[str, Any]:
        """Create or update a file in repository."""
        try:
            repo = self.get_repo(repo_name)

            # Try to get existing file
            try:
                file = repo.get_contents(path, ref=branch)
                # Update existing
                result = repo.update_file(
                    path=path,
                    message=message,
                    content=content,
                    sha=file.sha,
                    branch=branch,
                )
                return {"action": "updated", "sha": result["commit"].sha}
            except GithubException:
                # Create new
                result = repo.create_file(
                    path=path,
                    message=message,
                    content=content,
                    branch=branch,
                )
                return {"action": "created", "sha": result["commit"].sha}

        except GithubException as e:
            raise RuntimeError(f"Failed to write file: {e.data.get('message', str(e))}")

    async def create_pull_request(
        self,
        repo_name: str,
        title: str,
        body: str,
        head: str,
        base: str = "main",
    ) -> int:
        """Create a pull request."""
        try:
            repo = self.get_repo(repo_name)
            pr = repo.create_pull(title=title, body=body, head=head, base=base)
            return pr.number
        except GithubException as e:
            raise RuntimeError(f"Failed to create PR: {e.data.get('message', str(e))}")

    async def get_pr_diff(self, repo_name: str, pr_number: int) -> str:
        """Get PR diff content."""
        try:
            repo = self.get_repo(repo_name)
            pr = repo.get_pull(pr_number)

            # Get diff via API
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    pr.diff_url,
                    headers={
                        "Authorization": f"token {self.settings.github_token}",
                        "Accept": "application/vnd.github.v3.diff",
                    },
                )
                return response.text
        except Exception as e:
            return f"Unable to fetch diff: {str(e)}"

    async def get_pr_files(self, repo_name: str, pr_number: int) -> list[str]:
        """Get list of files changed in PR."""
        try:
            repo = self.get_repo(repo_name)
            pr = repo.get_pull(pr_number)
            return [f.filename for f in pr.get_files()]
        except GithubException:
            return []

    async def add_pr_comment(self, repo_name: str, pr_number: int, comment: str) -> None:
        """Add comment to pull request."""
        try:
            repo = self.get_repo(repo_name)
            pr = repo.get_pull(pr_number)
            pr.create_issue_comment(comment)
        except GithubException as e:
            raise RuntimeError(f"Failed to add comment: {e.data.get('message', str(e))}")


# Global instance
_github_client: GitHubClient | None = None


def get_github_client() -> GitHubClient:
    """Get or create global GitHub client."""
    global _github_client
    if _github_client is None:
        _github_client = GitHubClient()
    return _github_client


# Convenience functions
async def get_issue_details(repo: str, issue_number: int) -> str:
    client = get_github_client()
    return await client.get_issue_details(repo, issue_number)


async def get_file_contents(repo: str, path: str, ref: str = "main") -> str:
    client = get_github_client()
    return await client.get_file_contents(repo, path, ref)


async def get_file_tree(repo: str) -> str:
    client = get_github_client()
    return await client.get_file_tree(repo)


async def create_branch(repo: str, branch: str, from_branch: str = "main") -> str:
    client = get_github_client()
    return await client.create_branch(repo, branch, from_branch)


async def create_or_update_file(
    repo: str, path: str, content: str, branch: str, message: str
) -> dict[str, Any]:
    client = get_github_client()
    return await client.create_or_update_file(repo, path, content, branch, message)


async def create_pull_request(repo: str, title: str, body: str, head: str, base: str = "main") -> int:
    client = get_github_client()
    return await client.create_pull_request(repo, title, body, head, base)


async def get_pr_diff(repo: str, pr_number: int) -> str:
    client = get_github_client()
    return await client.get_pr_diff(repo, pr_number)


async def get_pr_files(repo: str, pr_number: int) -> list[str]:
    client = get_github_client()
    return await client.get_pr_files(repo, pr_number)


async def add_pr_comment(repo: str, pr_number: int, comment: str) -> None:
    client = get_github_client()
    return await client.add_pr_comment(repo, pr_number, comment)
