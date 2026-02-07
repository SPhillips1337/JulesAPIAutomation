import os
import json
import time
import argparse
import requests
import sys
from dotenv import load_dotenv
from typing import Dict, List, Optional
from dataclasses import dataclass

@dataclass
class Config:
    jules_api_key: str
    github_token: str
    ollama_url: str
    ollama_model: str
    repo_owner: str
    repo_name: str
    source_id: str

class JulesAutomator:
    JULES_BASE_URL = "https://jules.googleapis.com/v1alpha"
    GITHUB_API_URL = "https://api.github.com"

    def __init__(self, config: Config):
        self.config = config
        self.headers_jules = {"X-Goog-Api-Key": config.jules_api_key, "Content-Type": "application/json"}
        self.headers_github = {
            "Authorization": f"token {config.github_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        self.state_file = os.path.join(os.path.dirname(__file__), ".jules_state.json")
        self.state = self._load_state()

    def _load_state(self) -> Dict:
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                pass
        return {"processed_comments": [], "processed_sessions": [], "active_sessions": {}}

    def _save_state(self):
        with open(self.state_file, "w") as f:
            json.dump(self.state, f, indent=4)

    def create_session(self, prompt: str, source: str, branch: str = "main", title: str = "Automated Task") -> str:
        url = f"{self.JULES_BASE_URL}/sessions"
        payload = {
            "prompt": prompt,
            "sourceContext": {
                "source": source,
                "githubRepoContext": {"startingBranch": branch}
            },
            "automationMode": "AUTO_CREATE_PR",
            "title": title
        }
        print(f"Making POST request to {url}...")
        response = requests.post(url, headers=self.headers_jules, json=payload)
        
        if response.status_code != 200:
            print(f"API Error: {response.status_code}")
            print(f"Response Body: {response.text}")
            if response.status_code == 404:
                print("\n[TIP] 404 'Entity not found' usually means your repository is not connected to Jules.")
                print("Visit https://jules.google.com to ensure the repo is tracked and open in your dashboard.")
            elif response.status_code == 401:
                print("\n[TIP] 401 'Unauthenticated' means your API key is invalid or lacks permissions.")
        
        response.raise_for_status()
        session_id = response.json().get("id")
        print(f"Created Jules session: {session_id}")
        return session_id

    def get_session(self, session_id: str) -> Dict:
        url = f"{self.JULES_BASE_URL}/sessions/{session_id}"
        response = requests.get(url, headers=self.headers_jules)
        response.raise_for_status()
        return response.json()

    def list_sessions(self, page_size: int = 10) -> List[Dict]:
        url = f"{self.JULES_BASE_URL}/sessions"
        params = {"pageSize": page_size}
        response = requests.get(url, headers=self.headers_jules, params=params)
        response.raise_for_status()
        return response.json().get("sessions", [])

    def poll_session(self, session_id: str, interval: int = 60) -> Optional[Dict]:
        while True:
            data = self.get_session(session_id)
            # Check for completion: Look for PR output or terminal status
            if "outputs" in data and any("pullRequest" in o for o in data["outputs"]):
                print(f"Session {session_id} completed with PR.")
                return data
            
            state = data.get("state", "UNKNOWN")
            print(f"Session {session_id} status: {state}... sleeping {interval}s")
            
            if state in ["COMPLETED", "FAILED", "CANCELLED"]:
                return data
                
            time.sleep(interval)

    def send_message(self, session_id: str, prompt: str) -> Dict:
        """Sends a message to the agent within an existing session."""
        url = f"{self.JULES_BASE_URL}/sessions/{session_id}:sendMessage"
        payload = {"prompt": prompt}
        response = requests.post(url, headers=self.headers_jules, json=payload)
        response.raise_for_status()
        return response.json()

    def list_activities(self, session_id: str) -> List[Dict]:
        """Retrieves the interaction log/activities of the agent."""
        url = f"{self.JULES_BASE_URL}/sessions/{session_id}/activities"
        response = requests.get(url, headers=self.headers_jules)
        response.raise_for_status()
        return response.json().get("activities", [])

    def fetch_pr_comments(self, pr_number: int) -> List[Dict]:
        url = f"{self.GITHUB_API_URL}/repos/{self.config.repo_owner}/{self.config.repo_name}/pulls/{pr_number}/comments"
        print(f"Fetching review comments from: {url}")
        response = requests.get(url, headers=self.headers_github)
        response.raise_for_status()
        comments = response.json()
        print(f"Total review comments found: {len(comments)}")
        
        # Filter for Amazon Q and unprocessed comments
        new_comments = []
        for c in comments:
            author = c['user']['login']
            if 'amazon-q-developer' in author and c['id'] not in self.state["processed_comments"]:
                new_comments.append(c)
        return new_comments

    def mark_comment_processed(self, comment_id: int):
        if comment_id not in self.state["processed_comments"]:
            self.state["processed_comments"].append(comment_id)
            self._save_state()

    def assess_with_ollama(self, comments: List[Dict]) -> bool:
        prompt = f"Assess the following code review comments for security vulnerabilities or critical logic errors:\n\n"
        for c in comments:
            prompt += f"- {c['user']['login']}: {c['body']}\n"
        prompt += "\nRespond with 'YES' if any core issues need fixing, otherwise 'NO'."

        payload = {
            "model": self.config.ollama_model,
            "prompt": prompt,
            "stream": False
        }
        try:
            url = f"{self.config.ollama_url.rstrip('/')}/api/generate"
            response = requests.post(url, json=payload, timeout=30)
            response.raise_for_status()
            assessment = response.json().get("response", "").strip().upper()
            return "YES" in assessment
        except Exception as e:
            print(f"Ollama assessment failed: {e}")
            return None

    def handle_amazon_q_reviews(self, pr_number: int, session_id: str):
        """Fetches reviews, assesses them, and sends a single batch message to Jules."""
        comments = self.fetch_pr_comments(pr_number)
        if not comments:
            print(f"No new Amazon Q comments for PR #{pr_number}.")
            return

        print(f"Found {len(comments)} new comments. Assessing with Ollama...")
        assessment = self.assess_with_ollama(comments)
        
        if assessment is True:
            message = "The following logic and security issues were identified in the PR review. Please fix them:\n\n"
            for c in comments:
                message += f"File: {c['path']} (Line {c.get('line', 'N/A')}):\n{c['body']}\n\n"
            
            print(f"Sending batch fix request to session {session_id}...")
            self.send_message(session_id, message)
            
            for c in comments:
                self.mark_comment_processed(c['id'])
            print("Successfully communicated fixes to Jules.")
        elif assessment is False:
            print("Ollama determined no critical fixes are required.")
            for c in comments:
                self.mark_comment_processed(c['id'])
        else:
            print("Skipping processing due to Ollama failure (Connection issues?).")

    def run_loop(self, initial_prompt: str, source: str, branch: str = "main"):
        current_prompt = initial_prompt
        current_branch = branch

        while True:
            session_id = self.create_session(current_prompt, source, current_branch)
            session_data = self.poll_session(session_id)
            
            if "outputs" in session_data:
                # Potential for automated iteration based on PR comments here
                print("Session completed. Check the generated PR for details.")
            break

if __name__ == "__main__":
    load_dotenv()
    
    parser = argparse.ArgumentParser(description="Jules Automator CLI")
    parser.add_argument("--prompt", help="Initial prompt or path to a prompt file")
    parser.add_argument("--session_id", help="Session ID for status/message/review operations")
    parser.add_argument("--pr", type=int, help="Pull Request number (used in 'review' mode)")
    parser.add_argument("--title", default="Automated Task", help="Title for the new session")
    parser.add_argument("--branch", default="main", help="Starting branch for new sessions")
    parser.add_argument("--mode", choices=["create", "message", "loop", "status", "list", "activities", "review"], default="loop", help="Operation mode")
    
    args = parser.parse_args()

    config = Config(
        jules_api_key=os.getenv("JULES_API_KEY", ""),
        github_token=os.getenv("GITHUB_TOKEN", ""),
        ollama_url=os.getenv("OLLAMA_URL", "http://localhost:11434"),
        ollama_model=os.getenv("OLLAMA_MODEL", "qwen2.5:14b"),
        repo_owner=os.getenv("REPO_OWNER", "SPhillips1337"),
        repo_name=os.getenv("REPO_NAME", "LinkenIn-Poster"),
        source_id=os.getenv("SOURCE_ID", "sources/github/SPhillips1337/LinkenIn-Poster")
    )
    
    if not config.jules_api_key or not config.github_token:
        print("Error: JULES_API_KEY and GITHUB_TOKEN must be set in environment.")
        sys.exit(1)

    automator = JulesAutomator(config)

    prompt_content = None
    if args.prompt:
        if os.path.exists(args.prompt):
            with open(args.prompt, 'r') as f:
                prompt_content = f.read()
        else:
            prompt_content = args.prompt

    if args.mode == "create" and prompt_content:
        automator.create_session(prompt_content, config.source_id, branch=args.branch, title=args.title)
    elif args.mode == "message" and args.session_id and prompt_content:
        automator.send_message(args.session_id, prompt_content)
    elif args.mode == "loop" and prompt_content:
        automator.run_loop(prompt_content, config.source_id, branch=args.branch)
    elif args.mode == "status" and args.session_id:
        status = automator.get_session(args.session_id)
        print(json.dumps(status, indent=2))
    elif args.mode == "list":
        sessions = automator.list_sessions()
        for s in sessions:
            print(f"ID: {s.get('id')} | Title: {s.get('title')} | State: {s.get('state')}")
    elif args.mode == "activities" and args.session_id:
        activities = automator.list_activities(args.session_id)
        print(json.dumps(activities, indent=2))
    elif args.mode == "review" and args.pr and args.session_id:
        automator.handle_amazon_q_reviews(args.pr, args.session_id)
    else:
        if args.mode == "review" and (not args.pr or not args.session_id):
            print("Error: 'review' mode requires both --pr and --session_id.")
        else:
            print("Invalid arguments or missing prompt/ID. Use --help for usage.")
