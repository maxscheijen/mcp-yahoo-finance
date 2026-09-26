import json
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
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


def _series_records(series: Any, value_name: str) -> list[dict[str, Any]]:
    """Serialize an event series with a normalized calendar-date field."""
    return [
        {
            "date": to_json_compatible(index)[:10],
            value_name: to_json_compatible(value),
        }
        for index, value in series.items()
    ]


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
        """Get normalized dividend history for a given stock symbol.

        Args:
            symbol (str): Stock symbol in Yahoo Finance format.
        """
        try:
            symbol = validate_symbol(symbol)
            stock = Ticker(ticker=symbol, session=self.session)
            dividends = stock.get_dividends()
            if dividends.empty:
                return error_result("NO_DATA", f"No dividend data found for {symbol}")
            result: ToolResult = {
                "symbol": symbol,
                "dividends": _series_records(dividends, "amount"),
            }
            # These fields are optional in Yahoo's quoteSummary response. They
            # provide yield context without making the history dependent on it.
            try:
                info = stock.info
            except Exception:
                info = {}
            yield_context = {
                key: to_json_compatible(info[key])
                for key in (
                    "dividendYield",
                    "trailingAnnualDividendYield",
                    "trailingAnnualDividendRate",
                )
                if isinstance(info.get(key), (int, float))
                and not isinstance(info.get(key), bool)
            }
            if yield_context:
                result["yieldContext"] = yield_context
            return result
        except Exception as exc:
            return error_result(_error_code(exc), str(exc))

    def get_stock_splits(self, symbol: str) -> ToolResult:
        """Get normalized stock split history for a symbol.

        Args:
            symbol (str): Stock symbol in Yahoo Finance format.
        """
        try:
            symbol = validate_symbol(symbol)
            splits = Ticker(ticker=symbol, session=self.session).get_splits()
            if splits.empty:
                return error_result(
                    "NO_DATA", f"No stock split data found for {symbol}"
                )
            return {"symbol": symbol, "splits": _series_records(splits, "ratio")}
        except Exception as exc:
            return error_result(_error_code(exc), str(exc))

    def get_capital_gains(self, symbol: str) -> ToolResult:
        """Get normalized capital-gains distributions for a symbol.

        Args:
            symbol (str): Stock symbol in Yahoo Finance format.
        """
        try:
            symbol = validate_symbol(symbol)
            gains = Ticker(ticker=symbol, session=self.session).get_capital_gains()
            if gains.empty:
                return error_result(
                    "NO_DATA", f"No capital gains data found for {symbol}"
                )
            return {"symbol": symbol, "capitalGains": _series_records(gains, "amount")}
        except Exception as exc:
            return error_result(_error_code(exc), str(exc))

    def get_upcoming_dividends(self, symbol: str) -> ToolResult:
        """Get upcoming dividend dates and rates when Yahoo provides them.

        Args:
            symbol (str): Stock symbol in Yahoo Finance format.
        """
        try:
            symbol = validate_symbol(symbol)
            calendar = Ticker(ticker=symbol, session=self.session).get_calendar()
            if not isinstance(calendar, dict):
                return error_result(
                    "NO_DATA", f"No upcoming dividend data found for {symbol}"
                )
            fields = {
                "exDividendDate": calendar.get("Ex-Dividend Date"),
                "dividendDate": calendar.get("Dividend Date"),
                "dividendRate": calendar.get("Dividend Rate"),
                "dividendYield": calendar.get("Dividend Yield"),
            }
            result = {
                key: to_json_compatible(value)
                for key, value in fields.items()
                if value is not None
            }
            if not result:
                return error_result(
                    "NO_DATA", f"No upcoming dividend data found for {symbol}"
                )
            for key in ("exDividendDate", "dividendDate"):
                if key in result:
                    result[key] = result[key][:10]
            return {"symbol": symbol, "upcomingDividend": result}
        except Exception as exc:
            return error_result(_error_code(exc), str(exc))

    def get_earnings_analytics(self, symbol: str, limit: int = 12) -> ToolResult:
        """Get earnings surprise history and analyst estimate history.

        Args:
            symbol (str): Stock symbol in Yahoo Finance format.
            limit (int): Maximum rows returned for each history, from 1 to 100.
        """
        try:
            symbol = validate_symbol(symbol)
            if not 1 <= limit <= 100:
                return error_result(
                    "INVALID_ARGUMENT", "limit must be between 1 and 100"
                )
            stock = Ticker(ticker=symbol, session=self.session)
            history = stock.get_earnings_history()
            estimates = stock.get_earnings_estimate()
            result: ToolResult = {"symbol": symbol, "limit": limit}
            if isinstance(history, pd.DataFrame) and not history.empty:
                result["earningsHistory"] = _records(history.head(limit))
            if isinstance(estimates, pd.DataFrame) and not estimates.empty:
                result["earningsEstimates"] = _records(estimates.head(limit))
            if len(result) == 2:
                return error_result(
                    "NO_DATA", f"No earnings analytics found for {symbol}"
                )
            return result
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

    @staticmethod
    def _news_timestamp(value: Any) -> datetime | None:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            try:
                return datetime.fromtimestamp(value, timezone.utc)
            except (OverflowError, OSError, ValueError):
                return None
        if not isinstance(value, str) or not value.strip():
            return None
        try:
            timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            try:
                timestamp = parsedate_to_datetime(value)
            except (TypeError, ValueError, OverflowError):
                return None
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        return timestamp.astimezone(timezone.utc)

    @staticmethod
    def _news_value(article: dict[str, Any], *keys: str) -> Any:
        for key in keys:
            value = article.get(key)
            if value is not None:
                return value
        return None

    @classmethod
    def _normalize_news_article(cls, article: Any) -> dict[str, Any] | None:
        if not isinstance(article, dict):
            return None

        content = article.get("content")
        if not isinstance(content, dict):
            content = article

        title = cls._news_value(content, "title") or cls._news_value(article, "title")
        url_value = cls._news_value(content, "canonicalUrl", "clickThroughUrl", "link")
        if isinstance(url_value, dict):
            url_value = url_value.get("url")
        url = url_value or cls._news_value(article, "link", "url")
        if (
            not isinstance(title, str)
            or not title.strip()
            or not isinstance(url, str)
            or not url.strip()
        ):
            return None

        provider = cls._news_value(content, "provider", "publisher")
        if isinstance(provider, dict):
            provider = provider.get("displayName") or provider.get("name")
        publisher = (
            provider
            if isinstance(provider, str)
            else cls._news_value(article, "publisher")
        )

        timestamp_value = cls._news_value(
            content, "pubDate", "providerPublishTime", "displayTime", "publishedAt"
        )
        if timestamp_value is None:
            timestamp_value = cls._news_value(
                article, "providerPublishTime", "pubDate", "publishedAt"
            )
        published_at = cls._news_timestamp(timestamp_value)
        if published_at is None:
            return None

        thumbnail = cls._news_value(content, "thumbnail")
        if isinstance(thumbnail, dict):
            thumbnail = thumbnail.get("originalUrl") or thumbnail.get("url")
            if thumbnail is None:
                resolutions = content.get("thumbnail", {}).get("resolutions", [])
                if resolutions and isinstance(resolutions[0], dict):
                    thumbnail = resolutions[0].get("url")
        if not isinstance(thumbnail, str):
            thumbnail = None

        related = cls._news_value(content, "relatedTickers", "relatedSymbols")
        if related is None and isinstance(content.get("finance"), dict):
            related = content["finance"].get("tickerSymbols")
        if related is None:
            related = cls._news_value(article, "relatedTickers", "relatedSymbols")
        if not isinstance(related, list):
            related = []
        related_symbols = sorted(
            {
                item.upper().strip()
                for item in related
                if isinstance(item, str) and item.strip()
            }
        )

        return {
            "title": title.strip(),
            "url": url.strip(),
            "publisher": publisher.strip() if isinstance(publisher, str) else None,
            "publishedAt": published_at.isoformat().replace("+00:00", "Z"),
            "thumbnail": thumbnail,
            "relatedSymbols": related_symbols,
        }

    def get_news(
        self,
        symbol: str,
        limit: int = 10,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> ToolResult:
        """Get normalized, bounded news for a stock symbol.

        Args:
            symbol (str): Stock symbol in Yahoo Finance format.
            limit (int): Maximum number of articles, from 1 to 100.
            start_date (str): Include articles published on or after this YYYY-MM-DD date.
            end_date (str): Include articles published on or before this YYYY-MM-DD date.
        """
        try:
            symbol = validate_symbol(symbol)
            if not 1 <= limit <= 100:
                return error_result(
                    "INVALID_ARGUMENT", "limit must be between 1 and 100"
                )
            if start_date is not None:
                validate_date(start_date, "start_date")
            if end_date is not None:
                validate_date(end_date, "end_date")
            if start_date and end_date and start_date > end_date:
                return error_result(
                    "INVALID_ARGUMENT", "start_date must be on or before end_date"
                )

            # ``Ticker.news`` calls ``get_news()`` with yfinance's default count
            # of 10. Fetch a larger bounded window so date filters can inspect
            # more than just the newest ten articles.
            news = Ticker(ticker=symbol, session=self.session).get_news(count=100)
            if not news:
                return error_result("NO_DATA", f"No news found for {symbol}")

            start = date.fromisoformat(start_date) if start_date else None
            end = date.fromisoformat(end_date) if end_date else None
            articles = []
            for article in news:
                normalized = self._normalize_news_article(article)
                if normalized is None:
                    continue
                published_date = date.fromisoformat(normalized["publishedAt"][:10])
                if start and published_date < start:
                    continue
                if end and published_date > end:
                    continue
                articles.append(normalized)
                if len(articles) == limit:
                    break

            if not articles:
                return error_result("NO_DATA", f"No news found for {symbol}")
            return {"symbol": symbol, "limit": limit, "news": articles}
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

    def get_option_chain(
        self,
        symbol: str,
        expiration_date: str,
        option_type: Literal["calls", "puts", "both"] = "both",
        min_strike: float | None = None,
        max_strike: float | None = None,
        moneyness: Literal["itm", "otm", "atm"] | None = None,
        min_open_interest: int | None = None,
        min_volume: int | None = None,
        max_bid_ask_spread: float | None = None,
        limit: int = 100,
    ) -> ToolResult:
        """Get a filtered, bounded option chain for one expiration date.

        Args:
            symbol (str): Stock symbol in Yahoo Finance format.
            expiration_date (str): Expiration date in YYYY-MM-DD format.
            option_type (str): Return calls, puts, or both.
            min_strike (float): Minimum strike price, inclusive.
            max_strike (float): Maximum strike price, inclusive.
            moneyness (str): Restrict results to in-the-money, out-of-the-money, or at-the-money contracts.
            min_open_interest (int): Minimum open interest, inclusive.
            min_volume (int): Minimum volume, inclusive.
            max_bid_ask_spread (float): Maximum ask minus bid spread, inclusive.
            limit (int): Maximum contracts returned per side, from 1 to 100.
        """
        return self._get_option_chain(
            symbol,
            expiration_date,
            option_type=option_type,
            min_strike=min_strike,
            max_strike=max_strike,
            moneyness=moneyness,
            min_open_interest=min_open_interest,
            min_volume=min_volume,
            max_bid_ask_spread=max_bid_ask_spread,
            limit=limit,
        )

    @staticmethod
    def _filter_option_frame(
        frame: Any,
        option_type: str,
        underlying_price: float | None,
        min_strike: float | None,
        max_strike: float | None,
        moneyness: str | None,
        min_open_interest: int | None,
        min_volume: int | None,
        max_bid_ask_spread: float | None,
        limit: int,
    ) -> pd.DataFrame:
        """Apply common option filters without mutating yfinance's frame."""
        if not isinstance(frame, pd.DataFrame):
            return pd.DataFrame()
        result = frame.copy()

        def numeric_filter(column: str, minimum: float | None) -> None:
            nonlocal result
            if minimum is not None and column in result:
                result = result[
                    pd.to_numeric(result[column], errors="coerce") >= minimum
                ]

        numeric_filter("strike", min_strike)
        if max_strike is not None and "strike" in result:
            result = result[
                pd.to_numeric(result["strike"], errors="coerce") <= max_strike
            ]
        numeric_filter("openInterest", min_open_interest)
        numeric_filter("volume", min_volume)

        if max_bid_ask_spread is not None and {"bid", "ask"}.issubset(result.columns):
            bid = pd.to_numeric(result["bid"], errors="coerce")
            ask = pd.to_numeric(result["ask"], errors="coerce")
            result = result[(ask - bid) <= max_bid_ask_spread]

        if (
            moneyness is not None
            and underlying_price not in (None, 0)
            and "strike" in result
        ):
            strikes = pd.to_numeric(result["strike"], errors="coerce")
            if moneyness == "itm":
                result = result[
                    strikes < underlying_price
                    if option_type == "calls"
                    else strikes > underlying_price
                ]
            elif moneyness == "otm":
                result = result[
                    strikes > underlying_price
                    if option_type == "calls"
                    else strikes < underlying_price
                ]
            else:
                result = result[
                    ((strikes - underlying_price).abs() / underlying_price) <= 0.01
                ]

        return result.head(limit)

    @staticmethod
    def _option_underlying_price(underlying: Any) -> float | None:
        if not isinstance(underlying, dict):
            return None
        for key in ("regularMarketPrice", "currentPrice", "price"):
            value = underlying.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return float(value)
        return None

    def _get_option_chain(
        self,
        symbol: str,
        expiration_date: str,
        *,
        option_type: Literal["calls", "puts", "both"],
        min_strike: float | None,
        max_strike: float | None,
        moneyness: Literal["itm", "otm", "atm"] | None,
        min_open_interest: int | None,
        min_volume: int | None,
        max_bid_ask_spread: float | None,
        limit: int,
    ) -> ToolResult:
        try:
            symbol = validate_symbol(symbol)
            validate_date(expiration_date, "expiration_date")
            if option_type not in ("calls", "puts", "both"):
                return error_result(
                    "INVALID_ARGUMENT", "option_type must be calls, puts, or both"
                )
            if moneyness not in (None, "itm", "otm", "atm"):
                return error_result(
                    "INVALID_ARGUMENT", "moneyness must be itm, otm, or atm"
                )
            if not 1 <= limit <= 100:
                return error_result(
                    "INVALID_ARGUMENT", "limit must be between 1 and 100"
                )
            if (
                min_strike is not None
                and max_strike is not None
                and min_strike > max_strike
            ):
                return error_result(
                    "INVALID_ARGUMENT", "min_strike must be on or before max_strike"
                )
            if min_open_interest is not None and min_open_interest < 0:
                return error_result(
                    "INVALID_ARGUMENT", "min_open_interest must be non-negative"
                )
            if min_volume is not None and min_volume < 0:
                return error_result(
                    "INVALID_ARGUMENT", "min_volume must be non-negative"
                )
            if max_bid_ask_spread is not None and max_bid_ask_spread < 0:
                return error_result(
                    "INVALID_ARGUMENT", "max_bid_ask_spread must be non-negative"
                )

            source_timestamp = datetime.now(timezone.utc).isoformat()
            chain = Ticker(ticker=symbol, session=self.session).option_chain(
                expiration_date
            )
            underlying = to_json_compatible(chain.underlying)
            underlying_price = self._option_underlying_price(underlying)
            calls = (
                self._filter_option_frame(
                    chain.calls,
                    "calls",
                    underlying_price,
                    min_strike,
                    max_strike,
                    moneyness,
                    min_open_interest,
                    min_volume,
                    max_bid_ask_spread,
                    limit,
                )
                if option_type in ("calls", "both")
                else pd.DataFrame()
            )
            puts = (
                self._filter_option_frame(
                    chain.puts,
                    "puts",
                    underlying_price,
                    min_strike,
                    max_strike,
                    moneyness,
                    min_open_interest,
                    min_volume,
                    max_bid_ask_spread,
                    limit,
                )
                if option_type in ("puts", "both")
                else pd.DataFrame()
            )
            return {
                "symbol": symbol,
                "expirationDate": expiration_date,
                "sourceTimestamp": source_timestamp,
                "underlying": underlying,
                "calls": _records(calls),
                "puts": _records(puts),
            }
        except Exception as exc:
            return error_result(_error_code(exc), str(exc))

    def get_option_summary(
        self,
        symbol: str,
        expiration_date: str,
        limit: int = 100,
    ) -> ToolResult:
        """Summarize option interest, volume, volatility, ratios, and max pain.

        Args:
            symbol (str): Stock symbol in Yahoo Finance format.
            expiration_date (str): Expiration date in YYYY-MM-DD format.
            limit (int): Maximum contracts considered per side, from 1 to 100.
        """
        try:
            chain = self._get_option_chain(
                symbol,
                expiration_date,
                option_type="both",
                min_strike=None,
                max_strike=None,
                moneyness=None,
                min_open_interest=None,
                min_volume=None,
                max_bid_ask_spread=None,
                limit=limit,
            )
            if "error" in chain:
                return chain
            calls = pd.DataFrame(chain["calls"])
            puts = pd.DataFrame(chain["puts"])

            def total(frame: pd.DataFrame, column: str) -> float | int | None:
                if column not in frame:
                    return None
                values = pd.to_numeric(frame[column], errors="coerce").dropna()
                if values.empty:
                    return None
                value = values.sum()
                return (
                    int(value) if column in ("openInterest", "volume") else float(value)
                )

            def average(frame: pd.DataFrame, column: str) -> float | None:
                if column not in frame:
                    return None
                values = pd.to_numeric(frame[column], errors="coerce").dropna()
                return float(values.mean()) if not values.empty else None

            call_oi, put_oi = total(calls, "openInterest"), total(puts, "openInterest")
            call_volume, put_volume = total(calls, "volume"), total(puts, "volume")
            summary = {
                "symbol": chain["symbol"],
                "expirationDate": chain["expirationDate"],
                "sourceTimestamp": chain["sourceTimestamp"],
                "impliedVolatility": {
                    "calls": average(calls, "impliedVolatility"),
                    "puts": average(puts, "impliedVolatility"),
                },
                "openInterest": {"calls": call_oi, "puts": put_oi},
                "volume": {"calls": call_volume, "puts": put_volume},
                "putCallRatios": {
                    "openInterest": (put_oi / call_oi) if call_oi else None,
                    "volume": (put_volume / call_volume) if call_volume else None,
                },
                "maxPain": self._max_pain(calls, puts),
            }
            return to_json_compatible(summary)
        except Exception as exc:
            return error_result(_error_code(exc), str(exc))

    @staticmethod
    def _max_pain(calls: pd.DataFrame, puts: pd.DataFrame) -> float | None:
        if "strike" not in calls or "strike" not in puts:
            return None
        strikes = sorted(set(pd.concat([calls["strike"], puts["strike"]]).dropna()))
        if not strikes:
            return None
        call_strike = pd.to_numeric(calls["strike"], errors="coerce")
        put_strike = pd.to_numeric(puts["strike"], errors="coerce")
        call_oi = pd.to_numeric(
            calls["openInterest"]
            if "openInterest" in calls
            else pd.Series(0, index=calls.index),
            errors="coerce",
        ).fillna(0)
        put_oi = pd.to_numeric(
            puts["openInterest"]
            if "openInterest" in puts
            else pd.Series(0, index=puts.index),
            errors="coerce",
        ).fillna(0)
        pain = {
            strike: ((strike - call_strike).clip(lower=0) * call_oi).sum()
            + ((put_strike - strike).clip(lower=0) * put_oi).sum()
            for strike in strikes
        }
        return float(min(pain, key=pain.get))


TOOL_REGISTRY: dict[str, Any] = {}


def register_tools(yf: YahooFinance) -> None:
    TOOL_REGISTRY.clear()
    names = (
        "get_current_stock_price",
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
