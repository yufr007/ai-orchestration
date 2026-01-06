"""GitHub integration using PyGithub."""

from typing import Any

from github import Github
from github.GithubException import GithubException

from src.config import get_settings


def get_github_client() -> Github:
    """Get authenticated GitHub client."""
    settings = get_settings()
    return Github(settings.github_token)


async def get_issue_details(repo_full_name: str, issue_number: int) -> dict[str, Any]:
    """Get issue details from GitHub.

    Args:
        repo_full_name: Repository in format 'owner/repo'
        issue_number: Issue number

    Returns:
        Dictionary with issue details
    """
    g = get_github_client()
    repo = g.get_repo(repo_full_name)
    issue = repo.get_issue(issue_number)

    return {
        "number": issue.number,
        "title": issue.title,
        "body": issue.body or "",
        "state": issue.state,
        "labels": [label.name for label in issue.labels],
        "assignees": [user.login for user in issue.assignees],
        "created_at": issue.created_at.isoformat(),
        "updated_at": issue.updated_at.isoformat(),
        "url": issue.html_url,
    }


async def get_pr_details(repo_full_name: str, pr_number: int) -> dict[str, Any]:
    """Get pull request details.

    Args:
        repo_full_name: Repository in format 'owner/repo'
        pr_number: PR number

    Returns:
        Dictionary with PR details
    """
    g = get_github_client()
    repo = g.get_repo(repo_full_name)
    pr = repo.get_pull(pr_number)

    return {
        "number": pr.number,
        "title": pr.title,
        "body": pr.body or "",
        "state": pr.state,
        "head": pr.head.ref,
        "base": pr.base.ref,
        "mergeable": pr.mergeable,
        "merged": pr.merged,
        "files_changed": pr.changed_files,
        "additions": pr.additions,
        "deletions": pr.deletions,
        "url": pr.html_url,
    }


async def get_file_contents(repo_full_name: str, path: str, ref: str = "main") -> str:
    """Get file contents from repository.

    Args:
        repo_full_name: Repository in format 'owner/repo'
        path: File path in repository
        ref: Branch/tag/commit reference

    Returns:
        File content as string
    """
    g = get_github_client()
    repo = g.get_repo(repo_full_name)

    try:
        file_content = repo.get_contents(path, ref=ref)
        if isinstance(file_content, list):
            raise ValueError(f"{path} is a directory, not a file")
        return file_content.decoded_content.decode("utf-8")
    except GithubException as e:
        if e.status == 404:
            raise FileNotFoundError(f"File not found: {path}")
        raise


async def create_branch(repo_full_name: str, branch_name: str, from_branch: str = "main") -> None:
    """Create a new branch.

    Args:
        repo_full_name: Repository in format 'owner/repo'
        branch_name: Name for new branch
        from_branch: Source branch
    """
    g = get_github_client()
    repo = g.get_repo(repo_full_name)

    # Get source branch ref
    source_ref = repo.get_git_ref(f"heads/{from_branch}")
    source_sha = source_ref.object.sha

    # Create new branch
    try:
        repo.create_git_ref(f"refs/heads/{branch_name}", source_sha)
    except GithubException as e:
        if e.status == 422:  # Branch already exists
            pass
        else:
            raise


async def create_or_update_file(
    repo_full_name: str,
    path: str,
    content: str,
    branch: str,
    message: str,
) -> None:
    """Create or update a file in repository.

    Args:
        repo_full_name: Repository in format 'owner/repo'
        path: File path
        content: File content
        branch: Target branch
        message: Commit message
    """
    g = get_github_client()
    repo = g.get_repo(repo_full_name)

    try:
        # Try to get existing file
        existing_file = repo.get_contents(path, ref=branch)
        if isinstance(existing_file, list):
            raise ValueError(f"{path} is a directory")

        # Update existing file
        repo.update_file(
            path=path,
            message=message,
            content=content,
            sha=existing_file.sha,
            branch=branch,
        )
    except GithubException as e:
        if e.status == 404:
            # Create new file
            repo.create_file(
                path=path,
                message=message,
                content=content,
                branch=branch,
            )
        else:
            raise


async def create_pull_request(
    repo_full_name: str,
    head: str,
    base: str,
    title: str,
    body: str,
) -> int:
    """Create a pull request.

    Args:
        repo_full_name: Repository in format 'owner/repo'
        head: Source branch
        base: Target branch
        title: PR title
        body: PR description

    Returns:
        PR number
    """
    g = get_github_client()
    repo = g.get_repo(repo_full_name)

    pr = repo.create_pull(
        title=title,
        body=body,
        head=head,
        base=base,
    )

    return pr.number


async def get_pr_diff(repo_full_name: str, pr_number: int) -> str:
    """Get PR diff.

    Args:
        repo_full_name: Repository in format 'owner/repo'
        pr_number: PR number

    Returns:
        Diff as string
    """
    g = get_github_client()
    repo = g.get_repo(repo_full_name)
    pr = repo.get_pull(pr_number)

    # Get files changed
    files = pr.get_files()

    diff_parts = []
    for file in files:
        diff_parts.append(f"\n--- {file.filename} ---")
        diff_parts.append(f"Status: {file.status}")
        diff_parts.append(f"Changes: +{file.additions} -{file.deletions}")
        if file.patch:
            diff_parts.append(file.patch)

    return "\n".join(diff_parts)


async def add_pr_review_comment(
    repo_full_name: str,
    pr_number: int,
    body: str,
    path: str | None = None,
    line: int | None = None,
) -> None:
    """Add review comment to PR.

    Args:
        repo_full_name: Repository in format 'owner/repo'
        pr_number: PR number
        body: Comment text
        path: File path (optional, for inline comments)
        line: Line number (optional, for inline comments)
    """
    g = get_github_client()
    repo = g.get_repo(repo_full_name)
    pr = repo.get_pull(pr_number)

    if path and line:
        # Inline comment (requires commit SHA)
        commits = list(pr.get_commits())
        latest_commit = commits[-1]
        pr.create_review_comment(
            body=body,
            commit=latest_commit,
            path=path,
            line=line,
        )
    else:
        # General comment
        pr.create_issue_comment(body)
