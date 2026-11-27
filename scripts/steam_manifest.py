"""Give an upstream Steam tool a stable ID without changing its other fields."""

from pathlib import Path
import re
import sys


TOKEN = re.compile(r'(?P<gap>\A\ufeff|\s+|//[^\r\n]*)|(?P<quoted>"(?:\\[^\r\n]|[^"\\\r\n])*")|.')


def rewrite_tool_id(content, tool_id):
    tokens = [token for token in TOKEN.finditer(content) if token["gap"] is None]
    words = [token[0] for token in tokens]
    fields = tokens[6:-3]
    # shortcut: require a single tool with quoted field pairs; extend if upstream uses nested fields.
    if (
        words[:4] != ['"compatibilitytools"', "{", '"compat_tools"', "{"]
        or words[5:6] != ["{"]
        or words[-3:] != ["}", "}", "}"]
        or len(fields) % 2
        or any(token["quoted"] is None for token in tokens[4:5] + fields)
    ):
        raise ValueError("Expected one Steam compatibility tool with quoted fields")
    if words[6:-3:2].count('"install_path"') != 1:
        raise ValueError("Expected exactly one install_path in the Steam tool")

    start, end = tokens[4].span()
    return content[:start] + f'"{tool_id}"' + content[end:]


if __name__ == "__main__":
    path = Path(sys.argv[1])
    try:
        rewritten = rewrite_tool_id(path.read_bytes().decode("utf-8"), sys.argv[2])
    except ValueError as error:
        raise SystemExit(f"{path}: {error}") from error
    sys.stdout.buffer.write(rewritten.encode("utf-8"))
