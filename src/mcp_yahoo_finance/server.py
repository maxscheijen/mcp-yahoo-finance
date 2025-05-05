import json
from typing import Any, Literal

import pandas as pd
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool
from requests import Session
from yfinance import Ticker

from mcp_yahoo_finance.utils import generate_tool


class YahooFinance:
    def __init__(self, session: Session | None = None, verify: bool = True) -> None:
        self.session = session or Session()
        self.session.verify = verify

    def get_current_stock_price(self, symbol: str) -> str:
        """Get the current stock price based on stock symbol.

        Args:
            symbol (str): Stock symbol in Yahoo Finance format.
        """
        stock = Ticker(ticker=symbol, session=self.session).info
        current_price = stock.get(
            "regularMarketPrice", stock.get("currentPrice", "N/A")
        )
        return (
            f"{current_price:.4f}"
            if current_price
            else f"Couldn't fetch {symbol} current price"
        )

    def get_stock_price_by_date(self, symbol: str, date: str) -> str:
        """Get the stock price for a given stock symbol on a specific date.

        Args:
            symbol (str): Stock symbol in Yahoo Finance format.
            date (str): The date in YYYY-MM-DD format.
        """
        stock = Ticker(ticker=symbol, session=self.session)
        price = stock.history(start=date, period="1d")
        return f"{price.iloc[0]['Close']:.4f}"

    def get_stock_price_date_range(
        self, symbol: str, start_date: str, end_date: str
    ) -> str:
        """Get the stock prices for a given date range for a given stock symbol.

        Args:
            symbol (str): Stock symbol in Yahoo Finance format.
            start_date (str): The start date in YYYY-MM-DD format.
            end_date (str): The end date in YYYY-MM-DD format.
        """
        stock = Ticker(ticker=symbol, session=self.session)
        prices = stock.history(start=start_date, end=end_date)
        prices.index = prices.index.astype(str)
        return f"{prices['Close'].to_json(orient='index')}"

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
        stock = Ticker(ticker=symbol, session=self.session)
        prices = stock.history(period=period, interval=interval)

        if hasattr(prices.index, "date"):
            prices.index = prices.index.date.astype(str)  # type: ignore
        return f"{prices['Close'].to_json(orient='index')}"

    def get_dividends(self, symbol: str) -> str:
        """Get dividends for a given stock symbol.

        Args:
            symbol (str): Stock symbol in Yahoo Finance format.
        """
        stock = Ticker(ticker=symbol, session=self.session)
        dividends = stock.dividends

        if hasattr(dividends.index, "date"):
            dividends.index = dividends.index.date.astype(str)  # type: ignore
        return f"{dividends.to_json(orient='index')}"

    def get_income_statement(
        self, symbol: str, freq: Literal["yearly", "quarterly", "trainling"] = "yearly"
    ) -> str:
        """Get income statement for a given stock symbol.

        Args:
            symbol (str): Stock symbol in Yahoo Finance format.
            freq (str): At what frequency to get cashflow statements. Defaults to "yearly".
                    Valid freqencies: "yearly", "quarterly", "trainling"
        """
        stock = Ticker(ticker=symbol, session=self.session)
        income_statement = stock.get_income_stmt(freq=freq, pretty=True)

        if isinstance(income_statement, pd.DataFrame):
            income_statement.columns = [
                str(col.date()) for col in income_statement.columns
            ]
            return f"{income_statement.to_json()}"
        return f"{income_statement}"

    def get_cashflow(
        self, symbol: str, freq: Literal["yearly", "quarterly", "trainling"] = "yearly"
    ):
        """Get cashflow for a given stock symbol.

        Args:
            symbol (str): Stock symbol in Yahoo Finance format.
            freq (str): At what frequency to get cashflow statements. Defaults to "yearly".
                    Valid freqencies: "yearly", "quarterly", "trainling"
        """
        stock = Ticker(ticker=symbol, session=self.session)
        cashflow = stock.get_cashflow(freq=freq, pretty=True)

        if isinstance(cashflow, pd.DataFrame):
            cashflow.columns = [str(col.date()) for col in cashflow.columns]
            return f"{cashflow.to_json(indent=2)}"
        return f"{cashflow}"

    def get_earning_dates(self, symbol: str, limit: int = 12) -> str:
        """Get earning dates.


        Args:
            symbol (str): Stock symbol in Yahoo Finance format.
            limit (int): max amount of upcoming and recent earnings dates to return. Default value 12 should return next 4 quarters and last 8 quarters. Increase if more history is needed.
        """

        stock = Ticker(ticker=symbol, session=self.session)
        earning_dates = stock.get_earnings_dates(limit=limit)

        if isinstance(earning_dates, pd.DataFrame):
            earning_dates.index = earning_dates.index.date.astype(str)  # type: ignore
            return f"{earning_dates.to_json(indent=2)}"
        return f"{earning_dates}"

    def get_news(self, symbol: str) -> str:
        """Get news for a given stock symbol.

        Args:
            symbol (str): Stock symbol in Yahoo Finance format.
        """
        stock = Ticker(ticker=symbol, session=self.session)
        return json.dumps(stock.news, indent=2)

    def get_recommendations(self, symbol: str) -> str:
        """Get analyst recommendations for a given symbol.

        Args:
            symbol (str): Stock symbol in Yahoo Finance format.
        """
        stock = Ticker(ticker=symbol, session=self.session)
        recommendations = stock.get_recommendations()
        print(recommendations)
        if isinstance(recommendations, pd.DataFrame):
            return f"{recommendations.to_json(orient='records', indent=2)}"
        return f"{recommendations}"


async def serve() -> None:
    server = Server("mcp-yahoo-finance")
    yf = YahooFinance()

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            generate_tool(yf.get_current_stock_price),
            generate_tool(yf.get_stock_price_by_date),
            generate_tool(yf.get_stock_price_date_range),
            generate_tool(yf.get_historical_stock_prices),
            generate_tool(yf.get_dividends),
            generate_tool(yf.get_income_statement),
            generate_tool(yf.get_cashflow),
            generate_tool(yf.get_earning_dates),
            generate_tool(yf.get_news),
            generate_tool(yf.get_recommendations),
        ]

    @server.call_tool()
    async def call_tool(name: str, args: dict[str, Any]) -> list[TextContent]:
        match name:
            case "get_current_stock_price":
                price = yf.get_current_stock_price(**args)
                return [TextContent(type="text", text=price)]
            case "get_stock_price_by_date":
                price = yf.get_stock_price_by_date(**args)
                return [TextContent(type="text", text=price)]
            case "get_stock_price_date_range":
                price = yf.get_stock_price_date_range(**args)
                return [TextContent(type="text", text=price)]
            case "get_historical_stock_prices":
                price = yf.get_historical_stock_prices(**args)
                return [TextContent(type="text", text=price)]
            case "get_dividends":
                price = yf.get_dividends(**args)
                return [TextContent(type="text", text=price)]
            case "get_income_statement":
                price = yf.get_income_statement(**args)
                return [TextContent(type="text", text=price)]
            case "get_cashflow":
                price = yf.get_cashflow(**args)
                return [TextContent(type="text", text=price)]
            case "get_earning_dates":
                price = yf.get_earning_dates(**args)
                return [TextContent(type="text", text=price)]
            case "get_news":
                price = yf.get_news(**args)
                return [TextContent(type="text", text=price)]
            case "get_recommendations":
                recommendations = yf.get_recommendations(**args)
                return [TextContent(type="text", text=recommendations)]
            case _:
                raise ValueError(f"Unknown tool: {name}")

    options = server.create_initialization_options()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, options, raise_exceptions=True)
