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

## 🏃 Running the Loop

The main entry point is `jules_automator.py`. You can run a task by providing a prompt and a source context, and the script will handle the rest. It is designed to be run in a loop, with the script handling the iteration and decision-making can easily be operated by AI tooling such as Gemini 3 Flash in Google Antigravity IDE by asking it to use the JulesAPI scripts provided.

```python
from jules_automator import JulesAutomator, Config

config = Config(
    jules_api_key="...",
    github_token="...",
    ollama_url="http://localhost:11434",
    ollama_model="qwen2.5:14b",
    repo_owner="JoeBloggs",
    repo_name="GitProject"
)

automator = JulesAutomator(config)
automator.run_loop(
    initial_prompt="Add performance analytics to the user dashboard",
    source="sources/github/JoeBloggs/GitProject"
)
```

## 🔍 Monitoring

- **Terminal Output**: The script logs session creation, PR URLs, and Ollama assessments.
- **Jules Logs**: Use `list_activities(session_id)` to see the internal agent logs.
- **GitHub**: Check the generated Pull Request for comments from `amazon-q-developer`.
