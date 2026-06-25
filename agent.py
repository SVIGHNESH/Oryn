import os
import warnings
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from langchain_openai import ChatOpenAI

warnings.filterwarnings("ignore", category=DeprecationWarning, module="langgraph")

from tools import bash, read_file, write_file, edit_file
from prompts import SYSTEM_PROMPT


def create_agent():
    api_key = os.environ.get("NVIDIA_API_KEY")
    if not api_key:
        raise ValueError("NVIDIA_API_KEY environment variable is not set")

    model_name = os.environ.get("ORYN_MODEL", "deepseek-ai/deepseek-v4-pro")
    max_tokens = int(os.environ.get("ORYN_MAX_TOKENS", "8192"))
    temperature = float(os.environ.get("ORYN_TEMPERATURE", "0"))
    reasoning_effort = os.environ.get("ORYN_REASONING_EFFORT", "high")

    llm_kwargs = {
        "model": model_name,
        "base_url": "https://integrate.api.nvidia.com/v1",
        "api_key": api_key,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if reasoning_effort:
        llm_kwargs["reasoning_effort"] = reasoning_effort

    llm = ChatOpenAI(**llm_kwargs)

    tools = [bash, read_file, write_file, edit_file]
    recursion_limit = int(os.environ.get("ORYN_RECURSION_LIMIT", "30"))

    checkpointer = MemorySaver()

    agent = create_react_agent(
        model=llm,
        tools=tools,
        prompt=SYSTEM_PROMPT,
        checkpointer=checkpointer,
    )

    agent = agent.with_config({"recursion_limit": recursion_limit})

    return agent
