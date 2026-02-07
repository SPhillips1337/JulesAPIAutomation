# Jules Reference: Iterative Development & Reviews

This document expands on the core Jules guide with specific learnings from iterative development cycles involving automated code reviews.

## The Iteration Loop

Iterative development works best when specialized agents handle different parts of the SDLC:
1. **Architect (Antigravity)**: Plans the change and crafts the prompt.
2. **Implementer (Jules)**: Executes code changes and creates PRs.
3. **Reviewer (Amazon Q)**: Identifies security and quality issues in the PR.
4. **Assessor (Local LLM)**: Decides if the feedback is valid and needs another Jules cycle.

## Key Learnings

### Automated Review Handling
- **Amazon Q is strict**: It will catch command injection and insecure hashing (like MD5) even in non-critical paths. 
- **Feedback is structured**: Review comments usually include a CWE reference and a code suggestion. This makes them highly parseable for other AI agents.
- **Timing**: There is a delay between Jules finishing and Amazon Q starting. Automation scripts must account for this (polling the GH API).

### Jules-to-Jules Iteration
- **Branch Tracking**: When rescheduling a fix, point Jules to the **head branch** of the existing PR rather than the base branch.
- **Conversational Loops (New)**: Avoid creating 10 new sessions. Instead, use the `sendMessage` API within an existing session to iterate. This preserves the agent's "working memory" and is more token-efficient.
- **Activity Monitoring**: Use `listActivities` to read Jules' internal logs. This allows you to verify if Jules has already considered a specific issue but decided against fixing it (identifying false positives).

### Technical Gotchas
- **Shell Execution**: Amazon Q will flag `shell_exec` usage. When fixing, ensure you capture exit codes (e.g., `cmd 2>&1; echo $?`) and handle non-zero results.
- **JSON Encoding**: Always JSON-escape prompts to avoid payload errors.

## Integration Targets
- **Jules MCP Server**: The standardized interface for exposing these development patterns to other AI agents.
- **Ollama (Qwen 2.5)**: Excellent for qualitative assessment of review comments.
- **GitHub API**: Essential for fetching `reviewThreads` and `comments`.
