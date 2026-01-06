"""GitHub API integration using PyGithub."""

import base64
from typing import Any

from github import Github, GithubException
import structlog

from src.config import get_settings

logger = structlog.get_logger()


class GitHubClient:
    """GitHub API client wrapper."""

    def __init__(self):
        settings = get_settings()
        self.github = Github(settings.github_token)
        self.default_owner = settings.github_owner

    def get_repo(self, repo_name: str):
        """Get repository object, handling owner prefix."""
        if "/" not in repo_name:
            repo_name = f"{self.default_owner}/{repo_name}"
        return self.github.get_repo(repo_name)


# Singleton instance
_github_client = None


def get_github_client() -> GitHubClient:
    """Get or create GitHub client singleton."""
    global _github_client
    if _github_client is None:
        _github_client = GitHubClient()
    return _github_client


async def get_issue_details(repo: str, issue_number: int) -> dict[str, Any]:
    """Get issue details from GitHub.

    Args:
        repo: Repository name (owner/repo or just repo)
        issue_number: Issue number

    Returns:
        Dictionary with issue details (title, body, labels, etc.)
    """
    logger.info("Fetching issue details", repo=repo, issue_number=issue_number)
    client = get_github_client()
    repo_obj = client.get_repo(repo)
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
        "url": issue.html_url,
    }


async def get_repository_context(repo: str) -> dict[str, Any]:
    """Get repository context (language, structure, etc.).

    Args:
        repo: Repository name

    Returns:
        Dictionary with repository metadata
    """
    logger.info("Fetching repository context", repo=repo)
    client = get_github_client()
    repo_obj = client.get_repo(repo)

    # Get primary language
    language = repo_obj.language or "Unknown"

    # Get repository structure (top-level directories)
    try:
        contents = repo_obj.get_contents("")
        structure = [item.name for item in contents if item.type == "dir"][:10]
    except GithubException:
        structure = []

    # Detect framework (basic heuristics)
    framework = "Unknown"
    try:
        if repo_obj.get_contents("requirements.txt"):
            framework = "Python (pip)"
        if repo_obj.get_contents("setup.py"):
            framework = "Python (setuptools)"
        if repo_obj.get_contents("pyproject.toml"):
            framework = "Python (modern)"
    except GithubException:
        pass

    return {
        "name": repo_obj.name,
        "full_name": repo_obj.full_name,
        "description": repo_obj.description or "",
        "language": language,
        "framework": framework,
        "structure": structure,
        "default_branch": repo_obj.default_branch,
        "topics": repo_obj.get_topics(),
    }


async def create_branch(repo: str, branch_name: str, base_branch: str = "main") -> bool:
    """Create a new branch.

    Args:
        repo: Repository name
        branch_name: Name for new branch
        base_branch: Source branch (defaults to main)

    Returns:
        True if created, False if already exists
    """
    logger.info("Creating branch", repo=repo, branch=branch_name, base=base_branch)
    client = get_github_client()
    repo_obj = client.get_repo(repo)

    try:
        # Get base branch ref
        base_ref = repo_obj.get_git_ref(f"heads/{base_branch}")
        base_sha = base_ref.object.sha

        # Create new branch
        repo_obj.create_git_ref(f"refs/heads/{branch_name}", base_sha)
        logger.info("Branch created", branch=branch_name)
        return True
    except GithubException as e:
        if "Reference already exists" in str(e):
            logger.info("Branch already exists", branch=branch_name)
            return False
        raise


async def get_file_contents(repo: str, path: str, ref: str = "main") -> str | None:
    """Get file contents from repository.

    Args:
        repo: Repository name
        path: File path
        ref: Branch/tag/commit ref

    Returns:
        File contents as string, or None if not found
    """
    logger.info("Fetching file contents", repo=repo, path=path, ref=ref)
    client = get_github_client()
    repo_obj = client.get_repo(repo)

    try:
        contents = repo_obj.get_contents(path, ref=ref)
        if contents.encoding == "base64":
            return base64.b64decode(contents.content).decode("utf-8")
        return contents.decoded_content.decode("utf-8")
    except GithubException as e:
        if e.status == 404:
            logger.info("File not found", path=path)
            return None
        raise


async def create_or_update_file(
    repo: str, path: str, content: str, message: str, branch: str = "main"
) -> dict[str, Any]:
    """Create or update a file in the repository.

    Args:
        repo: Repository name
        path: File path
        content: File content
        message: Commit message
        branch: Target branch

    Returns:
        Commit details
    """
    logger.info("Creating/updating file", repo=repo, path=path, branch=branch)
    client = get_github_client()
    repo_obj = client.get_repo(repo)

    try:
        # Try to get existing file
        existing = repo_obj.get_contents(path, ref=branch)
        result = repo_obj.update_file(path, message, content, existing.sha, branch=branch)
        logger.info("File updated", path=path)
    except GithubException as e:
        if e.status == 404:
            # File doesn't exist, create it
            result = repo_obj.create_file(path, message, content, branch=branch)
            logger.info("File created", path=path)
        else:
            raise

    return {
        "path": path,
        "sha": result["commit"].sha,
        "url": result["commit"].html_url,
    }


async def list_repository_files(repo: str, path: str = "", ref: str = "main") -> list[str]:
    """List files in a repository directory.

    Args:
        repo: Repository name
        path: Directory path (empty for root)
        ref: Branch/tag/commit ref

    Returns:
        List of file paths
    """
    client = get_github_client()
    repo_obj = client.get_repo(repo)

    contents = repo_obj.get_contents(path, ref=ref)
    files = []

    for item in contents:
        if item.type == "file":
            files.append(item.path)
        elif item.type == "dir":
            # Recursively list subdirectories
            subfiles = await list_repository_files(repo, item.path, ref)
            files.extend(subfiles)

    return files


async def create_pull_request(
    repo: str, head: str, base: str, title: str, body: str
) -> int:
    """Create a pull request.

    Args:
        repo: Repository name
        head: Source branch
        base: Target branch
        title: PR title
        body: PR description

    Returns:
        PR number
    """
    logger.info("Creating pull request", repo=repo, head=head, base=base)
    client = get_github_client()
    repo_obj = client.get_repo(repo)

    pr = repo_obj.create_pull(title=title, body=body, head=head, base=base)
    logger.info("Pull request created", pr_number=pr.number, url=pr.html_url)

    return pr.number


async def get_pr_details(repo: str, pr_number: int) -> dict[str, Any]:
    """Get pull request details.

    Args:
        repo: Repository name
        pr_number: PR number

    Returns:
        PR details dictionary
    """
    client = get_github_client()
    repo_obj = client.get_repo(repo)
    pr = repo_obj.get_pull(pr_number)

    return {
        "number": pr.number,
        "title": pr.title,
        "body": pr.body or "",
        "state": pr.state,
        "head": pr.head.ref,
        "base": pr.base.ref,
        "url": pr.html_url,
        "created_at": pr.created_at.isoformat(),
        "updated_at": pr.updated_at.isoformat(),
    }


async def get_pr_diff(repo: str, pr_number: int) -> str:
    """Get pull request diff.

    Args:
        repo: Repository name
        pr_number: PR number

    Returns:
        Diff as string
    """
    client = get_github_client()
    repo_obj = client.get_repo(repo)
    pr = repo_obj.get_pull(pr_number)

    files = pr.get_files()
    diff_parts = []

    for file in files:
        diff_parts.append(f"--- {file.filename}")
        diff_parts.append(f"+++ {file.filename}")
        if file.patch:
            diff_parts.append(file.patch)

    return "\n".join(diff_parts)


async def add_pr_comment(repo: str, pr_number: int, body: str) -> None:
    """Add a comment to a pull request.

    Args:
        repo: Repository name
        pr_number: PR number
        body: Comment text
    """
    logger.info("Adding PR comment", repo=repo, pr_number=pr_number)
    client = get_github_client()
    repo_obj = client.get_repo(repo)
    pr = repo_obj.get_pull(pr_number)
    pr.create_issue_comment(body)


async def add_pr_review(
    repo: str, pr_number: int, body: str, event: str = "COMMENT"
) -> None:
    """Add a review to a pull request.

    Args:
        repo: Repository name
        pr_number: PR number
        body: Review text
        event: Review event (APPROVE, REQUEST_CHANGES, COMMENT)
    """
    logger.info("Adding PR review", repo=repo, pr_number=pr_number, event=event)
    client = get_github_client()
    repo_obj = client.get_repo(repo)
    pr = repo_obj.get_pull(pr_number)
    pr.create_review(body=body, event=event)
