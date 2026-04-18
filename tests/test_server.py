import asyncio
from unittest.mock import MagicMock, patch

import pytest
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.types import Tool


@pytest.fixture
def server_params():
    return StdioServerParameters(command="mcp-yahoo-finance")


@pytest.fixture
def client_tools() -> list[Tool]:
    server_params = StdioServerParameters(command="mcp-yahoo-finance")

    async def _get_tools():
        async with (
            stdio_client(server_params) as (read, write),
            ClientSession(read, write) as session,
        ):
            await session.initialize()
            tool_list_result = await session.list_tools()
            return tool_list_result.tools

    return asyncio.run(_get_tools())


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
    from mcp_yahoo_finance.server import YahooFinance

    mock_df = MagicMock()
    mock_df.empty = False
    mock_df.iloc.__getitem__.return_value = {"Close": float(expected_price)}

    with patch("mcp_yahoo_finance.server.Ticker") as mock_ticker_class:
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = mock_df
        mock_ticker_class.return_value = mock_ticker

        yf = YahooFinance()
        result = yf.get_stock_price_by_date(symbol, date)

        assert result == expected_price
