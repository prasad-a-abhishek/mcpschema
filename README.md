# mcpschema

[![PyPI](https://img.shields.io/badge/version-0.1.0-blue)](https://pypi.org/project/mcpschema)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-137%20passing-brightgreen.svg)](tests/)
[![Zero runtime deps](https://img.shields.io/badge/dependencies-none-blueviolet)](pyproject.toml)

> **Convert MCP tool schemas to OpenAI, Anthropic, Gemini, and other LLM provider formats — zero dependencies.**

`mcpschema` translates `mcp.types.Tool` `inputSchema` dicts into the
tool-call shapes used by OpenAI, Anthropic, Gemini, Ollama, DeepSeek, and
Mistral — so you can route an MCP server's tools to any LLM provider
without reimplementing the conversion per-provider. It runs as a library
**and** a CLI.

## Quick Start

Install from source:

```bash
pip install git+https://github.com/prasad-a-abhishek/mcpschema.git
```

Convert a single MCP tool to any provider format:

```python
from mcpschema import to_openai_tool, to_anthropic_tool, to_gemini_tool, to_ollama_tool

mcp_tool = {
    "name": "git_log",
    "description": "Get recent commits",
    "inputSchema": {
        "type": "object",
        "properties": {"n": {"type": "integer", "default": 10, "description": "Number of commits"}},
        "required": ["n"],
    },
}

openai = to_openai_tool(mcp_tool)       # {"type": "function", "function": {...}}
anthropic = to_anthropic_tool(mcp_tool) # {"name", "description", "input_schema"}
gemini = to_gemini_tool(mcp_tool)       # {"name", "description", "parameters": {OBJECT,...}}
ollama = to_ollama_tool(mcp_tool)       # + "system_prompt_suffix" for local-model prompting
```

Convert a whole server's tools in one call:

```python
from mcpschema import convert_all

tools = server.list_tools()  # any iterable of mcp.types.Tool
openai_batch = convert_all(tools, "openai")
```

## ⚡ Performance & Benchmarks

mcpschema is a thin, pure-Python library — every adapter is a single function.
We benchmark against a hand-written equivalent (the de-facto "no library" path
that every developer reaches for when they hit issue #235 of the MCP Python SDK).

The honest summary: mcpschema wins on **batch conversion** (saving per-tool
function-call overhead) and ties the hand-written baseline on single-tool
conversions. Full results in [benchmarks/BENCHMARK.md](benchmarks/BENCHMARK.md)
include every workload — including the ones where the hand-written baseline
is faster. Reproduce locally:

```bash
python benchmarks/run_benchmark.py
```

## Why `mcpschema`? (Problem & Trade-Off Statement)

The MCP Python SDK ships no adapter module — developers integrating MCP
with non-MCP LLM providers each hand-roll their own `inputSchema` →
provider-format conversion. Three GitHub issues document the gap:

- [`modelcontextprotocol/python-sdk#235`](https://github.com/modelcontextprotocol/python-sdk/issues/235) — "Official Adapter Functions for LLM Providers in MCP Python SDK" (18 reactions, open since 2024)
- [`modelcontextprotocol/python-sdk#226`](https://github.com/modelcontextprotocol/python-sdk/issues/226) — schema-conversion complexity (16 reactions)
- [`anthropics/claude-code#6915`](https://github.com/anthropics/claude-code/issues/6915) — multi-agent routing (89 reactions)

**What mcpschema is:** a focused, zero-dependency library that does ONE thing
(schema conversion) and does it well. It is NOT an LLM client, NOT a MCP
server, and NOT a replacement for the SDK.

**What mcpschema is NOT:**
- Not an LLM client. It only converts schemas; it never calls a provider.
- Not coupled to the MCP SDK. It accepts any object with `name`, `description`,
  `inputSchema` (duck-typed), so the SDK stays out of your dependency tree.
- Not a streaming/conversation manager. See the [out-of-scope list](#out-of-scope)
  below.

**Trade-offs you accept by using mcpschema:**
- Defaults are stripped on conversion (per the OpenAI/Anthropic/Gemini API
  specs). If you need to preserve them, copy them out before converting.
- `anyOf`/`oneOf`/`allOf` are not in any provider's tool-call schema; we
  drop them rather than silently mis-modeling them.
- New provider API changes require a small library update (each adapter is
  ~20 LOC).

## Key Features & Complete API / CLI Reference

### Library API

| Function | Returns | Provider |
|----------|---------|----------|
| `to_openai_tool(tool)` | `{"type":"function","function":{...}}` | OpenAI / GPT-4o / GPT-5 |
| `to_anthropic_tool(tool)` | `{"name","description","input_schema"}` | Anthropic Claude |
| `to_gemini_tool(tool)` | `{"name","description","parameters":{OBJECT,...}}` | Google Gemini |
| `to_ollama_tool(tool)` | OpenAI shape + `system_prompt_suffix` | Ollama (local models) |
| `to_deepseek_tool(tool)` | OpenAI shape | DeepSeek |
| `to_mistral_tool(tool)` | OpenAI shape | Mistral |
| `convert(tool, "provider")` | dispatches to the right adapter | any |
| `convert_all(tools, "provider")` | list | any |
| `tool_from_dict(raw)` | `MCPTool` | helper |
| `PROVIDERS` | dict mapping provider names to callables | — |

### CLI

```text
$ mcpschema --help
usage: mcpschema [-h] [--version] {providers,convert} ...

Convert MCP tool schemas to OpenAI, Anthropic, Gemini, Ollama, DeepSeek,
and Mistral tool-call formats.

$ mcpschema providers
mcpschema 0.1.0 supports 6 providers:
  - anthropic
  - deepseek
  - gemini
  - mistral
  - ollama
  - openai

$ mcpschema convert --provider openai --input '[{"name":"git_log","description":"...","inputSchema":{...}}]'
[
  {
    "type": "function",
    "function": {
      "name": "git_log",
      "description": "...",
      "parameters": {
        "type": "object",
        "properties": {"n": {"type": "integer"}},
        "required": ["n"]
      }
    }
  }
]

$ echo '[{...}]' | mcpschema convert --provider anthropic --input -
```

Flags:
- `--provider` (required): target provider name (case-insensitive)
- `--input` (required): JSON payload (single dict, list, or `-` for stdin)
- `--compact`: emit single-line JSON instead of pretty-printed

### Out of scope

- LLM provider authentication or API calls
- MCP server implementation
- Provider-specific parameter constraints (e.g. OpenAI's `max_items` limits)
- Streaming response parsing
- Multi-turn conversation management
- Tool result conversion (MCP → provider response format)

### Limitations

- **Defaults are stripped** — none of OpenAI/Anthropic/Gemini/Ollama's
  tool-call schemas accept `default` values.
- **`anyOf`/`oneOf`/`allOf` are dropped** — these JSON-Schema keywords are
  not in any provider's tool format.
- **Deeply nested objects** (>3 levels) may need flattening for some
  providers — we preserve nesting as deep as it goes.
- **Schema validation is not strict** — we coerce loose schemas (missing
  `type`, missing `properties`) to valid provider shapes rather than raising.

## Tests

```bash
pytest tests/ -q
```

137 tests across 9 files. Coverage spans all 22 spec acceptance criteria
plus angular sweep (empty/None inputs, unicode, large schemas, malformed
schemas, regression guards, batch conversion, JSON-RPC round-trip).

## License

MIT — see [LICENSE](LICENSE).