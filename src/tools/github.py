"""GitHub API integration using PyGithub."""

import base64
from typing import Any

from github import Github, GithubException
from github.Repository import Repository

from src.config import get_settings


def get_github_client() -> Github:
    """Get authenticated GitHub client."""
    settings = get_settings()
    return Github(settings.github_token)


def get_repo(repo: str) -> Repository:
    """Get repository object.
    
    Args:
        repo: Repository in format 'owner/name'
    
    Returns:
        GitHub Repository object
    """
    client = get_github_client()
    return client.get_repo(repo)


async def get_issue_details(repo: str, issue_number: int) -> str:
    """Get issue details as formatted text.
    
    Args:
        repo: Repository in format 'owner/name'
        issue_number: Issue number
    
    Returns:
        Formatted issue details
    """
    try:
        repository = get_repo(repo)
        issue = repository.get_issue(issue_number)
        
        # Format issue details
        details = f"""# Issue #{issue.number}: {issue.title}

**State**: {issue.state}
**Author**: @{issue.user.login}
**Created**: {issue.created_at}
**Labels**: {', '.join(label.name for label in issue.labels)}

## Description
{issue.body or '(No description provided)'}

## Comments ({issue.comments} total)
"""
        
        # Add recent comments
        comments = issue.get_comments()
        for i, comment in enumerate(comments[:5]):  # Limit to 5 comments
            details += f"\n### Comment by @{comment.user.login} on {comment.created_at}\n{comment.body}\n"
        
        return details
    
    except GithubException as e:
        return f"Error fetching issue: {e.data.get('message', str(e))}"


async def get_pr_details(repo: str, pr_number: int, include_diff: bool = False) -> str:
    """Get pull request details as formatted text.
    
    Args:
        repo: Repository in format 'owner/name'
        pr_number: PR number
        include_diff: Whether to include file diffs
    
    Returns:
        Formatted PR details
    """
    try:
        repository = get_repo(repo)
        pr = repository.get_pull(pr_number)
        
        details = f"""# Pull Request #{pr.number}: {pr.title}

**State**: {pr.state}
**Author**: @{pr.user.login}
**Branch**: {pr.head.ref} → {pr.base.ref}
**Created**: {pr.created_at}
**Updated**: {pr.updated_at}

## Description
{pr.body or '(No description provided)'}

## Files Changed ({pr.changed_files} files, +{pr.additions}/-{pr.deletions})
"""
        
        # Add file list
        files = pr.get_files()
        for file in files:
            details += f"\n- `{file.filename}` (+{file.additions}/-{file.deletions})"
        
        # Add diff if requested
        if include_diff:
            details += "\n\n## Diff\n"
            for file in files:
                if file.patch:
                    details += f"\n### {file.filename}\n```diff\n{file.patch}\n```\n"
        
        return details
    
    except GithubException as e:
        return f"Error fetching PR: {e.data.get('message', str(e))}"


async def get_file_contents(repo: str, path: str, ref: str = "main") -> str:
    """Get file contents from repository.
    
    Args:
        repo: Repository in format 'owner/name'
        path: File path
        ref: Git ref (branch, tag, commit)
    
    Returns:
        File contents as string
    """
    try:
        repository = get_repo(repo)
        file_content = repository.get_contents(path, ref=ref)
        
        if isinstance(file_content, list):
            raise ValueError(f"Path {path} is a directory, not a file")
        
        # Decode base64 content
        content = base64.b64decode(file_content.content).decode("utf-8")
        return content
    
    except GithubException as e:
        if e.status == 404:
            raise FileNotFoundError(f"File not found: {path}")
        raise Exception(f"Error fetching file: {e.data.get('message', str(e))}")


async def create_branch(repo: str, branch: str, from_branch: str = "main") -> dict[str, Any]:
    """Create a new branch.
    
    Args:
        repo: Repository in format 'owner/name'
        branch: New branch name
        from_branch: Source branch to branch from
    
    Returns:
        Branch creation result
    """
    try:
        repository = get_repo(repo)
        
        # Get source branch ref
        source_ref = repository.get_git_ref(f"heads/{from_branch}")
        source_sha = source_ref.object.sha
        
        # Create new branch
        new_ref = repository.create_git_ref(f"refs/heads/{branch}", source_sha)
        
        return {
            "branch": branch,
            "sha": new_ref.object.sha,
            "url": new_ref.url,
        }
    
    except GithubException as e:
        if "Reference already exists" in str(e):
            # Branch exists, return existing
            ref = repository.get_git_ref(f"heads/{branch}")
            return {
                "branch": branch,
                "sha": ref.object.sha,
                "url": ref.url,
                "existed": True,
            }
        raise Exception(f"Error creating branch: {e.data.get('message', str(e))}")


async def create_or_update_file(
    repo: str,
    path: str,
    content: str,
    branch: str,
    message: str,
) -> dict[str, Any]:
    """Create or update a file in the repository.
    
    Args:
        repo: Repository in format 'owner/name'
        path: File path
        content: File content
        branch: Branch to commit to
        message: Commit message
    
    Returns:
        Commit result
    """
    try:
        repository = get_repo(repo)
        
        # Try to get existing file
        try:
            existing_file = repository.get_contents(path, ref=branch)
            sha = existing_file.sha if not isinstance(existing_file, list) else None
        except GithubException:
            sha = None
        
        # Create or update
        if sha:
            result = repository.update_file(path, message, content, sha, branch=branch)
        else:
            result = repository.create_file(path, message, content, branch=branch)
        
        return {
            "path": path,
            "sha": result["commit"].sha,
            "url": result["commit"].html_url,
        }
    
    except GithubException as e:
        raise Exception(f"Error writing file: {e.data.get('message', str(e))}")


async def create_pull_request(
    repo: str,
    head: str,
    base: str,
    title: str,
    body: str,
    draft: bool = False,
) -> dict[str, Any]:
    """Create a pull request.
    
    Args:
        repo: Repository in format 'owner/name'
        head: Head branch (source)
        base: Base branch (target)
        title: PR title
        body: PR description
        draft: Whether to create as draft
    
    Returns:
        PR creation result
    """
    try:
        repository = get_repo(repo)
        
        pr = repository.create_pull(
            title=title,
            body=body,
            head=head,
            base=base,
            draft=draft,
        )
        
        return {
            "number": pr.number,
            "url": pr.html_url,
            "state": pr.state,
        }
    
    except GithubException as e:
        raise Exception(f"Error creating PR: {e.data.get('message', str(e))}")


async def add_pr_review_comment(
    repo: str,
    pr_number: int,
    body: str,
    path: str | None = None,
    line: int | None = None,
) -> dict[str, Any]:
    """Add a review comment to a PR.
    
    Args:
        repo: Repository in format 'owner/name'
        pr_number: PR number
        body: Comment text
        path: File path (for line comments)
        line: Line number (for line comments)
    
    Returns:
        Comment creation result
    """
    try:
        repository = get_repo(repo)
        pr = repository.get_pull(pr_number)
        
        if path and line:
            # Create line comment
            commit = pr.get_commits()[pr.commits - 1]
            comment = pr.create_review_comment(
                body=body,
                commit=commit,
                path=path,
                line=line,
            )
        else:
            # Create general comment
            comment = pr.create_issue_comment(body)
        
        return {
            "id": comment.id,
            "url": comment.html_url,
        }
    
    except GithubException as e:
        raise Exception(f"Error adding comment: {e.data.get('message', str(e))}")
