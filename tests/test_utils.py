from typing import Literal

from mcp_yahoo_finance.utils import generate_tool


def test_generate_tool_includes_literal_values_and_defaults() -> None:
    def get_prices(
        symbol: str,
        period: Literal["1d", "1mo"] = "1mo",
        limit: int = 12,
    ) -> str:
        """Get prices.

        Args:
            symbol (str): Stock symbol.
            period (str): History period.
            limit (int): Maximum number of results.
        """

    tool = generate_tool(get_prices)

    assert tool.input_schema["properties"] == {
        "symbol": {"type": "string", "description": "Stock symbol."},
        "period": {
            "type": "string",
            "enum": ["1d", "1mo"],
            "description": "History period.",
            "default": "1mo",
        },
        "limit": {
            "type": "integer",
            "description": "Maximum number of results.",
            "default": 12,
        },
    }
    assert tool.input_schema["required"] == ["symbol"]


def test_generate_tool_supports_modern_union_annotations() -> None:
    def configure(limit: int | None = None, enabled: bool = True) -> None:
        """Configure the client."""

    tool = generate_tool(configure)

    assert tool.input_schema["properties"] == {
        "limit": {
            "type": "integer",
            "description": "",
            "default": None,
        },
        "enabled": {
            "type": "boolean",
            "description": "",
            "default": True,
        },
    }
    assert "required" not in tool.input_schema
