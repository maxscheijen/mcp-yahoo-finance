import asyncio
import json

import pytest
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.types import TextContent, Tool


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
    ],
)
async def test_list_tools(client_tools: list[Tool], tool_name) -> None:
    tool_names = [tool.name for tool in client_tools]
    assert tool_name in tool_names


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "symbol, date, expected_price",
    [
        ("AAPL", "2025-01-01", 243.5822),
        ("GOOG", "2025-02-01", 202.4094),
        ("META", "2025-02-01", 696.8401),
    ],
)
async def test_get_stock_price_by_date(server_params, symbol, date, expected_price):
    async with (
        stdio_client(server_params) as (read, write),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        tool_result = await session.call_tool(
            "get_stock_price_by_date", {"symbol": symbol, "date": date}
        )

        assert len(tool_result.content) == 1
        assert isinstance(tool_result.content[0], TextContent)

        data = json.loads(tool_result.content[0].text)

        assert isinstance(data, float)
        assert data == expected_price
