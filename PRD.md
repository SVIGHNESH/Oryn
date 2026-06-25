# PRD: Oryn — LangGraph-Powered Coding Agent

| Field | Value |
|-------|-------|
| **Product** | Oryn Coding Agent |
| **Day** | DAY15 — AgenticWorkShop |
| **Status** | Draft |
| **Author** | Vighnesh |

---

## 1. Executive Summary

Oryn is a general-purpose coding agent built with LangGraph that can read, write, and edit files, execute shell commands, and reason about code — iterating until the task is done. It uses DeepSeek-V4-Pro (via NVIDIA NIM) as its LLM backbone and follows the ReAct agent pattern.

---

## 2. Problem Statement

Developers frequently perform repetitive coding workflows:
- Reading source files to understand code
- Writing new files or modifying existing ones
- Running shell commands to test, build, or lint
- Debugging by inspecting output and iterating

A CLI-based coding agent that can chain these actions autonomously reduces manual context-switching and speeds up development.

---

## 3. Goals

### Primary
- Build a CLI agent that accepts natural-language coding tasks
- Agent can autonomously loop: think → act (bash/read/write/edit) → observe → think again
- Deliver final result (code, fix, explanation) back to the user

### Non-Goals
- No IDE or GUI integration (pure CLI/REPL)
- No multi-agent orchestration (single agent)
- No persistent memory across sessions (ephemeral conversation)

---

## 4. Architecture

```
┌─────────────────────────────────────────────┐
│                  Layer                      │
├─────────────────────────────────────────────┤
│  User Interface          REPL (main.py)     │
│  Agent Orchestration     LangGraph Agent    │
│  LLM Backbone            DeepSeek-V4-Pro    │
│  Tool Layer              Bash / Read /      │
│                          Write / Edit       │
│  Execution Env           Local filesystem,  │
│                          Subprocess         │
└─────────────────────────────────────────────┘
```

### Agent Loop (ReAct Pattern)

```
User → call_model → tool_calls? ─yes→ execute_tools → call_model
                     │ no
                     ▼
                  Final answer → User
```

---

## 5. Functional Requirements

### FR1: Interactive REPL
- **ID**: FR-REPL-01
- **Description**: Agent starts in interactive REPL mode, accepting one task per prompt
- **Acceptance**: User types a task → agent acknowledges → processes → returns result → ready for next input

### FR2: File Reading
- **ID**: FR-TOOL-01
- **Description**: Agent can read any file from the filesystem
- **Input**: Absolute or relative `file_path`
- **Output**: File content as string
- **Error Handling**: File not found, permission denied, binary detection

### FR3: File Writing
- **ID**: FR-TOOL-02
- **Description**: Agent can write content to a file, creating intermediate directories as needed
- **Input**: `file_path`, `content`
- **Output**: Success/error message

### FR4: File Editing
- **ID**: FR-TOOL-03
- **Description**: Agent can perform exact substring replacement in an existing file
- **Input**: `file_path`, `old_string`, `new_string`
- **Error Handling**: Pattern not found, multiple matches (ambigous)

### FR5: Shell Execution
- **ID**: FR-TOOL-04
- **Description**: Agent can run arbitrary shell commands
- **Input**: `command` string
- **Constraints**: Timeout at 30 seconds; returns both stdout and stderr
- **Error Handling**: Non-zero exit codes returned as errors

### FR6: Agent Loop Termination
- **ID**: FR-LOOP-01
- **Description**: Agent loop terminates naturally when LLM produces a final answer (no tool_calls)
- **Safety**: Hard limit of 30 iterations to prevent infinite loops

### FR7: Model Configuration
- **ID**: FR-LLM-01
- **Description**: Uses DeepSeek-V4-Pro via NVIDIA NIM (OpenAI-compatible endpoint)
- **Endpoint**: `https://integrate.api.nvidia.com/v1`
- **Model ID**: `deepseek-ai/deepseek-v4-pro`
- **Auth**: Bearer token via `NVIDIA_API_KEY` env var

---

## 6. Non-Functional Requirements

| ID | Requirement | Target |
|----|------------|--------|
| NFR-01 | **Cold start time** | < 2s to REPL prompt |
| NFR-02 | **LLM latency** | < 10s per LLM call (95th percentile) |
| NFR-03 | **Tool execution** | bash timeout at 30s |
| NFR-04 | **Loop safety** | Max 30 iterations, then force-terminate |
| NFR-05 | **Config** | All config via environment variables only |
| NFR-06 | **Portability** | Runs on any Linux with Python 3.10+ |

---

## 7. Error Handling Matrix

| Scenario | Detection | Response |
|----------|-----------|----------|
| Missing API key | `os.environ` check at startup | Print clear error and exit |
| API auth failure | HTTP 401 from NVIDIA | Retry once, then show auth error |
| API rate limit | HTTP 429 | Retry with exponential backoff (max 3) |
| API timeout | `requests.exceptions.Timeout` | Retry once |
| File not found | `FileNotFoundError` | Return descriptive error to LLM |
| Permission denied | `PermissionError` | Return descriptive error to LLM |
| Bash command fails | Non-zero exit code | Return stderr to LLM |
| Edit pattern not found | No match in file | Return "pattern not found" to LLM |
| Edit multiple matches | >1 occurrence | Return "multiple matches found" to LLM |
| Infinite agent loop | >30 iterations | Graph terminates with error message |
| KeyboardInterrupt | Ctrl+C | Graceful exit, print goodbye message |

---

## 8. Tool Specifications

### `bash(command: str) -> str`
- Runs via `subprocess.run(shell=True, timeout=30)`
- Returns combined stdout + stderr
- Truncates output at 10,000 characters to avoid token overflow

### `read_file(file_path: str) -> str`
- Uses Python `open()` with UTF-8 encoding
- Auto-detects binary files (checks null bytes in first 8KB)
- Returns content as string or error message

### `write_file(file_path: str, content: str) -> str`
- Creates parent directories with `os.makedirs(exist_ok=True)`
- Writes with UTF-8 encoding
- Returns confirmation or error

### `edit_file(file_path: str, old_string: str, new_string: str) -> str`
- Reads file, performs `str.replace(old, new, count=1)` (single replacement)
- If `old_string` appears 0 times → error
- If `old_string` appears >1 times and no unique context → error requesting more context
- Writes result back

---

## 9. System Prompt Design

The system prompt defines Oryn's persona:
- **Identity**: Expert coding assistant with access to bash, read, write, edit tools
- **Behavior**: Thinks step by step, explains actions concisely, uses tools autonomously
- **Rules**: 
  - Always verify file writes by reading them back
  - Run tests after writing code to verify correctness
  - Never hallucinate content — verify with tools
  - Acknowledge errors and retry with corrected approach

---

## 10. Dependencies

```
langgraph>=0.4.0
langchain-core>=0.3.0
langchain-openai>=0.3.0
```

Runtime: Python 3.10+

---

## 11. CLI Interface

```
Usage:
  export NVIDIA_API_KEY="nvapi-..."
  python main.py

Commands (in REPL):
  <natural language task>   Execute coding task
  exit / Ctrl+C             Quit
```

---

## 12. Future Considerations (Post-MVP)

- Add `glob` and `grep` search tools for codebase navigation
- Persistent session memory (checkpointing via LangGraph)
- Streaming output token-by-token for responsive UX
- Multi-agent: separate planner, reviewer, executor agents
- Docker sandboxing for safe bash execution
- Web UI (Streamlit or FastAPI + React)

---

## 13. Success Metrics

| Metric | Definition | Target |
|--------|-----------|--------|
| Task completion rate | % of tasks where user accepts result | > 80% |
| Tool accuracy | % of tool calls that succeed on first try | > 90% |
| Loop efficiency | Avg iterations per task | < 5 |
| Cold start | Time from `python main.py` to prompt | < 2s |

---

## 14. Open Questions

- Should bash commands be sandboxed (Docker) for safety?
- Should there be a confirmation step before destructive writes?
- Should we add a `diff` preview before editing files?
