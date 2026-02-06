# Agent's Guide: Automated Jules Iterations

Welcome, Agent. Your goal is to manage the `JulesAPI` loop. This project is a meta-developer: an orchestrator that uses specialized coding agents and reviews.

## High-Level Flow
1. **Initialize Session**: Trigger Google Jules API with a structured prompt.
2. **Monitor & Log**: Poll the session status. Use `list_activities` to read Jules' internal comments and progress logs.
3. **Review**: Fetch Pull Request comments (e.g., from `amazon-q-developer`).
4. **Agent-to-Agent Check**: Before rescheduling, use `send_message` to ask Jules: "The reviewer flagged X. Do you agree this is a valid issue that requires a fix in our context?" 
5. **Decide**: Use a local LLM to weigh Jules' response against the reviewer's feedback.
6. **Iteration**: If valid, use `send_message` in the *same* session to request the fix, keeping context continuous.

## Rules of Engagement
- **Avoid Loops**: If Jules explains that a flag is a false positive (e.g., "The DIR usage is safe because X"), and the local LLM agrees, break the loop. 
- **Context Continuity**: Prefer `sendMessage` within an active session over creating new sessions to maintain the agent's mental model of the code.

## Tools & Context
- **Jules API**: `https://jules.googleapis.com/v1alpha/`
- **GitHub API**: Used for fetching PR reviews.
- **Ollama**: `http://localhost:11434` - use for decision logic.
