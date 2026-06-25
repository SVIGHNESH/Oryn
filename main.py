import os
import sys
import json
import warnings
import textwrap

from langgraph.errors import GraphRecursionError
from langchain_core.messages import AIMessage, ToolMessage, HumanMessage

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.prompt import Prompt
from rich.status import Status
from rich import box
from rich.text import Text
from rich.columns import Columns
from rich.table import Table
from rich.layout import Layout

from agent import create_agent

warnings.filterwarnings("ignore", category=DeprecationWarning, module="langgraph")

console = Console()


def build_logo() -> Panel:
    logo = Text(
        r"""
 ██████╗ ██████╗ ██╗   ██╗███╗   ██╗
██╔═══██╗██╔══██╗╚██╗ ██╔╝████╗  ██║
██║   ██║██████╔╝ ╚████╔╝ ██╔██╗ ██║
██║   ██║██╔══██╗  ╚██╔╝  ██║╚██╗██║
╚██████╔╝██║  ██║   ██║   ██║ ╚████║
 ╚═════╝ ╚═╝  ╚═╝   ╚═╝   ╚═╝  ╚═══╝
""",
        style="bold cyan",
    )
    subtitle = Text("  LangGraph · DeepSeek V4 Pro · Coding Agent", style="dim white")
    content = Columns([logo, subtitle], align="center")
    return Panel(
        content,
        box=box.HEAVY,
        border_style="bright_blue",
        padding=(1, 2),
        title="[bold bright_blue]Oryn[/]",
        subtitle="[dim]exit to quit · Ctrl+C to cancel[/]",
    )


def check_env():
    from dotenv import load_dotenv

    load_dotenv()
    if not os.environ.get("NVIDIA_API_KEY"):
        console.print(
            Panel(
                "NVIDIA_API_KEY not found.\n"
                "Add it to [bold].env[/] or set:\n"
                "  [green]export NVIDIA_API_KEY=\"nvapi-...\"[/]",
                title="[red]✗ Configuration Error[/]",
                border_style="red",
            )
        )
        sys.exit(1)


def truncate(text: str, max_len: int = 600) -> str:
    if len(text) > max_len:
        return text[:max_len] + "..."
    return text


def format_tool_call(tc: dict) -> Table:
    args = tc.get("args", {})
    table = Table(
        box=box.SIMPLE,
        show_header=False,
        style="bright_yellow",
        padding=(0, 1),
    )
    table.add_column("icon", width=2)
    table.add_column("detail")
    args_preview = ", ".join(
        f"{k}={json.dumps(v)[:80]}" for k, v in args.items()
    )
    table.add_row("⚡", f"[bold]{tc['name']}[/]({args_preview})")
    return table


def show_tool_result(name: str, content: str):
    output = truncate(content)
    console.print(
        Panel(
            Syntax(output, "text", word_wrap=True, theme="monokai")
            if "\n" in output
            else Text(output, style="dim white"),
            title=f"[dim]└─ {name}[/]",
            border_style="dim",
            box=box.SIMPLE,
            padding=(0, 1),
        )
    )


def show_error(msg: str):
    console.print(Panel(msg, border_style="red", box=box.SIMPLE))


def main():
    check_env()
    console.print(build_logo())

    try:
        agent = create_agent()
    except Exception as e:
        show_error(f"Agent initialization failed: {e}")
        sys.exit(1)

    config = {"configurable": {"thread_id": "oryn-session-1"}}

    while True:
        try:
            user_input = Prompt.ask("\n[bold bright_blue]You[/]")
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Goodbye![/]")
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit"):
            console.print("[dim]Goodbye![/]")
            break

        last_event = None
        with Status("[bold cyan]Oryn is thinking...", spinner="dots") as status:
            try:
                for event in agent.stream(
                    {"messages": [HumanMessage(content=user_input)]},
                    config=config,
                    stream_mode="values",
                ):
                    last_event = event
                    last_msg = event["messages"][-1]

                    if isinstance(last_msg, AIMessage):
                        status.update(
                            status="[bold green]Oryn is acting...",
                            spinner="dots",
                        )
                        if last_msg.tool_calls:
                            for tc in last_msg.tool_calls:
                                console.print(format_tool_call(tc))

                    elif isinstance(last_msg, ToolMessage):
                        show_tool_result(last_msg.name, last_msg.content)
                        status.update(
                            status="[bold cyan]Oryn is thinking...",
                            spinner="dots",
                        )

            except GraphRecursionError:
                show_error("Agent hit the iteration limit. Break the task into smaller steps.")
                continue
            except Exception as e:
                show_error(str(e))
                continue

        if last_event:
            final = last_event["messages"][-1]
            if isinstance(final, AIMessage) and final.content:
                console.print()
                console.print(Panel(
                    Markdown(final.content),
                    border_style="green",
                    box=box.ROUNDED,
                    padding=(1, 2),
                ))

        console.print()


if __name__ == "__main__":
    main()
