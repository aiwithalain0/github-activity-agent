
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


def test_github_connection():
    """Verify that the repository can be accessed."""
    response = requests.get(
        API_URL,
        headers=HEADERS,
        timeout=15,
    )
    response.raise_for_status()

    repository = response.json()
    print(f"Connected to: {repository['full_name']}")


def get_recent_commits(limit=5, since=None):
    """Retrieve commits, optionally limited to those after a timestamp."""
    url = f"{API_URL}/commits"

    params = {"per_page": limit}

    if since:
        params["since"] = since

    response = requests.get(
        url,
        headers=HEADERS,
        params=params,
        timeout=15,
    )
    response.raise_for_status()

    results = []

    for commit in response.json():
        sha = commit["sha"]

        details_response = requests.get(
            f"{API_URL}/commits/{sha}",
            headers=HEADERS,
            timeout=15,
        )
        details_response.raise_for_status()

        details = details_response.json()
        author = commit.get("author") or {}

        results.append({
            "sha": sha,
            "author": author.get("login", "Unknown"),
            "message": commit["commit"]["message"],
            "date": commit["commit"]["author"]["date"],
            "files_changed": [
                {
                    "filename": file["filename"],
                    "status": file["status"],
                    "additions": file["additions"],
                    "deletions": file["deletions"],
                }
                for file in details.get("files", [])
            ],
        })

    return results


def get_issue_comments(since=None, limit=100):
    """Retrieve issue and pull-request comments, optionally since a timestamp."""
    url = f"{API_URL}/issues/comments"
    comments = []
    page = 1

    while len(comments) < limit:
        remaining = limit - len(comments)
        page_size = min(100, remaining)

        params = {
            "per_page": page_size,
            "page": page,
            "sort": "updated",
            "direction": "asc",
        }

        if since:
            params["since"] = since

        response = requests.get(
            url,
            headers=HEADERS,
            params=params,
            timeout=15,
        )
        response.raise_for_status()

        page_comments = response.json()

        if not page_comments:
            break

        for comment in page_comments:
            comments.append({
                "id": comment["id"],
                "author": (
                    comment.get("user") or {}
                ).get("login", "Unknown"),
                "body": comment.get("body", ""),
                "created_at": comment.get("created_at"),
                "updated_at": comment.get("updated_at"),
                "issue_url": comment.get("issue_url"),
                "html_url": comment.get("html_url"),
            })

        if len(page_comments) < page_size:
            break

        page += 1

    return comments


if __name__ == "__main__":
    try:
        check_configuration()
        test_github_connection()

        commits = get_recent_commits(limit=5)
        print(f"\nRecent commits found: {len(commits)}")

        for commit in commits:
            print("\n" + "=" * 50)
            print(f"SHA: {commit['sha'][:7]}")
            print(f"Author: {commit['author']}")
            print(f"Date: {commit['date']}")
            print(f"Message: {commit['message']}")
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

        comments = get_issue_comments(limit=100)
        print(
            f"\nIssue and pull-request comments found: {len(comments)}"
        )

    except (requests.RequestException, ValueError) as error:
        print(f"Error: {error}")
