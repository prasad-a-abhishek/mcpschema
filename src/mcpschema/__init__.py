"""mcpschema — Convert MCP tool schemas to LLM provider formats.

Zero-dependency Python 3.11+ library that translates `mcp.types.Tool`
inputSchema dicts into the tool-calling shapes used by OpenAI, Anthropic,
Gemini, Ollama, DeepSeek, and Mistral.

Example::

    from mcpschema import to_openai_tool, to_anthropic_tool, convert_all

    openai = to_openai_tool(my_mcp_tool)
    anthropic = to_anthropic_tool(my_mcp_tool)
    batch = convert_all(server_tools(), "openai")

The library accepts any object with ``name``, ``description``, and
``inputSchema`` attributes (duck-typed) so it does not require the MCP
Python SDK as a dependency.
"""

from mcpschema.adapters import (
    PROVIDERS,
    convert,
    convert_all,
    to_anthropic_tool,
    to_deepseek_tool,
    to_gemini_tool,
    to_mistral_tool,
    to_ollama_tool,
    to_openai_tool,
)
from mcpschema.tool import MCPTool, tool_from_dict

__all__ = [
    "MCPTool",
    "PROVIDERS",
    "convert",
    "convert_all",
    "to_anthropic_tool",
    "to_deepseek_tool",
    "to_gemini_tool",
    "to_mistral_tool",
    "to_ollama_tool",
    "to_openai_tool",
    "tool_from_dict",
]

__version__ = "0.1.0"