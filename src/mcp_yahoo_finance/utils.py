import inspect
import math
import types
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Literal, Union, get_args, get_origin

from mcp.types import Tool


def to_json_compatible(value: Any) -> Any:
    """Convert common Yahoo Finance values into JSON-compatible values."""
    if hasattr(value, "item"):
        return to_json_compatible(value.item())
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return None if math.isnan(value) or math.isinf(value) else value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, Enum):
        return to_json_compatible(value.value)
    if isinstance(value, Mapping):
        return {str(key): to_json_compatible(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [to_json_compatible(item) for item in value]
    return str(value)


def dataframe_to_records(dataframe: Any) -> list[dict[str, Any]]:
    """Serialize a dataframe while keeping columns and normalized date indexes.

    Yahoo Finance may return either naive or timezone-aware ``DatetimeIndex``
    values depending on the endpoint.  The public API exposes calendar dates
    as ``YYYY-MM-DD`` so callers do not have to interpret provider timezones.
    """
    frame = dataframe.copy()
    index_name = frame.index.name or (
        "date" if hasattr(frame.index, "date") else "index"
    )
    frame.index.name = index_name
    records = frame.reset_index().to_dict(orient="records")
    return [
        {
            str(key): (
                _calendar_date(value)
                if key == index_name and _is_datetime_value(value)
                else to_json_compatible(value)
            )
            for key, value in record.items()
        }
        for record in records
    ]


def _is_datetime_value(value: Any) -> bool:
    return isinstance(value, (datetime, date)) or (
        hasattr(value, "to_pydatetime") and not isinstance(value, str)
    )


def _calendar_date(value: Any) -> str:
    """Return a provider-independent calendar date from a datetime value."""
    if hasattr(value, "tz_localize") and getattr(value, "tzinfo", None) is not None:
        value = value.tz_localize(None)
    elif isinstance(value, datetime) and value.tzinfo is not None:
        value = value.replace(tzinfo=None)
    if hasattr(value, "date"):
        value = value.date()
    return value.isoformat()


def parse_docstring(docstring: str) -> dict[str, str]:
    """Parses a Google-style docstring to extract parameter descriptions."""
    descriptions = {}
    if not docstring:
        return descriptions

    lines = docstring.split("\n")
    current_param = None

    for line in lines:
        line = line.strip()
        if line.startswith("Args:"):
            continue
        elif line and "(" in line and ")" in line and ":" in line:
            param = line.split("(")[0].strip()
            desc = line.split("):")[1].strip()
            descriptions[param] = desc
            current_param = param
        elif current_param and line:
            descriptions[current_param] += " " + line.strip()

    return descriptions


def _json_type_for_value(value: Any) -> str | None:
    """Return the JSON Schema type for a literal value."""
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    return None


def _infer_json_schema(annotation: Any) -> dict[str, Any]:
    """Infer a JSON Schema fragment from a Python type annotation."""
    if annotation is None or annotation is inspect.Parameter.empty:
        return {"type": "string"}

    origin = get_origin(annotation)

    if origin is Literal:
        values = list(get_args(annotation))
        schema: dict[str, Any] = {"enum": values}
        value_types = {_json_type_for_value(value) for value in values}
        value_types.discard(None)
        if len(value_types) == 1:
            schema["type"] = value_types.pop()
        return schema

    if origin in (Union, types.UnionType):
        args = [arg for arg in get_args(annotation) if arg is not type(None)]
        schemas = [_infer_json_schema(arg) for arg in args]
        if len(schemas) == 1:
            return schemas[0]
        return {"anyOf": schemas}

    if annotation is int:
        return {"type": "integer"}
    if annotation is float:
        return {"type": "number"}
    if annotation is bool:
        return {"type": "boolean"}
    if annotation is str:
        return {"type": "string"}

    if origin in (list, Sequence):
        args = get_args(annotation)
        item_schema = _infer_json_schema(args[0]) if args else {}
        return {"type": "array", "items": item_schema}

    return {"type": "string"}


def generate_tool(func: Any) -> Tool:
    """Generates a tool schema from a Python function."""
    signature = inspect.signature(func)
    docstring = inspect.getdoc(func) or ""
    param_descriptions = parse_docstring(docstring)

    schema = {
        "name": func.__name__,
        "description": docstring.split("Args:")[0].strip(),
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    }

    for param_name, param in signature.parameters.items():
        property_schema = _infer_json_schema(param.annotation)
        property_schema["description"] = param_descriptions.get(param_name, "")
        if param.default is not inspect.Parameter.empty:
            property_schema["default"] = param.default

        schema["inputSchema"]["properties"][param_name] = property_schema

        if param.default is inspect.Parameter.empty:
            schema["inputSchema"].setdefault("required", []).append(param_name)

    return Tool(**schema)


def validate_symbol(symbol: str) -> str:
    if not symbol or not isinstance(symbol, str):
        raise ValueError("Symbol must be a non-empty string")
    return symbol.upper().strip()


def validate_date(date_str: str, param_name: str = "date") -> str:
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except (ValueError, TypeError):
        raise ValueError(f"{param_name} must be in YYYY-MM-DD format")
    return date_str
