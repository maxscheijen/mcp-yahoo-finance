# MCP Yahoo Finance

## Overview

A Model Context Protocol (MCP) server for Yahoo Finance interaction. This server provides tools to get pricing, company information and more.

> Please note that `mcp-yahoo-finance` is currently in early development. The functionality and available tools are subject to change and expansion as I continue to develop and improve the server.

## Installation

Clone the repository to your machine.

```sh
git clone git@github.com:maxscheijen/mcp-yahoo-finance.git
```

In the future this server will be made available on PyPi.

## Configuration

### Claude Desktop

Add this to your `claude_desktop_config.json`:

```json
{
    "mcpServers": {
        "yahoo-finance": {
            "command": "uv",
            "args": [
                "--directory",
                "/path/to/repo",
                "run",
                "mcp-yahoo-finance"
            ]
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
            "command": "uv",
            "args": [
                "--directory",
                "/path/to/repo",
                "run",
                "mcp-yahoo-finance"
            ]
        }
    }
}
```

## Examples of Questions

1. "What is the stock price of Apple?"
2. "What is the difference in stock price between Apple and Google?"
3. "How much did the stock price of Apple change between 2024-01-01 and 2025-01-01?"
