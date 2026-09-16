#!/usr/bin/env python3
"""A toy MCP server (stdio, newline-delimited JSON-RPC) serving the fixture
quotes - exists so the MCP client path is exercised end-to-end in CI with the
same protocol a real brokerage MCP server speaks."""
import json
import os
import pathlib
import sys

QUOTES = json.loads((pathlib.Path(__file__).resolve().parents[1] / "data" / "quotes.json").read_text())

for line in sys.stdin:
    msg = json.loads(line)
    if "id" not in msg:
        continue
    if msg["method"] == "initialize":
        result = {"protocolVersion": "2025-06-18", "capabilities": {"tools": {}},
                  "serverInfo": {"name": "toy-quotes", "version": "0.1"}}
    elif msg["method"] == "tools/call":
        syms = msg["params"]["arguments"]["symbols"]
        if os.environ.get("TOY_MCP_BAD_QUOTES"):
            text = "{bad quote data"
        else:
            text = json.dumps({s: QUOTES.get(s) for s in syms})
        result = {"content": [{"type": "text", "text": text}]}
    else:
        result = {}
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": msg["id"], "result": result}) + "\n")
    sys.stdout.flush()
