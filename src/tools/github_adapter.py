"""GitHub API integration using PyGithub."""

import base64
from typing import Any
import importlib

# Use importlib to avoid potential shadowing issues with local modules
try:
    github_pkg = importlib.import_module("github")
    Github = github_pkg.Github
    GithubException = github_pkg.GithubException
except (ImportError, AttributeError) as e:
    print(f"DEBUG Error importing github: {e}")
    # Fallback or re-raise with more info
    raise

from src.config.settings import get_settings

def get_github_client() -> Github:
    """Get GitHub client."""
    settings = get_settings()
    return Github(settings.github_token)

def get_repo(repo: str) -> Any:
    """Get repository object."""
    client = get_github_client()
    return client.get_repo(repo)

def get_issue_details(repo: str, issue_number: int) -> dict:
    """Get issue details."""
    repository = get_repo(repo)
    issue = repository.get_issue(issue_number)
    return {
        "title": issue.title,
        "body": issue.body,
        "number": issue.number,
        "labels": [label.name for label in issue.get_labels()]
    }

def get_pr_details(repo: str, pr_number: int) -> dict:
    """Get pull request details."""
    repository = get_repo(repo)
    pr = repository.get_pull(pr_number)
    return {
        "title": pr.title,
        "body": pr.body,
        "number": pr.number,
        "base": pr.base.ref,
        "head": pr.head.ref
    }

def create_pull_request(repo: str, title: str, body: str, head: str, base: str = "develop") -> Any:
    """Create pull request."""
    repository = get_repo(repo)
    return repository.create_pull(title=title, body=body, head=head, base=base)

def add_pr_review_comment(repo: str, pr_number: int, body: str) -> Any:
    """Add review comment to PR."""
    repository = get_repo(repo)
    pr = repository.get_pull(pr_number)
    return pr.create_issue_comment(body)
