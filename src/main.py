
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from src.github_client import (
    check_configuration,
    test_github_connection,
    get_recent_commits,
    get_issue_comments,
    get_pull_request_review_comments,
)
from src.crew_setup import (
    create_activity_analyst,
    create_comment_analyst,
    create_analysis_crew,
)
from src.tasks import (
    create_commit_analysis_task,
    create_comment_analysis_task,
)


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
REPORTS_DIR = BASE_DIR / "reports"
LAST_RUN_FILE = DATA_DIR / "last_run.txt"

# Keep AI requests bounded to reduce Groq token-limit errors.
AI_MAX_COMMITS = 4
AI_MAX_FILES_PER_COMMIT = 2
AI_MAX_PATCH_CHARS_PER_FILE = 1000
AI_MAX_COMMENTS = 5
AI_MAX_COMMENT_CHARS = 600
AI_MAX_COMMIT_MESSAGE_CHARS = 400


def read_last_run():
    """Read the timestamp of the previous run."""
    if not LAST_RUN_FILE.exists():
        return None

    timestamp = LAST_RUN_FILE.read_text(
        encoding="utf-8"
    ).strip()

    return timestamp or None


def save_last_run(timestamp):
    """Save the timestamp after processing."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LAST_RUN_FILE.write_text(timestamp, encoding="utf-8")


def build_ai_commit_data(commits):
    """
    Build a compact AI payload containing commit metadata
    and bounded excerpts of actual code changes.
    """
    compact_commits = []

    for commit in commits[:AI_MAX_COMMITS]:
        files = []
        changed_files = commit.get("files_changed", [])

        for file_info in changed_files[:AI_MAX_FILES_PER_COMMIT]:
            patch = file_info.get("patch") or ""

            # Limit each patch excerpt to control prompt size.
            patch_excerpt = str(patch)[:AI_MAX_PATCH_CHARS_PER_FILE]

            files.append({
                "filename": str(
                    file_info.get("filename", "Unknown")
                )[:200],
                "status": file_info.get("status", "unknown"),
                "additions": file_info.get("additions", 0),
                "deletions": file_info.get("deletions", 0),
                "changes": file_info.get("changes", 0),
                "patch_excerpt": (
                    patch_excerpt
                    if patch_excerpt
                    else "Patch unavailable from GitHub API."
                ),
                "patch_truncated": (
                    bool(patch)
                    and len(str(patch)) > AI_MAX_PATCH_CHARS_PER_FILE
                ),
            })

        compact_commits.append({
            "sha": commit.get("short_sha", "Unknown"),
            "message": str(
                commit.get("message", "No commit message")
            )[:AI_MAX_COMMIT_MESSAGE_CHARS],
            "author": str(commit.get("author", "Unknown"))[:100],
            "url": commit.get("html_url", ""),
            "files_changed": files,
            "total_files_reported": len(changed_files),
            "files_included_in_ai_input": len(files),
        })

    return json.dumps(
        compact_commits,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def build_ai_comment_data(comments):
    """Create a compact comment payload for AI analysis."""
    compact_comments = []

    for comment in comments[:AI_MAX_COMMENTS]:
        body = (
            comment.get("body")
            or comment.get("comment")
            or comment.get("text")
            or ""
        )

        compact_comments.append({
            "author": str(comment.get("author", "Unknown"))[:100],
            "body": str(body)[:AI_MAX_COMMENT_CHARS],
            "url": (
                comment.get("html_url")
                or comment.get("url")
                or ""
            ),
            "created_at": comment.get("created_at", ""),
        })

    return json.dumps(
        compact_comments,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def build_contributor_summary(commits, comments):
    """Count commit and comment activity for each contributor."""
    activity = {}

    for commit in commits:
        name = commit.get("author") or "Unknown"
        activity.setdefault(
            name, {"commits": 0, "comments": 0}
        )
        activity[name]["commits"] += 1

    for comment in comments:
        name = comment.get("author") or "Unknown"
        activity.setdefault(
            name, {"commits": 0, "comments": 0}
        )
        activity[name]["comments"] += 1

    if not activity:
        return "No contributor activity found.\n"

    lines = [
        "| Contributor | Commits | Comments |",
        "|---|---:|---:|",
    ]

    for name, counts in sorted(activity.items()):
        lines.append(
            f"| {name} | {counts['commits']} | "
            f"{counts['comments']} |"
        )

    return "\n".join(lines) + "\n"


def build_file_summary(commits):
    """Summarize changed files using GitHub API metadata."""
    files = {}

    for commit in commits:
        for file_info in commit.get("files_changed", []):
            name = file_info.get("filename", "Unknown")

            entry = files.setdefault(
                name,
                {
                    "status": file_info.get("status", "unknown"),
                    "additions": 0,
                    "deletions": 0,
                    "commits": set(),
                },
            )

            entry["additions"] += file_info.get("additions", 0) or 0
            entry["deletions"] += file_info.get("deletions", 0) or 0
            entry["commits"].add(commit.get("short_sha", ""))

    if not files:
        return "No changed-file details found.\n"

    lines = [
        "| File | Status | Additions | Deletions | Commits |",
        "|---|---|---:|---:|---|",
    ]

    for name, details in sorted(files.items()):
        commit_ids = ", ".join(
            sorted(value for value in details["commits"] if value)
        )

        lines.append(
            f"| `{name}` | {details['status']} | "
            f"{details['additions']} | {details['deletions']} | "
            f"{commit_ids or 'Unknown'} |"
        )

    return "\n".join(lines) + "\n"


def build_commit_links(commits):
    """Create a factual list of commits and changed-file links."""
    if not commits:
        return "No commits found in this analysis period.\n"

    lines = []

    for commit in commits:
        message = commit.get("message", "No commit message")
        author = commit.get("author", "Unknown")
        sha = commit.get("short_sha", "Unknown")
        url = commit.get("html_url", "")

        if url:
            lines.append(
                f"- [{sha}: {message}]({url}) — Author: {author}"
            )
        else:
            lines.append(
                f"- {sha}: {message} — Author: {author}"
            )

        for file_info in commit.get("files_changed", []):
            filename = file_info.get("filename", "Unknown")
            file_url = file_info.get("blob_url")

            if file_url:
                lines.append(f"  - [{filename}]({file_url})")
            else:
                lines.append(f"  - `{filename}`")

    return "\n".join(lines) + "\n"


def main():
    """Fetch GitHub activity, analyze it, and save a report."""
    parser = argparse.ArgumentParser(
        description="Analyze GitHub repository activity."
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Analyze historical activity instead of only new activity.",
    )
    args = parser.parse_args()

    check_configuration()
    test_github_connection()

    previous_run = read_last_run()
    run_started_at = datetime.now(timezone.utc)
    run_started_iso = run_started_at.isoformat()

    since_timestamp = None if args.full else previous_run

    if args.full:
        print("\nAnalysis mode: FULL HISTORICAL ANALYSIS")
    else:
        print("\nAnalysis mode: INCREMENTAL")

    print("\nPrevious successful run:")
    print(
        previous_run
        or "No previous timestamp; checking recent activity."
    )

    print("\nFetching commits...")
    commits = get_recent_commits(
        limit=100,
        since=since_timestamp,
    )
    print(f"Commits retrieved: {len(commits)}")

    print("\nFetching issue and pull-request conversation comments...")
    issue_comments = get_issue_comments(
        since=since_timestamp,
        limit=100,
    )
    print(f"Conversation comments retrieved: {len(issue_comments)}")

    print("\nFetching pull-request review comments...")
    review_comments = get_pull_request_review_comments(
        since=since_timestamp,
        limit=100,
    )
    print(f"Review comments retrieved: {len(review_comments)}")

    comments = issue_comments + review_comments

    if not commits and not comments:
        print("\nNo GitHub activity found for this analysis.")
        print("Skipping CrewAI analysis.")

        save_last_run(run_started_iso)
        print(f"Updated last-run timestamp: {run_started_iso}")
        return

    # Send only bounded payloads to the AI.
    # Keep all retrieved records for factual summaries and links.
    ai_commits = commits[:AI_MAX_COMMITS]
    ai_comments = comments[:AI_MAX_COMMENTS]

    commit_data = build_ai_commit_data(ai_commits)
    comment_data = build_ai_comment_data(ai_comments)

    print("\nPreparing bounded AI inputs...")
    print(
        f"AI commit records: {len(ai_commits)} "
        f"of {len(commits)} retrieved"
    )
    print(
        f"AI comment records: {len(ai_comments)} "
        f"of {len(comments)} retrieved"
    )
    print(
        "AI patch limits: "
        f"{AI_MAX_FILES_PER_COMMIT} files per commit, "
        f"{AI_MAX_PATCH_CHARS_PER_FILE} characters per file."
    )
    print(
        "The AI receives available patch excerpts, not complete diffs."
    )

    commit_analyst = create_activity_analyst()
    comment_analyst = create_comment_analyst()

    commit_task = create_commit_analysis_task(
        agent=commit_analyst,
        commits=commit_data,
    )
    comment_task = create_comment_analysis_task(
        agent=comment_analyst,
        comments=comment_data,
    )

    crew = create_analysis_crew(commit_task, comment_task)

    print("\nStarting CrewAI analysis...")
    crew.kickoff()

    commit_result = commit_task.output.raw
    comment_result = comment_task.output.raw

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    report_generated_at = datetime.now(timezone.utc)
    report_timestamp = report_generated_at.strftime("%Y%m%d_%H%M%S")
    report_path = REPORTS_DIR / f"github_report_{report_timestamp}.md"

    repository = (
        f"{os.getenv('GITHUB_OWNER')}/"
        f"{os.getenv('GITHUB_REPO')}"
    )

    contributor_summary = build_contributor_summary(commits, comments)
    file_summary = build_file_summary(commits)
    commit_links = build_commit_links(commits)

    report_content = (
        "# GitHub Activity Analysis\n\n"
        f"- Repository: [{repository}](https://github.com/{repository})\n"
        f"- Analysis mode: "
        f"{'Full historical' if args.full else 'Incremental'}\n"
        f"- Previous successful run: {previous_run or 'First run'}\n"
        f"- Analysis started (UTC): {run_started_iso}\n"
        f"- Report generated (UTC): {report_generated_at.isoformat()}\n"
        f"- Commits retrieved: {len(commits)}\n"
        f"- Conversation comments retrieved: {len(issue_comments)}\n"
        f"- Pull-request review comments retrieved: "
        f"{len(review_comments)}\n"
        f"- Commits supplied to AI: {len(ai_commits)}\n"
        f"- Comments supplied to AI: {len(ai_comments)}\n\n"
        "## Contributor Activity\n\n"
        f"{contributor_summary}\n"
        "## Changed Files (GitHub API Facts)\n\n"
        f"{file_summary}\n"
        "## Commits and File Links\n\n"
        f"{commit_links}\n"
        "## AI Commit Analysis\n\n"
        f"{commit_result}\n\n"
        "## AI Discussion and Review Analysis\n\n"
        f"{comment_result}\n\n"
        "## AI Analysis Coverage\n\n"
        f"- The AI received at most {AI_MAX_COMMITS} commits.\n"
        f"- At most {AI_MAX_FILES_PER_COMMIT} changed-file entries per "
        "commit were included in the AI input.\n"
        f"- Each available patch excerpt was limited to "
        f"{AI_MAX_PATCH_CHARS_PER_FILE} characters.\n"
        f"- The AI received at most {AI_MAX_COMMENTS} comments, with each "
        f"comment body limited to {AI_MAX_COMMENT_CHARS} characters.\n"
        "- GitHub may not provide a patch for every changed file.\n"
        "- The AI received excerpts, not complete diffs or the entire "
        "repository. Its code explanations may therefore be incomplete.\n"
        "- The factual summaries and links above use retrieved GitHub API "
        "records, which may cover more activity than the AI analyzed.\n\n"
        "## Interpretation Notes\n\n"
        "- Commit messages, authors, file names, statistics, and links "
        "come from GitHub API records.\n"
        "- AI explanations are interpretations of the supplied commit "
        "metadata, available patch excerpts, and comment text. They are "
        "not guaranteed to establish the author's intent.\n"
        "- Verify interpretations against the linked source changes "
        "when accuracy is critical.\n"
    )

    report_path.write_text(report_content, encoding="utf-8")
    save_last_run(run_started_iso)

    print("\nAnalysis completed.")
    print(f"Report saved to: {report_path}")
    print(f"Saved last-run timestamp: {run_started_iso}")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"\nError: {error}")
        raise
