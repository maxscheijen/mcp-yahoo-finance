import inspect
from datetime import datetime
from typing import Any, Literal, Union, get_origin

from mcp.types import Tool


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


def _infer_json_type(annotation: Any) -> str:
    """Infer JSON schema type from Python type annotation."""
    if annotation is None or annotation is inspect.Parameter.empty:
        return "string"

    origin = get_origin(annotation)

    if origin is Union:
        args = annotation.__args__
        for arg in args:
            if arg is type(None):
                continue
            return _infer_json_type(arg)

    if origin is list:
        args = annotation.__args__
        if args:
            return _infer_json_type(args[0])
        return "string"

    if hasattr(annotation, "__origin__") and hasattr(annotation, "__args__"):
        if annotation.__origin__ is Literal:
            args = annotation.__args__
            if args:
                return _infer_json_type(type(args[0]))
            return "string"

    if annotation in (int, float):
        return "number"
    if annotation is bool:
        return "boolean"
    if annotation is str:
        return "string"

    return "string"


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
        param_type = _infer_json_type(param.annotation)
        schema["inputSchema"]["properties"][param_name] = {
            "type": param_type,
            "description": param_descriptions.get(param_name, ""),
        }

        if "required" not in schema["inputSchema"]:
            schema["inputSchema"]["required"] = [param_name]
        else:
            if "=" not in str(param):
                schema["inputSchema"]["required"].append(param_name)

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
