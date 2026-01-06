"""GitHub integration using PyGithub and direct API calls."""

import base64
from typing import Any

from github import Github
from github.GithubException import GithubException
import httpx

from src.config import get_settings


class GitHubTools:
    """GitHub operations wrapper."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.token = self.settings.github_token
        self.client = Github(self.token)
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def get_issue(self, repo: str, issue_number: int) -> dict[str, Any]:
        """Get issue details."""
        repository = self.client.get_repo(repo)
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

    async def get_repo_structure(self, repo: str, path: str = "") -> str:
        """Get repository structure."""
        repository = self.client.get_repo(repo)
        contents = repository.get_contents(path)

        structure = []
        if isinstance(contents, list):
            for content in contents:
                structure.append(f"{content.type}: {content.path}")
        else:
            structure.append(f"{contents.type}: {contents.path}")

        return "\n".join(structure[:50])  # Limit to 50 items

    async def analyze_code_patterns(self, repo: str) -> str:
        """Analyze existing code patterns in the repository."""
        repository = self.client.get_repo(repo)

        # Get common file types and structure
        patterns = []
        try:
            # Check for Python
            py_files = repository.get_contents("", ref="main")
            has_python = any(f.name.endswith(".py") for f in py_files if hasattr(f, "name"))
            if has_python:
                patterns.append("Python project detected")

            # Check for TypeScript/JavaScript
            has_ts = any(f.name.endswith((".ts", ".tsx")) for f in py_files if hasattr(f, "name"))
            if has_ts:
                patterns.append("TypeScript project detected")

            # Check for package managers
            file_names = [f.name for f in py_files if hasattr(f, "name")]
            if "package.json" in file_names:
                patterns.append("npm/yarn project")
            if "requirements.txt" in file_names or "pyproject.toml" in file_names:
                patterns.append("Python package manager detected")

        except GithubException:
            patterns.append("Unable to fully analyze repository structure")

        return "\n".join(patterns) if patterns else "No specific patterns detected"

    async def get_relevant_files(
        self,
        repo: str,
        tasks: list[dict[str, Any]],
    ) -> str:
        """Get relevant existing files based on tasks."""
        repository = self.client.get_repo(repo)
        files_content = []

        # Extract potential file paths from tasks
        for task in tasks[:3]:  # Limit to first 3 tasks
            description = task.get("description", "")
            # Simple extraction - in production, use more sophisticated parsing
            if "src/" in description or "test/" in description:
                # Try to find mentioned files
                words = description.split()
                for word in words:
                    if "/" in word and word.endswith((".py", ".ts", ".js")):
                        try:
                            content = repository.get_contents(word.strip("`'\""))
                            if hasattr(content, "decoded_content"):
                                decoded = content.decoded_content.decode("utf-8")
                                files_content.append(f"### {word}\n```\n{decoded[:500]}\n```")
                        except GithubException:
                            pass

        return "\n\n".join(files_content) if files_content else "No existing files found"

    async def create_branch(self, repo: str, branch_name: str, from_branch: str = "main") -> None:
        """Create a new branch."""
        repository = self.client.get_repo(repo)
        source = repository.get_branch(from_branch)
        repository.create_git_ref(f"refs/heads/{branch_name}", source.commit.sha)

    async def create_or_update_file(
        self,
        repo: str,
        path: str,
        content: str,
        branch: str,
        message: str,
    ) -> None:
        """Create or update a file in the repository."""
        repository = self.client.get_repo(repo)

        try:
            # Try to get existing file
            existing = repository.get_contents(path, ref=branch)
            repository.update_file(
                path=path,
                message=message,
                content=content,
                sha=existing.sha,
                branch=branch,
            )
        except GithubException:
            # File doesn't exist, create it
            repository.create_file(
                path=path,
                message=message,
                content=content,
                branch=branch,
            )

    async def create_pull_request(
        self,
        repo: str,
        head: str,
        base: str,
        title: str,
        body: str,
    ) -> int:
        """Create a pull request."""
        repository = self.client.get_repo(repo)
        pr = repository.create_pull(title=title, body=body, head=head, base=base)
        return pr.number

    async def get_pr_diff(self, repo: str, pr_number: int) -> str:
        """Get PR diff."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://api.github.com/repos/{repo}/pulls/{pr_number}",
                headers={**self.headers, "Accept": "application/vnd.github.diff"},
            )
            return response.text

    async def get_pr_files(self, repo: str, pr_number: int) -> dict[str, str]:
        """Get files changed in a PR."""
        repository = self.client.get_repo(repo)
        pr = repository.get_pull(pr_number)
        files = {}

        for file in pr.get_files():
            if file.patch:  # Only include files with actual changes
                files[file.filename] = file.patch

        return files

    async def add_review_comment(
        self,
        repo: str,
        pr_number: int,
        body: str,
        path: str | None = None,
        line: int | None = None,
    ) -> None:
        """Add a review comment to a PR."""
        repository = self.client.get_repo(repo)
        pr = repository.get_pull(pr_number)

        if path and line:
            # Line-specific comment
            pr.create_review_comment(
                body=body,
                commit=pr.get_commits()[pr.commits - 1],
                path=path,
                line=line,
            )
        else:
            # General comment
            pr.create_issue_comment(body)

    async def submit_review(
        self,
        repo: str,
        pr_number: int,
        event: str,
        body: str,
    ) -> None:
        """Submit a PR review."""
        repository = self.client.get_repo(repo)
        pr = repository.get_pull(pr_number)
        pr.create_review(body=body, event=event)
