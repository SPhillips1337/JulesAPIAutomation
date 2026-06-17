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

    def poll_session(self, session_id: str, interval: int = 15, wait_for_running: bool = False) -> Optional[Dict]:
        """Polls the session until completion, optionally waiting for it to enter a running state first."""
        if wait_for_running:
            print(f"Waiting for session {session_id} to transition to running state...")
            for _ in range(5):
                time.sleep(3)
                data = self.get_session(session_id)
                state = data.get("state", "UNKNOWN")
                if state not in ["COMPLETED", "FAILED", "CANCELLED"]:
                    print(f"Session has started running (state: {state}).")
                    break
            else:
                print("Session did not transition to running state; checking current state...")

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

    def get_session_summary(self, session_id: str):
        """Fetches session details and activities and prints a clean, human-readable summary of plans, explanations, and suggested changes."""
        try:
            session = self.get_session(session_id)
            print(f"==================================================")
            print(f"SESSION ID: {session_id}")
            print(f"TITLE:      {session.get('title', 'N/A')}")
            print(f"STATE:      {session.get('state', 'UNKNOWN')}")
            print(f"PROMPT:     {session.get('prompt', 'N/A')}")
            print(f"==================================================\n")
        except Exception as e:
            print(f"Error fetching session details: {e}")

        try:
            activities = self.list_activities(session_id)
        except Exception as e:
            print(f"Error fetching activities: {e}")
            return

        plans = []
        messages = []
        changes = []

        for act in activities:
            originator = act.get("originator")
            create_time = act.get("createTime")
            desc = act.get("description", "")

            # Check for plan generated
            if "planGenerated" in act:
                plan_data = act["planGenerated"]
                steps = plan_data.get("plan", {}).get("steps", [])
                if steps:
                    plans.append((create_time, steps))

            # Check for agent message
            msg = self._extract_agent_message(act)
            if msg and originator == "agent" and "Session completed" not in desc:
                messages.append((create_time, msg))

            # Check for artifacts / changes
            artifacts = act.get("artifacts", [])
            for art in artifacts:
                changeset = art.get("changeSet", {})
                if changeset:
                    git_patch = changeset.get("gitPatch", {})
                    commit_msg = git_patch.get("suggestedCommitMessage")
                    patch = git_patch.get("unidiffPatch")
                    if commit_msg or patch:
                        changes.append((create_time, commit_msg, patch))

        if plans:
            print("📋 JULES PLANS GENERATED:")
            for t, steps in plans:
                print(f"--- Plan at {t} ---")
                for i, step in enumerate(steps):
                    print(f"  {i+1}. {step.get('description', 'No description')}")
            print()

        if messages:
            print("💬 JULES COMMUNICATIONS/EXPLANATIONS:")
            for t, msg in messages:
                print(f"--- Message at {t} ---")
                print(msg.strip())
                print()

        if changes:
            print("🧹 SUGGESTED IMPROVEMENTS & CODE CHANGES:")
            for t, commit_msg, patch in changes:
                print(f"--- Change at {t} ---")
                if commit_msg:
                    print("Suggested Commit Message:")
                    print(f"\"\"\"\n{commit_msg.strip()}\n\"\"\"")
                    print()
                if patch:
                    lines = patch.split("\n")
                    modified_files = [line for line in lines if line.startswith("+++ b/")]
                    print("Files modified:")
                    for f in modified_files:
                        print(f"  - {f[6:]}")
                    print()
                    print("Patch snippet:")
                    snippet = "\n".join(lines[:25])
                    print(snippet)
                    if len(lines) > 25:
                        print(f"... ({len(lines) - 25} lines truncated)")
                print()

    def get_latest_agent_message(self, session_id: str, after_activity_id: Optional[str] = None) -> Optional[str]:
        """Iterates through activities to find the latest agent response after a specific activity ID."""
        activities = self.list_activities(session_id)
        if after_activity_id:
            try:
                idx = next(i for i, act in enumerate(activities) if act.get("id") == after_activity_id)
                activities = activities[idx+1:]
            except StopIteration:
                pass
        
        for act in reversed(activities):
            if act.get("originator") == "agent":
                msg = self._extract_agent_message(act)
                if msg:
                    return msg
        return None

    def _extract_agent_message(self, activity: Dict) -> Optional[str]:
        if "agentMessaged" in activity:
            am = activity["agentMessaged"]
            if isinstance(am, dict):
                return am.get("message") or am.get("agentMessage") or am.get("text")
            elif isinstance(am, str):
                return am
        if "agentMessage" in activity:
            return activity["agentMessage"]
        if activity.get("description"):
            return activity.get("description")
        return None

    def fetch_pr_comments(self, repo_owner: str, repo_name: str, pr_number: int) -> List[Dict]:
        url = f"{self.GITHUB_API_URL}/repos/{repo_owner}/{repo_name}/pulls/{pr_number}/comments"
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
        """Fallback simple assessor for backward compatibility."""
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

    def assess_comment_with_ollama(self, comment: Dict, jules_response: str) -> bool:
        """Weighs Jules' response against a reviewer comment to decide if a fix is required."""
        prompt = (
            f"You are an AI coordinator deciding whether a Pull Request review comment requires a code fix.\n\n"
            f"Reviewer Comment:\n"
            f"File: {comment['path']} (Line {comment.get('line', 'N/A')})\n"
            f"Comment: {comment['body']}\n\n"
            f"Jules (the developer agent) provided this response explaining their work/context:\n"
            f"\"\"\"\n{jules_response}\n\"\"\"\n\n"
            f"Weigh Jules' explanation against the reviewer's feedback for this specific comment.\n"
            f"Do we need to apply a code fix for this comment?\n"
            f"Respond ONLY with 'YES' (needs fix) or 'NO' (false positive or no change needed). Do not include any other text."
        )

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
            print(f"Ollama raw assessment for {comment['path']} L{comment.get('line', 'N/A')}: {assessment}")
            return "YES" in assessment
        except Exception as e:
            print(f"Ollama assessment failed: {e}. Defaulting to YES to be safe.")
            return True

    def handle_amazon_q_reviews(self, repo_owner: str, repo_name: str, pr_number: int, session_id: str):
        """Fetches reviews, asks Jules for verification (Agent-to-Agent), assesses with Ollama, and requests fixes."""
        comments = self.fetch_pr_comments(repo_owner, repo_name, pr_number)
        if not comments:
            print(f"No new Amazon Q comments for PR #{pr_number}.")
            return

        print(f"Found {len(comments)} new comments. Starting Agent-to-Agent check...")

        # Get activities before sending the message to get the last activity ID
        activities_before = self.list_activities(session_id)
        last_activity_id = activities_before[-1]['id'] if activities_before else None

        # Ask Jules for its explanation on the comments
        question = "The reviewer flagged the following issues in the Pull Request:\n\n"
        for i, c in enumerate(comments):
            question += f"--- ISSUE {i} ---\n"
            question += f"File: {c['path']} (Line {c.get('line', 'N/A')})\n"
            question += f"Comment: {c['body']}\n\n"
        question += "For each of the issues above, do you agree this is a valid issue that requires a fix in our context? Please explain your reasoning for each issue so we can make a decision."

        print(f"Sending batch question to Jules session {session_id}...")
        self.send_message(session_id, question)

        # Poll session until it transitions and completes
        print("Polling session for Jules' explanation...")
        self.poll_session(session_id, interval=15, wait_for_running=True)

        # Get the response from Jules
        jules_response = self.get_latest_agent_message(session_id, last_activity_id)
        if not jules_response:
            print("Warning: Could not retrieve a specific response from Jules activities. Using generic fallback.")
            jules_response = "No explanation provided by Jules."
        else:
            print(f"\n--- Jules Explanation ---\n{jules_response}\n-------------------------\n")

        # Assess each comment with Ollama in the context of Jules' response
        comments_to_fix = []
        for c in comments:
            print(f"Assessing comment on {c['path']} (Line {c.get('line', 'N/A')})...")
            decision = self.assess_comment_with_ollama(c, jules_response)
            if decision:
                print("Decision: FIX REQUIRED")
                comments_to_fix.append(c)
            else:
                print("Decision: SKIP (False positive or already handled)")
                self.mark_comment_processed(c['id'])

        # Send the fix requests for the accepted comments
        if comments_to_fix:
            print(f"Requesting fixes for {len(comments_to_fix)} issues...")
            fix_message = "Please apply fixes for the following issues:\n\n"
            for c in comments_to_fix:
                fix_message += f"File: {c['path']} (Line {c.get('line', 'N/A')}):\n{c['body']}\n\n"
            
            self.send_message(session_id, fix_message)
            print("Polling session for fix implementation...")
            self.poll_session(session_id, interval=15, wait_for_running=True)
            
            for c in comments_to_fix:
                self.mark_comment_processed(c['id'])
            print("Successfully processed fixes with Jules.")
        else:
            print("All review comments were assessed as false positives or do not require fixes. No changes made.")

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
    parser.add_argument("--mode", choices=["create", "message", "loop", "status", "list", "activities", "review", "summary"], default="loop", help="Operation mode")
    
    args = parser.parse_args()

    repo_owner = os.getenv("REPO_OWNER") or "SPhillips1337"
    repo_name = os.getenv("REPO_NAME") or "LinkenIn-Poster"
    config = Config(
        jules_api_key=os.getenv("JULES_API_KEY") or "",
        github_token=os.getenv("GITHUB_TOKEN") or "",
        ollama_url=os.getenv("OLLAMA_URL") or "http://localhost:11434",
        ollama_model=os.getenv("OLLAMA_MODEL") or "qwen2.5:14b",
        repo_owner=repo_owner,
        repo_name=repo_name,
        source_id=os.getenv("SOURCE_ID") or f"sources/github/{repo_owner}/{repo_name}"
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
        automator.handle_amazon_q_reviews(config.repo_owner, config.repo_name, args.pr, args.session_id)
    elif args.mode == "summary" and args.session_id:
        automator.get_session_summary(args.session_id)
    else:
        if args.mode == "review" and (not args.pr or not args.session_id):
            print("Error: 'review' mode requires both --pr and --session_id.")
        elif args.mode == "summary" and not args.session_id:
            print("Error: 'summary' mode requires --session_id.")
        else:
            print("Invalid arguments or missing prompt/ID. Use --help for usage.")
