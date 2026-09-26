import json
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import pandas as pd
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    CallToolRequestParams,
    CallToolResult,
    ListToolsResult,
    TextContent,
)
from requests import Session
from yfinance import Ticker

from mcp_yahoo_finance.utils import (
    dataframe_to_records,
    generate_tool,
    to_json_compatible,
    validate_date,
    validate_symbol,
)

ToolResult = dict[str, Any]


def error_result(code: str, message: str) -> ToolResult:
    """Return the common error shape used by every tool."""
    return {"error": {"code": code, "message": message}}


def _error_code(exc: Exception) -> str:
    if isinstance(exc, ValueError):
        return "INVALID_ARGUMENT"
    return "UPSTREAM_ERROR"


def _records(dataframe: pd.DataFrame) -> list[dict[str, Any]]:
    return dataframe_to_records(dataframe)


def _next_date(date_string: str) -> str:
    return (datetime.strptime(date_string, "%Y-%m-%d") + timedelta(days=1)).strftime(
        "%Y-%m-%d"
    )


def tool_result_to_mcp(result: ToolResult) -> CallToolResult:
    """Convert a tool result into MCP structured and readable content."""
    is_error = "error" in result
    text = result["error"]["message"] if is_error else json.dumps(result, indent=2)
    return CallToolResult(
        content=[TextContent(type="text", text=text)],
        structuredContent=result,
        isError=is_error,
    )


class YahooFinance:
    def __init__(self, session: Session | None = None, verify: bool = True) -> None:
        self.session = session
        if self.session:
            self.session.verify = verify

    def get_current_stock_price(self, symbol: str) -> ToolResult:
        """Get the current stock price based on stock symbol.

        Args:
            symbol (str): Stock symbol in Yahoo Finance format.
        """
        try:
            symbol = validate_symbol(symbol)
            info = Ticker(ticker=symbol, session=self.session).info
            price = info.get("regularMarketPrice") or info.get("currentPrice")
            if price is None:
                return error_result("NO_DATA", f"No current price found for {symbol}")
            result = {
                "symbol": symbol,
                "price": price,
                "currency": info.get("currency"),
                "exchange": info.get("exchange"),
                "source": "Yahoo Finance",
            }
            if info.get("regularMarketTime"):
                result["timestamp"] = datetime.fromtimestamp(
                    info["regularMarketTime"], timezone.utc
                ).isoformat()
            return to_json_compatible(result)
        except Exception as exc:
            return error_result(_error_code(exc), f"Error fetching {symbol}: {exc}")

    def get_stock_price_by_date(self, symbol: str, date: str) -> ToolResult:
        """Get the stock price for a given stock symbol on a specific date.

        Args:
            symbol (str): Stock symbol in Yahoo Finance format.
            date (str): The date in YYYY-MM-DD format.
        """
        try:
            symbol = validate_symbol(symbol)
            validate_date(date, "date")
            prices = Ticker(ticker=symbol, session=self.session).history(
                start=date, end=_next_date(date), auto_adjust=True
            )
            if prices.empty:
                return error_result(
                    "NO_DATA", f"No trading data found for {symbol} on {date}"
                )
            return {
                "symbol": symbol,
                "date": date,
                "close": to_json_compatible(prices.iloc[0]["Close"]),
            }
        except Exception as exc:
            return error_result(_error_code(exc), str(exc))

    def get_stock_price_date_range(
        self, symbol: str, start_date: str, end_date: str
    ) -> ToolResult:
        """Get stock prices for a symbol over an inclusive date range.

        Args:
            symbol (str): Stock symbol in Yahoo Finance format.
            start_date (str): The start date in YYYY-MM-DD format.
            end_date (str): The end date in YYYY-MM-DD format.
        """
        try:
            symbol = validate_symbol(symbol)
            validate_date(start_date, "start_date")
            validate_date(end_date, "end_date")
            if start_date > end_date:
                return error_result(
                    "INVALID_ARGUMENT", "start_date must be on or before end_date"
                )
            prices = Ticker(ticker=symbol, session=self.session).history(
                start=start_date, end=_next_date(end_date), auto_adjust=True
            )
            if prices.empty:
                return error_result(
                    "NO_DATA",
                    f"No trading data found for {symbol} between {start_date} and {end_date}",
                )
            return {
                "symbol": symbol,
                "startDate": start_date,
                "endDate": end_date,
                "adjusted": True,
                "prices": _records(prices[["Close"]]),
            }
        except Exception as exc:
            return error_result(_error_code(exc), str(exc))

    def get_historical_stock_prices(
        self,
        symbol: str,
        period: Literal[
            "1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"
        ] = "1mo",
        interval: Literal["1d", "5d", "1wk", "1mo", "3mo"] = "1d",
        adjusted: bool = True,
    ) -> ToolResult:
        """Get historical stock prices for a given stock symbol.

        Args:
            symbol (str): Stock symbol in Yahoo Finance format.
            period (str): The period for historical data.
            interval (str): The interval between data points.
            adjusted (bool): Return split- and dividend-adjusted prices. Defaults to True.
        """
        try:
            symbol = validate_symbol(symbol)
            prices = Ticker(ticker=symbol, session=self.session).history(
                period=period, interval=interval, auto_adjust=adjusted
            )
            if prices.empty:
                return error_result("NO_DATA", f"No historical data found for {symbol}")
            return {
                "symbol": symbol,
                "period": period,
                "interval": interval,
                "adjusted": adjusted,
                "prices": _records(prices),
            }
        except Exception as exc:
            return error_result(_error_code(exc), str(exc))

    def get_dividends(self, symbol: str) -> ToolResult:
        """Get dividends for a given stock symbol.

        Args:
            symbol (str): Stock symbol in Yahoo Finance format.
        """
        try:
            symbol = validate_symbol(symbol)
            dividends = Ticker(ticker=symbol, session=self.session).dividends
            if dividends.empty:
                return error_result("NO_DATA", f"No dividend data found for {symbol}")
            records = [
                {"date": to_json_compatible(index), "amount": to_json_compatible(value)}
                for index, value in dividends.items()
            ]
            return {"symbol": symbol, "dividends": records}
        except Exception as exc:
            return error_result(_error_code(exc), str(exc))

    def _get_statement(self, symbol: str, freq: str, kind: str) -> ToolResult:
        symbol = validate_symbol(symbol)
        stock = Ticker(ticker=symbol, session=self.session)
        statement = (
            stock.get_income_stmt(freq=freq, pretty=True)
            if kind == "incomeStatement"
            else stock.get_cashflow(freq=freq, pretty=True)
        )
        if not isinstance(statement, pd.DataFrame) or statement.empty:
            return error_result("NO_DATA", f"No {kind} data found for {symbol}")
        return {"symbol": symbol, "frequency": freq, kind: _records(statement)}

    def get_income_statement(
        self, symbol: str, freq: Literal["yearly", "quarterly", "trailing"] = "yearly"
    ) -> ToolResult:
        """Get the income statement for a given stock symbol.

        Args:
            symbol (str): Stock symbol in Yahoo Finance format.
            freq (str): Statement frequency. Defaults to "yearly".
        """
        try:
            return self._get_statement(symbol, freq, "incomeStatement")
        except Exception as exc:
            return error_result(_error_code(exc), str(exc))

    def get_cashflow(
        self, symbol: str, freq: Literal["yearly", "quarterly", "trailing"] = "yearly"
    ) -> ToolResult:
        """Get the cashflow statement for a given stock symbol.

        Args:
            symbol (str): Stock symbol in Yahoo Finance format.
            freq (str): Statement frequency. Defaults to "yearly".
        """
        try:
            return self._get_statement(symbol, freq, "cashflow")
        except Exception as exc:
            return error_result(_error_code(exc), str(exc))

    def get_earning_dates(self, symbol: str, limit: int = 12) -> ToolResult:
        """Get recent and upcoming earnings dates.

        Args:
            symbol (str): Stock symbol in Yahoo Finance format.
            limit (int): Maximum number of earnings dates, from 1 to 100.
        """
        try:
            symbol = validate_symbol(symbol)
            if not 1 <= limit <= 100:
                return error_result(
                    "INVALID_ARGUMENT", "limit must be between 1 and 100"
                )
            earnings = Ticker(ticker=symbol, session=self.session).get_earnings_dates(
                limit=limit
            )
            if not isinstance(earnings, pd.DataFrame) or earnings.empty:
                return error_result("NO_DATA", f"No earnings data found for {symbol}")
            return {"symbol": symbol, "limit": limit, "earnings": _records(earnings)}
        except Exception as exc:
            return error_result(_error_code(exc), str(exc))

    def get_news(self, symbol: str) -> ToolResult:
        """Get news for a given stock symbol.

        Args:
            symbol (str): Stock symbol in Yahoo Finance format.
        """
        try:
            symbol = validate_symbol(symbol)
            news = Ticker(ticker=symbol, session=self.session).news
            if not news:
                return error_result("NO_DATA", f"No news found for {symbol}")
            return {"symbol": symbol, "news": to_json_compatible(news)}
        except Exception as exc:
            return error_result(_error_code(exc), str(exc))

    def get_recommendations(self, symbol: str) -> ToolResult:
        """Get analyst recommendations for a given symbol.

        Args:
            symbol (str): Stock symbol in Yahoo Finance format.
        """
        try:
            symbol = validate_symbol(symbol)
            recommendations = Ticker(
                ticker=symbol, session=self.session
            ).get_recommendations()
            if not isinstance(recommendations, pd.DataFrame) or recommendations.empty:
                return error_result("NO_DATA", f"No recommendations found for {symbol}")
            return {"symbol": symbol, "recommendations": _records(recommendations)}
        except Exception as exc:
            return error_result(_error_code(exc), str(exc))

    def get_option_expiration_dates(self, symbol: str) -> ToolResult:
        """Get available option expiration dates for a stock symbol.

        Args:
            symbol (str): Stock symbol in Yahoo Finance format.
        """
        try:
            symbol = validate_symbol(symbol)
            dates = Ticker(ticker=symbol, session=self.session).options
            if not dates:
                return error_result("NO_DATA", f"No options data found for {symbol}")
            return {"symbol": symbol, "expirationDates": list(dates)}
        except Exception as exc:
            return error_result(_error_code(exc), str(exc))

    def get_option_chain(self, symbol: str, expiration_date: str) -> ToolResult:
        """Get an option chain for a specific expiration date.

        Args:
            symbol (str): Stock symbol in Yahoo Finance format.
            expiration_date (str): Expiration date in YYYY-MM-DD format.
        """
        try:
            symbol = validate_symbol(symbol)
            validate_date(expiration_date, "expiration_date")
            chain = Ticker(ticker=symbol, session=self.session).option_chain(
                expiration_date
            )
            return {
                "symbol": symbol,
                "expirationDate": expiration_date,
                "underlying": to_json_compatible(chain.underlying),
                "calls": _records(chain.calls) if chain.calls is not None else [],
                "puts": _records(chain.puts) if chain.puts is not None else [],
            }
        except Exception as exc:
            return error_result(_error_code(exc), str(exc))


TOOL_REGISTRY: dict[str, Any] = {}


def register_tools(yf: YahooFinance) -> None:
    TOOL_REGISTRY.clear()
    names = (
        "get_current_stock_price",
        "get_stock_price_by_date",
        "get_stock_price_date_range",
        "get_historical_stock_prices",
        "get_dividends",
        "get_income_statement",
        "get_cashflow",
        "get_earning_dates",
        "get_news",
        "get_recommendations",
        "get_option_expiration_dates",
        "get_option_chain",
    )
    TOOL_REGISTRY.update({name: getattr(yf, name) for name in names})


async def serve() -> None:
    register_tools(YahooFinance())
    tools = [generate_tool(method) for method in TOOL_REGISTRY.values()]

    async def list_tools(_context: Any, _params: Any) -> ListToolsResult:
        return ListToolsResult(tools=tools)

    async def call_tool(_context: Any, params: CallToolRequestParams) -> CallToolResult:
        if params.name not in TOOL_REGISTRY:
            return tool_result_to_mcp(
                error_result("UNKNOWN_TOOL", f"Unknown tool: {params.name}")
            )
        return tool_result_to_mcp(
            TOOL_REGISTRY[params.name](**(params.arguments or {}))
        )

    server = Server(
        "mcp-yahoo-finance",
        on_list_tools=list_tools,
        on_call_tool=call_tool,
    )
    options = server.create_initialization_options()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, options, raise_exceptions=True)
