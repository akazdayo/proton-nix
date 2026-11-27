"""Give an upstream Steam tool a stable ID and display name."""

from pathlib import Path
import re
import sys


TOKEN = re.compile(r'(?P<gap>\A\ufeff|\s+|//[^\r\n]*)|(?P<quoted>"(?:\\[^\r\n]|[^"\\\r\n])*")|.')


def rewrite_tool(content, tool_id, display_name):
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
    keys = words[6:-3:2]
    if keys.count('"install_path"') != 1:
        raise ValueError("Expected exactly one install_path in the Steam tool")
    if keys.count('"display_name"') != 1:
        raise ValueError("Expected exactly one display_name in the Steam tool")

    name_start, name_end = fields[2 * keys.index('"display_name"') + 1].span()
    content = content[:name_start] + f'"{display_name}"' + content[name_end:]
    start, end = tokens[4].span()
    return content[:start] + f'"{tool_id}"' + content[end:]


if __name__ == "__main__":
    path = Path(sys.argv[1])
    try:
        rewritten = rewrite_tool(path.read_bytes().decode("utf-8"), sys.argv[2], sys.argv[3])
    except ValueError as error:
        raise SystemExit(f"{path}: {error}") from error
    sys.stdout.buffer.write(rewritten.encode("utf-8"))
