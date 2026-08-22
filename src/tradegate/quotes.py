"""Market-data connectors: live analytics in, orders never out.

Three sources behind one interface:
  FixtureQuotes - committed synthetic quotes (CI, tests, keyless clones)
  APIQuotes     - any REST quotes endpoint (QUOTES_API_URL with a {symbol}
                  placeholder + QUOTES_API_KEY bearer token)
  MCPQuotes     - a minimal MCP stdio client (newline-delimited JSON-RPC):
                  spawns the configured server command and calls its quote
                  tool. Point it at a brokerage MCP server (e.g. a Robinhood
                  MCP server's get_equity_quotes) for live data; tests point
                  it at the bundled toy server speaking the same protocol.

This module READS market data. There is deliberately no order-placement
connector anywhere in this repo.
"""
import json
import os
import pathlib
import subprocess
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[2]


class FixtureQuotes:
    name = "fixture"

    def get(self, symbols):
        quotes = json.loads((ROOT / "data" / "quotes.json").read_text())
        return {s: quotes.get(s) for s in symbols}


class APIQuotes:
    name = "api"

    def get(self, symbols):
        out = {}
        for s in symbols:
            req = urllib.request.Request(
                os.environ["QUOTES_API_URL"].format(symbol=s),
                headers={"Authorization": f"Bearer {os.environ['QUOTES_API_KEY']}"})
            with urllib.request.urlopen(req, timeout=30) as r:
                out[s] = float(json.loads(r.read())["price"])
        return out


class MCPQuotes:
    """Minimal MCP client over stdio. Config (connectors.json -> "mcp"):
    {"command": [...], "tool": "...", "symbol_arg": "..."}"""
    name = "mcp"

    def __init__(self, command, tool, symbol_arg="symbols"):
        self.command, self.tool, self.symbol_arg = command, tool, symbol_arg

    def _rpc(self, proc, msg):
        proc.stdin.write((json.dumps(msg) + "\n").encode())
        proc.stdin.flush()
        if "id" in msg:
            return json.loads(proc.stdout.readline())

    def get(self, symbols):
        proc = subprocess.Popen(self.command, stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE)
        try:
            self._rpc(proc, {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                             "params": {"protocolVersion": "2025-06-18",
                                        "capabilities": {},
                                        "clientInfo": {"name": "tradegate", "version": "0.2"}}})
            self._rpc(proc, {"jsonrpc": "2.0", "method": "notifications/initialized"})
            resp = self._rpc(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                                    "params": {"name": self.tool,
                                               "arguments": {self.symbol_arg: list(symbols)}}})
            text = resp["result"]["content"][0]["text"]
            data = json.loads(text)
            return {s: data.get(s) for s in symbols}
        finally:
            proc.terminate()


def get_source(config=None):
    config = config or json.loads((ROOT / "connectors.json").read_text())
    mode = os.environ.get("QUOTES_MODE", config.get("mode", "fixture"))
    if mode == "api":
        return APIQuotes()
    if mode == "mcp":
        m = config["mcp"]
        return MCPQuotes(m["command"], m["tool"], m.get("symbol_arg", "symbols"))
    return FixtureQuotes()
