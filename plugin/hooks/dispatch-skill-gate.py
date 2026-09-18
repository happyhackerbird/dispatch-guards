#!/usr/bin/env python3
"""PreToolUse(Agent|Task|Workflow) gate: the dispatch skill must be
loaded before any dispatch.

Root cause this closes (skill-ify move, 2026-08-05): the dispatch
discipline used to live in a loose ~/.claude/dispatch-discipline.md
under a read-by-convention rule ("read it before delegating") — a
prose rule with no mechanical consumer, so a session could dispatch
all day without the discipline in context and nothing fired. Moving
the discipline into this plugin's `dispatch` skill made the load
observable in the transcript; this gate replaces the convention with
a deny (the corpus-edit gate's transcript-scan pattern, applied to
dispatch time).

Predicate: SESSION-scoped transcript scan (not per-turn — one load
covers the session, matching what the read-convention meant). The
skill counts as loaded when the transcript shows, in any assistant
turn, either
  - a Skill tool_use whose `skill` input names the dispatch skill
    (`dispatch`, `dispatch-guards:dispatch`, or any fully-qualified
    form ending in `:dispatch`), or
  - a Read of this plugin's `skills/dispatch/SKILL.md` (source repo
    or installed cache — suffix match).
Subagent contexts scan the subagent's own sidechain transcript
(`<session>/subagents/agent-<agent_id>.jsonl`) when it exists — the
subagent is the dispatching context; falls back to the parent
transcript otherwise (a dispatching parent has typically loaded it,
and the gate must not brick escalation-free sideways dispatches on a
missing file).

Fail-open (standing guard rule, _dispatch_common): unparseable hook
input, missing transcript_path, or an unreadable transcript never
block. The --test bite-tests registered in the machine-bootstrap
doctor are the tripwire for a harness change that silently breaks
the scan (transcript-format drift class — the corpus-edit gate died
fail-open exactly that way once).

Accepted residue: the scan proves the skill was LOADED this session,
not that it is still in context after compaction — the trade the
session scope deliberately makes; and a dispatching agent whose tool
roster lacks both Skill and Read cannot discharge the gate itself
(none of the site's agent types are so restricted as of 2026-08-05).
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
from _dispatch_common import dispatch_tier, fire, light_tier_hint  # noqa: E402

_SOURCE = "dispatch-guards/dispatch-skill-gate"

_DISPATCH_TOOLS = ("Agent", "Task", "Workflow")
_SKILL_MD_SUFFIX = "/skills/dispatch/SKILL.md"


def _skill_md_path() -> str:
    """This plugin's own SKILL.md, resolved relative to the hook file —
    valid in the source repo and in the installed plugin cache alike."""
    return os.path.normpath(os.path.join(
        os.path.dirname(os.path.realpath(__file__)),
        "..", "skills", "dispatch", "SKILL.md"))


def _names_dispatch_skill(skill: str) -> bool:
    """True iff a Skill input string names the dispatch skill: `dispatch`
    bare or any `:`-qualified form whose last segment is `dispatch`.
    A substring match would false-hit unrelated skills; the segment
    match cannot."""
    return skill.rsplit(":", 1)[-1] == "dispatch"


def _tool_uses(transcript_path: str):
    """(name, input) of every assistant tool_use in the transcript, or
    None on the fail-open modes (unreadable file). Malformed lines are
    skipped, not fatal — a partially-written transcript still scans."""
    try:
        events = []
        with open(transcript_path, "r", encoding="utf-8",
                  errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return None
    uses = []
    for event in events:
        msg = event.get("message")
        if not isinstance(msg, dict) or msg.get("role") != "assistant":
            continue
        content = msg.get("content", [])
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "tool_use":
                continue
            tool_input = block.get("input", {})
            uses.append((block.get("name"),
                         tool_input if isinstance(tool_input, dict) else {}))
    return uses


def resolve_scan_transcript(transcript_path: str, agent_id: str) -> str:
    """Subagent tool calls carry the PARENT transcript_path plus the
    subagent's agent_id; the subagent's own loads live in its sidechain
    transcript. Resolve to it when present (same pattern as the
    corpus-edit gate); main-session calls pass through unchanged."""
    if not agent_id or not transcript_path.endswith(".jsonl"):
        return transcript_path
    sub = (transcript_path[: -len(".jsonl")]
           + "/subagents/agent-" + agent_id + ".jsonl")
    return sub if os.path.exists(sub) else transcript_path


def skill_loaded(transcript_path: str) -> bool:
    """True if the dispatch skill was loaded anywhere in this
    transcript — or on the fail-open modes (couldn't verify, so don't
    block)."""
    uses = _tool_uses(transcript_path)
    if uses is None:
        return True
    for name, inp in uses:
        if name == "Skill" and _names_dispatch_skill(str(inp.get("skill", ""))):
            return True
        if (name == "Read"
                and str(inp.get("file_path", "")).endswith(_SKILL_MD_SUFFIX)):
            return True
    return False


def deny_text() -> str:
    return (
        "Blocked: dispatch without the dispatch skill loaded this "
        "session. Load it first — Skill tool: "
        "Skill(skill=\"dispatch-guards:dispatch\") (or Read "
        f"{_skill_md_path()}) — then retry the dispatch. The skill "
        "carries the brief and report discipline (§§1-2) this "
        "dispatch is checked against; one load covers the session."
        + light_tier_hint()
    )


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0  # never fail the workflow on a hook parse error
    if payload.get("tool_name") not in _DISPATCH_TOOLS:
        return 0
    transcript_path = payload.get("transcript_path", "")
    if not transcript_path:
        return 0  # fail-open: nothing to scan
    scan_path = resolve_scan_transcript(transcript_path,
                                        payload.get("agent_id", ""))
    # Light tiers (2026-09-18, _dispatch_common.dispatch_tier): a
    # read-type or declared small-write dispatch owes no brief form,
    # so the skill that teaches the form is not a precondition.
    if dispatch_tier(payload.get("tool_input") or {}) != "full":
        return 0
    if not skill_loaded(scan_path):
        # mode-aware deny: logged, warn-stageable via guard_modes
        fire(deny_text(), source=_SOURCE, payload=payload)
    return 0


if __name__ == "__main__":
    if "--test" in sys.argv:
        import io
        import tempfile
        from contextlib import redirect_stdout

        def write_transcript(path, events):
            with open(path, "w", encoding="utf-8") as f:
                for ev in events:
                    f.write(json.dumps(ev) + "\n")

        def tool_event(name, inp):
            return {"message": {"role": "assistant", "content": [
                {"type": "tool_use", "name": name, "input": inp}]}}

        with tempfile.TemporaryDirectory() as d:
            # keep the deny-path e2e runs below out of the REAL fire log
            os.environ["CLAUDE_DISPATCH_GUARDS_FIRELOG"] = \
                os.path.join(d, "fires.jsonl")
            t = os.path.join(d, "session.jsonl")

            # RED: transcript without a skill load → not loaded.
            write_transcript(t, [
                {"message": {"role": "user", "content": "dispatch something"}},
                tool_event("Bash", {"command": "ls"}),
            ])
            assert skill_loaded(t) is False

            # GREEN: Skill invocation, plain and fully-qualified forms.
            for skill in ("dispatch", "dispatch-guards:dispatch",
                          "plugin:dispatch-guards:dispatch"):
                write_transcript(t, [tool_event("Skill", {"skill": skill})])
                assert skill_loaded(t) is True, skill

            # A different skill whose name merely CONTAINS "dispatch"
            # does not count (segment match, not substring).
            write_transcript(t, [
                tool_event("Skill", {"skill": "dispatcher-tools"}),
                tool_event("Skill", {"skill": "foo:dispatch-helper"}),
            ])
            assert skill_loaded(t) is False

            # GREEN: Read of the SKILL.md (any home carrying the suffix).
            write_transcript(t, [tool_event("Read", {
                "file_path": "/x/plugins/cache/m/dispatch-guards/0.3.0"
                             "/skills/dispatch/SKILL.md"})])
            assert skill_loaded(t) is True
            # A Read of some other skill's SKILL.md does not count.
            write_transcript(t, [tool_event("Read", {
                "file_path": "/x/skills/worktree/SKILL.md"})])
            assert skill_loaded(t) is False

            # Fail-open: unreadable transcript → treated as loaded.
            assert skill_loaded(os.path.join(d, "missing.jsonl")) is True

            # Sidechain resolution: subagent id resolves to its own
            # transcript when present, parent otherwise.
            agent_id = "aXYZ"
            sub = os.path.join(d, "session", "subagents",
                               "agent-" + agent_id + ".jsonl")
            assert resolve_scan_transcript(t, agent_id) == t
            os.makedirs(os.path.dirname(sub), exist_ok=True)
            write_transcript(sub, [tool_event("Skill",
                                              {"skill": "dispatch"})])
            assert resolve_scan_transcript(t, agent_id) == sub
            assert resolve_scan_transcript(t, "") == t

            # main() wiring end to end: deny payload on the red case,
            # silence on the green case, fail-open on garbage stdin
            # and non-dispatch tools.
            def run_main(raw):
                old = sys.stdin
                out = io.StringIO()
                exited, code, ret = False, None, None
                try:
                    sys.stdin = io.StringIO(raw)
                    with redirect_stdout(out):
                        try:
                            ret = main()
                        except SystemExit as e:
                            exited, code = True, e.code
                finally:
                    sys.stdin = old
                return ret, out.getvalue(), exited, code

            write_transcript(t, [tool_event("Bash", {"command": "ls"})])
            ret, out, exited, code = run_main(json.dumps({
                "tool_name": "Agent", "transcript_path": t}))
            assert exited is True and code == 0
            dp = json.loads(out)
            assert dp["hookSpecificOutput"]["permissionDecision"] == "deny"
            assert "dispatch skill" in dp["systemMessage"]

            write_transcript(t, [tool_event("Skill",
                                            {"skill": "dispatch"})])
            ret, out, exited, code = run_main(json.dumps({
                "tool_name": "Agent", "transcript_path": t}))
            assert exited is False and ret == 0 and out == ""

            ret, out, exited, code = run_main("not json")
            assert ret == 0 and exited is False
            ret, out, exited, code = run_main(json.dumps({
                "tool_name": "Bash", "transcript_path": t}))
            assert ret == 0 and exited is False
            ret, out, exited, code = run_main(json.dumps({
                "tool_name": "Agent", "transcript_path": ""}))
            assert ret == 0 and exited is False

        print("dispatch-skill-gate: all tests passed")
        sys.exit(0)
    sys.exit(main())
