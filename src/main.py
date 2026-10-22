
from datetime import datetime, timezone
from pathlib import Path
import json
import os

from src.github_client import (
    check_configuration,
    test_github_connection,
    get_recent_commits,
    get_issue_comments,
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


def read_last_run():
    """Read the previous successful execution timestamp."""
    if not LAST_RUN_FILE.exists():
        return None

    timestamp = LAST_RUN_FILE.read_text(
        encoding="utf-8"
    ).strip()

    return timestamp or None


def save_last_run(timestamp):
    """Save the timestamp after a successful check or report."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LAST_RUN_FILE.write_text(timestamp, encoding="utf-8")


def main():
    """Fetch new GitHub activity, analyze it, and save a report."""
    check_configuration()
    test_github_connection()

    previous_run = read_last_run()

    print("\nPrevious successful run:")
    print(
        previous_run
        or "No previous timestamp; checking recent activity."
    )

    # Capture the start time before fetching activity.
    run_started_at = datetime.now(timezone.utc)

    print("\nFetching commits...")
    commits = get_recent_commits(
        limit=100,
        since=previous_run,
    )
    print(f"Commits retrieved: {len(commits)}")

    print("\nFetching issue and pull-request comments...")
    comments = get_issue_comments(
        since=previous_run,
        limit=100,
    )
    print(f"Comments retrieved: {len(comments)}")

    # Skip AI calls when no new activity exists.
    if not commits and not comments:
        print("\nNo new GitHub activity found.")
        print("Skipping CrewAI analysis.")

        save_last_run(run_started_at.isoformat())
        print(
            f"Updated last-run timestamp: "
            f"{run_started_at.isoformat()}"
        )
        return

    commit_data = json.dumps(
        commits,
        indent=2,
        ensure_ascii=False,
    )
    comment_data = json.dumps(
        comments,
        indent=2,
        ensure_ascii=False,
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

    crew = create_analysis_crew(
        commit_task,
        comment_task,
    )

    print("\nStarting CrewAI analysis...")
    crew.kickoff()

    # Read the result from each task separately.
    commit_result = commit_task.output.raw
    comment_result = comment_task.output.raw

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    report_generated_at = datetime.now(timezone.utc)
    report_timestamp = report_generated_at.strftime("%Y%m%d_%H%M%S")
    report_path = REPORTS_DIR / f"github_report_{report_timestamp}.md"

    report_content = (
        "# GitHub Activity Analysis\n\n"
        f"- Repository: {os.getenv('GITHUB_OWNER')}/"
        f"{os.getenv('GITHUB_REPO')}\n"
        f"- Previous run: {previous_run or 'First run'}\n"
        f"- Analysis started (UTC): {run_started_at.isoformat()}\n"
        f"- Report generated (UTC): {report_generated_at.isoformat()}\n"
        f"- Commits retrieved: {len(commits)}\n"
        f"- Comments retrieved: {len(comments)}\n\n"
        "## Commit Analysis\n\n"
        f"{commit_result}\n\n"
        "## Comment Analysis\n\n"
        f"{comment_result}\n"
    )

    report_path.write_text(report_content, encoding="utf-8")

    # Update the timestamp only after report generation succeeds.
    save_last_run(run_started_at.isoformat())

    print("\nAnalysis completed.")
    print(f"Report saved to: {report_path}")
    print(f"Saved last-run timestamp: {run_started_at.isoformat()}")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"\nError: {error}")
        raise
