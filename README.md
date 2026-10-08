# MCP Yahoo Finance

![PyPI - Version](https://img.shields.io/pypi/v/mcp-yahoo-finance)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/mcp-yahoo-finance)
![PyPI - License](https://img.shields.io/pypi/l/mcp-yahoo-finance)

MCP Yahoo Finance is a [Model Context Protocol](https://modelcontextprotocol.io) (MCP) server. It gets data from Yahoo Finance. You can use it to get stock prices, company data, past prices, financial reports, news, analyst ratings, earnings dates, dividends, and options data.

> This project is in early development. Tool names and response fields can change between releases.

## Install

You can run `mcp-yahoo-finance` without a separate install. Use [`uvx`](https://docs.astral.sh/uv/guides/tools/).

### Use pip

```sh
pip install mcp-yahoo-finance
```

### Use Git

Clone the repository. Then install the development environment:

```sh
git clone git@github.com:maxscheijen/mcp-yahoo-finance.git
cd mcp-yahoo-finance
uv sync
```

## Configure

### Claude Desktop

Add this entry to your `claude_desktop_config.json` file:

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

You can also use Docker. Replace `IMAGE` with the Docker image name:

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

### VS Code

Add this entry to your `.vscode/mcp.json` file:

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

## Example questions

You can ask questions like these:

1. "What is the stock price of Apple?"
2. "Give me a rich quote for AAPL with the previous close, intraday range, and market status."
3. "Show me the company overview for Nvidia."
4. "What is the difference in stock price between Apple and Google?"
5. "How much did the stock price of Apple change between 2024-01-01 and 2025-01-01?"
6. "What are the available options expiration dates for AAPL?"
7. "Show me the options chain for AAPL expiring on 2024-01-19."
8. "What are the call and put options for Tesla?"

## Response data

Tools return data in JSON format. This is an example of a rich quote:

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

Errors use the same format for all tools. An error includes an error code and a message:

```json
{
  "error": {
    "code": "NO_DATA",
    "message": "No historical data found for AAPL"
  }
}
```

Historical and table results keep the column names from the data source. Dates use the `YYYY-MM-DD` format. The server does not show the time zone used by Yahoo Finance.

Historical price tools return adjusted prices by default. Adjusted prices include changes from stock splits and dividends. To get prices without these changes, set `adjusted` to `false` in `get_historical_stock_prices`.

Date searches include both the start date and the end date. If a date is a weekend or market holiday, there may be no price data for that date. In that case, the tool returns a `NO_DATA` error.

If quote or company data is missing, its value is `null`. The news tool returns 10 articles by default. It can return up to 100 articles. It includes the title, URL, publisher, thumbnail, related stock symbols, and publish time. The publish time uses UTC and the ISO 8601 format. You can set `start_date` and `end_date` to filter news. The filter includes both dates.

Recommendation, earnings, dividend, financial report, and options tools use a top-level `symbol` field. They return data from Yahoo Finance when that data is available.

## Available tools

Use Yahoo Finance ticker symbols for `symbol` values. Examples are `AAPL` and `MSFT`.

| Tool | Purpose |
| --- | --- |
| `get_current_stock_price` | Gets the current stock price and quote data. |
| `get_rich_quote` | Gets a quote with price, price change, trading range, market status, and source data. |
| `get_company_overview` | Gets a company profile with its sector, industry, market value, website, employee count, description, and source data. |
| `get_symbol_comparison` | Compares current quotes for up to 20 symbols. |
| `get_performance_analysis` | Compares returns, moving averages, volatility, drawdown, benchmark returns, and correlation for multiple symbols. |
| `get_stock_price_by_date` | Gets the adjusted closing price for one trading date. |
| `get_stock_price_date_range` | Gets adjusted closing prices for a date range. |
| `get_historical_stock_prices` | Gets past prices for a period and time interval. |
| `get_dividends` | Gets past dividend payments. |
| `get_stock_splits` | Gets past stock splits. |
| `get_capital_gains` | Gets capital-gains payments. |
| `get_upcoming_dividends` | Gets future dividend dates and rates. |
| `get_earnings_analytics` | Gets earnings results and estimates. |
| `get_income_statement` | Gets an income statement by year, quarter, or trailing period. |
| `get_cashflow` | Gets a cash flow statement by period. |
| `get_earning_dates` | Gets past and future earnings dates. |
| `get_news` | Gets Yahoo Finance news. You can set date filters. |
| `get_recommendations` | Gets analyst recommendations. |
| `get_option_expiration_dates` | Gets available option expiration dates. |
| `get_option_chain` | Gets calls and puts for one expiration date. You can filter by strike price, moneyness, liquidity, spread, type, and number of results. |
| `get_option_summary` | Gets implied volatility, open interest, volume, put/call ratios, and max pain for one expiration date. |

## Performance calculations

Performance analysis uses closing prices adjusted for stock splits and dividends.

Total return is `(last close / first close) - 1`.

Annual volatility is the standard deviation of daily returns multiplied by `sqrt(252)`.

Maximum drawdown is the largest fall from a previous high.

The tool calculates correlation from daily returns on dates shared by the symbols. This lets it compare symbols that have different trading calendars.

## Develop locally

Run `uv sync` to install the locked development environment. Then run these commands:

```sh
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv build
```

You can also use these Makefile commands:

```sh
make test
make lint
make docker-build
```

The tests use mock Yahoo Finance data. They do not make live requests to Yahoo Finance.

## Build the Docker image

Run this command:

```sh
docker build -t mcp-yahoo-finance .
```

## Test with MCP Inspector

Run this command:

```sh
npx @modelcontextprotocol/inspector uv run mcp-yahoo-finance
```

## Yahoo Finance limits

Yahoo Finance is a third-party data source. Its data can be late, incomplete, or unavailable. This project does not give investment advice. It does not guarantee that the data is correct, complete, or up to date. Check important data with an authoritative source before you use it.
