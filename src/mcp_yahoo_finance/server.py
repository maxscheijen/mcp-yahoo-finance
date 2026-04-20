import json
from datetime import datetime, timedelta
from typing import Any, Literal

import pandas as pd
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool
from requests import Session
from yfinance import Ticker

from mcp_yahoo_finance.utils import generate_tool, validate_date, validate_symbol


class YahooFinance:
    def __init__(self, session: Session | None = None, verify: bool = True) -> None:
        self.session = session
        self._ticker_cache: dict[str, Ticker] = {}

        if self.session:
            self.session.verify = verify

    def _get_ticker(self, symbol: str) -> Ticker:
        if symbol not in self._ticker_cache:
            self._ticker_cache[symbol] = Ticker(ticker=symbol, session=self.session)
        return self._ticker_cache[symbol]

    def get_current_stock_price(self, symbol: str) -> str:
        """Get the current stock price based on stock symbol.

        Args:
            symbol (str): Stock symbol in Yahoo Finance format.
        """
        try:
            symbol = validate_symbol(symbol=symbol)
            stock = self._get_ticker(symbol).info
            current_price = stock.get("regularMarketPrice") or stock.get("currentPrice")
            if current_price is None:
                return f"Error: No price data found for {symbol}"
            return f"{current_price:.4f}"
        except ValueError as e:
            return f"Error: {str(e)}"
        except Exception as e:
            return f"Error: Failed to fetch price for {symbol}: {str(e)}"

    def get_stock_price_by_date(self, symbol: str, date: str) -> str:
        """Get the stock price for a given stock symbol on a specific date.

        Args:
            symbol (str): Stock symbol in Yahoo Finance format.
            date (str): The date in YYYY-MM-DD format.
        """
        try:
            symbol = validate_symbol(symbol=symbol)
            validate_date(date_str=date, param_name="date")
            stock = self._get_ticker(symbol)
            price = stock.history(start=date, period="1d")
            if price.empty:
                return f"Error: No trading data found for {symbol} on {date}"
            return f"{price.iloc[0]['Close']:.4f}"
        except ValueError as e:
            return f"Error: {str(e)}"
        except Exception as e:
            return f"Error: Failed to fetch price for {symbol}: {str(e)}"

    def get_stock_price_date_range(
        self, symbol: str, start_date: str, end_date: str
    ) -> str:
        """Get the stock prices for a given date range for a given stock symbol.

        Args:
            symbol (str): Stock symbol in Yahoo Finance format.
            start_date (str): The start date in YYYY-MM-DD format.
            end_date (str): The end date in YYYY-MM-DD format.
        """
        try:
            symbol = validate_symbol(symbol=symbol)
            validate_date(date_str=start_date, param_name="start_date")
            validate_date(date_str=end_date, param_name="end_date")

            stock = self._get_ticker(symbol)
            end = (
                datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
            ).strftime("%Y-%m-%d")
            prices = stock.history(start=start_date, end=end)
            if prices.empty:
                return f"Error: No trading data found for {symbol} between {start_date} and {end_date}"
            prices.index = prices.index.astype(str)
            return f"{prices['Close'].to_json(orient='index')}"
        except ValueError as e:
            return f"Error: {str(e)}"
        except Exception as e:
            return f"Error: Failed to fetch prices for {symbol}: {str(e)}"

    def get_historical_stock_prices(
        self,
        symbol: str,
        period: Literal[
            "1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"
        ] = "1mo",
        interval: Literal["1d", "5d", "1wk", "1mo", "3mo"] = "1d",
    ) -> str:
        """Get historical stock prices for a given stock symbol.

        Args:
            symbol (str): Stock symbol in Yahoo Finance format.
            period (str): The period for historical data. Defaults to "1mo".
                    Valid periods: "1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"
            interval (str): The interval beween data points. Defaults to "1d".
                    Valid intervals: "1d", "5d", "1wk", "1mo", "3mo"
        """
        try:
            symbol = validate_symbol(symbol=symbol)
            stock = self._get_ticker(symbol)
            prices = stock.history(period=period, interval=interval)
            if prices.empty:
                return f"Error: No historical data found for {symbol}"

            if hasattr(prices.index, "date"):
                prices.index = prices.index.date.astype(str)  # type: ignore
            return f"{prices['Close'].to_json(orient='index')}"
        except ValueError as e:
            return f"Error: {str(e)}"
        except Exception as e:
            return f"Error: Failed to fetch historical data for {symbol}: {str(e)}"

    def get_dividends(self, symbol: str) -> str:
        """Get dividends for a given stock symbol.

        Args:
            symbol (str): Stock symbol in Yahoo Finance format.
        """
        try:
            symbol = validate_symbol(symbol=symbol)
            stock = self._get_ticker(symbol)
            dividends = stock.dividends

            if dividends.empty:
                return f"Error: No dividend data found for {symbol}"

            if hasattr(dividends.index, "date"):
                dividends.index = dividends.index.date.astype(str)  # type: ignore
            return f"{dividends.to_json(orient='index')}"
        except ValueError as e:
            return f"Error: {str(e)}"
        except Exception as e:
            return f"Error: Failed to fetch dividends for {symbol}: {str(e)}"

    def get_income_statement(
        self, symbol: str, freq: Literal["yearly", "quarterly", "trailing"] = "yearly"
    ) -> str:
        """Get income statement for a given stock symbol.

        Args:
            symbol (str): Stock symbol in Yahoo Finance format.
            freq (str): At what frequency to get cashflow statements. Defaults to "yearly".
                    Valid freqencies: "yearly", "quarterly", "trainling"
        """
        try:
            symbol = validate_symbol(symbol=symbol)
            stock = self._get_ticker(symbol)
            income_statement = stock.get_income_stmt(freq=freq, pretty=True)

            if isinstance(income_statement, pd.DataFrame):
                income_statement.columns = [
                    str(col.date()) for col in income_statement.columns
                ]
                return f"{income_statement.to_json()}"
            return f"{income_statement}"
        except ValueError as e:
            return f"Error: {str(e)}"
        except Exception as e:
            return f"Error: Failed to fetch income statement for {symbol}: {str(e)}"

    def get_cashflow(
        self, symbol: str, freq: Literal["yearly", "quarterly", "trailing"] = "yearly"
    ) -> str:
        """Get cashflow for a given stock symbol.

        Args:
            symbol (str): Stock symbol in Yahoo Finance format.
            freq (str): At what frequency to get cashflow statements. Defaults to "yearly".
                    Valid freqencies: "yearly", "quarterly", "trainling"
        """
        try:
            symbol = validate_symbol(symbol=symbol)
            stock = self._get_ticker(symbol)
            cashflow = stock.get_cashflow(freq=freq, pretty=True)

            if isinstance(cashflow, pd.DataFrame):
                cashflow.columns = [str(col.date()) for col in cashflow.columns]
                return f"{cashflow.to_json(indent=2)}"
            return f"{cashflow}"
        except ValueError as e:
            return f"Error: {str(e)}"
        except Exception as e:
            return f"Error: Failed to fetch cashflow for {symbol}: {str(e)}"

    def get_earning_dates(self, symbol: str, limit: int = 12) -> str:
        """Get earning dates.


        Args:
            symbol (str): Stock symbol in Yahoo Finance format.
            limit (int): max amount of upcoming and recent earnings dates to return. Default value 12 should return next 4 quarters and last 8 quarters. Increase if more history is needed.
        """
        try:
            symbol = validate_symbol(symbol=symbol)
            if limit < 1 or limit > 100:
                return "Error: limit must be between 1 and 100"
            stock = self._get_ticker(symbol)
            earning_dates = stock.get_earnings_dates(limit=limit)

            if isinstance(earning_dates, pd.DataFrame):
                earning_dates.index = earning_dates.index.date.astype(str)  # type: ignore
                return f"{earning_dates.to_json(indent=2)}"
            return f"{earning_dates}"
        except ValueError as e:
            return f"Error: {str(e)}"
        except Exception as e:
            return f"Error: Failed to fetch earning dates for {symbol}: {str(e)}"

    def get_news(self, symbol: str) -> str:
        """Get news for a given stock symbol.

        Args:
            symbol (str): Stock symbol in Yahoo Finance format.
        """
        try:
            symbol = validate_symbol(symbol=symbol)
            stock = self._get_ticker(symbol)
            if not stock.news:
                return f"Error: No news found for {symbol}"
            return json.dumps(stock.news, indent=2)
        except ValueError as e:
            return f"Error: {str(e)}"
        except Exception as e:
            return f"Error: Failed to fetch news for {symbol}: {str(e)}"

    def get_recommendations(self, symbol: str) -> str:
        """Get analyst recommendations for a given symbol.

        Args:
            symbol (str): Stock symbol in Yahoo Finance format.
        """
        try:
            symbol = validate_symbol(symbol=symbol)
            stock = self._get_ticker(symbol)
            recommendations = stock.get_recommendations()
            if isinstance(recommendations, pd.DataFrame):
                return f"{recommendations.to_json(orient='records', indent=2)}"
            return f"{recommendations}"
        except ValueError as e:
            return f"Error: {str(e)}"
        except Exception as e:
            return f"Error: Failed to fetch recommendations for {symbol}: {str(e)}"

    def get_option_expiration_dates(self, symbol: str) -> str:
        """Get available options expiration dates for a given stock symbol.

        Args:
            symbol (str): Stock symbol in Yahoo Finance format.
        """
        try:
            symbol = validate_symbol(symbol=symbol)
            stock = self._get_ticker(symbol)
            expiration_dates = stock.options
            if not expiration_dates:
                return f"Error: No options data found for {symbol}"
            return json.dumps(list(expiration_dates), indent=2)
        except ValueError as e:
            return f"Error: {str(e)}"
        except Exception as e:
            return f"Error: Failed to fetch options for {symbol}: {str(e)}"

    def get_option_chain(self, symbol: str, expiration_date: str) -> str:
        """Get options chain for a specific expiration date.

        Args:
            symbol (str): Stock symbol in Yahoo Finance format.
            expiration_date (str): Options expiration date in YYYY-MM-DD format.
        """
        try:
            symbol = validate_symbol(symbol=symbol)
            validate_date(date_str=expiration_date, param_name="expiration_date")
            stock = self._get_ticker(symbol)
            option_chain = stock.option_chain(expiration_date)

            def _convert_dates(df: pd.DataFrame) -> pd.DataFrame:
                if df is None or "lastTradeDate" not in df.columns:
                    return df
                df = df.copy()
                df["lastTradeDate"] = df["lastTradeDate"].astype(str)
                return df

            result = {
                "calls": None,
                "puts": None,
                "underlying": option_chain.underlying,
            }

            if option_chain.calls is not None:
                result["calls"] = _convert_dates(option_chain.calls).to_dict(
                    orient="records"
                )

            if option_chain.puts is not None:
                result["puts"] = _convert_dates(option_chain.puts).to_dict(
                    orient="records"
                )

            return json.dumps(result, indent=2)
        except ValueError as e:
            return f"Error: {str(e)}"
        except Exception as e:
            return f"Error: Failed to fetch option chain for {symbol}: {str(e)}"


TOOL_REGISTRY: dict[str, callable] = {}


def register_tools(yf: YahooFinance) -> None:
    TOOL_REGISTRY.update(
        {
            "get_current_stock_price": yf.get_current_stock_price,
            "get_stock_price_by_date": yf.get_stock_price_by_date,
            "get_stock_price_date_range": yf.get_stock_price_date_range,
            "get_historical_stock_prices": yf.get_historical_stock_prices,
            "get_dividends": yf.get_dividends,
            "get_income_statement": yf.get_income_statement,
            "get_cashflow": yf.get_cashflow,
            "get_earning_dates": yf.get_earning_dates,
            "get_news": yf.get_news,
            "get_recommendations": yf.get_recommendations,
            "get_option_expiration_dates": yf.get_option_expiration_dates,
            "get_option_chain": yf.get_option_chain,
        }
    )


async def serve() -> None:
    server = Server("mcp-yahoo-finance")
    yf = YahooFinance()
    register_tools(yf)

    tools = [generate_tool(method) for method in TOOL_REGISTRY.values()]

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return tools

    @server.call_tool()
    async def call_tool(name: str, args: dict[str, Any]) -> list[TextContent]:
        if name not in TOOL_REGISTRY:
            raise ValueError(f"Unknown tool: {name}")
        result = TOOL_REGISTRY[name](**args)
        return [TextContent(type="text", text=result)]

    options = server.create_initialization_options()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, options, raise_exceptions=True)
