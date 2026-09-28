# MCP Yahoo Finance

![PyPI - Version](https://img.shields.io/pypi/v/mcp-yahoo-finance)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/mcp-yahoo-finance)
![PyPI - License](https://img.shields.io/pypi/l/mcp-yahoo-finance)


A [Model Context Protocol](https://modelcontextprotocol.io) (MCP) server for Yahoo Finance. It provides tools for prices, company information, historical data, financial statements, news, recommendations, earnings, dividends, and options.

> `mcp-yahoo-finance` is in early development. Tool names and response fields may change between releases.

## Installation

You can run `mcp-yahoo-finance` without a separate install by using
[`uvx`](https://docs.astral.sh/uv/guides/tools/).

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

## Examples of questions

1. "What is the stock price of Apple?"
2. "Give me a rich quote for AAPL with the previous close, intraday range, and market status."
3. "Show me the company overview for Nvidia."
4. "What is the difference in stock price between Apple and Google?"
5. "How much did the stock price of Apple change between 2024-01-01 and 2025-01-01?"
6. "What are the available options expiration dates for AAPL?"
7. "Show me the options chain for AAPL expiring on 2024-01-19"
8. "What are the call and put options for Tesla?"

## Response format

Tool calls return JSON-compatible structured data. For example, a rich quote
looks like this:

```json
{
  "symbol": "AAPL",
  "currentPrice": 243.5822,
  "previousClose": 241.33,
  "absoluteChange": 2.2522,
  "percentChange": 0.9331,
  "open": 242.1,
  "dayHigh": 244.2,
  "dayLow": 241.9,
  "volume": 45678901,
  "marketStatus": "REGULAR",
  "currency": "USD",
  "exchange": "NMS",
  "timestamp": "2025-01-02T15:30:00+00:00",
  "source": {
    "provider": "Yahoo Finance",
    "endpoint": "info",
    "fetchedAt": "2025-01-02T15:30:01+00:00"
  }
}
```

Errors use the same shape for every tool and are marked as MCP errors:

```json
{
  "error": {
    "code": "NO_DATA",
    "message": "No historical data found for AAPL"
  }
}
```

Historical and tabular results keep their column names and include dates as
`YYYY-MM-DD` calendar-date strings. This is true for both naive and
timezone-aware Yahoo Finance indexes; the provider timezone is not exposed.
Historical, single-date, and date-range price tools return adjusted prices by
default (split and dividend adjustments). `get_historical_stock_prices` accepts
`adjusted: false` when unadjusted OHLC values are required. A single-date
lookup and a date range use inclusive calendar dates; weekends and market
holidays return a structured `NO_DATA` error when no trading row exists.
Missing quote and company-overview fields are represented as `null`. News is
limited to 10 articles by default (up to 100), normalizes title, URL,
publisher, thumbnail, related symbols, and `publishedAt` as a UTC ISO 8601
timestamp, and accepts optional inclusive `start_date` and `end_date` filters.
Recommendations, earnings, dividends, statements, and options use the same
top-level `symbol` field and return provider-shaped data when it is available.

## Available tools

The server exposes these tools. `symbol` values use Yahoo Finance ticker
symbols, such as `AAPL` or `MSFT`.

| Tool | Purpose |
| --- | --- |
| `get_current_stock_price` | Current price and quote metadata |
| `get_rich_quote` | Normalized quote snapshot with price, change, session range, market status, and source metadata |
| `get_company_overview` | Normalized company profile with sector, industry, market cap, website, employee count, description, and source metadata |
| `get_symbol_comparison` | Current quote comparison for up to 20 symbols |
| `get_performance_analysis` | Bounded multi-symbol returns, moving averages, volatility, drawdown, benchmark-relative return, and correlation |
| `get_stock_price_by_date` | Adjusted closing price for one trading date |
| `get_stock_price_date_range` | Adjusted closing prices for an inclusive date range |
| `get_historical_stock_prices` | Historical prices by period and interval |
| `get_dividends` | Dividend history |
| `get_stock_splits` | Stock split history |
| `get_capital_gains` | Capital-gains distributions |
| `get_upcoming_dividends` | Upcoming dividend dates and rates |
| `get_earnings_analytics` | Earnings surprises and estimates |
| `get_income_statement` | Income statement by yearly, quarterly, or trailing frequency |
| `get_cashflow` | Cash-flow statement by frequency |
| `get_earning_dates` | Recent and upcoming earnings dates |
| `get_news` | Bounded, normalized Yahoo Finance news with optional date filters |
| `get_recommendations` | Analyst recommendations |
| `get_option_expiration_dates` | Available option expirations |
| `get_option_chain` | Bounded calls and puts for one expiration date with strike, moneyness, liquidity, spread, type, and count filters |
| `get_option_summary` | Implied volatility, open interest, volume, put/call ratios, and max-pain summary for one expiration |

Performance analysis uses split- and dividend-adjusted closes. Total return is
`(last close / first close) - 1`; annualized volatility is the standard
deviation of daily returns multiplied by `sqrt(252)`; maximum drawdown is the
minimum drawdown from a running peak. Correlations use daily returns on shared
trading dates, so symbols with unequal calendars remain comparable.

## Local development

Install the locked development environment with `uv sync`, then run:

```sh
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv build
```

The Makefile provides shortcuts for the common commands:

```sh
make test
make lint
make docker-build
```

The test suite mocks Yahoo Finance and does not make live provider requests.

## Build

Build the Docker image with:

```sh
docker build -t mcp-yahoo-finance .
```

## Test with MCP Inspector

```sh
npx @modelcontextprotocol/inspector uv run mcp-yahoo-finance
```

## Yahoo Finance limitations

Yahoo Finance data is provided by a third party and may be delayed, incomplete,
or unavailable. This project does not provide investment advice and does not
guarantee the accuracy, completeness, or timeliness of returned data. Check
important values against an authoritative source before relying on them.
