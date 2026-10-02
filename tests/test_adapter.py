import time
from unittest.mock import MagicMock, patch

import pytest

from mcp_yahoo_finance.server import YahooFinance, YahooFinanceAdapter, register_tools


def test_adapter_retries_failed_requests_and_caches_successes() -> None:
    attempts = 0

    def operation(_ticker):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("temporary upstream failure")
        return {"price": 123}

    with patch("mcp_yahoo_finance.server.Ticker") as ticker_class:
        adapter = YahooFinanceAdapter(max_retries=1, cache_ttl=60)
        first = adapter.request("AAPL", operation, cache_key="quote")
        second = adapter.request("AAPL", operation, cache_key="quote")

    assert first == second == {"price": 123}
    assert attempts == 2
    ticker_class.assert_called_once_with(ticker="AAPL", session=adapter.session)


def test_adapter_does_not_cache_when_ttl_is_zero() -> None:
    operation = MagicMock(return_value={"price": 123})

    with patch("mcp_yahoo_finance.server.Ticker"):
        adapter = YahooFinanceAdapter(cache_ttl=0)
        adapter.request("AAPL", operation, cache_key="quote")
        adapter.request("AAPL", operation, cache_key="quote")

    assert operation.call_count == 2


def test_adapter_deadline_stops_retries_and_backoff() -> None:
    attempts = 0

    def operation(_ticker):
        nonlocal attempts
        attempts += 1
        raise RuntimeError("temporary upstream failure")

    with patch("mcp_yahoo_finance.server.Ticker"):
        adapter = YahooFinanceAdapter(
            max_retries=3,
            retry_backoff=1,
        )
        with pytest.raises(TimeoutError, match="deadline exceeded"):
            adapter.request(
                "AAPL",
                operation,
                cache_key="deadline",
                deadline=time.monotonic() + 0.01,
            )

    assert attempts == 1


def test_adapter_raises_a_bounded_timeout() -> None:
    with patch("mcp_yahoo_finance.server.Ticker"):
        adapter = YahooFinanceAdapter(timeout=0.01, max_retries=0)

        started = time.monotonic()
        with pytest.raises(
            TimeoutError,
            match="Yahoo Finance request timed out after 0.01 seconds",
        ):
            adapter.request(
                "AAPL",
                lambda _ticker: time.sleep(0.05),
                cache_key="slow",
            )

    assert time.monotonic() - started < 0.04


@pytest.mark.parametrize(
    "kwargs",
    [
        {"timeout": 0},
        {"max_retries": -1},
        {"cache_ttl": -1},
        {"retry_backoff": -1},
    ],
)
def test_adapter_rejects_invalid_configuration(kwargs) -> None:
    with pytest.raises(ValueError):
        YahooFinanceAdapter(**kwargs)


def test_tool_registries_are_instance_local() -> None:
    first = register_tools(YahooFinance(cache_ttl=0))
    second = register_tools(YahooFinance(cache_ttl=0))

    assert first is not second
    assert set(first) == set(second)
    assert (
        first["get_current_stock_price"].__self__
        is not second["get_current_stock_price"].__self__
    )
