"""GitHub integration using PyGithub."""

import base64
from typing import Any

from github import Github, GithubException
from src.config import get_settings


class GitHubClient:
    """Wrapper for GitHub API operations."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.client = Github(self.settings.github_token)

    def get_repo(self, repo_name: str) -> Any:
        """Get repository object.
        
        Args:
            repo_name: Repository name in format 'owner/repo'
        
        Returns:
            Repository object
        """
        return self.client.get_repo(repo_name)

    async def get_issue(self, repo: str, issue_number: int) -> dict[str, Any]:
        """Get issue details.
        
        Args:
            repo: Repository name
            issue_number: Issue number
        
        Returns:
            Issue details
        """
        repo_obj = self.get_repo(repo)
        issue = repo_obj.get_issue(issue_number)
        
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

    async def get_file(self, repo: str, path: str, ref: str = "main") -> str:
        """Get file contents.
        
        Args:
            repo: Repository name
            path: File path
            ref: Git ref (branch, tag, commit)
        
        Returns:
            File contents as string
        """
        repo_obj = self.get_repo(repo)
        try:
            content = repo_obj.get_contents(path, ref=ref)
            if isinstance(content, list):
                raise ValueError(f"{path} is a directory, not a file")
            return base64.b64decode(content.content).decode("utf-8")
        except GithubException as e:
            if e.status == 404:
                raise FileNotFoundError(f"File not found: {path}")
            raise

    async def create_branch(self, owner: str, repo: str, branch: str, from_branch: str = "main") -> None:
        """Create a new branch.
        
        Args:
            owner: Repository owner
            repo: Repository name
            branch: New branch name
            from_branch: Source branch
        """
        repo_obj = self.get_repo(f"{owner}/{repo}")
        source = repo_obj.get_branch(from_branch)
        repo_obj.create_git_ref(f"refs/heads/{branch}", source.commit.sha)

    async def create_or_update_file(
        self,
        owner: str,
        repo: str,
        path: str,
        content: str,
        message: str,
        branch: str,
    ) -> None:
        """Create or update a file.
        
        Args:
            owner: Repository owner
            repo: Repository name
            path: File path
            content: File content
            message: Commit message
            branch: Target branch
        """
        repo_obj = self.get_repo(f"{owner}/{repo}")
        try:
            # Try to get existing file
            existing = repo_obj.get_contents(path, ref=branch)
            if isinstance(existing, list):
                raise ValueError(f"{path} is a directory")
            # Update existing file
            repo_obj.update_file(path, message, content, existing.sha, branch=branch)
        except GithubException as e:
            if e.status == 404:
                # Create new file
                repo_obj.create_file(path, message, content, branch=branch)
            else:
                raise

    async def create_pull_request(
        self,
        owner: str,
        repo: str,
        title: str,
        body: str,
        head: str,
        base: str,
    ) -> dict[str, Any]:
        """Create a pull request.
        
        Args:
            owner: Repository owner
            repo: Repository name
            title: PR title
            body: PR description
            head: Source branch
            base: Target branch
        
        Returns:
            PR details
        """
        repo_obj = self.get_repo(f"{owner}/{repo}")
        pr = repo_obj.create_pull(title=title, body=body, head=head, base=base)
        
        return {
            "number": pr.number,
            "title": pr.title,
            "body": pr.body,
            "state": pr.state,
            "html_url": pr.html_url,
        }

    async def get_pull_request(self, owner: str, repo: str, pr_number: int) -> dict[str, Any]:
        """Get pull request details.
        
        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: PR number
        
        Returns:
            PR details
        """
        repo_obj = self.get_repo(f"{owner}/{repo}")
        pr = repo_obj.get_pull(pr_number)
        
        return {
            "number": pr.number,
            "title": pr.title,
            "body": pr.body or "",
            "state": pr.state,
            "head": pr.head.ref,
            "base": pr.base.ref,
            "html_url": pr.html_url,
            "mergeable": pr.mergeable,
        }

    async def get_pull_request_files(self, owner: str, repo: str, pr_number: int) -> list[dict[str, Any]]:
        """Get files changed in a PR.
        
        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: PR number
        
        Returns:
            List of changed files
        """
        repo_obj = self.get_repo(f"{owner}/{repo}")
        pr = repo_obj.get_pull(pr_number)
        
        return [
            {
                "filename": file.filename,
                "status": file.status,
                "additions": file.additions,
                "deletions": file.deletions,
                "changes": file.changes,
                "patch": getattr(file, "patch", None),
            }
            for file in pr.get_files()
        ]

    async def add_pull_request_comment(self, owner: str, repo: str, pr_number: int, body: str) -> None:
        """Add a comment to a PR.
        
        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: PR number
            body: Comment text
        """
        repo_obj = self.get_repo(f"{owner}/{repo}")
        pr = repo_obj.get_pull(pr_number)
        pr.create_issue_comment(body)


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


async def get_file_contents(repo: str, path: str, ref: str = "main") -> str:
    """Get file contents."""
    client = get_github_client()
    return await client.get_file(repo, path, ref)


async def create_branch(owner: str, repo: str, branch: str, from_branch: str = "main") -> None:
    """Create a new branch."""
    client = get_github_client()
    await client.create_branch(owner, repo, branch, from_branch)


async def create_or_update_file(
    owner: str, repo: str, path: str, content: str, message: str, branch: str
) -> None:
    """Create or update a file."""
    client = get_github_client()
    await client.create_or_update_file(owner, repo, path, content, message, branch)


async def create_pull_request(
    owner: str, repo: str, title: str, body: str, head: str, base: str
) -> dict[str, Any]:
    """Create a pull request."""
    client = get_github_client()
    return await client.create_pull_request(owner, repo, title, body, head, base)


async def get_pr_details(owner: str, repo: str, pr_number: int) -> dict[str, Any]:
    """Get PR details."""
    client = get_github_client()
    return await client.get_pull_request(owner, repo, pr_number)


async def get_pr_files(owner: str, repo: str, pr_number: int) -> list[dict[str, Any]]:
    """Get files changed in a PR."""
    client = get_github_client()
    return await client.get_pull_request_files(owner, repo, pr_number)


async def add_pr_comment(owner: str, repo: str, pr_number: int, body: str) -> None:
    """Add a comment to a PR."""
    client = get_github_client()
    await client.add_pull_request_comment(owner, repo, pr_number, body)
