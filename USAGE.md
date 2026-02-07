# Usage Guide

This guide explains how to set up and run the JulesAPI iteration loop.

## 📋 Prerequisites

- Python 3.8+
- [Ollama](https://ollama.com/) running locally.
- Google Jules API access.
- GitHub Personal Access Token with repo scope.

## 🛠️ Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/JoeBloggs/GitProject.git
   cd GitProject
   ```

2. **Configure Environment Variables**:
   Copy the example environment file and fill in your keys:
   ```bash
   cp .env.example .env
   ```
   Edit `.env` with your `JULES_API_KEY`, `GITHUB_TOKEN`, and `OLLAMA_URL`.

3. **Install Dependencies**:
   ```bash
   pip install requests
   ```

## 🏃 Running the Automator

The `jules_automator.py` script provides a CLI for managing Jules sessions and automating code reviews.

### CLI Modes

- **loop** (Default): Creates a new session and polls for completion.
  ```bash
  python3 jules_automator.py --prompt "Refactor codebase" --branch main
  ```
- **create**: Creates a session and exits.
  ```bash
  python3 jules_automator.py --mode create --prompt "prompt.txt" --title "My Task"
  ```
- **message**: Sends a message to an existing session.
  ```bash
  python3 jules_automator.py --mode message --session_id <ID> --prompt "Check for bugs"
  ```
- **status**: Gets current session status (JSON).
  ```bash
  python3 jules_automator.py --mode status --session_id <ID>
  ```
- **list**: Lists recent sessions.
  ```bash
  python3 jules_automator.py --mode list
  ```
- **review**: Processes Amazon Q reviews for a PR and sends fixes to Jules.
  ```bash
  python3 jules_automator.py --mode review --pr <PR_NUM> --session_id <ID>
  ```

## 🔍 Monitoring & State

- **State Management**: The script tracks processed PR comments in `.jules_state.json` to avoid duplicate processing.
- **Ollama Integration**: Uses a local Ollama instance to assess if PR reviews require code changes before prompting Jules.
- **Activities**: View internal agent logs with `python3 jules_automator.py --mode activities --session_id <ID>`.
