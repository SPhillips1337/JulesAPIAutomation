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
    return Config(
        jules_api_key=os.environ["JULES_API_KEY"],
        github_token=os.environ["GITHUB_TOKEN"],
        ollama_url=os.getenv("OLLAMA_URL", "http://localhost:11434"),
        ollama_model=os.getenv("OLLAMA_MODEL", "qwen2.5:14b"),
        repo_owner=os.getenv("REPO_OWNER", "SPhillips1337"),
        repo_name=os.getenv("REPO_NAME", "LinkenIn-Poster"),
        source_id=os.getenv("SOURCE_ID", "sources/github/SPhillips1337/LinkenIn-Poster")
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
def jules_process_reviews(repo_owner: str, repo_name: str, pr_number: int, session_id: str) -> str:
    """Fetches PR reviews, assesses them via Ollama, and sends fix requests to Jules.

    Args:
        repo_owner: The GitHub repository owner.
        repo_name: The GitHub repository name.
        pr_number: The Pull Request number.
        session_id: The ID of the session.
    """
    f = io.StringIO()
    try:
        with redirect_stdout(f):
            automator.handle_amazon_q_reviews(repo_owner, repo_name, pr_number, session_id)
        return f.getvalue()
    except Exception as e:
        return f"Error processing reviews: {str(e)}\n{f.getvalue()}"

if __name__ == "__main__":
    mcp.run()
