import os
import sys
import json
import requests
from jules_automator import JulesAutomator, Config
from dotenv import load_dotenv

def process_reviews(pr_number: int, session_id: str):
    load_dotenv()
    
    config = Config(
        jules_api_key=os.getenv("JULES_API_KEY", ""),
        github_token=os.getenv("GITHUB_TOKEN", ""),
        ollama_url=os.getenv("OLLAMA_URL", "http://localhost:11434"),
        ollama_model=os.getenv("OLLAMA_MODEL", "qwen2.5:14b"),
        repo_owner=os.getenv("REPO_OWNER", "SPhillips1337"),
        repo_name=os.getenv("REPO_NAME", "LinkenIn-Poster"),
        source_id=os.getenv("SOURCE_ID", "")
    )
    
    automator = JulesAutomator(config)
    
    print(f"Fetching comments for PR #{pr_number}...")
    url = f"{automator.GITHUB_API_URL}/repos/{config.repo_owner}/{config.repo_name}/pulls/{pr_number}/comments"
    response = requests.get(url, headers=automator.headers_github)
    response.raise_for_status()
    comments = response.json()
    
    if not comments:
        print("No new review comments found.")
        return

    print(f"Assessing {len(comments)} comments with Ollama ({config.ollama_model})...")
    needs_fix = automator.assess_with_ollama(comments)
    
    if needs_fix:
        print("Ollama assessment: Changes are required.")
        
        # Construct a refinement prompt
        refinement_prompt = "Amazon Q Developer review has flagged several issues in the PR. Please address the following:\n\n"
        for c in comments:
            refinement_prompt += f"- File: {c['path']}, Line: {c.get('line', 'N/A')}\n"
            refinement_prompt += f"  Issue: {c['body']}\n\n"
        
        refinement_prompt += "\nPlease apply the suggested fixes, particularly focusing on the security vulnerabilities (hardcoded credentials, session fixation, CSRF, command injection) and the logic errors (race conditions, CWD usage)."
        
        print("Sending message to Jules...")
        resp = automator.send_message(session_id, refinement_prompt)
        print(f"Jules response: {resp}")
        print("Now polling session for completion...")
        automator.poll_session(session_id)
    else:
        print("Ollama assessment: No critical issues found or changes already handled.")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 process_reviews.py <PR_NUMBER> <SESSION_ID>")
    else:
        process_reviews(int(sys.argv[1]), sys.argv[2])
