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

    mock_df = pd.DataFrame({"Close": [float(expected_price)]})
    mock_df.index = pd.DatetimeIndex(["2025-01-02"])

    with patch("mcp_yahoo_finance.server.Ticker") as mock_ticker_class:
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = mock_df
        mock_ticker_class.return_value = mock_ticker

        yf = YahooFinance()
        result = yf.get_stock_price_by_date(symbol, date)

        assert result == {
            "symbol": symbol,
            "date": date,
            "close": float(expected_price),
        }
        mock_ticker.history.assert_called_once_with(
            start=date,
            end=("2025-01-03" if date == "2025-01-02" else "2025-01-04"),
            auto_adjust=True,
        )


def test_date_range_rejects_reversed_dates():
    result = YahooFinance().get_stock_price_date_range(
        "AAPL", "2025-01-03", "2025-01-02"
    )
    assert result == {
        "error": {
            "code": "INVALID_ARGUMENT",
            "message": "start_date must be on or before end_date",
        }
    }


def test_timezone_aware_indexes_use_calendar_dates():
    import pandas as pd

    from mcp_yahoo_finance.utils import dataframe_to_records

    frame = pd.DataFrame(
        {"Close": [10.5]},
        index=pd.DatetimeIndex(["2025-01-02 23:30:00-05:00"]),
    )
    assert dataframe_to_records(frame) == [{"date": "2025-01-02", "Close": 10.5}]


def test_structured_serialization_handles_dataframe_values():
    import json

    import numpy as np
    import pandas as pd

    from mcp_yahoo_finance.utils import dataframe_to_records

    frame = pd.DataFrame(
        {"Close": [np.float64(10.5), np.nan], "Volume": [np.int64(100), np.int64(200)]},
        index=pd.DatetimeIndex(["2025-01-02", "2025-01-03"]),
    )

    records = dataframe_to_records(frame)

    assert json.loads(json.dumps(records)) == [
        {"date": "2025-01-02", "Close": 10.5, "Volume": 100},
        {"date": "2025-01-03", "Close": None, "Volume": 200},
    ]


def test_empty_result_has_consistent_error_shape():
    import pandas as pd

    with patch("mcp_yahoo_finance.server.Ticker") as mock_ticker_class:
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = pd.DataFrame()
        mock_ticker_class.return_value = mock_ticker

        result = YahooFinance().get_historical_stock_prices("AAPL")

    assert result == {
        "error": {
            "code": "NO_DATA",
            "message": "No historical data found for AAPL",
        }
    }


def test_tool_result_to_mcp_marks_structured_errors():
    from mcp.types import CallToolResult

    from mcp_yahoo_finance.server import tool_result_to_mcp

    result = tool_result_to_mcp({"error": {"code": "NO_DATA", "message": "No data"}})

    assert isinstance(result, CallToolResult)
    assert result.structured_content == {
        "error": {"code": "NO_DATA", "message": "No data"}
    }
    assert result.is_error is True


def test_current_price_includes_quote_metadata():
    with patch("mcp_yahoo_finance.server.Ticker") as mock_ticker_class:
        mock_ticker_class.return_value.info = {
            "regularMarketPrice": 123.45,
            "currency": "USD",
            "exchange": "NMS",
            "regularMarketTime": 1735831800,
        }

        result = YahooFinance().get_current_stock_price("aapl")

    assert result["symbol"] == "AAPL"
    assert result["price"] == 123.45
    assert result["currency"] == "USD"
    assert result["source"] == "Yahoo Finance"


def test_news_is_normalized_bounded_and_supports_date_filters():
    with patch("mcp_yahoo_finance.server.Ticker") as mock_ticker_class:
        mock_ticker_class.return_value.get_news.return_value = [
            {
                "title": "Older story",
                "link": "https://example.com/old",
                "publisher": "Example",
                "providerPublishTime": 1735689600,
                "relatedTickers": ["msft", "AAPL", "AAPL"],
            },
            {
                "content": {
                    "title": "Current story",
                    "canonicalUrl": {"url": "https://example.com/current"},
                    "pubDate": "2025-01-03T12:00:00+02:00",
                    "provider": {"displayName": "Publisher"},
                    "thumbnail": {"originalUrl": "https://example.com/image"},
                    "finance": {"tickerSymbols": ["aapl"]},
                }
            },
            {"title": "Malformed"},
        ]

        result = YahooFinance().get_news(
            "aapl", limit=1, start_date="2025-01-02", end_date="2025-01-03"
        )
        mock_ticker_class.return_value.get_news.assert_called_once_with(count=100)

    assert result == {
        "symbol": "AAPL",
        "limit": 1,
        "news": [
            {
                "title": "Current story",
                "url": "https://example.com/current",
                "publisher": "Publisher",
                "publishedAt": "2025-01-03T10:00:00Z",
                "thumbnail": "https://example.com/image",
                "relatedSymbols": ["AAPL"],
            }
        ],
    }


@pytest.mark.parametrize(
    "kwargs, message",
    [
        ({"limit": 0}, "limit must be between 1 and 100"),
        (
            {"start_date": "2025-01-03", "end_date": "2025-01-02"},
            "start_date must be on or before end_date",
        ),
    ],
)
def test_news_rejects_invalid_filters(kwargs, message):
    result = YahooFinance().get_news("AAPL", **kwargs)

    assert result == {"error": {"code": "INVALID_ARGUMENT", "message": message}}


def test_news_empty_after_filter_has_consistent_error_shape():
    with patch("mcp_yahoo_finance.server.Ticker") as mock_ticker_class:
        mock_ticker_class.return_value.get_news.return_value = [
            {
                "title": "Story",
                "link": "https://example.com/story",
                "providerPublishTime": 1735689600,
            }
        ]

        result = YahooFinance().get_news("AAPL", start_date="2025-02-01")

    assert result == {"error": {"code": "NO_DATA", "message": "No news found for AAPL"}}
