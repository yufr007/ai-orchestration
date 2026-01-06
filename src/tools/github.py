"""GitHub integration using GitHub API (wraps GitHub MCP tools)."""

import base64
from typing import Any

import httpx
from github import Github
from github.GithubException import GithubException

from src.config import get_settings

settings = get_settings()


class GitHubClient:
    """GitHub API client wrapper."""

    def __init__(self) -> None:
        self.token = settings.github_token
        self.owner = settings.github_owner
        self.gh = Github(self.token)
        self.base_url = "https://api.github.com"

    def _parse_repo(self, repo: str) -> tuple[str, str]:
        """Parse repo string into owner/name."""
        if "/" in repo:
            owner, name = repo.split("/", 1)
            return owner, name
        return self.owner, repo

    async def get_issue(self, repo: str, issue_number: int) -> dict[str, Any]:
        """Get issue details."""
        owner, repo_name = self._parse_repo(repo)
        repository = self.gh.get_repo(f"{owner}/{repo_name}")
        issue = repository.get_issue(issue_number)
        return {
            "number": issue.number,
            "title": issue.title,
            "body": issue.body or "",
            "state": issue.state,
            "labels": [label.name for label in issue.labels],
            "assignees": [assignee.login for assignee in issue.assignees],
            "created_at": issue.created_at.isoformat(),
            "updated_at": issue.updated_at.isoformat(),
        }

    async def get_pull_request(self, repo: str, pr_number: int) -> dict[str, Any]:
        """Get pull request details."""
        owner, repo_name = self._parse_repo(repo)
        repository = self.gh.get_repo(f"{owner}/{repo_name}")
        pr = repository.get_pull(pr_number)
        return {
            "number": pr.number,
            "title": pr.title,
            "body": pr.body or "",
            "state": pr.state,
            "head": pr.head.ref,
            "base": pr.base.ref,
            "mergeable": pr.mergeable,
            "merged": pr.merged,
        }

    async def get_file(self, repo: str, path: str, ref: str = "main") -> str:
        """Get file contents."""
        owner, repo_name = self._parse_repo(repo)
        repository = self.gh.get_repo(f"{owner}/{repo_name}")
        try:
            contents = repository.get_contents(path, ref=ref)
            if isinstance(contents, list):
                raise ValueError(f"{path} is a directory, not a file")
            return base64.b64decode(contents.content).decode("utf-8")
        except GithubException as e:
            if e.status == 404:
                raise FileNotFoundError(f"File not found: {path}")
            raise

    async def create_branch(self, repo: str, branch_name: str, from_branch: str = "main") -> None:
        """Create a new branch."""
        owner, repo_name = self._parse_repo(repo)
        repository = self.gh.get_repo(f"{owner}/{repo_name}")
        source = repository.get_branch(from_branch)
        repository.create_git_ref(ref=f"refs/heads/{branch_name}", sha=source.commit.sha)

    async def create_or_update_file(
        self, repo: str, path: str, content: str, branch: str, message: str
    ) -> None:
        """Create or update a file."""
        owner, repo_name = self._parse_repo(repo)
        repository = self.gh.get_repo(f"{owner}/{repo_name}")

        try:
            # Try to get existing file
            contents = repository.get_contents(path, ref=branch)
            if isinstance(contents, list):
                raise ValueError(f"{path} is a directory")
            # Update existing file
            repository.update_file(
                path=path, message=message, content=content, sha=contents.sha, branch=branch
            )
        except GithubException as e:
            if e.status == 404:
                # Create new file
                repository.create_file(path=path, message=message, content=content, branch=branch)
            else:
                raise

    async def create_pull_request(
        self, repo: str, head: str, base: str, title: str, body: str
    ) -> int:
        """Create a pull request."""
        owner, repo_name = self._parse_repo(repo)
        repository = self.gh.get_repo(f"{owner}/{repo_name}")
        pr = repository.create_pull(title=title, body=body, head=head, base=base)
        return pr.number

    async def add_pr_comment(self, repo: str, pr_number: int, comment: str) -> None:
        """Add a comment to a pull request."""
        owner, repo_name = self._parse_repo(repo)
        repository = self.gh.get_repo(f"{owner}/{repo_name}")
        pr = repository.get_pull(pr_number)
        pr.create_issue_comment(comment)

    async def add_pr_review(
        self, repo: str, pr_number: int, body: str, event: str = "COMMENT"
    ) -> None:
        """Add a review to a pull request.

        Args:
            repo: Repository name
            pr_number: Pull request number
            body: Review comment body
            event: Review event type (APPROVE, REQUEST_CHANGES, COMMENT)
        """
        owner, repo_name = self._parse_repo(repo)
        repository = self.gh.get_repo(f"{owner}/{repo_name}")
        pr = repository.get_pull(pr_number)
        pr.create_review(body=body, event=event)

    async def get_pr_diff(self, repo: str, pr_number: int) -> str:
        """Get pull request diff."""
        owner, repo_name = self._parse_repo(repo)
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/repos/{owner}/{repo_name}/pulls/{pr_number}",
                headers={
                    "Authorization": f"token {self.token}",
                    "Accept": "application/vnd.github.v3.diff",
                },
            )
            response.raise_for_status()
            return response.text


# Singleton instance
_github_client: GitHubClient | None = None


def get_github_client() -> GitHubClient:
    """Get or create GitHub client singleton."""
    global _github_client
    if _github_client is None:
        _github_client = GitHubClient()
    return _github_client


# Convenience functions
async def get_issue_details(repo: str, issue_number: int) -> dict[str, Any]:
    """Get issue details."""
    client = get_github_client()
    return await client.get_issue(repo, issue_number)


async def get_pr_details(repo: str, pr_number: int) -> dict[str, Any]:
    """Get pull request details."""
    client = get_github_client()
    return await client.get_pull_request(repo, pr_number)


async def get_file_contents(repo: str, path: str, ref: str = "main") -> str:
    """Get file contents from repository."""
    client = get_github_client()
    return await client.get_file(repo, path, ref)


async def create_branch(repo: str, branch_name: str, from_branch: str = "main") -> None:
    """Create a new branch."""
    client = get_github_client()
    await client.create_branch(repo, branch_name, from_branch)


async def create_or_update_file(
    repo: str, path: str, content: str, branch: str, message: str
) -> None:
    """Create or update a file in the repository."""
    client = get_github_client()
    await client.create_or_update_file(repo, path, content, branch, message)


async def create_pull_request(repo: str, head: str, base: str, title: str, body: str) -> int:
    """Create a pull request."""
    client = get_github_client()
    return await client.create_pull_request(repo, head, base, title, body)


async def add_pr_comment(repo: str, pr_number: int, comment: str) -> None:
    """Add a comment to a pull request."""
    client = get_github_client()
    await client.add_pr_comment(repo, pr_number, comment)


async def add_pr_review(repo: str, pr_number: int, body: str, event: str = "COMMENT") -> None:
    """Add a review to a pull request."""
    client = get_github_client()
    await client.add_pr_review(repo, pr_number, body, event)


async def get_pr_diff(repo: str, pr_number: int) -> str:
    """Get pull request diff."""
    client = get_github_client()
    return await client.get_pr_diff(repo, pr_number)
