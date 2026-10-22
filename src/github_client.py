
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


def test_github_connection():
    response = requests.get(
        API_URL,
        headers=HEADERS,
        timeout=15,
    )
    response.raise_for_status()

    repository = response.json()
    print(f"Connected to: {repository['full_name']}")


def get_recent_commits(limit=5):
    url = f"{API_URL}/commits"

    response = requests.get(
        url,
        headers=HEADERS,
        params={"per_page": limit},
        timeout=15,
    )
    response.raise_for_status()

    commits = response.json()
    results = []

    for commit in commits:
        sha = commit["sha"]

        details_response = requests.get(
            f"{API_URL}/commits/{sha}",
            headers=HEADERS,
            timeout=15,
        )
        details_response.raise_for_status()
        details = details_response.json()

        results.append({
            "sha": sha,
            "author": (
                commit.get("author") or {}
            ).get("login", "Unknown"),
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


if __name__ == "__main__":
    try:
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

    except requests.RequestException as error:
        print(f"GitHub API error: {error}")
