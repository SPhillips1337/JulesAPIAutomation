import os
import json
import time
import requests
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

    def poll_session(self, session_id: str, interval: int = 60) -> Optional[Dict]:
        url = f"{self.JULES_BASE_URL}/sessions/{session_id}"
        while True:
            response = requests.get(url, headers=self.headers_jules)
            response.raise_for_status()
            data = response.json()
            # Check for completion: Look for PR output or terminal status
            if "outputs" in data and any("pullRequest" in o for o in data["outputs"]):
                print(f"Session {session_id} completed with PR.")
                return data
            print(f"Session {session_id} still in progress... sleeping {interval}s")
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
        response = requests.get(url, headers=self.headers_github)
        response.raise_for_status()
        return response.json()

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
            response = requests.post(f"{self.config.ollama_url}/api/generate", json=payload)
            response.raise_for_status()
            assessment = response.json().get("response", "").strip().upper()
            return "YES" in assessment
        except Exception as e:
            print(f"Ollama assessment failed: {e}")
            return False

    def run_loop(self, initial_prompt: str, source: str):
        current_prompt = initial_prompt
        current_branch = "main"

        while True:
            session_id = self.create_session(current_prompt, source, current_branch)
            session_data = self.poll_session(session_id)
            
            # Extract PR number from outputs (mock logic)
            # pr_url = session_data['outputs'][0]['pullRequest']['url']
            # pr_number = pr_url.split('/')[-1]
            
            # Dummy logic for PoC:
            print("Session finished. Fetching reviews...")
            # comments = self.fetch_pr_comments(pr_number)
            # needs_fix = self.assess_with_ollama(comments)
            
            needs_fix = False # Placeholder
            if not needs_fix:
                print("No critical issues found. Task complete.")
                break
            
            print("Issues detected. Refining prompt and restarting...")
            # current_prompt = refine_prompt(current_prompt, comments)
            # current_branch = head_branch_of_pr
            time.sleep(5)

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    config = Config(
        jules_api_key=os.getenv("JULES_API_KEY"),
        github_token=os.getenv("GITHUB_TOKEN"),
        ollama_url=os.getenv("OLLAMA_URL"),
        ollama_model=os.getenv("OLLAMA_MODEL"),
        repo_owner=os.getenv("REPO_OWNER"),
        repo_name=os.getenv("REPO_NAME")
    )

    if not config.jules_api_key:
        print("Error: JULES_API_KEY not found in .env")
        exit(1)

    work_order_path = "jules_work_order.txt"
    if not os.path.exists(work_order_path):
        print(f"Error: {work_order_path} not found")
        exit(1)

    with open(work_order_path, "r") as f:
        prompt = f.read()

    source_id = os.getenv("SOURCE_ID", f"sources/github/{config.repo_owner}/{config.repo_name}")
    
    automator = JulesAutomator(config)
    print(f"Scheduling work order for {config.repo_name}...")
    
    try:
        session_id = automator.create_session(
            prompt=prompt,
            source=source_id,
            title="Songbird V2 Optimization"
        )
        print(f"Successfully scheduled! Session ID: {session_id}")
        print("You can monitor the progress on the Jules dashboard or I can poll for completion.")
    except Exception as e:
        print(f"Failed to schedule session: {e}")
