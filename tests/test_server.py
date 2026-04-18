from unittest.mock import MagicMock, patch

import pytest
from mcp.types import Tool

from mcp_yahoo_finance.server import YahooFinance
from mcp_yahoo_finance.utils import generate_tool


@pytest.fixture
def client_tools() -> list[Tool]:
    yf = YahooFinance()
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
        generate_tool(yf.get_option_expiration_dates),
        generate_tool(yf.get_option_chain),
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "tool_name",
    [
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
    ],
)
async def test_list_tools(client_tools: list[Tool], tool_name) -> None:
    tool_names = [tool.name for tool in client_tools]
    assert tool_name in tool_names


@pytest.mark.parametrize(
    "symbol, date, expected_price",
    [
        ("AAPL", "2025-01-02", "243.5822"),
        ("GOOG", "2025-01-03", "142.5683"),
        ("META", "2025-01-03", "594.8756"),
    ],
)
def test_get_stock_price_by_date(symbol, date, expected_price):
    import pandas as pd

    from mcp_yahoo_finance.server import YahooFinance

    mock_row = pd.Series({"Close": float(expected_price)})

    mock_df = pd.DataFrame({"Close": [float(expected_price)]})
    mock_df.index = pd.DatetimeIndex(["2025-01-02"])

    with patch("mcp_yahoo_finance.server.Ticker") as mock_ticker_class:
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = mock_df
        mock_ticker_class.return_value = mock_ticker

        yf = YahooFinance()
        result = yf.get_stock_price_by_date(symbol, date)

        assert result == expected_price
