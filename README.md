# Oryn Architecture Document

> DeepSeek-V4-Pro + LangGraph + Python Coding Agent

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Library Stack & Responsibilities](#2-library-stack--responsibilities)
3. [Architecture Diagram](#3-architecture-diagram)
4. [Module Breakdown](#4-module-breakdown)
5. [Agent Loop Lifecycle](#5-agent-loop-lifecycle)
6. [Data Flow](#6-data-flow)
7. [Graph Structure (LangGraph)](#7-graph-structure-langgraph)
8. [Tool Design Patterns](#8-tool-design-patterns)
9. [Configuration & Environment](#9-configuration--environment)

---

## 1. System Overview

Oryn is a **ReAct agent** that takes natural-language coding tasks, reasons about them, and uses tools (bash, read, write, edit) to accomplish them on the local filesystem. It runs as a CLI REPL and uses LangGraph's built-in `create_react_agent` for the agent loop.

```
                    ┌─────────────────────┐
                    │    User (CLI REPL)  │
                    └────────┬────────────┘
                             │ "create a fibonacci script"
                             ▼
┌───────────────────────────────────────────────────────┐
│                   LangGraph Agent                     │
│  ┌─────────────────────────────────────────────────┐  │
│  │            create_react_agent                   │  │
│  │                                                 │  │
│  │  ┌──────────┐    ┌──────────┐    ┌──────────┐  │  │
│  │  │call_model│───▶│ToolNode  │───▶│call_model│  │  │
│  │  └────┬─────┘    └──────────┘    └────┬─────┘  │  │
│  │       │                               │        │  │
│  │       └───(no tool_calls)────────────▶│        │  │
│  │              (final answer)            │        │  │
│  └─────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────┘
                             │
                             ▼
                    ┌─────────────────────┐
                    │  Tool Execution     │
                    │  bash / read_file   │
                    │  write_file / edit  │
                    └─────────────────────┘
```

---

## 2. Library Stack & Responsibilities

| Library | Version | Role in Oryn | Why this library? |
|---------|---------|-------------|-------------------|
| **`langgraph`** | >= 0.4.0 | Agent orchestration — defines the graph, manages state, runs the loop | Built-in `create_react_agent` gives us ReAct loop out of the box with minimal boilerplate |
| **`langchain-core`** | >= 0.3.0 | Tool definition — `@tool` decorator, `ToolNode`, `BaseMessage` types | The tool abstraction that `langgraph` expects; type-safe schemas auto-generated for the LLM |
| **`langchain-openai`** | >= 0.3.0 | LLM client — wraps `ChatOpenAI` pointing to NVIDIA NIM endpoint | Drop-in OpenAI-compatible client; just change `base_url` and `model` to use DeepSeek-V4-Pro |
| **`openai`** (transitive) | — | HTTP transport — handles HTTP requests to NVIDIA API | Installed as dependency of `langchain-openai`; manages auth, streaming, retries |
| **`subprocess`** (stdlib) | — | Runs bash commands | Built-in, no external dependency needed |
| **`pathlib` / `os` (stdlib)** | — | File system operations | Standard library, zero overhead |
| **`sys` / `readline` (stdlib)** | — | REPL input handling | Cross-platform CLI input with history support |

### Dependency Hierarchy

```
┌─────────────────────────────────────────┐
│               Oryn (main.py)            │
├─────────────────────────────────────────┤
│  langgraph ◄── create_react_agent       │
│     │                                   │
│     └── langchain-core ◄── @tool,       │
│              │           ToolNode,       │
│              │           BaseMessage     │
│              │                           │
│              └── langchain-openai ◄──    │
│                        │   ChatOpenAI    │
│                        │                 │
│                        └── openai ◄──    │
│                              HTTP client │
└─────────────────────────────────────────┘
```

---

## 3. Architecture Diagram (Detailed)

```
┌──────────────────────────────────────────────────────────────┐
│                        main.py                               │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  REPL Loop                                             │  │
│  │                                                        │  │
│  │  while True:                                           │  │
│  │    user_input = input("You > ")                        │  │
│  │    if user_input == "exit": break                      │  │
│  │                                                        │  │
│  │    for event in agent.stream(msgs):                    │  │
│  │      # stream tool calls + final answer                │  │
│  │      print_event(event)                                │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                       agent.py                                │
│                                                               │
│  llm = ChatOpenAI(                                            │
│    model="deepseek-ai/deepseek-v4-pro",                       │
│    base_url="https://integrate.api.nvidia.com/v1",            │
│    temperature=0, max_tokens=8192,                            │
│  )                                                            │
│                                                               │
│  tools = [bash, read_file, write_file, edit_file]            │
│                                                               │
│  agent = create_react_agent(                                  │
│    model=llm,                                                 │
│    tools=tools,                                               │
│    state_modifier=SYSTEM_PROMPT,                              │
│  )                                                            │
│                                                               │
│  # Internally creates:                                        │
│  #   StateGraph(AgentState)                                   │
│  #   ├── call_model  (LLM node)                              │
│  #   ├── ToolNode    (tool execution)                        │
│  #   └── should_continue (conditional edge)                   │
└──────────────────────────────────────────────────────────────┘
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
┌─────────────────┐ ┌──────────────┐ ┌──────────────┐
│   tools.py      │ │  prompts.py  │ │  state.py    │
│                 │ │              │ │              │
│ bash()          │ │ System msg   │ │ AgentState   │
│ read_file()     │ │ Tool usage   │ │ TypedDict    │
│ write_file()    │ │ rules        │ │              │
│ edit_file()     │ └──────────────┘ └──────────────┘
└─────────────────┘
```

---

## 4. Module Breakdown

### 4.1 `main.py` — Entry Point / REPL

**Responsibility**: Drive the interactive loop, stream agent output.

```
┌──────────────────────────────────────────────┐
│                main.py                       │
├──────────────────────────────────────────────┤
│ init_env()       → Validate NVIDIA_API_KEY   │
│                   is set                     │
│                   Load .env if available     │
├──────────────────────────────────────────────┤
│ print_banner()   → Show Oryn ASCII art       │
├──────────────────────────────────────────────┤
│ repl_loop()      → while True:               │
│                     input → agent.stream()   │
│                     print events             │
├──────────────────────────────────────────────┤
│ main()           → init → banner → loop      │
└──────────────────────────────────────────────┘
```

**Key behavior**:
- Each user message is wrapped as `{"role": "user", "content": msg}` and appended to `messages` list
- `agent.stream()` returns events — either tool calls (with intermediate results) or final answer
- On `GraphRecursionError` (infinite loop protection), prints error and resets
- `KeyboardInterrupt` prints goodbye and exits

### 4.2 `agent.py` — Agent Construction

**Responsibility**: Wire together the LLM, tools, and system prompt into a compiled LangGraph agent.

```
┌──────────────────────────────────────────────┐
│               agent.py                       │
├──────────────────────────────────────────────┤
│ create_agent()                               │
│   1. Initialize ChatOpenAI with NVIDIA config│
│   2. Import tool list from tools.py          │
│   3. Load system prompt from prompts.py      │
│   4. Build via create_react_agent()          │
│   5. Compile the graph                       │
│      └── recursion_limit=30                  │
│      └── return compiled app                 │
└──────────────────────────────────────────────┘
```

**ChatOpenAI Configuration**:

```python
llm = ChatOpenAI(
    model="deepseek-ai/deepseek-v4-pro",
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=os.environ["NVIDIA_API_KEY"],
    temperature=0,
    max_tokens=8192,
    model_kwargs={
        "reasoning_effort": "high",  # enables DeepSeek's reasoning
    },
)
```

### 4.3 `tools.py` — Tool Definitions

**Responsibility**: Define the 4 tools that Oryn uses to interact with the filesystem and shell.

Each tool is a function decorated with `@tool` from `langchain_core.tools`. The decorator:
- Generates a JSON schema from the function signature and docstring
- Registers the function as a callable tool
- Handles type coercion and validation

```
Tool                     Input                        Output
────                     ─────                        ──────
bash(command: str)       Shell command string         stdout + stderr (str)
read_file(file_path)     Path to file                 File contents (str)
write_file(path, cont)   Path + content               Confirmation (str) 
edit_file(path, old,new) Path + old → new             Confirmation (str)
```

**Error handling pattern for all tools**:
- Wrap implementation in try/except
- Never raise exceptions — always return a string describing the error
- This lets the LLM see the error and decide how to recover

### 4.4 `prompts.py` — System Prompt

**Responsibility**: Hold the system prompt that defines Oryn's behavior.

Structure:
```
You are Oryn, an expert coding assistant.
You have access to tools: bash, read_file, write_file, edit_file.

Guidelines:
- Think step by step.
- Explain what you're doing.
- Always verify writes with reads.
- Run code after writing to check correctness.
- If a tool fails, read the error and retry with a corrected approach.
- Prefer edit_file for small changes, write_file for new files.
```

### 4.5 `state.py` — Agent State

**Responsibility**: Define the state type for the LangGraph graph.

```python
from langgraph.graph import MessagesState
# MessagesState = TypedDict with {"messages": list}
# add_messages reducer handles merging
```

LangGraph's `create_react_agent` expects `MessagesState` by default. The `messages` key holds the full conversation history (user, assistant, tool messages), which the LLM uses as context.

---

## 5. Agent Loop Lifecycle

### Step-by-step execution of `agent.stream({"messages": [user_msg]})`:

```
Iteration 1:
  1. call_model node
     └── LLM receives: [sys_prompt, user_msg] + tool schemas
     └── LLM decides: needs to read files first
     └── Returns: AIMessage with tool_calls = [read_file(...)]

  2. should_continue edge
     └── Checks: has tool_calls? → YES → route to ToolNode

  3. ToolNode executes tools
     └── Runs read_file(...), returns ToolMessage with result
     └── Result appended to state["messages"]

Iteration 2:
  4. call_model node again
     └── LLM receives: [sys_prompt, user_msg, 
     └──              AIMessage(tool_calls), ToolMessage(result)]
     └── LLM decides: now needs to write a file
     └── Returns: AIMessage with tool_calls = [write_file(...)]

  5. ToolNode → writes file → returns ToolMessage

Iteration 3:
  6. call_model node
     └── LLM receives full context
     └── Decides: task complete
     └── Returns: AIMessage(content="Done! Created fib.py")

  7. should_continue edge
     └── No tool_calls → route to END
     └── Final answer streamed to user
```

---

## 6. Data Flow

```
                    ┌──────────┐
                    │ User     │
                    │ Input    │
                    └────┬─────┘
                         │ str
                         ▼
┌────────────────────────────────────────────┐
│           Agent State (messages[])         │
│                                            │
│  [                                          │
│    {"role": "system", "content": "..."},   │
│    {"role": "user",   "content": "task"},  │
│    {"role": "assistant",                    │
│     "content": "",                          │
│     "tool_calls": [...]},                  │
│    {"role": "tool",                         │
│     "content": "result",                    │
│     "tool_call_id": "..."},                │
│    ...                                      │
│  ]                                          │
└────────────────────────────────────────────┘
          │                            ▲
          │ state update               │ state update
          ▼                            │
┌──────────────────┐        ┌──────────────────┐
│   call_model     │        │   ToolNode       │
│   (LLM)          │        │                  │
│                  │        │  bash()          │
│  Returns:        │        │  read_file()     │
│  text or         │        │  write_file()    │
│  tool_calls      │        │  edit_file()     │
└──────────────────┘        └──────────────────┘
```

---

## 7. Graph Structure (LangGraph)

### What `create_react_agent` generates internally:

```python
builder = StateGraph(AgentState)

builder.add_node("call_model", call_model)    # LLM inference
builder.add_node("tools", ToolNode(tools))     # tool executor

builder.add_edge(START, "call_model")
builder.add_conditional_edges(
    "call_model",
    should_continue,              # routes to "tools" or END
)
builder.add_edge("tools", "call_model")  # always loop back

app = builder.compile()
```

### `should_continue` logic:

```python
def should_continue(state: AgentState) -> str:
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return END
```

### Visual Graph:

```
  START
    │
    ▼
┌───────────┐
│call_model │
└─────┬─────┘
      │
      │ conditional
      │
  ┌───┴───┐
  │       │
  ▼       ▼
tools    END
  │
  └── always back to call_model ──┐
                                  │
                                  ▼
                              (loops until final)
```

---

## 8. Tool Design Patterns

### Pattern 1: Errors as strings, not exceptions

```python
@tool
def read_file(file_path: str) -> str:
    """Read the contents of a file at the given path."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return f"Error: File not found: {file_path}"
    except PermissionError:
        return f"Error: Permission denied: {file_path}"
    except UnicodeDecodeError:
        return f"Error: Binary or non-UTF8 file: {file_path}"
```

**Why**: The LLM receives the error string directly in the next iteration and can decide how to fix it (try another path, use bash `ls`, etc.). Raising exceptions would break the agent loop.

### Pattern 2: Tool schemas auto-generated

`@tool` reads the function name, docstring, and type hints to generate the OpenAI-compatible JSON schema:

```json
{
  "type": "function",
  "function": {
    "name": "read_file",
    "description": "Read the contents of a file at the given path.",
    "parameters": {
      "type": "object",
      "properties": {
        "file_path": {
          "type": "string",
          "description": "The path to the file to read"
        }
      },
      "required": ["file_path"]
    }
  }
}
```

### Pattern 3: Output truncation

`bash` output is truncated at 10,000 characters to prevent token overflow in the LLM context window.

---

## 9. Configuration & Environment

| Variable | Required | Purpose |
|----------|----------|---------|
| `NVIDIA_API_KEY` | Yes | Bearer token for DeepSeek-V4-Pro access |
| `ORYN_MODEL` | No | Override model name (default: `deepseek-ai/deepseek-v4-pro`) |
| `ORYN_MAX_TOKENS` | No | Override max tokens (default: `8192`) |
| `ORYN_TEMPERATURE` | No | Override temperature (default: `0`) |
| `ORYN_RECURSION_LIMIT` | No | Max agent loop iterations (default: `30`) |

### Startup Validation

```
main.py startup sequence:
  1. Load .env if exists (python-dotenv optional)
  2. Check NVIDIA_API_KEY is set
     └── if not: print "Error: NVIDIA_API_KEY not set" + exit(1)
  3. Initialize LLM client (lazy — no HTTP call yet)
  4. Build + compile agent graph
  5. Print banner → enter REPL loop
```

---

## Appendix: Key Library Details

### LangGraph (`langgraph`)

- **`create_react_agent`**: Factory function that builds a complete ReAct agent graph. Takes LLM, tools, and optional system prompt. Handles the loop, state management, and routing.
- **`StateGraph`**: The graph class. Nodes are Python functions that take state and return state updates. Edges define routing.
- **`MessagesState`**: Pre-built state type with `messages` key and `add_messages` reducer for merging.
- **`ToolNode`**: Built-in node that executes tool calls from the LLM output.
- **`GraphRecursionError`**: Raised when the graph exceeds `recursion_limit`. Caught in `main.py` for graceful handling.

### LangChain Core (`langchain-core`)

- **`@tool`**: Decorator that converts a function into a LangChain tool. Auto-generates JSON schema from docstring and type hints.
- **`BaseMessage`**: Base class for `HumanMessage`, `AIMessage`, `ToolMessage` etc. Used in state.
- **`ToolMessage`**: Message type for tool execution results. Contains `content`, `tool_call_id`, and `name`.

### LangChain OpenAI (`langchain-openai`)

- **`ChatOpenAI`**: LangChain wrapper for OpenAI-compatible chat endpoints. Configurable with `base_url` — this is what allows us to target NVIDIA NIM instead of OpenAI.
- **`BaseChatModel`**: Abstract base class that `ChatOpenAI` implements. `create_react_agent` accepts any `BaseChatModel` instance.
- **Default params**: `temperature`, `max_tokens`, `model_kwargs` for additional payload fields like `reasoning_effort`.
