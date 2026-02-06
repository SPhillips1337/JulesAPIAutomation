# JulesAPI Automation

**JulesAPI Automation** is a meta-developer orchestrator designed to automate the iterative Software Development Life Cycle (SDLC) using specialized AI agents.

## 🚀 Overview

This project implements an automated development loop by integrating:
- **[Google Jules](https://jules.googleapis.com)**: For code implementation and Pull Request creation.
- **Amazon Q Developer**: For rigorous code review and security auditing.
- **Local LLMs (via Ollama)**: For qualitative assessment of review feedback and iteration decision-making.

## 🏗️ Architecture

1. **Plan**: An architect agent (like Antigravity) crafts the initial task prompt.
2. **Execute**: Jules implements the changes in a new branch and creates a PR.
3. **Review**: Amazon Q reviews the PR for security vulnerabilities and quality issues.
4. **Iterate**: A local LLM assesses the feedback. If valid, Jules receives a refinement request within the same session.

## 📂 Project Structure

- `jules_automator.py`: The core orchestration script.
- `AGENTS.md`: Technical guide for AI agents participating in the loop.
- `JULES.md`: Reference for iterative development patterns and best practices.
- `USAGE.md`: Detailed setup and execution instructions.

## 📜 License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details.
