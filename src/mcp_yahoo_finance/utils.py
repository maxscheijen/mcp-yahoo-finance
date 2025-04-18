import inspect
from typing import Any

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
        param_type = (
            "number"
            if param.annotation is float
            else "string"
            if param.annotation is str
            else "string"
        )
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
