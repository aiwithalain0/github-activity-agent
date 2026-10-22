
# AI-Powered GitHub Commit & Comment Analysis Agent

An AI-powered Python application that analyzes new GitHub repository activity using the GitHub REST API and CrewAI agents.

The goal is to help developers catch up on repository changes by summarizing commits, identifying modified files, and extracting useful information from issue and pull-request comments.

## Features

- Retrieve GitHub commits and their changed files.
- Fetch issue and pull-request comments.
- Use dedicated CrewAI agents to analyze commits and discussions.
- Track the previous execution timestamp.
- Detect new activity since the previous successful check.
- Generate Markdown reports containing the analysis.
- Skip AI analysis when no new activity is found.
- Keep generated reports and API credentials out of Git.

## Technology Stack

- Python 3.12
- CrewAI
- GitHub REST API
- Requests
- python-dotenv
- Groq API for language-model inference

## Project Structure

```text
github-activity-agent/
├── src/
│   ├── main.py
│   ├── github_client.py
│   ├── crew_setup.py
│   └── tasks.py
├── data/
│   └── last_run.txt
├── reports/
├── .env
├── .gitignore
├── requirements.txt
└── README.md
```

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/aiwithalain0/github-activity-agent.git
cd github-activity-agent
```

### 2. Create and activate a virtual environment

On Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```powershell
python -m pip install -r requirements.txt
```

### 4. Configure environment variables

Create a `.env` file in the project root:

```dotenv
GITHUB_TOKEN=your_github_token
GITHUB_OWNER=your_github_username
GITHUB_REPO=your_repository_name
GROQ_API_KEY=your_groq_api_key
```

Use a GitHub token with the minimum permissions needed to read the target repository. Obtain a Groq API key from the Groq developer console.

**Never commit your `.env` file or expose your API keys.**

### 5. Run the agent

```powershell
python -m src.main
```

## How It Works

1. Connects to the configured GitHub repository.
2. Reads the timestamp saved from the previous successful check.
3. Retrieves commits and issue or pull-request comments newer than that timestamp.
4. Passes the retrieved activity to specialized CrewAI analysis agents.
5. Generates a Markdown report in the `reports/` directory.
6. Saves the execution timestamp for the next run.

When no new activity is found, the application skips AI analysis and updates the timestamp.

## Output

Generated reports are saved locally in the `reports/` directory.

Each report includes repository information, execution timestamps, commit analysis, changed files, and comment analysis.

The reports and execution timestamp are local runtime data and are not intended to be committed to Git.

## Limitations

- Analysis quality depends on the information returned by the GitHub API and the language model.
- Comments are analyzed only when available through the implemented GitHub API endpoints.
- AI-generated summaries should be verified against the actual code changes when making technical decisions.

## Author

[AI with Alain](https://github.com/aiwithalain0)
