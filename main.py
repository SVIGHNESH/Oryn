import os
import sys
import json
import warnings

from langgraph.errors import GraphRecursionError
from langchain_core.messages import AIMessage, ToolMessage, HumanMessage

from agent import create_agent

warnings.filterwarnings("ignore", category=DeprecationWarning, module="langgraph")

BANNER = r"""
╔══════════════════════════════════════════╗
║   ____                   _              ║
║  / __ \                 (_)             ║
║ | |  | |_ __   ___ _ __ _ _ __   __ _  ║
║ | |  | | '_ \ / _ \ '__| | '_ \ / _` | ║
║ | |__| | |_) |  __/ |  | | | | | (_| | ║
║  \____/| .__/ \___|_|  |_|_| |_|\__, | ║
║        | |                       __/ | ║
║        |_|                      |___/  ║
║                                        ║
║  Coding Agent · LangGraph · DeepSeek   ║
╚══════════════════════════════════════════╝
"""


def print_banner():
    print(BANNER)
    print("  Type 'exit' or Ctrl+C to quit")
    print()


def check_env():
    from dotenv import load_dotenv
    load_dotenv()

    if not os.environ.get("NVIDIA_API_KEY"):
        print("Error: NVIDIA_API_KEY not found.")
        print("Add it to .env or set:  export NVIDIA_API_KEY=\"nvapi-...\"")
        sys.exit(1)


def format_tool_call(tc: dict) -> str:
    args = tc.get("args", {})
    args_str = ", ".join(f"{k}={json.dumps(v)}" for k, v in args.items())
    return f"  ⚡ {tc['name']}({args_str})"


def truncate(text: str, max_len: int = 600) -> str:
    if len(text) > max_len:
        return text[:max_len] + "..."
    return text


def main():
    check_env()
    print_banner()

    try:
        agent = create_agent()
    except Exception as e:
        print(f"Error initializing agent: {e}")
        sys.exit(1)

    config = {"configurable": {"thread_id": "oryn-session-1"}}

    while True:
        try:
            user_input = input("\nYou > ").strip()
        except EOFError:
            print()
            break
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit"):
            print("Goodbye!")
            break

        try:
            for event in agent.stream(
                {"messages": [HumanMessage(content=user_input)]},
                config=config,
                stream_mode="values",
            ):
                last_msg = event["messages"][-1]

                if isinstance(last_msg, AIMessage):
                    if last_msg.content:
                        print(f"\n  {last_msg.content}")
                    if last_msg.tool_calls:
                        for tc in last_msg.tool_calls:
                            print(format_tool_call(tc))

                elif isinstance(last_msg, ToolMessage):
                    output = truncate(last_msg.content)
                    print(f"  └─ Result: {output}")

            print()

        except GraphRecursionError:
            print("\n  ⚠ Agent hit the iteration limit. Try breaking the task into smaller steps.")
        except Exception as e:
            print(f"\n  ⚠ Error: {e}")


if __name__ == "__main__":
    main()
