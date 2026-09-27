from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from mcp.types import CallToolRequestParams, CallToolResult

from mcp_yahoo_finance.server import (
    TOOL_REGISTRY,
    YahooFinance,
    call_registered_tool,
    register_tools,
)


def _prices() -> pd.DataFrame:
    return pd.DataFrame(
        {"Open": [99.0, 101.0], "Close": [100.0, 102.0], "Volume": [100, 200]},
        index=pd.DatetimeIndex(["2025-01-02", "2025-01-03"]),
    )


def _statement() -> pd.DataFrame:
    return pd.DataFrame(
        {pd.Timestamp("2024-01-01"): [100], pd.Timestamp("2023-01-01"): [90]},
        index=pd.Index(["Total Revenue"], name="Breakdown"),
    )


def _option_chain() -> SimpleNamespace:
    return SimpleNamespace(
        underlying={"regularMarketPrice": 100},
        calls=pd.DataFrame(
            {
                "contractSymbol": ["C100"],
                "strike": [100],
                "bid": [4.0],
                "ask": [5.0],
                "volume": [10],
                "openInterest": [20],
                "impliedVolatility": [0.25],
            }
        ),
        puts=pd.DataFrame(
            {
                "contractSymbol": ["P100"],
                "strike": [100],
                "bid": [4.0],
                "ask": [5.0],
                "volume": [8],
                "openInterest": [16],
                "impliedVolatility": [0.3],
            }
        ),
    )


def test_register_tools_contains_every_public_mcp_tool() -> None:
    register_tools(YahooFinance())

    assert set(TOOL_REGISTRY) == {
        "get_current_stock_price",
        "get_symbol_comparison",
        "get_performance_analysis",
        "get_stock_price_by_date",
        "get_stock_price_date_range",
        "get_historical_stock_prices",
        "get_dividends",
        "get_stock_splits",
        "get_capital_gains",
        "get_upcoming_dividends",
        "get_earnings_analytics",
        "get_income_statement",
        "get_cashflow",
        "get_earning_dates",
        "get_news",
        "get_recommendations",
        "get_option_expiration_dates",
        "get_option_chain",
        "get_option_summary",
    }


def test_core_history_and_statement_tools_return_structured_records() -> None:
    with patch("mcp_yahoo_finance.server.Ticker") as ticker_class:
        ticker = MagicMock()
        ticker.history.return_value = _prices()
        ticker.get_income_stmt.return_value = _statement()
        ticker.get_cashflow.return_value = _statement()
        ticker.get_earnings_dates.return_value = _statement()
        ticker_class.return_value = ticker

        client = YahooFinance()
        history = client.get_historical_stock_prices("aapl", period="5d")
        date_range = client.get_stock_price_date_range(
            "aapl", "2025-01-02", "2025-01-03"
        )
        income = client.get_income_statement("aapl", freq="quarterly")
        cashflow = client.get_cashflow("aapl", freq="trailing")
        earnings = client.get_earning_dates("aapl", limit=1)

    assert history["prices"][0] == {
        "date": "2025-01-02",
        "Open": 99.0,
        "Close": 100.0,
        "Volume": 100,
    }
    assert date_range["startDate"] == "2025-01-02"
    assert date_range["prices"][-1]["Close"] == 102.0
    assert income["frequency"] == "quarterly"
    assert income["incomeStatement"][0]["Breakdown"] == "Total Revenue"
    assert cashflow["frequency"] == "trailing"
    assert earnings["earnings"][0]["Breakdown"] == "Total Revenue"
    ticker.history.assert_any_call(period="5d", interval="1d", auto_adjust=True)
    ticker.history.assert_any_call(
        start="2025-01-02", end="2025-01-04", auto_adjust=True
    )


def test_remaining_tool_success_paths_are_mocked() -> None:
    index = pd.DatetimeIndex(["2025-01-02"])
    with patch("mcp_yahoo_finance.server.Ticker") as ticker_class:
        ticker = MagicMock()
        ticker.get_dividends.return_value = pd.Series([0.5], index=index)
        ticker.get_splits.return_value = pd.Series([2.0], index=index)
        ticker.get_capital_gains.return_value = pd.Series([0.25], index=index)
        ticker.get_calendar.return_value = {"Dividend Date": "2025-03-01"}
        ticker.get_recommendations.return_value = pd.DataFrame(
            {"To Grade": ["Buy"]}, index=index
        )
        ticker.options = ("2025-01-17",)
        ticker.option_chain.return_value = _option_chain()
        ticker_class.return_value = ticker

        client = YahooFinance()
        dividends = client.get_dividends("aapl")
        splits = client.get_stock_splits("aapl")
        gains = client.get_capital_gains("aapl")
        upcoming = client.get_upcoming_dividends("aapl")
        recommendations = client.get_recommendations("aapl")
        expirations = client.get_option_expiration_dates("aapl")
        chain = client.get_option_chain("aapl", "2025-01-17", option_type="puts")
        summary = client.get_option_summary("aapl", "2025-01-17")

    assert dividends["dividends"] == [{"date": "2025-01-02", "amount": 0.5}]
    assert splits["splits"] == [{"date": "2025-01-02", "ratio": 2.0}]
    assert gains["capitalGains"] == [{"date": "2025-01-02", "amount": 0.25}]
    assert upcoming["upcomingDividend"] == {"dividendDate": "2025-03-01"}
    assert recommendations["recommendations"] == [
        {"date": "2025-01-02", "To Grade": "Buy"}
    ]
    assert expirations["expirationDates"] == ["2025-01-17"]
    assert chain["calls"] == []
    assert chain["puts"][0]["contractSymbol"] == "P100"
    assert summary["openInterest"] == {"calls": 20, "puts": 16}


@pytest.mark.parametrize(
    ("method", "configure", "arguments", "message"),
    [
        (
            "get_current_stock_price",
            lambda ticker: setattr(ticker, "info", {}),
            {"symbol": "AAPL"},
            "No current price found for AAPL",
        ),
        (
            "get_symbol_comparison",
            lambda ticker: setattr(ticker, "info", {}),
            {"symbols": ["AAPL"]},
            "No current quote data found",
        ),
        (
            "get_performance_analysis",
            lambda ticker: setattr(ticker.history, "return_value", pd.DataFrame()),
            {"symbols": ["AAPL"], "start_date": "2025-01-01", "end_date": "2025-01-02"},
            "No historical data found for requested symbols",
        ),
        (
            "get_stock_price_by_date",
            lambda ticker: setattr(ticker.history, "return_value", pd.DataFrame()),
            {"symbol": "AAPL", "date": "2025-01-02"},
            "No trading data found for AAPL on 2025-01-02",
        ),
        (
            "get_stock_price_date_range",
            lambda ticker: setattr(ticker.history, "return_value", pd.DataFrame()),
            {"symbol": "AAPL", "start_date": "2025-01-01", "end_date": "2025-01-02"},
            "No trading data found for AAPL between 2025-01-01 and 2025-01-02",
        ),
        (
            "get_historical_stock_prices",
            lambda ticker: setattr(ticker.history, "return_value", pd.DataFrame()),
            {"symbol": "AAPL"},
            "No historical data found for AAPL",
        ),
        (
            "get_dividends",
            lambda ticker: setattr(
                ticker, "get_dividends", MagicMock(return_value=pd.Series(dtype=float))
            ),
            {"symbol": "AAPL"},
            "No dividend data found for AAPL",
        ),
        (
            "get_stock_splits",
            lambda ticker: setattr(
                ticker, "get_splits", MagicMock(return_value=pd.Series(dtype=float))
            ),
            {"symbol": "AAPL"},
            "No stock split data found for AAPL",
        ),
        (
            "get_capital_gains",
            lambda ticker: setattr(
                ticker,
                "get_capital_gains",
                MagicMock(return_value=pd.Series(dtype=float)),
            ),
            {"symbol": "AAPL"},
            "No capital gains data found for AAPL",
        ),
        (
            "get_upcoming_dividends",
            lambda ticker: setattr(ticker, "get_calendar", MagicMock(return_value={})),
            {"symbol": "AAPL"},
            "No upcoming dividend data found for AAPL",
        ),
        (
            "get_earnings_analytics",
            lambda ticker: (
                setattr(
                    ticker,
                    "get_earnings_history",
                    MagicMock(return_value=pd.DataFrame()),
                ),
                setattr(
                    ticker,
                    "get_earnings_estimate",
                    MagicMock(return_value=pd.DataFrame()),
                ),
            ),
            {"symbol": "AAPL"},
            "No earnings analytics found for AAPL",
        ),
        (
            "get_income_statement",
            lambda ticker: setattr(
                ticker, "get_income_stmt", MagicMock(return_value=pd.DataFrame())
            ),
            {"symbol": "AAPL"},
            "No incomeStatement data found for AAPL",
        ),
        (
            "get_cashflow",
            lambda ticker: setattr(
                ticker, "get_cashflow", MagicMock(return_value=pd.DataFrame())
            ),
            {"symbol": "AAPL"},
            "No cashflow data found for AAPL",
        ),
        (
            "get_earning_dates",
            lambda ticker: setattr(
                ticker, "get_earnings_dates", MagicMock(return_value=pd.DataFrame())
            ),
            {"symbol": "AAPL"},
            "No earnings data found for AAPL",
        ),
        (
            "get_news",
            lambda ticker: setattr(ticker, "get_news", MagicMock(return_value=[])),
            {"symbol": "AAPL"},
            "No news found for AAPL",
        ),
        (
            "get_recommendations",
            lambda ticker: setattr(
                ticker, "get_recommendations", MagicMock(return_value=pd.DataFrame())
            ),
            {"symbol": "AAPL"},
            "No recommendations found for AAPL",
        ),
        (
            "get_option_expiration_dates",
            lambda ticker: setattr(ticker, "options", ()),
            {"symbol": "AAPL"},
            "No options data found for AAPL",
        ),
    ],
)
def test_tools_return_consistent_no_data_errors(
    method, configure, arguments, message
) -> None:
    with patch("mcp_yahoo_finance.server.Ticker") as ticker_class:
        ticker = MagicMock()
        configure(ticker)
        ticker_class.return_value = ticker
        result = getattr(YahooFinance(), method)(**arguments)

    assert result == {"error": {"code": "NO_DATA", "message": message}}


@pytest.mark.parametrize(
    "method, arguments",
    [
        ("get_current_stock_price", {"symbol": ""}),
        ("get_stock_price_by_date", {"symbol": "AAPL", "date": "01-02-2025"}),
        (
            "get_stock_price_date_range",
            {"symbol": "AAPL", "start_date": "2025-01-03", "end_date": "2025-01-02"},
        ),
        ("get_earnings_analytics", {"symbol": "AAPL", "limit": 0}),
        ("get_earning_dates", {"symbol": "AAPL", "limit": 101}),
        ("get_news", {"symbol": "AAPL", "limit": 0}),
        (
            "get_option_chain",
            {"symbol": "AAPL", "expiration_date": "2025-01-17", "limit": 0},
        ),
        (
            "get_option_summary",
            {"symbol": "AAPL", "expiration_date": "2025-01-17", "limit": 101},
        ),
    ],
)
def test_invalid_arguments_are_reported_without_upstream_calls(
    method, arguments
) -> None:
    with patch("mcp_yahoo_finance.server.Ticker") as ticker_class:
        result = getattr(YahooFinance(), method)(**arguments)

    assert result["error"]["code"] == "INVALID_ARGUMENT"
    ticker_class.assert_not_called()


@pytest.mark.asyncio
async def test_registered_tool_uses_registry_and_returns_mcp_result() -> None:
    with patch("mcp_yahoo_finance.server.Ticker") as ticker_class:
        ticker_class.return_value.info = {
            "regularMarketPrice": 123.45,
            "currency": "USD",
        }
        register_tools(YahooFinance())
        result = await call_registered_tool(
            TOOL_REGISTRY,
            CallToolRequestParams(
                name="get_current_stock_price", arguments={"symbol": "aapl"}
            ),
        )

    assert isinstance(result, CallToolResult)
    assert result.is_error is False
    assert result.structured_content == {
        "symbol": "AAPL",
        "price": 123.45,
        "currency": "USD",
        "exchange": None,
        "source": "Yahoo Finance",
    }


@pytest.mark.asyncio
async def test_registered_tool_rejects_unknown_tools() -> None:
    result = await call_registered_tool(
        {}, CallToolRequestParams(name="missing", arguments={})
    )

    assert result.is_error is True
    assert result.structured_content == {
        "error": {"code": "UNKNOWN_TOOL", "message": "Unknown tool: missing"}
    }
