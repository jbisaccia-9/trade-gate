"""The monitoring agent overtop: a recommend-only overseer.

It reads the decision log and live quotes through tools and writes a review -
which gates are refusing, whether the caps look miscalibrated, which symbols
lack quotes. Its authority is structural, not rhetorical: the overseer has NO
mutating tools. It cannot edit config, cannot place orders, cannot clear a
refusal. It recommends; a human decides. (The pattern comes from running a
real overseer over a real trading loop: graders grade, they do not steer.)

Backends share one loop: Anthropic Claude live (optional `anthropic` extra),
scripted policy for keyless CI. Either way the report faces the GROUNDING
GATE: every decision id cited must exist in the log it reviewed.
"""
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]

SYSTEM = ("You are the recommend-only overseer for an order-gating pipeline. "
          "Use the tools to review recent gate decisions and current quotes. "
          "Write a short report: refusal patterns, possible cap miscalibration, "
          "data-quality issues. Cite decision ids like [d3] for every claim. "
          "You have no authority to change anything - recommend only.")


def load_log():
    p = ROOT / "data" / "decision_log.jsonl"
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]


def make_tools():
    log = load_log()

    def get_decision_log():
        return log

    def get_gate_stats():
        stats = {}
        for d in log:
            for g in d["failed_gates"]:
                stats[g] = stats.get(g, 0) + 1
        return {"decisions": len(log),
                "refused": sum(1 for d in log if not d["cleared"]),
                "refusals_by_gate": stats}

    def get_quotes(symbols):
        from .quotes import FixtureQuotes
        return FixtureQuotes().get(symbols)

    registry = {"get_decision_log": (get_decision_log, {}),
                "get_gate_stats": (get_gate_stats, {}),
                "get_quotes": (get_quotes, {"symbols": {"type": "array",
                                                        "items": {"type": "string"}}})}
    schema = [{"name": n, "description": n.replace("_", " "),
               "input_schema": {"type": "object", "properties": p, "required": list(p)}}
              for n, (_, p) in registry.items()]
    return registry, schema, log


class ClaudeModel:
    name = "claude"

    def __init__(self):
        import anthropic                       # optional extra: pip install .[live]
        self.client = anthropic.Anthropic()
        self.model = "claude-opus-5"

    def complete(self, messages, tools):
        resp = self.client.messages.create(
            model=self.model, max_tokens=2000, system=SYSTEM,
            messages=messages, tools=tools)
        return resp


class ScriptedModel:
    """Deterministic policy: stats, then the log, then a report grounded in
    the decision ids it actually read."""
    name = "scripted"

    def __init__(self):
        self.step = 0
        self.stats, self.log = None, None

    def complete(self, messages, tools):
        class Block:                                   # anthropic-shaped stand-ins
            def __init__(self, **kw): self.__dict__.update(kw)
        class Resp:
            def __init__(self, blocks, stop): self.content, self.stop_reason = blocks, stop
        last = messages[-1]
        if isinstance(last.get("content"), list) and last["content"] and \
           last["content"][0].get("type") == "tool_result":
            payload = json.loads(last["content"][0]["content"])
            if isinstance(payload, dict) and "refusals_by_gate" in payload:
                self.stats = payload
            elif isinstance(payload, list):
                self.log = payload
        if self.step == 0:
            self.step += 1
            return Resp([Block(type="tool_use", id="t1", name="get_gate_stats", input={})], "tool_use")
        if self.step == 1:
            self.step += 1
            return Resp([Block(type="tool_use", id="t2", name="get_decision_log", input={})], "tool_use")
        lines = [f"Overseer review: {self.stats['decisions']} decisions, "
                 f"{self.stats['refused']} refused."]
        for gate, n in sorted(self.stats["refusals_by_gate"].items(), key=lambda kv: -kv[1]):
            ids = [d["id"] for d in self.log if gate in d["failed_gates"]]
            lines.append(f"- '{gate}' refused {n} order(s) "
                         f"[{', '.join(ids)}] - review whether the threshold matches intent.")
        lines.append("Recommendations only; no configuration was changed.")
        return Resp([Block(type="text", text="\n".join(lines))], "end_turn")


class HallucinatingModel(ScriptedModel):
    name = "hallucinating"

    def complete(self, messages, tools):
        resp = super().complete(messages, tools)
        for b in resp.content:
            if getattr(b, "type", "") == "text":
                b.text += "\n- 'exclusion-list' also refused [d99] - loosen it."
        return resp


def run_overseer(model, max_turns=8):
    registry, schema, log = make_tools()
    messages = [{"role": "user", "content": "Review the recent gate decisions."}]
    for _ in range(max_turns):
        resp = model.complete(messages, schema)
        blocks = resp.content
        messages.append({"role": "assistant", "content": [
            {"type": b.type, **({"id": b.id, "name": b.name, "input": b.input}
                                if b.type == "tool_use" else {"text": b.text})}
            for b in blocks]})
        tool_uses = [b for b in blocks if getattr(b, "type", "") == "tool_use"]
        if not tool_uses:
            text = " ".join(b.text for b in blocks if getattr(b, "type", "") == "text")
            return text, [d["id"] for d in log]
        results = []
        for tu in tool_uses:
            fn, _ = registry[tu.name]
            results.append({"type": "tool_result", "tool_use_id": tu.id,
                            "content": json.dumps(fn(**tu.input))})
        messages.append({"role": "user", "content": results})
    raise RuntimeError("overseer exceeded max turns")


def report_gate(report, valid_ids):
    cited = set(re.findall(r"\bd\d+\b", report))
    ghosts = sorted(cited - set(valid_ids))
    print(f"  {'PASS' if not ghosts else 'FAIL'}  report grounding: "
          f"{len(cited)} decision ids cited, {len(ghosts)} not in the log")
    for g in ghosts:
        print(f"    UNGROUNDED: [{g}]")
    if ghosts:
        print("OVERSEER GATE: FAILED - the review cites decisions that never happened.")
        return 1
    print("OVERSEER GATE: PASSED - every cited decision exists in the log.")
    return 0


def get_model(kind="scripted"):
    return {"scripted": ScriptedModel, "hallucinating": HallucinatingModel,
            "claude": ClaudeModel}[kind]()
