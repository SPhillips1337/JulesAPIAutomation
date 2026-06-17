import os
import io
from contextlib import redirect_stdout
from typing import Optional, List, Dict
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from jules_automator import JulesAutomator, Config

# Load environment variables
load_dotenv()

# Initialize FastMCP server
mcp = FastMCP("Jules MCP Server")

def get_config() -> Config:
    repo_owner = os.getenv("REPO_OWNER") or "SPhillips1337"
    repo_name = os.getenv("REPO_NAME") or "LinkenIn-Poster"
    return Config(
        jules_api_key=os.getenv("JULES_API_KEY") or "",
        github_token=os.getenv("GITHUB_TOKEN") or "",
        ollama_url=os.getenv("OLLAMA_URL") or "http://localhost:11434",
        ollama_model=os.getenv("OLLAMA_MODEL") or "qwen2.5:14b",
        repo_owner=repo_owner,
        repo_name=repo_name,
        source_id=os.getenv("SOURCE_ID") or f"sources/github/{repo_owner}/{repo_name}"
    )

automator = JulesAutomator(get_config())

@mcp.tool()
def jules_create_session(prompt: str, source_id: str, branch: str = "main", title: str = "Automated Task") -> str:
    """Creates a new Jules session.

    Args:
        prompt: The prompt for the session.
        source_id: The source ID formatted as 'sources/github/owner/repo'.
        branch: The starting branch (defaults to "main").
        title: The title of the session.
    """
    return automator.create_session(prompt, source_id, branch, title)

@mcp.tool()
def jules_list_sessions(page_size: int = 10) -> List[Dict]:
    """Retrieves a list of recent sessions.

    Args:
        page_size: The number of sessions to retrieve.
    """
    return automator.list_sessions(page_size)

@mcp.tool()
def jules_get_status(session_id: str) -> Dict:
    """Returns the current state and outputs of a session.

    Args:
        session_id: The ID of the session.
    """
    return automator.get_session(session_id)

@mcp.tool()
def jules_send_message(session_id: str, prompt: str) -> Dict:
    """Sends a follow-up prompt to an active session.

    Args:
        session_id: The ID of the session.
        prompt: The message content.
    """
    return automator.send_message(session_id, prompt)

@mcp.tool()
def jules_get_activities(session_id: str) -> List[Dict]:
    """Retrieves the internal interaction log for a session.

    Args:
        session_id: The ID of the session.
    """
    return automator.list_activities(session_id)

@mcp.tool()
def jules_process_reviews(pr_number: int, session_id: str, repo_owner: Optional[str] = None, repo_name: Optional[str] = None) -> str:
    """Fetches PR reviews, performs Agent-to-Agent check, decides via Ollama, and executes fixes.

    Args:
        pr_number: The Pull Request number.
        session_id: The ID of the session.
        repo_owner: Optional GitHub repository owner (defaults to config).
        repo_name: Optional GitHub repository name (defaults to config).
    """
    owner = repo_owner or automator.config.repo_owner
    name = repo_name or automator.config.repo_name
    f = io.StringIO()
    try:
        with redirect_stdout(f):
            automator.handle_amazon_q_reviews(owner, name, pr_number, session_id)
        return f.getvalue()
    except Exception as e:
        return f"Error processing reviews: {str(e)}\n{f.getvalue()}"

if __name__ == "__main__":
    mcp.run()
