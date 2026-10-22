
import os

from dotenv import load_dotenv
from crewai import Agent, Crew, LLM, Process

# Work around CrewAI passing an unsupported cache_breakpoint
# field to providers such as Groq.
import crewai.llms.cache as crew_cache
import crewai.experimental.agent_executor as experimental_executor

crew_cache.mark_cache_breakpoint = lambda message: message
experimental_executor.mark_cache_breakpoint = lambda message: message

load_dotenv()

groq_api_key = os.getenv("GROQ_API_KEY")

if not groq_api_key:
    raise ValueError(
        "GROQ_API_KEY is missing. Add it to your .env file."
    )

llm = LLM(
    model="groq/openai/gpt-oss-120b",
    api_key=groq_api_key,
)


def create_activity_analyst():
    return Agent(
        role="GitHub Activity Analyst",
        goal=(
            "Explain what changed in GitHub commits and which files "
            "were affected, using only the available evidence."
        ),
        backstory=(
            "You are a software development analyst who writes accurate, "
            "concise commit summaries without inventing details."
        ),
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )


def create_comment_analyst():
    return Agent(
        role="Code Review Analyst",
        goal=(
            "Identify important discussions, reported bugs, suggestions, "
            "unresolved questions, and follow-up actions from GitHub comments."
        ),
        backstory=(
            "You are a careful code-review analyst who distinguishes "
            "facts from suggestions and never invents discussions."
        ),
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )


def create_analysis_crew(commit_task, comment_task):
    """Create a sequential crew with two dedicated analysis agents."""
    return Crew(
        agents=[commit_task.agent, comment_task.agent],
        tasks=[commit_task, comment_task],
        process=Process.sequential,
        verbose=True,
    )
