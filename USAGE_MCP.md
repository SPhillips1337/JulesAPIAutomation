# Jules MCP Server Usage

This MCP server exposes Jules automation capabilities as standardized tools, allowing AI agents to interact with Jules sessions.

## Prerequisites

- Python 3.10+
- `pip`

## Installation

1.  Clone the repository.
2.  Install dependencies:

    ```bash
    pip install mcp python-dotenv requests
    ```

3.  Configure environment variables in `.env`:

    ```env
    JULES_API_KEY=your_jules_api_key
    GITHUB_TOKEN=your_github_token
    OLLAMA_URL=http://localhost:11434
    OLLAMA_MODEL=qwen2.5:14b
    REPO_OWNER=your_repo_owner
    REPO_NAME=your_repo_name
    SOURCE_ID=sources/github/your_repo_owner/your_repo_name
    ```

## Running the Server

To run the server locally (using stdio transport):

```bash
python jules_mcp_server.py
```

## Integrating with Claude Desktop

Add the following configuration to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "jules": {
      "command": "python",
      "args": ["/path/to/jules_mcp_server.py"],
      "env": {
        "JULES_API_KEY": "your_jules_api_key",
        "GITHUB_TOKEN": "your_github_token"
      }
    }
  }
}
```

## Available Tools

### Session Management

-   `jules_create_session(prompt, source_id, branch, title)`: Creates a new Jules session.
-   `jules_list_sessions(page_size)`: Retrieves a list of recent sessions.
-   `jules_get_status(session_id)`: Returns the current state and outputs of a session.

### Interaction

-   `jules_send_message(session_id, prompt)`: Sends a follow-up prompt to an active session.
-   `jules_get_activities(session_id)`: Retrieves the internal interaction log for a session.

### Automated Reviews

-   `jules_process_reviews(pr_number, session_id)`: Fetches PR reviews, assesses them via Ollama, and sends fix requests to Jules.

## Troubleshooting

-   Ensure Ollama is running if you plan to use `jules_process_reviews`.
-   Check `.env` file for correct API keys.
