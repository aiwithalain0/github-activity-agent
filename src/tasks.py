
from crewai import Task


def create_commit_analysis_task(agent, commits):
    """Create a task to summarize commits and changed files."""
    return Task(
        description=(
            "Analyze the following GitHub commit activity:\n\n"
            "{commits}\n\n"
            "For each commit, report:\n"
            "1. Commit message and author.\n"
            "2. Important files changed.\n"
            "3. What the changes appear to accomplish.\n"
            "4. Any limitations in the available evidence.\n\n"
            "Use only the supplied data. Do not invent features or details. "
            "If there are no commits, state that clearly."
        ).format(commits=commits),
        expected_output=(
            "A concise, structured commit report covering commit messages, "
            "authors, changed files, likely purpose, and evidence limitations."
        ),
        agent=agent,
    )


def create_comment_analysis_task(agent, comments):
    """Create a task to analyze GitHub comments and discussions."""
    return Task(
        description=(
            "Analyze the following GitHub issue and pull-request comments:\n\n"
            "{comments}\n\n"
            "Identify reported bugs, suggestions, decisions, unresolved "
            "questions, and requested follow-up actions. Distinguish facts "
            "from opinions. Do not invent discussions. If there are no "
            "comments, state that no comments were available to analyze."
        ).format(comments=comments),
        expected_output=(
            "A structured comment analysis listing important discussions, "
            "suggestions, unresolved issues, and follow-up actions, or "
            "clearly stating that no comments were found."
        ),
        agent=agent,
    )
