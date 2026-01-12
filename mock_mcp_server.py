"""Simple MCP mock server for testing."""
import sys
import json


def read_request():
    line = sys.stdin.readline()
    if not line:
        return None
    return json.loads(line.strip())


def write_response(response):
    sys.stdout.write(json.dumps(response) + chr(10))
    sys.stdout.flush()


while True:
    try:
        request = read_request()
        if request is None:
            break

        method = request.get("method")
        request_id = request.get("id")

        if method == "initialize":
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "serverInfo": {"name": "Mock MCP Server", "version": "1.0.0"}
                }
            }
        elif method == "tools/list":
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "tools": [
                        {"name": "get_time", "description": "Get current time", "inputSchema": {"type": "object"}},
                        {"name": "echo", "description": "Echo back input", "inputSchema": {"type": "object", "properties": {"text": {"type": "string"}}}}
                    ]
                }
            }
        elif method == "tools/call":
            params = request.get("params", {})
            name = params.get("name", "")
            args = params.get("arguments", {})

            if name == "get_time":
                import datetime
                result = datetime.datetime.now().isoformat()
            elif name == "echo":
                result = f"Echo: {args.get('text', '')}"
            else:
                result = f"Unknown tool: {name}"

            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"content": [{"type": "text", "text": result}]}
            }
        elif method == "initialized":
            continue
        else:
            response = {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": f"Method not found: {method}"}}

        write_response(response)

    except Exception as e:
        error_response = {"jsonrpc": "2.0", "id": request_id if "request_id" in locals() else None, "error": {"code": -32603, "message": str(e)}}
        write_response(error_response)
