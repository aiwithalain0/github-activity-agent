
import os

import requests
from dotenv import load_dotenv

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_OWNER = os.getenv("GITHUB_OWNER")
GITHUB_REPO = os.getenv("GITHUB_REPO")

API_URL = (
    f"https://api.github.com/repos/"
    f"{GITHUB_OWNER}/{GITHUB_REPO}"
)

HEADERS = {
    "Accept": "application/vnd.github+json",
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "X-GitHub-Api-Version": "2022-11-28",
}

TIMEOUT = 15
PAGE_SIZE = 100


def check_configuration():
    """Check required GitHub settings without displaying secrets."""
    missing = []

    if not GITHUB_TOKEN:
        missing.append("GITHUB_TOKEN")
    if not GITHUB_OWNER:
        missing.append("GITHUB_OWNER")
    if not GITHUB_REPO:
        missing.append("GITHUB_REPO")

    if missing:
        raise ValueError(
            "Missing .env settings: " + ", ".join(missing)
        )


def github_get(url, params=None):
    """Make a GitHub API request and raise clear errors on failure."""
    response = requests.get(
        url,
        headers=HEADERS,
        params=params,
        timeout=TIMEOUT,
    )

    try:
        response.raise_for_status()
    except requests.HTTPError as error:
        raise requests.HTTPError(
            f"GitHub API request failed "
            f"({response.status_code}) for {response.url}: "
            f"{response.text[:300]}",
            response=response,
        ) from error

    return response.json()


def get_paginated_results(url, params=None, limit=100):
    """Fetch multiple API pages until the limit or final page."""
    results = []
    page = 1

    while len(results) < limit:
        remaining = limit - len(results)
        page_size = min(PAGE_SIZE, remaining)

        page_params = dict(params or {})
        page_params.update({
            "per_page": page_size,
            "page": page,
        })

        page_results = github_get(url, page_params)

        if not isinstance(page_results, list):
            raise ValueError(
                f"Expected a list from GitHub API: {url}"
            )

        if not page_results:
            break

        results.extend(page_results)

        if len(page_results) < page_size:
            break

        page += 1

    return results


def test_github_connection():
    """Verify that the configured repository can be accessed."""
    repository = github_get(API_URL)
    print(f"Connected to: {repository['full_name']}")


def get_recent_commits(limit=100, since=None):
    """Retrieve commits and their changed-file details and patches."""
    if limit < 1:
        return []

    params = {
        "since": since,
    }

    # Do not send an empty since parameter.
    if not since:
        params = {}

    commits = get_paginated_results(
        f"{API_URL}/commits",
        params=params,
        limit=limit,
    )

    results = []

    for commit in commits:
        sha = commit["sha"]

        details = github_get(f"{API_URL}/commits/{sha}")

        author_data = commit.get("author") or {}
        commit_data = commit.get("commit") or {}
        author_details = commit_data.get("author") or {}

        files_changed = []

        for file in details.get("files", []):
            files_changed.append({
                "filename": file.get("filename", "Unknown"),
                "status": file.get("status", "unknown"),
                "additions": file.get("additions", 0),
                "deletions": file.get("deletions", 0),
                "changes": file.get("changes", 0),
                "patch": file.get("patch", ""),
                "blob_url": file.get("blob_url"),
                "contents_url": file.get("contents_url"),
            })

        results.append({
            "sha": sha,
            "short_sha": sha[:7],
            "author": author_data.get(
                "login",
                author_details.get("name", "Unknown"),
            ),
            "message": commit_data.get("message", ""),
            "date": author_details.get("date"),
            "html_url": commit.get("html_url"),
            "files_changed": files_changed,
            "stats": details.get("stats", {}),
        })

    return results


def get_issue_comments(since=None, limit=100):
    """Retrieve issue and PR conversation comments."""
    if limit < 1:
        return []

    params = {
        "sort": "updated",
        "direction": "asc",
    }

    if since:
        params["since"] = since

    raw_comments = get_paginated_results(
        f"{API_URL}/issues/comments",
        params=params,
        limit=limit,
    )

    comments = []

    for comment in raw_comments:
        user = comment.get("user") or {}

        comments.append({
            "comment_type": "issue_or_pr_conversation",
            "id": comment.get("id"),
            "author": user.get("login", "Unknown"),
            "body": comment.get("body", ""),
            "created_at": comment.get("created_at"),
            "updated_at": comment.get("updated_at"),
            "issue_url": comment.get("issue_url"),
            "html_url": comment.get("html_url"),
        })

    return comments


def get_pull_request_review_comments(since=None, limit=100):
    """Retrieve comments attached to lines of code in pull requests."""
    if limit < 1:
        return []

    params = {
        "sort": "updated",
        "direction": "asc",
    }

    if since:
        params["since"] = since

    raw_comments = get_paginated_results(
        f"{API_URL}/pulls/comments",
        params=params,
        limit=limit,
    )

    comments = []

    for comment in raw_comments:
        user = comment.get("user") or {}

        comments.append({
            "comment_type": "pull_request_review",
            "id": comment.get("id"),
            "author": user.get("login", "Unknown"),
            "body": comment.get("body", ""),
            "created_at": comment.get("created_at"),
            "updated_at": comment.get("updated_at"),
            "path": comment.get("path"),
            "line": comment.get("line"),
            "diff_hunk": comment.get("diff_hunk", ""),
            "commit_id": comment.get("commit_id"),
            "pull_request_url": comment.get("pull_request_url"),
            "html_url": comment.get("html_url"),
        })

    return comments


if __name__ == "__main__":
    try:
        check_configuration()
        test_github_connection()

        commits = get_recent_commits(limit=5)
        print(f"\nRecent commits found: {len(commits)}")

        for commit in commits:
            print("\n" + "=" * 50)
            print(f"SHA: {commit['short_sha']}")
            print(f"Author: {commit['author']}")
            print(f"Date: {commit['date']}")
            print(f"Message: {commit['message']}")
            print(f"Link: {commit['html_url']}")
            print("Changed files:")

            if not commit["files_changed"]:
                print("  No file details available.")
            else:
                for file in commit["files_changed"]:
                    print(
                        f"  {file['filename']} "
                        f"({file['status']}, "
                        f"+{file['additions']}, "
                        f"-{file['deletions']})"
                    )

                    if file["patch"]:
                        print("  Code patch available.")

        issue_comments = get_issue_comments(limit=100)
        review_comments = get_pull_request_review_comments(
            limit=100
        )

        print(
            "\nIssue/PR conversation comments: "
            f"{len(issue_comments)}"
        )
        print(
            "Pull-request review comments: "
            f"{len(review_comments)}"
        )

    except (requests.RequestException, ValueError) as error:
        print(f"Error: {error}")
