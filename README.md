# MCP Yahoo Finance

![PyPI - Version](https://img.shields.io/pypi/v/mcp-yahoo-finance)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/mcp-yahoo-finance)
![PyPI - License](https://img.shields.io/pypi/l/mcp-yahoo-finance)


A [Model Context Protocol](https://modelcontextprotocol.io) (MCP) server for Yahoo Finance interaction. This server provides tools to get pricing, company information and more.

> Please note that `mcp-yahoo-finance` is currently in early development. The functionality and available tools are subject to change and expansion as I continue to develop and improve the server.

## Installation

You don't need to manually install `mcp-yahoo-finance` if you use [`uv`](https://docs.astral.sh/uv/). We'll use [`uvx`](https://docs.astral.sh/uv/guides/tools/) to directly run `mcp-yahoo-finance`.

I would recommend using this method if you simply want to use the MCP server.

### Using pip

Using `pip`.

```sh
pip install mcp-yahoo-finance
```

### Using Git

You can also install the package after cloning the repository to your machine.

```sh
git clone git@github.com:maxscheijen/mcp-yahoo-finance.git
cd mcp-yahoo-finance
uv sync
```

## Configuration

### Claude Desktop

Add this to your `claude_desktop_config.json`:

```json
{
    "mcpServers": {
        "yahoo-finance": {
            "command": "uvx",
            "args": ["mcp-yahoo-finance"]
        }
    }
}
```
You can also use docker:

```json
{
    "mcpServers": {
        "yahoo-finance": {
            "command": "docker",
            "args": ["run", "-i", "--rm", "IMAGE"]
        }
    }
}
```

### VSCode

Add this to your `.vscode/mcp.json`:

```json
{
    "servers": {
        "yahoo-finance": {
            "command": "uvx",
            "args": ["mcp-yahoo-finance"]
        }
    }
}
```

## Examples of Questions

1. "What is the stock price of Apple?"
2. "What is the difference in stock price between Apple and Google?"
3. "How much did the stock price of Apple change between 2024-01-01 and 2025-01-01?"

## Build

Docker:

```sh
docker build -t [IMAGE] .
```

## Test with MCP Inspector

```sh
npx @modelcontextprotocol/inspector uv run mcp-yahoo-finance
```
