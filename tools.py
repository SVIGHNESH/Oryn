import subprocess
import os
from pathlib import Path
from langchain_core.tools import tool


@tool
def bash(command: str) -> str:
    """Execute a shell command and return its output. Use this for running scripts, compilers, linters, tests, or any system command."""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            if output:
                output += "\n"
            output += result.stderr
        if result.returncode != 0:
            output = f"Exit code {result.returncode}\n{output}"
        if len(output) > 10000:
            output = output[:10000] + "\n... (truncated)"
        return output.strip() or "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: Command timed out after 30 seconds"
    except FileNotFoundError:
        return f"Error: Command not found: {command.split()[0]}"
    except Exception as e:
        return f"Error executing command: {e}"


@tool
def read_file(file_path: str) -> str:
    """Read the contents of a file at the given path. Use this to inspect code, configs, or any text file."""
    try:
        path = Path(file_path).expanduser().resolve()
        if not path.exists():
            return f"Error: File not found: {path}"
        if not path.is_file():
            return f"Error: Not a file: {path}"
        try:
            content = path.read_text(encoding="utf-8")
            if len(content) > 10000:
                content = content[:10000] + "\n... (file truncated at 10000 chars)"
            return content
        except UnicodeDecodeError:
            return "Error: Binary or non-UTF8 file — cannot read as text"
    except PermissionError:
        return f"Error: Permission denied: {file_path}"
    except Exception as e:
        return f"Error reading file: {e}"


@tool
def write_file(file_path: str, content: str) -> str:
    """Write content to a file at the given path. Creates parent directories automatically. Use this to create new files or overwrite existing ones."""
    try:
        path = Path(file_path).expanduser().resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return f"Successfully wrote {len(content)} bytes to {path}"
    except PermissionError:
        return f"Error: Permission denied: {file_path}"
    except OSError as e:
        return f"Error writing file: {e}"
    except Exception as e:
        return f"Error writing file: {e}"


@tool
def edit_file(file_path: str, old_string: str, new_string: str) -> str:
    """Replace the first occurrence of old_string with new_string in a file. Use this for making targeted edits to existing files. If old_string appears multiple times, provide more surrounding context to make it unique."""
    try:
        path = Path(file_path).expanduser().resolve()
        if not path.exists():
            return f"Error: File not found: {path}"
        if not path.is_file():
            return f"Error: Not a file: {path}"

        original = path.read_text(encoding="utf-8")
        occurrences = original.count(old_string)

        if occurrences == 0:
            return f"Error: Pattern not found in {path}. Make sure the string matches exactly, including whitespace and indentation."
        if occurrences > 1:
            return f"Error: Found {occurrences} occurrences. Provide more surrounding context to identify the correct match."

        new_content = original.replace(old_string, new_string, 1)
        path.write_text(new_content, encoding="utf-8")
        return f"Successfully edited {path} (1 replacement)"
    except PermissionError:
        return f"Error: Permission denied: {file_path}"
    except UnicodeDecodeError:
        return f"Error: Binary or non-UTF8 file: {file_path}"
    except Exception as e:
        return f"Error editing file: {e}"
