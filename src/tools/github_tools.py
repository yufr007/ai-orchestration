"""GitHub API integration tools."""

from typing import Any

import structlog
from github import Github, GithubException
from github.Repository import Repository

from src.config import get_settings

logger = structlog.get_logger()


class GitHubTools:
    """Tools for interacting with GitHub API."""

    def __init__(self):
        self.settings = get_settings()
        self.client = Github(self.settings.github_token)
        self.logger = logger.bind(tool="github")

    def _get_repo(self, repo: str) -> Repository:
        """Get repository object."""
        return self.client.get_repo(repo)

    async def get_issue(self, repo: str, issue_number: int) -> dict[str, Any]:
        """Get issue details."""
        try:
            repository = self._get_repo(repo)
            issue = repository.get_issue(issue_number)

            return {
                "number": issue.number,
                "title": issue.title,
                "body": issue.body,
                "state": issue.state,
                "labels": [label.name for label in issue.labels],
                "assignees": [assignee.login for assignee in issue.assignees],
                "created_at": issue.created_at.isoformat(),
            }
        except GithubException as e:
            self.logger.error("Failed to get issue", error=str(e))
            raise

    async def get_repo_info(self, repo: str) -> dict[str, Any]:
        """Get repository information."""
        try:
            repository = self._get_repo(repo)
            return {
                "name": repository.name,
                "full_name": repository.full_name,
                "description": repository.description,
                "language": repository.language,
                "default_branch": repository.default_branch,
                "topics": repository.get_topics(),
            }
        except GithubException as e:
            self.logger.error("Failed to get repo info", error=str(e))
            raise

    async def get_file_contents(self, repo: str, path: str, ref: str = "main") -> str | None:
        """Get file contents from repository."""
        try:
            repository = self._get_repo(repo)
            contents = repository.get_contents(path, ref=ref)
            if isinstance(contents, list):
                return None  # Directory
            return contents.decoded_content.decode("utf-8")
        except GithubException as e:
            if e.status == 404:
                return None  # File doesn't exist
            self.logger.error("Failed to get file contents", error=str(e))
            raise

    async def create_branch(self, repo: str, branch_name: str, from_branch: str = "main") -> None:
        """Create a new branch."""
        try:
            repository = self._get_repo(repo)
            source = repository.get_branch(from_branch)
            repository.create_git_ref(f"refs/heads/{branch_name}", source.commit.sha)
            self.logger.info("Created branch", branch=branch_name)
        except GithubException as e:
            self.logger.error("Failed to create branch", error=str(e))
            raise

    async def update_file(
        self, repo: str, branch: str, path: str, content: str, message: str
    ) -> None:
        """Create or update a file."""
        try:
            repository = self._get_repo(repo)

            # Try to get existing file
            try:
                existing = repository.get_contents(path, ref=branch)
                repository.update_file(path, message, content, existing.sha, branch=branch)
                self.logger.info("Updated file", path=path)
            except GithubException as e:
                if e.status == 404:
                    # File doesn't exist, create it
                    repository.create_file(path, message, content, branch=branch)
                    self.logger.info("Created file", path=path)
                else:
                    raise
        except GithubException as e:
            self.logger.error("Failed to update file", error=str(e))
            raise

    async def create_pull_request(
        self, repo: str, title: str, body: str, head: str, base: str = "main"
    ) -> int:
        """Create a pull request."""
        try:
            repository = self._get_repo(repo)
            pr = repository.create_pull(title=title, body=body, head=head, base=base)
            self.logger.info("Created PR", pr_number=pr.number)
            return pr.number
        except GithubException as e:
            self.logger.error("Failed to create PR", error=str(e))
            raise

    async def get_pr(self, repo: str, pr_number: int) -> dict[str, Any]:
        """Get pull request details."""
        try:
            repository = self._get_repo(repo)
            pr = repository.get_pull(pr_number)

            return {
                "number": pr.number,
                "title": pr.title,
                "body": pr.body,
                "state": pr.state,
                "head": pr.head.ref,
                "base": pr.base.ref,
                "mergeable": pr.mergeable,
                "created_at": pr.created_at.isoformat(),
            }
        except GithubException as e:
            self.logger.error("Failed to get PR", error=str(e))
            raise

    async def get_pr_diff(self, repo: str, pr_number: int) -> str:
        """Get pull request diff."""
        try:
            repository = self._get_repo(repo)
            pr = repository.get_pull(pr_number)
            files = pr.get_files()

            diff = ""
            for file in files:
                diff += f"\n--- {file.filename}\n"
                if file.patch:
                    diff += file.patch + "\n"

            return diff
        except GithubException as e:
            self.logger.error("Failed to get PR diff", error=str(e))
            raise

    async def add_pr_comment(self, repo: str, pr_number: int, body: str) -> None:
        """Add comment to pull request."""
        try:
            repository = self._get_repo(repo)
            pr = repository.get_pull(pr_number)
            pr.create_issue_comment(body)
            self.logger.info("Added PR comment", pr_number=pr_number)
        except GithubException as e:
            self.logger.error("Failed to add PR comment", error=str(e))
            raise
