"""GitHub operations wrapper using PyGithub."""

import base64
from typing import Any

from github import Github, GithubException
from github.Repository import Repository

from src.config import get_settings


class GitHubClient:
    """GitHub API client wrapper."""

    def __init__(self) -> None:
        settings = get_settings()
        self.github = Github(settings.github_token)
        self.owner = settings.github_owner

    def get_repo(self, repo_name: str) -> Repository:
        """Get repository object.

        Args:
            repo_name: Repository in format 'owner/repo'

        Returns:
            PyGithub Repository object
        """
        return self.github.get_repo(repo_name)

    async def get_repository_context(self, repo_name: str) -> dict[str, Any]:
        """Get repository metadata.

        Args:
            repo_name: Repository in format 'owner/repo'

        Returns:
            Repository context (language, description, etc.)
        """
        repo = self.get_repo(repo_name)
        return {
            "name": repo.name,
            "full_name": repo.full_name,
            "description": repo.description,
            "language": repo.language,
            "default_branch": repo.default_branch,
            "topics": repo.get_topics(),
            "url": repo.html_url,
        }

    async def get_issue_details(self, repo_name: str, issue_number: int) -> dict[str, Any]:
        """Get issue details.

        Args:
            repo_name: Repository in format 'owner/repo'
            issue_number: Issue number

        Returns:
            Issue details (title, body, labels, etc.)
        """
        repo = self.get_repo(repo_name)
        issue = repo.get_issue(issue_number)
        return {
            "number": issue.number,
            "title": issue.title,
            "body": issue.body or "",
            "labels": [label.name for label in issue.labels],
            "state": issue.state,
            "created_at": issue.created_at.isoformat(),
            "url": issue.html_url,
        }

    async def get_file_contents(
        self, repo_name: str, file_path: str, ref: str = "main"
    ) -> str:
        """Get file contents from repository.

        Args:
            repo_name: Repository in format 'owner/repo'
            file_path: Path to file
            ref: Branch/commit reference

        Returns:
            File contents as string
        """
        repo = self.get_repo(repo_name)
        try:
            content = repo.get_contents(file_path, ref=ref)
            if isinstance(content, list):
                raise ValueError(f"{file_path} is a directory, not a file")
            return content.decoded_content.decode("utf-8")
        except GithubException as e:
            if e.status == 404:
                raise FileNotFoundError(f"File not found: {file_path}")
            raise

    async def create_branch(self, repo_name: str, branch_name: str, from_branch: str = "main") -> None:
        """Create a new branch.

        Args:
            repo_name: Repository in format 'owner/repo'
            branch_name: Name for new branch
            from_branch: Source branch to branch from
        """
        repo = self.get_repo(repo_name)
        source = repo.get_branch(from_branch)
        repo.create_git_ref(f"refs/heads/{branch_name}", source.commit.sha)

    async def create_or_update_file(
        self,
        repo_name: str,
        path: str,
        content: str,
        message: str,
        branch: str = "main",
    ) -> None:
        """Create or update a file in the repository.

        Args:
            repo_name: Repository in format 'owner/repo'
            path: File path
            content: File contents
            message: Commit message
            branch: Target branch
        """
        repo = self.get_repo(repo_name)
        try:
            # Try to get existing file
            file = repo.get_contents(path, ref=branch)
            if isinstance(file, list):
                raise ValueError(f"{path} is a directory")
            # Update existing file
            repo.update_file(path, message, content, file.sha, branch=branch)
        except GithubException as e:
            if e.status == 404:
                # Create new file
                repo.create_file(path, message, content, branch=branch)
            else:
                raise

    async def create_pull_request(
        self,
        repo_name: str,
        title: str,
        body: str,
        head: str,
        base: str = "main",
    ) -> int:
        """Create a pull request.

        Args:
            repo_name: Repository in format 'owner/repo'
            title: PR title
            body: PR description
            head: Source branch
            base: Target branch

        Returns:
            Pull request number
        """
        repo = self.get_repo(repo_name)
        pr = repo.create_pull(title=title, body=body, head=head, base=base)
        return pr.number

    async def add_pr_comment(self, repo_name: str, pr_number: int, body: str) -> None:
        """Add comment to pull request.

        Args:
            repo_name: Repository in format 'owner/repo'
            pr_number: PR number
            body: Comment text
        """
        repo = self.get_repo(repo_name)
        pr = repo.get_pull(pr_number)
        pr.create_issue_comment(body)

    async def add_pr_review(
        self, repo_name: str, pr_number: int, body: str, event: str = "COMMENT"
    ) -> None:
        """Add review to pull request.

        Args:
            repo_name: Repository in format 'owner/repo'
            pr_number: PR number
            body: Review comment
            event: Review event (APPROVE, REQUEST_CHANGES, COMMENT)
        """
        repo = self.get_repo(repo_name)
        pr = repo.get_pull(pr_number)
        pr.create_review(body=body, event=event)

    async def get_pr_diff(self, repo_name: str, pr_number: int) -> str:
        """Get pull request diff.

        Args:
            repo_name: Repository in format 'owner/repo'
            pr_number: PR number

        Returns:
            Unified diff string
        """
        repo = self.get_repo(repo_name)
        pr = repo.get_pull(pr_number)
        
        # Get all files in the PR
        files = pr.get_files()
        diff_parts = []
        
        for file in files:
            diff_parts.append(f"\n--- {file.filename} ---")
            if file.patch:
                diff_parts.append(file.patch)
        
        return "\n".join(diff_parts)


# Global client instance
_client: GitHubClient | None = None


def get_github_client() -> GitHubClient:
    """Get or create GitHub client singleton."""
    global _client
    if _client is None:
        _client = GitHubClient()
    return _client


# Convenience functions
async def get_repository_context(repo_name: str) -> dict[str, Any]:
    """Get repository context."""
    return await get_github_client().get_repository_context(repo_name)


async def get_issue_details(repo_name: str, issue_number: int) -> dict[str, Any]:
    """Get issue details."""
    return await get_github_client().get_issue_details(repo_name, issue_number)


async def get_file_contents(repo_name: str, file_path: str, ref: str = "main") -> str:
    """Get file contents."""
    return await get_github_client().get_file_contents(repo_name, file_path, ref)


async def create_branch(repo_name: str, branch_name: str, from_branch: str = "main") -> None:
    """Create branch."""
    await get_github_client().create_branch(repo_name, branch_name, from_branch)


async def create_or_update_file(
    repo_name: str, path: str, content: str, message: str, branch: str = "main"
) -> None:
    """Create or update file."""
    await get_github_client().create_or_update_file(repo_name, path, content, message, branch)


async def create_pull_request(
    repo_name: str, title: str, body: str, head: str, base: str = "main"
) -> int:
    """Create pull request."""
    return await get_github_client().create_pull_request(repo_name, title, body, head, base)


async def add_pr_comment(repo_name: str, pr_number: int, body: str) -> None:
    """Add PR comment."""
    await get_github_client().add_pr_comment(repo_name, pr_number, body)


async def add_pr_review(repo_name: str, pr_number: int, body: str, event: str = "COMMENT") -> None:
    """Add PR review."""
    await get_github_client().add_pr_review(repo_name, pr_number, body, event)


async def get_pr_diff(repo_name: str, pr_number: int) -> str:
    """Get PR diff."""
    return await get_github_client().get_pr_diff(repo_name, pr_number)
