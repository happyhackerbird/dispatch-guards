#!/usr/bin/env python3
"""PreToolUse(Agent|Task) reminder: brief-side counterpart to report-reminder.

Closes the §1 consumer gap (skill-craft review finding, 2026-07-19):
the brief form had no mechanical consumer at dispatch time — a
below-session-tier dispatch with an underspecified brief passed
silently (only fable dispatches force the permission dialog). One
line lands before the dispatch starts, reminding the dispatcher of
the §1 brief checks and the §2 report channel (dispatch skill,
this plugin: skills/dispatch/SKILL.md + references/forms.md).
The hook never judges the brief — judgment stays with the
dispatcher: it reminds on the judgment half and DENIES on the
computable slice of §§1-2. The enforced subset is THIS hook's,
version-stamped with the plugin — the skill deliberately does not
enumerate it. Deny-repair and relief-valve rules: SKILL.md §5
(general form for every guard; source label, not restated here).

Environment binding (as-of 2026-08-05): PreToolUse
`additionalContext` injection into the dispatching conversation —
CONFIRMED live, reminder line visible before each spawn (unverified
only at mint time 2026-07-19). Fail-open and
inert if the harness ignores it; --test covers the logic only
(bootstrap doctor tripwire).

Verb conversion, missing_tail lane (2026-09-15, guard-rewrite arc
item 2, `docs/directives/2026-09-15-guard-rewrite-arc.md`): a
tail-less brief that DECLARES it writes (a write-boundary or
commit-plan body marker — the one condition `_tail_rewrite_decidable`
decides, since `_tail_kind()` cannot: it reads anchors that live
INSIDE the tail, absent by construction at this lane's firing
moment) is now REPAIRED — the shipped EXECUTION tail from
forms.md, channel line filled from `name` presence — via
`hookSpecificOutput.updatedInput`, never denied, under BOTH "deny"
and "warn" `guard_modes`. The AMBIGUOUS class (no such marker) keeps
the deny, now MODE-AWARE for the first time: `deny()` does not
consult `guard_modes` at all (this file's own main() comment
elsewhere says so, and wave 0's probe confirmed it live), so before
this the lane could not be demoted by any site; it now routes
through `fire()` on the shared "brief-reminder" key, `off` silencing
the whole lane for both classes. Never a silent pass: a decidable
brief whose repair cannot be computed (forms.md unreadable or its
heading moved) falls back to the same mode-aware exit rather than
passing. DELIVERY, not compliance — wave 0's probe record proved an
injected prompt block reaches the subagent's effective prompt, and
separately that the agent quoted rather than obeyed an injected
line in that same run; this lane's docstrings and its fire-log
reason describe it as delivering the tail, never as a guarantee the
agent then follows it. Read-only is never positively decided or
auto-appended (asymmetry: an execution tail on a read-only brief
over-specifies harmlessly; a read-only tail on a writing brief
strips its commit discipline and would be actively wrong — see
`_tail_rewrite_decidable`'s own docstring). Unaffected this arc: the
other three deny lanes (`deny_text`, `tail_mode_mismatch`,
`missing_sections`) and both existing fire()-routed lanes stay as
they are.
"""
from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
from _dispatch_common import (deny, dispatch_tier, fire, fire_log,  # noqa: E402
                              guard_mode, light_tier_hint, policy)

_SOURCE = "dispatch-guards/brief-reminder"


def _forms_path() -> str:
    """The dispatch skill's forms reference (§2 tails + §3 roadmap),
    resolved relative to this hook — valid in the source repo and in
    the installed plugin cache alike. Denies point HERE so a bounce
    carries the exact file the fix is pasted from."""
    return os.path.normpath(os.path.join(
        os.path.dirname(os.path.realpath(__file__)),
        "..", "skills", "dispatch", "references", "forms.md"))


def _norm(text: str) -> str:
    """Lowercase and collapse all whitespace runs to single spaces.

    Every marker/anchor below is matched against THIS form. Basis
    (live false-fire 2026-07-30): the §2 tails carry hard line wraps
    in their source file (now references/forms.md), so a tail pasted
    verbatim — exactly what the deny text instructs — arrived as
    "never bridged\\nwith a guess" and failed the single-line
    anchor."""
    return re.sub(r"\s+", " ", text.lower())


def reminder_text() -> str:
    doc = policy().get("discipline_doc")
    if doc:
        return (
            f"Dispatch starting — brief check ({doc} §1): "
            "decision-complete (assignments made, files listed not "
            "paraphrased, grounding section, write boundaries, commit "
            "convention verbatim, gaps-surface instruction)? Report "
            "channel per §2 named in the brief? Verifier dispatch → "
            "artifact + question ONLY."
        )
    return (
        "Dispatch starting — brief check: decision-complete (assignments "
        "made, files listed not paraphrased, grounding stated, write "
        "boundaries, gaps surfaced not filled)? Report channel named in "
        "the brief? Verifier dispatch → artifact + question ONLY."
    )


_CHANNEL_MARKERS = ("sendmessage", "send_message", "report channel",
                    "final text is the report")


def mailbox_lane(tool_input: dict) -> bool:
    """True iff this dispatch lands in the MAILBOX lane, where the
    agent's final text reaches no one and only SendMessage delivers.

    `name` alone decides the lane (forms.md §2, binding as of
    2026-08-15, harness 2.1.232, controlled probe matrix): a NAMED
    dispatch — generic or pinned type alike — spawns as a mailbox
    teammate ("Spawned successfully … via mailbox"), promises no
    completion notification, and does not appear in the subagent
    listing. An UNNAMED dispatch launches as a background task
    ("Async agent launched") whose completion task-notification
    carries the agent's final text to the dispatcher VERBATIM —
    observed from an agent that called no tool at all, so that
    delivery does not depend on the agent cooperating.

    Supersedes the run_in_background predicate: the Agent tool takes
    no such parameter (schema `additionalProperties: false`, key
    absent), so the old `.get("run_in_background") is not False` was
    CONSTANT TRUE. That classified every dispatch as background,
    which made the unnamed lane's correct channel line unreachable
    and had tail_mode_mismatch deny it — the guard manufacturing the
    defect it exists to prevent, the same shape the 2026-08-07 lane
    repair closed for named sync-flagged dispatches.

    One predicate for both call sites below, so the two lanes cannot
    disagree about which channel line a dispatch owes."""
    return bool(tool_input.get("name"))


def missing_channel(payload: dict) -> bool:
    """True iff this is a MAILBOX-lane Agent dispatch whose prompt
    names no report channel — the deliver-into-the-void class (JOURNAL
    2026-07-27, epsilon-probe: agent finished, reported as final text,
    reached no one). The lane is decided by mailbox_lane() above:
    a `name` is present. Fail-open on any doubt."""
    if payload.get("tool_name") != "Agent":
        return False  # Task tool has its own return path
    tool_input = payload.get("tool_input") or {}
    if not mailbox_lane(tool_input):
        return False  # background task: final text IS delivered
    prompt = _norm(tool_input.get("prompt") or "")
    if not prompt:
        return False
    return not any(m in prompt for m in _CHANNEL_MARKERS)


def deny_text(payload: dict) -> str:
    """Deny text for missing_channel — it must name a repair that
    clears on retry. missing_channel fires on the MAILBOX lane only,
    which is exactly the named case, so there is one repair: paste
    the mailbox channel line. The other exit — dropping the name —
    changes the lane, so it is named too, with the gate that limits
    it. The superseded text offered `run_in_background: false`, a
    parameter the Agent tool does not accept: a repair that could
    never clear on retry."""
    return (
        "Blocked: mailbox-lane dispatch without a report channel. "
        "This dispatch is NAMED, and a name puts it in the mailbox "
        "lane — no completion notification fires for it, so its "
        "final text reaches no one. The brief must instruct "
        "delivery: paste the tail block's mailbox channel line from "
        f"{_forms_path()} §2 (SendMessage to the dispatcher — your "
        "final text reaches no one). Dropping the `name` instead "
        "moves the dispatch to the background-task lane, whose "
        "completion notification does deliver the final text — but "
        "the model gate mandates a name on every generic dispatch, "
        "so that exit is open to pinned types only. Fix the brief "
        "and retry."
    )


_TAIL_ANCHOR = "never bridged with a guess"
# Lane markers, named for the DELIVERY each asserts rather than for a
# launch mode: the unnamed lane's notification delivers the final
# text, the mailbox lane's does not exist.
_DELIVERED_TAIL_MARKER = "final text is the report"
_MAILBOX_TAIL_MARKER = "final text reaches no one"

# The BRIEF is prompt + any brief files the prompt names (forms.md
# §2: the tail reaches the executing agent inline OR in a referenced
# brief file; inline is required only when no file brief exists). The
# channel lanes above stay prompt-only by design — the channel line
# is bound to `name`, decided at the call site, which a static file
# cannot know.
#
# Two alternatives, because a brief names a path in two forms and both
# occur here: QUOTED (the only form that can carry spaces) and bare.
# Neither may be restricted to ASCII — project trees carry directories
# like "Planungsbüro …", and a character class that stops at the umlaut
# does not fail loudly: it yields a TRUNCATED path, which resolves to
# nothing and is indistinguishable from a brief file carrying no tail.
_MD_PATH_RE = re.compile(
    r"""["']([^"'`\n]*\.md)["']"""
    r"""|((?:~/|/|[^\s"'`()\[\]]*/)[^\s"'`()\[\]]*\.md)\b""")
_MAX_REFERENCED_FILES = 8
_MAX_FILE_BYTES = 262144


def _md_paths(text: str) -> list[str]:
    """Every .md path the text names, quoted span or bare token."""
    return [m.group(1) if m.group(1) is not None else m.group(2)
            for m in _MD_PATH_RE.finditer(text)]


def _referenced_md_texts(payload: dict) -> list[str]:
    """Contents of .md files the prompt references, best-effort.

    Relative paths resolve against the hook input's cwd. Unreadable,
    oversized, or missing files contribute nothing — only verified
    content counts toward the tail/section checks (naming a file is
    not evidence its tail exists)."""
    tool_input = payload.get("tool_input") or {}
    prompt = tool_input.get("prompt") or ""
    cwd = payload.get("cwd") or ""
    texts: list[str] = []
    for match in _md_paths(prompt)[:_MAX_REFERENCED_FILES]:
        path = os.path.expanduser(match)
        if not os.path.isabs(path):
            if not cwd:
                continue
            path = os.path.join(cwd, path)
        path = os.path.normpath(path)
        try:
            if os.path.getsize(path) > _MAX_FILE_BYTES:
                continue
            with open(path, encoding="utf-8", errors="replace") as f:
                texts.append(f.read())
        except OSError:
            continue
    return texts


def missing_tail(payload: dict) -> bool:
    """True iff an Agent dispatch's BRIEF — prompt plus any referenced
    brief files — lacks the §2 tail block's anchor sentence ("never
    bridged with a guess"): the free-composed-brief-drops-the-
    invariant-tail class named in §2. Inline tail required only when
    the prompt names no tail-bearing brief file. Fail-open on any
    parse doubt."""
    if payload.get("tool_name") != "Agent":
        return False
    tool_input = payload.get("tool_input") or {}
    prompt = _norm(tool_input.get("prompt") or "")
    if not prompt:
        return False
    if _TAIL_ANCHOR in prompt:
        return False
    return not any(_TAIL_ANCHOR in _norm(t)
                   for t in _referenced_md_texts(payload))


def missing_tail_deny_text() -> str:
    return (
        "Blocked: dispatch brief without the §2 tail block, and its "
        "body names no write-boundary or commit-plan marker — the one "
        "condition under which this lane auto-repairs by appending the "
        "EXECUTION tail (dg-46). If this brief DOES write, add a "
        "'Write boundaries' or 'Commit plan' section and retry, or "
        "paste the tail yourself: EXECUTION or READ-ONLY tail verbatim "
        f"from {_forms_path()} — "
        "pick the channel line matching the dispatch LANE, which "
        "`name` alone decides (named = mailbox, unnamed = background "
        "task) — or point the prompt at a brief FILE that "
        "carries the tail, and retry."
        + light_tier_hint()
    )


def tail_mode_mismatch(payload: dict) -> bool:
    """True iff the pasted tail's channel line contradicts the
    dispatch's LANE — the wrong tail variant for the lane `name`
    selects (§2: named/mailbox → SendMessage/'reaches no one';
    unnamed/background task → 'final text IS the report'). Fail-open
    on any parse doubt."""
    if payload.get("tool_name") != "Agent":
        return False
    tool_input = payload.get("tool_input") or {}
    prompt = _norm(tool_input.get("prompt") or "")
    if not prompt:
        return False
    if mailbox_lane(tool_input):
        wrong, right = _DELIVERED_TAIL_MARKER, _MAILBOX_TAIL_MARKER
    else:
        wrong, right = _MAILBOX_TAIL_MARKER, _DELIVERED_TAIL_MARKER
    # The lane's OWN line being present is a declared exemption: a
    # brief that pastes the correct channel line and also QUOTES the
    # other one is conforming — quoting is how §2 itself gets edited,
    # and briefs to do exactly that are routine in this repo. Firing
    # on the mere presence of the other marker denied those with a
    # repair that cannot be followed: "paste the correct line" when
    # it is already pasted. Same class as the verifier-brief false
    # fire, one level in — there the other lane's text arrived by
    # CITING forms.md, here by quoting it inline.
    # This keeps the catch it exists for: a brief carrying only the
    # wrong line still has `right` absent and still denies.
    return wrong in prompt and right not in prompt


def tail_mode_mismatch_deny_text(payload: dict) -> str:
    """Deny text naming a repair that actually CLEARS.

    Two knobs move a dispatch between lanes — the channel line and
    the `name` — so this deny must not name only the line. An UNNAMED
    GENERIC dispatch cannot stay unnamed: the model gate mandates a
    `<model>-` name on every generic dispatch, so "swap the line"
    sends the author into a bounce loop (mismatch → model gate →
    mismatch), and the one-step repair, ADD THE NAME AND KEEP THE
    MAILBOX LINE, is the only exit. Naming just the line here
    reintroduced one lane over exactly the un-followable-repair class
    that missing_channel's deny text was fixed for."""
    doc = policy().get("discipline_doc") or "the dispatch skill"
    tool_input = payload.get("tool_input") or {}
    if mailbox_lane(tool_input):
        return (
            "Blocked: tail channel line contradicts the dispatch "
            'lane — the background-task channel line ("your final '
            'text IS the report") was pasted into a NAMED dispatch, '
            "which runs in the mailbox lane: no completion "
            "notification fires, so that final text reaches no one. "
            "Repair: keep the name and paste the MAILBOX line "
            '("SendMessage to the dispatcher — your final text '
            'reaches no one") from '
            f"{_forms_path()} §2, and retry."
        )
    return (
        "Blocked: tail channel line contradicts the dispatch lane — "
        'the mailbox channel line ("your final text reaches no one") '
        "was pasted into an UNNAMED dispatch, whose completion "
        "notification does deliver the final text. TWO repairs, and "
        "which one applies depends on the agent type: for a GENERIC "
        "dispatch (general-purpose, Explore, Plan, claude) ADD the "
        "`<model>-<slug>` name the model gate mandates and KEEP this "
        "mailbox line — dropping the line instead only moves the "
        "bounce to the model gate. For a pinned-type agent, which the "
        "model gate exempts, either works: name it and keep this "
        'line, or stay unnamed and paste "your final text IS the '
        f'report" instead ({doc} §2). Retry.'
    )


_SECTIONS_ANCHOR = "closing report (mandatory"
# The READ-ONLY tail's own signature — a marker FAMILY, like the
# section markers below, because the tail's wording is amended over
# time and briefs already in flight carry the older form: one hit is
# enough, and both members are read-only-exclusive (the execution tail
# says "do NOT write a report FILE", which contains neither). The
# report-file prohibition moved to the head of the block, which is
# where the second marker lives.
# Needed because forms.md carries
# BOTH tails verbatim, and the brief text this guard reads includes
# every .md file the prompt names: a verifier brief whose only offence
# is CITING forms.md — which §1 tells verifier briefs to cite — picked
# up the execution anchor from the citation and was denied for lacking
# §1 execution sections it is explicitly exempt from. Observed live on
# a legitimate verifier dispatch.
_READONLY_ANCHORS = ("no repo writes, no report files",
                     "is not a report, is not read as one")
# Marker-Familien statt Einzel-Literale: Haus-Briefe folgen dem
# DEV-RUNBOOK-Formular mit deutschen Feld-Etiketten (GROUNDING-BASIS,
# SCHREIB-GRENZEN) — die Erkennung akzeptiert die Abschnitts-Etiketten
# beider Sprachen; ein Treffer je Familie genügt.
_GROUNDING_MARKERS = ("grounding", "grounding-basis")
_WRITE_BOUNDARY_MARKERS = ("write boundar", "schreib-grenzen",
                           "schreibgrenzen")


def missing_sections(payload: dict) -> bool:
    """True iff an Agent dispatch's prompt carries the EXECUTION tail
    (identified by its "closing report (mandatory" signature, present
    only in the execution tail and absent from the READ-ONLY tail) but
    lacks one or both §1 mandatory execution-brief sections: a
    grounding-basis section and a write-boundaries section. An
    execution brief per the dispatch skill §1 always carries a
    grounding-basis section (what to read before building) and a
    write-boundaries section (paths owned); verifier/discovery briefs
    take the READ-ONLY tail and are exempt by that tail's absence of
    the anchor. Reads the BRIEF — prompt plus referenced brief files
    (see _referenced_md_texts). Fail-open on any parse doubt."""
    if payload.get("tool_name") != "Agent":
        return False
    tool_input = payload.get("tool_input") or {}
    if not (tool_input.get("prompt") or ""):
        return False
    if _tail_kind(payload) != "execution":
        return False  # verifier/discovery or no tail; exempt
    brief = _brief_text(payload)
    return not (any(m in brief for m in _GROUNDING_MARKERS)
                and any(m in brief for m in _WRITE_BOUNDARY_MARKERS))


def _tail_kind(payload: dict) -> str:
    """Which §2 tail governs this dispatch: 'execution' | 'readonly' |
    'none'.

    Decided from the PROMPT wherever the prompt itself carries a tail,
    and only otherwise from the referenced brief files. Prompt-first is
    the whole point: forms.md contains both tails verbatim, so reading
    the referenced files first makes every brief that cites the forms
    file look like an execution brief — the false fire this exemption
    closes. A brief file may still carry the tail (§2 allows it), which
    is why the referenced-file fallback stays."""
    tool_input = payload.get("tool_input") or {}
    prompt = _norm(tool_input.get("prompt") or "")
    for text in (prompt, _brief_text(payload)):
        if any(a in text for a in _READONLY_ANCHORS):
            return "readonly"
        if _SECTIONS_ANCHOR in text:
            return "execution"
    return "none"


def _brief_text(payload: dict) -> str:
    """The whole normalized brief: prompt + referenced brief files."""
    tool_input = payload.get("tool_input") or {}
    parts = [tool_input.get("prompt") or ""]
    parts += _referenced_md_texts(payload)
    return _norm(" ".join(parts))


def missing_sections_deny_text(payload: dict) -> str:
    doc = policy().get("discipline_doc") or "the dispatch skill"
    prompt = _brief_text(payload)
    missing = []
    if not any(m in prompt for m in _GROUNDING_MARKERS):
        missing.append("a grounding-basis section (label "
                       "'Grounding' or 'GROUNDING-BASIS')")
    if not any(m in prompt for m in _WRITE_BOUNDARY_MARKERS):
        missing.append("a write-boundaries section (label "
                       "'Write boundaries' or 'SCHREIB-GRENZEN')")
    missing_text = " and ".join(missing)
    return (
        f"Blocked: execution brief missing mandatory {doc} §1 "
        f"section(s) — {missing_text}. An execution brief always "
        "carries a grounding-basis section (what to read before "
        "building) and a write-boundaries section (paths owned, "
        "targeted git add). Add the missing section(s) to the brief "
        "and retry."
        + light_tier_hint()
    )


# The §1 skeleton's `## Commit plan` heading. Two spellings, both
# normalized: `_norm` collapses the hard wrap in a pasted skeleton
# ("Commit\nplan") to the spaced form.
_COMMIT_PLAN_MARKERS = ("commit plan", "commit-plan")


def missing_commit_plan(payload: dict) -> bool:
    """True iff an execution-tail Agent brief carries no commit-plan
    section — the §1 skeleton slot where the dispatcher states the
    target repo's commit-blocking guards, read at compose time, and
    where the bump or ordering commit sits.

    Scope is exactly missing_sections' above — including its
    verifier/discovery exemption, which this lane must share: both
    decide the governing tail through _tail_kind(), so a verifier
    brief that merely CITES forms.md is exempt here too. Read
    referenced-files-first, this lane false-fired on exactly the
    brief shape its twin was repaired for, one function below the
    repair. What this establishes is PRESENCE OF THE LABEL and
    nothing more — a plan naming the wrong guard reads identical to a
    correct one here, so this lane grades composition, never the
    plan.

    PROMOTED TO DENY 2026-09-15 (dotfiles df-238), through the
    fire-rate review the repo's staging rule demands. The record, in
    the form the evidence actually supports: 47 fires in the machine
    fire log, all mode=warn, of which 39 post-date the one known
    false-fire class (a verifier brief merely CITING forms.md,
    repaired 2026-08-15 in 372dcc7 and pinned by the regression case
    below); at least six of those are desk-confirmed true positives
    (wave-5 brief set, lane E, df-3 build brief 2026-09-14), each
    repaired per instance. NOT a measured zero of false fires: the
    fire-log record carries no truth-value field (_dispatch_common
    fire_log), so "no false fire since" is an absence of record in
    any carrier, never a measurement — stated here in that honest
    form because a promotion record wider than its evidence is the
    assurance-wider-than-its-predicate class. Fail-open on parse
    doubt."""
    if payload.get("tool_name") != "Agent":
        return False
    tool_input = payload.get("tool_input") or {}
    if not (tool_input.get("prompt") or ""):
        return False
    if _tail_kind(payload) != "execution":
        return False  # verifier/discovery or no tail; exempt
    return not any(m in _brief_text(payload)
                   for m in _COMMIT_PLAN_MARKERS)


def missing_commit_plan_deny_text() -> str:
    doc = policy().get("discipline_doc") or "the dispatch skill"
    return (
        f"Blocked: execution brief without a commit-plan section "
        f"({doc} §1 skeleton, '## Commit plan'). State the target "
        "repo's "
        "commit-blocking guards READ at compose time and where the "
        "bump or ordering commit sits: a payload-version guard "
        "comparing against the RELEASE state clears every later "
        "same-batch commit once the bump is in, so bump-first turns "
        "one shared gate into zero bounces for every writer behind "
        "it — where its basis is the origin manifest, push at "
        "integration only, and a plugin-payload brief names who "
        "bumps the manifest. 'none' (no such guard) is a valid "
        "filling; silence is not. Add the section and retry."
        + light_tier_hint()
    )


# ── Tail auto-repair (missing_tail REWRITE; dg-46, guard-rewrite arc
# item 2, 2026-09-15) ─────────────────────────────────────────────
#
# ASYMMETRY (the stated basis for the one-directional rule below): an
# execution tail appended to a genuinely read-only brief
# over-specifies harmlessly — the agent reads a closing-report
# skeleton it does not need. A read-only tail appended to a brief
# that actually writes is actively wrong — it tells the agent "no
# repo writes, no report files" and strips the commit/pathspec
# discipline the work needs. So this lane only ever appends the
# EXECUTION tail, never the read-only one: read-only is NEVER
# positively decided from body markers, only ever falling through to
# the unchanged ambiguous-class exit below.
_EXECUTION_TAIL_HEADING = "EXECUTION tail (any dispatch that writes):"
_MAILBOX_CHANNEL_LINE = (
    "Report channel: SendMessage to the dispatcher — your final text "
    "reaches no one.")
_BACKGROUND_CHANNEL_LINE = "Report channel: your final text IS the report."
_CHANNEL_LINE_PLACEHOLDER = "<channel line>"


def _tail_rewrite_decidable(payload: dict) -> bool:
    """True iff a tail-less brief's BODY declares that it writes —
    the one condition under which missing_tail's deny becomes a
    rewrite instead.

    _tail_kind() (above) decides EXECUTION vs READONLY from anchors
    that live INSIDE the tail itself — at missing_tail's firing
    moment the tail is absent by definition, so _tail_kind() returns
    "none" by construction and cannot serve this decision; that
    circularity is why this reads the body instead. It reuses the
    two marker families missing_sections and missing_commit_plan
    already key on (_WRITE_BOUNDARY_MARKERS, _COMMIT_PLAN_MARKERS) —
    those two lanes are the precedent for deciding from these same
    substrings, so this is the hook's existing idiom extended, not a
    new concept.

    Accepted residue, named rather than left to be discovered later:
    both marker families are SUBSTRING matches, so a genuinely
    read-only brief that merely DISCUSSES write boundaries ("no
    write boundaries apply") false-fires into the execution-append.
    That lands in the harmless direction the ASYMMETRY note above
    describes, which is precisely why the one-direction rule
    survives it rather than needing a stricter (and more fragile)
    predicate."""
    brief = _brief_text(payload)
    return (any(m in brief for m in _WRITE_BOUNDARY_MARKERS)
            or any(m in brief for m in _COMMIT_PLAN_MARKERS))


def _execution_tail_body() -> str | None:
    """The shipped EXECUTION tail's raw text (channel-line
    placeholder still in it), read from forms.md AT FIRE TIME —
    never a second copy pasted into this hook, which would drift
    from the source it is meant to mirror (paraphrase-drift).
    Extracts the markdown indented-code block that follows the
    "EXECUTION tail (any dispatch that writes):" heading: every
    line indented 4 spaces, de-indented, until the first
    non-indented line. None on any read/parse failure — an
    unreadable forms.md or a moved heading must not manufacture a
    tail from nothing; the caller falls back to the unchanged
    deny/warn exit rather than a silent pass."""
    try:
        with open(_forms_path(), encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return None
    lines = text.splitlines()
    try:
        start = next(i for i, ln in enumerate(lines)
                     if ln.strip() == _EXECUTION_TAIL_HEADING)
    except StopIteration:
        return None
    body: list[str] = []
    for ln in lines[start + 1:]:
        if ln.startswith("    "):
            body.append(ln[4:])
        elif not ln.strip() and not body:
            continue  # the blank line between heading and block
        else:
            break
    return "\n".join(body) if body else None


def rewrite_tail_input(payload: dict) -> dict | None:
    """The repaired `tool_input` for a DECIDABLE tail-less brief: the
    shipped EXECUTION tail appended to the prompt, its channel-line
    placeholder filled from `name` presence exactly as the existing
    channel lanes decide it (mailbox_lane()) — named → the mailbox
    line, unnamed → the background line. None when
    _execution_tail_body() cannot produce a tail (forms.md
    unreadable or moved); the caller then falls back to the
    unchanged deny/warn exit rather than passing silently, mirroring
    agent-model-gate's never-silent-fallback convention for its own
    rewrite lane.

    DELIVERY, not compliance: this appends the tail into the
    effective prompt the agent reads — wave 0's probe record proved
    an injected block reaches the subagent, and separately that the
    agent QUOTED rather than obeyed an injected instruction in that
    same probe. Appending is not a guarantee the agent then follows
    the tail's rules, only that it is no longer absent from what the
    agent reads."""
    body = _execution_tail_body()
    if not body:
        return None
    tool_input = payload.get("tool_input") or {}
    line = (_MAILBOX_CHANNEL_LINE if mailbox_lane(tool_input)
           else _BACKGROUND_CHANNEL_LINE)
    tail = body.replace(_CHANNEL_LINE_PLACEHOLDER, line)
    prompt = tool_input.get("prompt") or ""
    new_input = dict(tool_input)
    new_input["prompt"] = prompt.rstrip("\n") + "\n" + tail
    return new_input


# A devbook/section fingerprint as the §6 register and the class
# devbooks spell one: a 64-character sha256 in hex. Matched over the
# NORMALIZED brief (lower-cased), and both ends anchored — an
# unanchored 64-run would also match inside a longer hex blob, which
# is the prefix-match-in-an-equality's-costume shape.
_HEX64_RE = re.compile(r"(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])")
_PIN_UNREADABLE_REASON = (
    "devbook-pin lane: could not verify — no readiness register was "
    "readable at {path}, so whether this brief names a registered "
    "class is UNKNOWN. Lane silent by design (a guess here would fire "
    "on legitimate work); logged so the absence is countable rather "
    "than invisible.")


def _registered_class_names() -> list | None:
    """Every name a brief can legitimately cite a registered class BY,
    read from the §6 register: each `prozesse[].id`, plus the
    SECTION-NAME TAIL of each `heimat` (`<file>#<section>` →
    `<section>`), because a brief names the devbook section at least
    as often as the class id.

    Three answers, not two (repo CLAUDE.md, the checker's third
    answer). `None` is COULD NOT VERIFY — register absent,
    unreadable, malformed, or not the register's own
    `{"prozesse": [...]}` shape (_register_entries) — and the caller
    maps it to silence-plus-a-log, never to "clean". An empty list is
    a real answer: the register was read and certifies zero classes,
    so no brief can be naming one. A malformed ENTRY inside a good
    file degrades to skipping that entry, mirroring _register_row:
    one bad row must not blank the whole consult."""
    path = _register_path()
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError, ValueError):
        return None
    entries = _register_entries(data)
    if entries is None:
        return None
    names = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        class_id = entry.get("id")
        if isinstance(class_id, str) and class_id.strip():
            names.append(class_id.strip())
        heimat = entry.get("heimat")
        if isinstance(heimat, str) and "#" in heimat:
            tail = heimat.split("#", 1)[1].strip()
            if tail:
                names.append(tail)
    return names


def missing_devbook_pin(payload: dict) -> str | None:
    """The matched class/section name iff an execution-tail Agent
    brief cites a REGISTERED class and pins no fingerprint — else
    None.

    The class this closes (dotfiles df-238): a build brief named a
    registered devbook section that had been amended the same day and
    pinned nothing, so the executing lane worked from whatever the
    file happened to say at read time. §6 makes the fingerprint the
    instrument for exactly that drift, and until now nothing asked for
    it at the one moment it is cheap — compose time. Caught by hand
    that day; a mechanism is what survives into the next session.

    Scope is its two siblings' — `_tail_kind(payload) == "execution"`,
    so verifier/discovery briefs are exempt, including one that merely
    CITES forms.md (the false-fire class repaired 2026-08-15).

    Accepted residue, named rather than discovered later: the class
    match is a SUBSTRING test over the normalized brief, so a heimat
    tail that is ordinary English ("Registered procedure") matches a
    brief that discusses it without dispatching against it. The
    direction is deliberate — this lane ships WARN, and an over-fire
    here costs a line the dispatcher reads, while an under-fire costs
    the drift the lane exists to catch. A `guard_modes` promotion to
    deny is what would make that residue expensive, which is the
    fire-rate review's question, not this docstring's.

    Fail-open on parse doubt, like every lane in this file."""
    if payload.get("tool_name") != "Agent":
        return None
    tool_input = payload.get("tool_input") or {}
    if not (tool_input.get("prompt") or ""):
        return None
    if _tail_kind(payload) != "execution":
        return None  # verifier/discovery or no tail; exempt
    brief = _brief_text(payload)
    if _HEX64_RE.search(brief):
        return None  # a pin is present; this lane asks nothing more
    names = _registered_class_names()
    if names is None:
        # COULD NOT VERIFY: with no register the lane cannot know
        # whether a class was named. Silent — but logged, so the
        # blind stretch is countable instead of reading as clean.
        fire_log(_SOURCE, "could-not-verify",
                 _PIN_UNREADABLE_REASON.format(path=_register_path()),
                 payload)
        return None
    for name in names:
        if _norm(name) in brief:
            return name
    return None


def missing_devbook_pin_warn_text(class_name: str) -> str:
    doc = policy().get("discipline_doc") or "the dispatch skill"
    return (
        f"Execution brief cites the registered class/section "
        f"\"{class_name}\" ({doc} §6 register) and pins NO 64-hex "
        "fingerprint. A registered devbook section can be amended "
        "between compose time and the lane's read — the §6 "
        "invalidation exists for exactly that — and an unpinned lane "
        "cannot tell which text it holds, so it reports \"the devbook "
        "says\" about a snapshot nobody graded. Repair: paste the "
        "section's sha256 into the brief. The recipe is the devbook "
        "section's OWN fingerprint paragraph (sha256 from its `## ` "
        "heading line up to, exclusive, the next `## `-prefixed line "
        "or EOF). RECOMPUTE IT FROM THE FILE, never copy it from the "
        "register: a register entry standing stale against the file "
        "is the drift the pin exists to catch, so a pin derived from "
        "the register agrees with itself and grades nothing."
    )


def check(payload: dict) -> str | None:
    """Return the reminder, or None (= stay silent)."""
    if payload.get("tool_name") not in ("Agent", "Task"):
        return None
    return reminder_text()


def _register_path() -> str:
    """Resolves the §6 CLASS register path — never the per-repo
    READINESS.json, which carries only exclusions/deviations (§6).
    `CLAUDE_DISPATCH_GUARDS_REGISTER` overrides, mirroring the
    `_dispatch_common` idiom (fire-log/config env overrides): bites
    and the bench point this at a fixture or a nonexistent path
    without ever touching the operator's real
    `~/.claude/readiness.json`."""
    env = os.environ.get("CLAUDE_DISPATCH_GUARDS_REGISTER")
    if env:
        return os.path.expanduser(env)
    return os.path.expanduser("~/.claude/readiness.json")


_REGISTER_ROW_MAX = 100
_REGISTER_ABSENT_LINE = (
    "Tier-readiness register (dispatch skill \xa76): no readiness "
    "register was readable at {path} — treat as NO certified "
    "classes verified, not as a clean register.")
_REGISTER_EMPTY_LINE = (
    "Tier-readiness register (dispatch skill \xa76): register at "
    "{path} readable, zero certified classes.")
_REGISTER_HEADER_LINE = (
    "Tier-readiness register (dispatch skill \xa76): id \xb7 tier "
    "\xb7 status \xb7 klasse")


def _register_row(class_id: str, entry) -> str:
    """One `id \xb7 tier \xb7 status \xb7 klasse` row (BACKLOG
    2026-08-11 entry's row format), truncated to _REGISTER_ROW_MAX so
    a long klasse one-liner cannot blow up the block. A malformed
    ENTRY (not a dict, or missing a subfield) degrades that field to
    '?' rather than raising — only a malformed/unreadable FILE
    degrades to the explicit absence line; one bad entry must not
    blank the whole register consult."""
    if not isinstance(entry, dict):
        entry = {}
    tier = entry.get("tier") or "?"
    status = entry.get("status") or "?"
    klasse = entry.get("klasse") or ""
    head = f"{class_id} \xb7 {tier} \xb7 {status} \xb7 "
    row = head + klasse
    if len(row) <= _REGISTER_ROW_MAX:
        return row
    budget = max(_REGISTER_ROW_MAX - len(head) - 1, 0)
    return head + klasse[:budget] + "…"


def _register_entries(data) -> list | None:
    """Extracts the class-entry list from a parsed register document,
    or None if the document's shape is not the register's.

    The real, deployed global register (`dotfiles/claude/readiness.json`,
    read directly to ground this function — no schema fixture exists
    in this repo or in §6's prose) wraps its entries in a top-level
    object under a `prozesse` (German: "processes") key, each entry
    carrying its OWN `id` field — never a bare dict keyed by class id,
    which was this function's first (unverified) shape and would have
    rendered the wrapper's own metadata keys (`_hinweis`,
    `schema_version`, `lineup_stand`) as if they were classes. §6's
    prose ("one entry per class with target tier, status, probe
    evidence, fingerprint") describes the ENTRY fields, not the
    container — this is the container, confirmed against the one real
    instance rather than assumed."""
    if not isinstance(data, dict):
        return None
    entries = data.get("prozesse")
    if not isinstance(entries, list):
        return None
    return entries


def register_lines(payload: dict) -> list[str]:
    """The §6 tier-readiness register's own rows, in front of the
    dispatcher's eyes at the one moment the tier choice is made
    (BACKLOG 2026-08-11 entry — the register consult otherwise has no
    mechanism at the moment it is owed). Scoped like the reminder
    line itself: Agent/Task dispatches only.

    Informational only: never a deny, never a predicate over the
    brief text — the hook cannot know the work's class, and guessing
    one would be the false-fire class the corpus forbids. Absent,
    unreadable, or malformed register -> one explicit line, never
    silence and never an empty block: a missing register that renders
    as nothing reads as "no certified classes", the
    could-not-verify-as-verified failure the entry names. Malformed
    JSON, or JSON that parses but is not the register's own
    `{"prozesse": [...]}` shape (see _register_entries), takes the
    same absence line — both are the same could-not-verify. A
    POPULATED register additionally gets a header row
    (_REGISTER_HEADER_LINE) naming the column vocabulary ahead of the
    bare `id · tier · status · klasse` rows — the absence and empty
    lines are already self-labelled; the populated case previously
    was not."""
    if payload.get("tool_name") not in ("Agent", "Task"):
        return []
    path = _register_path()
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError, ValueError):
        return [_REGISTER_ABSENT_LINE.format(path=path)]
    entries = _register_entries(data)
    if entries is None:
        return [_REGISTER_ABSENT_LINE.format(path=path)]
    if not entries:
        return [_REGISTER_EMPTY_LINE.format(path=path)]
    return [_REGISTER_HEADER_LINE] + [
        _register_row(e.get("id") or "?" if isinstance(e, dict)
                     else "?", e) for e in entries]


def worktree_advisory_text() -> str:
    return (
        "Worktree isolation — base advisory: harness-cut worktrees have "
        "come from a snapshot OLDER than local HEAD (observed twice "
        "2026-08-05, both cuts == origin/main while local main was "
        "ahead; mechanism unverified). Three classes: (1) SESSION-repo "
        "worktree cut stale — the brief must STATE the base commit and "
        "carry the §1 sanctioned recovery (ff-only to that base over a "
        "clean tree), else the executor halts on a guard doing its job; "
        "(2) a brief naming a SIBLING repo — isolation cuts the session "
        "repo regardless, so provision the working copy yourself and "
        "name its path in the brief; (3) a sibling-repo brief run UNDER "
        "isolation — the unused session worktree can be auto-reclaimed "
        "mid-run, killing Bash outright: run sibling-repo dispatches "
        "WITHOUT isolation."
    )


def worktree_advisory(payload: dict) -> str | None:
    """Non-blocking advisory for `isolation: "worktree"` Agent calls.

    Fires only on that call shape; every other dispatch is untouched.
    Rides this ALREADY-WIRED hook entry deliberately: a hooks.json
    entry new in an update stays dormant until a full restart, while
    changed code behind a wired entry reloads (dotfiles CLAUDE.md,
    probe 2026-08-05)."""
    if payload.get("tool_name") != "Agent":
        return None
    tool_input = payload.get("tool_input") or {}
    if tool_input.get("isolation") != "worktree":
        return None
    return worktree_advisory_text()


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0  # never fail the workflow on a hook parse error
    # deny() emits BOTH permissionDecisionReason (reaches the model)
    # and systemMessage (reaches the user), source-tagged. Basis
    # (2026-07-30): a deny carrying only systemMessage left the model
    # with the harness's bare "Hook PreToolUse:Agent denied this tool",
    # which two sessions misattributed to a Claude Code permission bug.
    if missing_channel(payload):
        deny(deny_text(payload), source=_SOURCE, payload=payload)
    if tail_mode_mismatch(payload):
        deny(tail_mode_mismatch_deny_text(payload), source=_SOURCE,
             payload=payload)
    # Light tiers (2026-09-18, _dispatch_common.dispatch_tier): a
    # read-type or declared small-write dispatch skips every FORM lane
    # below — tail, sections, commit plan, devbook pin. The channel
    # lane above still applies to every tier. Logged so the relief's
    # use is countable in the fire-rate review like any lane.
    tier = dispatch_tier(payload.get("tool_input") or {})
    if payload.get("tool_name") == "Agent" and tier != "full":
        fire_log(_SOURCE, "light-" + tier,
                 f"light tier {tier}: form lanes skipped", payload)
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": (
                    f"Dispatch tier: {tier} — brief form lanes skipped. "
                    "You still verify the result before relying on it."),
            }
        }))
        return 0
    # MODE-AWARE since 2026-09-15 (dg-46, guard-rewrite arc item 2) —
    # a verb conversion carrying this lane's existing record forward:
    # it was never staged (hard deny from the day it shipped, like
    # the mandatory-name lane's declared exception), so the default
    # here stays "deny" and a fresh/unconfigured site sees exactly
    # the old behavior. What is NEW is the DECIDABLE class, which
    # repairs unconditionally in "deny" and "warn" alike (the repair
    # is the action, not a punishment grade — CLAUDE.md three-verbs
    # bullet) and only "off" turns the whole lane silent for both
    # classes. `guard_modes["brief-reminder"]` is SHARED with
    # missing_commit_plan and missing_devbook_pin below (one key,
    # one file, per the existing convention) — a site demoting the
    # commit-plan lane to "warn" also softens this lane's AMBIGUOUS
    # exit from deny to warn-and-pass; the decidable class is
    # unaffected by that (it never denies in "deny" or "warn"),
    # named here because nothing else in this file's history says so.
    if missing_tail(payload):
        if guard_mode(_SOURCE) != "off":
            if _tail_rewrite_decidable(payload):
                new_input = rewrite_tail_input(payload)
            else:
                new_input = None
            if new_input is not None:
                reason = (
                    "brief-reminder: appended the EXECUTION tail "
                    f"({_forms_path()} §2) — the brief's body names a "
                    "write-boundary or commit-plan marker (declares it "
                    "writes) and carried no §2 tail. Delivered into "
                    "the effective prompt; the agent may quote it, "
                    "this does not guarantee it then complies."
                )
                fire_log(_SOURCE, "rewrite", reason, payload)
                print(json.dumps({
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "updatedInput": new_input,
                    }
                }))
                return 0
            # AMBIGUOUS class, or the decidable rewrite could not be
            # computed (forms.md unreadable/moved) — never a silent
            # pass: fall back to the mode-aware deny/warn exit.
            fire(missing_tail_deny_text(), source=_SOURCE, payload=payload,
                 default_mode="deny")
    if missing_sections(payload):
        deny(missing_sections_deny_text(payload), source=_SOURCE,
             payload=payload)
    # PROMOTED to deny 2026-09-15 (df-238) — the evidence and its
    # honest limits live in missing_commit_plan's docstring. It stays
    # on fire() rather than deny() so a site can demote it through
    # `guard_modes` without a code change.
    #
    # The `guard_modes` key is "brief-reminder" (the source tag's last
    # segment), and it now reaches BOTH fire()-routed lanes in this
    # file, no longer one: a site setting it to "warn" demotes this
    # deny, and setting it to "deny" promotes the staged pin lane
    # below. The four deny() lanes above are unaffected either way,
    # since deny() does not consult the modes at all. Stated because
    # the superseded comment here claimed the key "reaches this lane
    # alone", which stopped being true the moment a second fire()
    # lane landed — a mechanism's own words outliving their predicate.
    if missing_commit_plan(payload):
        fire(missing_commit_plan_deny_text(), source=_SOURCE,
             payload=payload, default_mode="deny")
    # Staged lane (WARN by shipped default, repo CLAUDE.md: a new lane
    # earns deny through the fire-rate review), ordered LAST ON
    # PURPOSE — after every deny lane above. fire() exits in EVERY
    # mode, warn included, so a warn lane placed EARLIER would exit
    # before the denies behind it ever ran: a staged lane silently
    # disabling four shipped ones. The named-diagnostic ordering rule
    # (put the specific message ahead of the broad one) is a
    # Report-pattern rule, where every check appends and none exits;
    # transferred to an exit-per-lane hook its mechanism does not
    # hold. What the ordering costs is bounded: a pin-less brief that
    # is ALSO denied gets the deny, is repaired, and the pin warn
    # fires on the retry.
    pin_class = missing_devbook_pin(payload)
    if pin_class:
        fire(missing_devbook_pin_warn_text(pin_class), source=_SOURCE,
             payload=payload, default_mode="warn")
    # One additionalContext field per hook call: the advisory and the
    # register rows ride the reminder line rather than replacing it.
    lines = [t for t in (check(payload), worktree_advisory(payload)) if t]
    lines += register_lines(payload)
    if lines:
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": "\n".join(lines),
            }
        }))
    return 0


if __name__ == "__main__":
    if "--test" in sys.argv:
        import tempfile
        from _dispatch_common import _reset_policy_cache
        os.environ["CLAUDE_DISPATCH_GUARDS_CONFIG"] = "/nonexistent"
        _reset_policy_cache()
        assert check({"tool_name": "Agent"}) is not None
        assert check({"tool_name": "Task"}) is not None
        assert "brief check" in check({"tool_name": "Agent"})
        with tempfile.NamedTemporaryFile("w", suffix=".json",
                                         delete=False) as tf:
            tf.write('{"discipline_doc": "dispatch skill"}')
            os.environ["CLAUDE_DISPATCH_GUARDS_CONFIG"] = tf.name
        _reset_policy_cache()
        assert "dispatch skill §1" in check({"tool_name": "Agent"})
        assert check({"tool_name": "Bash"}) is None
        assert check({}) is None
        # Channel gate: mailbox lane (NAMED) + no channel → deny
        assert missing_channel({"tool_name": "Agent", "tool_input": {
            "name": "sonnet-x",
            "prompt": "Go read files and report your findings."}})
        # Channel named (any marker) → allow
        assert not missing_channel({"tool_name": "Agent", "tool_input": {
            "name": "sonnet-x",
            "prompt": "Do X. Deliver via SendMessage to main."}})
        # Task tool, empty prompt, non-dispatch tools → never deny
        assert not missing_channel({"tool_name": "Task", "tool_input": {
            "name": "sonnet-x", "prompt": "no channel here"}})
        assert not missing_channel({"tool_name": "Agent", "tool_input": {}})
        assert not missing_channel({"tool_name": "Bash", "tool_input": {
            "command": "ls"}})
        _named = {"tool_name": "Agent", "tool_input": {
            "name": "sonnet-x", "prompt": "do the thing"}}
        assert "Blocked" in deny_text(_named)
        assert "mailbox" in deny_text(_named)
        # The superseded text advised `run_in_background: false`, a
        # parameter the Agent tool does not accept — a repair that
        # could never clear on retry. It must not come back.
        assert "run_in_background" not in deny_text(_named)

        # ── The LANE is set by `name` alone ────────────────────────
        # Expectations derived from forms.md §2's binding (as of
        # 2026-08-15, harness 2.1.232) and the probe matrix behind
        # it — never from this hook's behavior. Measured: a NAMED
        # dispatch (generic or pinned type) spawns as a mailbox
        # teammate and fires no completion notification; an UNNAMED
        # one launches as a background task whose notification
        # carried the agent's final text verbatim, from an agent
        # that called no tool at all.
        # (i) UNNAMED + no channel line → NO deny. The background
        # task's notification delivers the final text, so nothing is
        # owed. The superseded flag predicate was constant-true and
        # denied here.
        assert not missing_channel({"tool_name": "Agent", "tool_input": {
            "prompt": "Do the thing and report back."}})
        # (ii) UNNAMED carrying the background-task line → silent.
        # This is the shape the superseded predicate bounced: it read
        # every dispatch as background and denied the line that is
        # true for this lane.
        _unnamed_delivered = {"tool_name": "Agent", "tool_input": {
            "subagent_type": "claude-code-guide",
            "prompt": "Do the thing.\nReport channel: your final text "
                      "IS the report."}}
        assert not missing_channel(_unnamed_delivered)
        assert not tail_mode_mismatch(_unnamed_delivered)
        # (iii) UNNAMED carrying the MAILBOX line → mismatch: that
        # line tells an agent its final text reaches no one when the
        # notification does deliver it.
        assert tail_mode_mismatch({"tool_name": "Agent", "tool_input": {
            "subagent_type": "claude-code-guide",
            "prompt": "Do the thing.\nReport channel: SendMessage to "
                      "the dispatcher — your final text reaches no "
                      "one."}})
        # (iv) NAMED carrying the correct mailbox line → silent;
        # NAMED carrying the background-task line → mismatch.
        assert not tail_mode_mismatch({"tool_name": "Agent", "tool_input": {
            "name": "x-agent",
            "prompt": "Do the thing.\nReport channel: SendMessage to "
                      "the dispatcher — your final text reaches no "
                      "one."}})
        assert tail_mode_mismatch({"tool_name": "Agent", "tool_input": {
            "name": "x-agent",
            "prompt": "Do the thing.\nReport channel: your final text "
                      "IS the report."}})
        # (v) a pinned type is not itself a lane: NAMED pinned sits in
        # the mailbox lane with every other named dispatch. This is
        # the cell that separated `name` from agent type in the probe.
        assert mailbox_lane({"name": "x-agent",
                             "subagent_type": "claude-code-guide"})
        assert not mailbox_lane({"subagent_type": "claude-code-guide"})
        # the predicate itself, both directions
        assert mailbox_lane({"name": "x-agent"})
        assert not mailbox_lane({})
        # a dead `run_in_background` key changes nothing either way
        assert mailbox_lane({"name": "x-agent",
                             "run_in_background": False})
        assert not mailbox_lane({"run_in_background": False})

        # ── Tail-presence lane (missing_tail) ──────────────────────
        # Tails copied verbatim from the §2 forms (cite: dispatch
        # skill, references/forms.md §2) — literals here, never
        # referenced from the detection constants, so the test
        # doesn't share parentage with what it's meant to catch.
        EXECUTION_TAIL_BG = (
            "A mid-run message may not arrive before the turn ends: "
            "on a gap HALT THE ITEM, FINISH THE REMAINDER, REPORT — "
            "never halt the LANE, since \"halt and wait\" is not a "
            "survivable state for a subagent (source: \xa72, the "
            "delivery binding).\n"
            "Closing report (mandatory; the project's own report form "
            "if it defines one, else the \xa72 form here — never "
            "both; \"none\" is a valid slot answer, silence is not): "
            "(a) items completed w/ evidence, (b) checks RUN w/ real "
            "output — FULL counts incl. skips (`N passed, M failed, "
            "K skipped`), each skip dispositioned (which check, why, "
            "whether the reason touches the item); a skip in a check "
            "YOU built is a finding, not a pass — the built branch "
            "did not execute, (c) gaps surfaced — incl. anything needing a "
            "tier above yours, returned as a question with its "
            "evidence, never settled at your tier, (d) deviations w/ "
            "reason, (e) candidate lessons, (f) files touched + commit "
            "hashes (unpushed) — only commits whose Co-Authored-By "
            "trailer is YOURS; one you cannot claim by trailer is "
            "\"present in the tree, not mine\"; a `.git/config` write "
            "counts as a repo write, (g) what was NOT verified, "
            "(h) sources actually read, of those the brief named.\n"
            "Every claim about something OUTSIDE your own work — a "
            "file you did not write, a mechanism, another repo, a "
            "tool's behavior — names the read that opened it, or "
            "carries \"inferred, unverified\"; a recommendation "
            "resting on an unopened claim carries the grade too.\n"
            "Drain your inbox before sending, and between parts of a "
            "multi-part report: every dispatcher message received up "
            "to send time is dispositioned or named as unhandled.\n"
            "Report channel: SendMessage to the dispatcher — your "
            "final text reaches no one.\n"
            "Message ≤3000 chars each: a report longer than one "
            "message is SPLIT into labeled parts (1/N) — do NOT write "
            "a report FILE (harness-blocked for subagents); supporting "
            "data goes to the brief's assigned DATA files, the message "
            "carries key findings + any such paths. A missing "
            "decision, file, or value is surfaced as a gap, never "
            "bridged with a guess.\n"
            "A check that got backgrounded is AWAITED before the "
            "closing report (TaskOutput block=true on its task id) — "
            "ending your turn orphans it; a report sent with a check "
            "still running is an INTERIM report, says so, and names "
            "what remains.\n"
            "Commits unpushed, by pathspec — `git commit -m \"…\" -- "
            "<paths>` with every flag BEFORE the `--` (after it git "
            "reads `-m` as a pathspec and the commit fails; `-F` for a "
            "multi-line message), never `git add` then `git commit` "
            "and never `-A`: the "
            "index is shared, so a co-writer staging between your `git "
            "status` and your commit rides out under your message "
            "whatever you added. A NEW file is invisible to a pathspec "
            "commit until `git add -N <path>` registers it "
            "(intent-to-add: zero content staged, full body still "
            "committed). Trailer: `Co-Authored-By: Claude <model> "
            "<noreply@anthropic.com>`.\n"
            "Never amend — always a new commit: the amend-gate denies "
            "subagent amends regardless of ownership (source: \xa71 amend "
            "rule).\n"
            "After sending the report your write grant is over: a "
            "defect you find later is REPORTED, never edited or "
            "amended (source: \xa74 ownership rule)."
        )
        EXECUTION_TAIL_SYNC_LINE = EXECUTION_TAIL_BG.replace(
            "Report channel: SendMessage to the dispatcher — your "
            "final text reaches no one.",
            "Report channel: your final text IS the report.",
        )
        READONLY_TAIL_SYNC = (
            "Report channel: your final text IS the report.\n"
            "Return your findings in ONE message (verifier: verdict + "
            "basis; discovery: the N named facts, sources actually "
            "read). A missing decision, file, or value is surfaced as "
            "a gap, never bridged with a guess. No file writes, no "
            "interim messages."
        )
        READONLY_TAIL_BG_LINE = READONLY_TAIL_SYNC.replace(
            "Report channel: your final text IS the report.",
            "Report channel: SendMessage to the dispatcher — your "
            "final text reaches no one.",
        )

        # (i) tail-less Agent brief, both modes → missing_tail True
        assert missing_tail({"tool_name": "Agent", "tool_input": {
            "prompt": "Do X and report back."}})
        assert missing_tail({"tool_name": "Agent", "tool_input": {
            "name": "sonnet-x",
            "prompt": "Do X and report back."}})

        # (ii) each §2 tail verbatim, correct channel line for the
        # mode used → missing_tail False, tail_mode_mismatch False
        bg_brief = {"tool_name": "Agent", "tool_input": {
            "name": "sonnet-x",
            "prompt": "Do X.\n" + EXECUTION_TAIL_BG}}
        assert not missing_tail(bg_brief)
        assert not tail_mode_mismatch(bg_brief)
        sync_brief = {"tool_name": "Agent", "tool_input": {
            "prompt": "Do X.\n" + READONLY_TAIL_SYNC}}
        assert not missing_tail(sync_brief)
        assert not tail_mode_mismatch(sync_brief)

        # (iii) wrong channel line for the mode → tail_mode_mismatch
        # True, both directions
        bg_with_sync_line = {"tool_name": "Agent", "tool_input": {
            "name": "sonnet-x",
            "prompt": "Do X.\n" + EXECUTION_TAIL_SYNC_LINE}}
        assert not missing_tail(bg_with_sync_line)  # tail present
        assert tail_mode_mismatch(bg_with_sync_line)
        sync_with_bg_line = {"tool_name": "Agent", "tool_input": {
            "prompt": "Do X.\n" + READONLY_TAIL_BG_LINE}}
        assert not missing_tail(sync_with_bg_line)  # tail present
        assert tail_mode_mismatch(sync_with_bg_line)

        # (iv) matched mode+line → False (covered by (ii) above;
        # explicit restatement for the background-default case)
        assert not tail_mode_mismatch(bg_brief)

        # (v) Task tool and parse-garbage payloads → never deny
        assert not missing_tail({"tool_name": "Task", "tool_input": {
            "prompt": "no tail here"}})
        assert not missing_tail({"tool_name": "Agent", "tool_input": {}})
        assert not missing_tail({"tool_name": "Bash", "tool_input": {
            "command": "ls"}})
        assert not missing_tail({})
        assert not tail_mode_mismatch({"tool_name": "Task",
                                        "tool_input": {"prompt": "x"}})
        assert not tail_mode_mismatch({"tool_name": "Agent",
                                        "tool_input": {}})
        assert not tail_mode_mismatch({})

        assert "Blocked" in missing_tail_deny_text()
        assert "Blocked" in tail_mode_mismatch_deny_text(bg_with_sync_line)

        # ── Tail auto-repair (dg-46, guard-rewrite arc item 2) ──────
        # Marker text literal here, never the detection constants
        # (_WRITE_BOUNDARY_MARKERS / _COMMIT_PLAN_MARKERS), same
        # no-shared-parentage convention as every other lane in this
        # suite.
        _WB_MARKER_TEXT = ("Write boundaries: you own src/foo.py only; "
                           "targeted git add, never -A.")
        _CP_MARKER_TEXT = "Commit plan: one commit by pathspec, no bump."

        # (i) _tail_rewrite_decidable: the two marker families, both
        # directions, plus the exemptions its siblings share.
        assert _tail_rewrite_decidable({"tool_name": "Agent", "tool_input": {
            "prompt": "Do X.\n" + _WB_MARKER_TEXT}})
        assert _tail_rewrite_decidable({"tool_name": "Agent", "tool_input": {
            "prompt": "Do X.\n" + _CP_MARKER_TEXT}})
        assert not _tail_rewrite_decidable({"tool_name": "Agent",
                                            "tool_input": {"prompt": "Do X."}})
        # Accepted residue, pinned rather than left to surprise later:
        # a read-only brief that merely DISCUSSES write boundaries
        # false-fires True here — the harmless direction the
        # docstring names.
        assert _tail_rewrite_decidable({"tool_name": "Agent", "tool_input": {
            "prompt": "Verifier. No write boundaries apply to this "
                      "read-only brief."}})

        # (ii) _execution_tail_body / rewrite_tail_input: read the REAL
        # forms.md, channel line filled from `name` presence, and the
        # result is normalized-equal to the shipped tail — proving
        # this reads forms.md rather than carrying a second copy.
        _body = _execution_tail_body()
        assert _body and _TAIL_ANCHOR in _norm(_body), _body
        assert _CHANNEL_LINE_PLACEHOLDER in _body, _body
        _named_decidable = {"tool_name": "Agent", "tool_input": {
            "name": "sonnet-x", "prompt": "Do X.\n" + _WB_MARKER_TEXT}}
        _rewritten = rewrite_tail_input(_named_decidable)
        assert _rewritten is not None
        assert _MAILBOX_CHANNEL_LINE in _rewritten["prompt"]
        assert _BACKGROUND_CHANNEL_LINE not in _rewritten["prompt"]
        assert _norm(_rewritten["prompt"]).endswith(
            _norm(_body.replace(_CHANNEL_LINE_PLACEHOLDER,
                                _MAILBOX_CHANNEL_LINE)))
        assert _rewritten["prompt"].startswith("Do X.\n" + _WB_MARKER_TEXT)
        assert not missing_tail({"tool_name": "Agent",
                                 "tool_input": _rewritten})  # tail now present
        _unnamed_decidable = {"tool_name": "Agent", "tool_input": {
            "subagent_type": "claude-code-guide",
            "prompt": "Do X.\n" + _CP_MARKER_TEXT}}
        _rewritten_bg = rewrite_tail_input(_unnamed_decidable)
        assert _BACKGROUND_CHANNEL_LINE in _rewritten_bg["prompt"]
        assert _MAILBOX_CHANNEL_LINE not in _rewritten_bg["prompt"]
        # other tool_input keys ride along unchanged
        assert _rewritten_bg["subagent_type"] == "claude-code-guide"

        # (iii) never-silent fallback: an unresolvable forms.md path
        # must not manufacture a tail, mirroring agent-model-gate's
        # own never-silent convention for its rewrite lane.
        _real_forms_path = _forms_path
        globals()["_forms_path"] = lambda: "/nonexistent/forms.md"
        assert _execution_tail_body() is None
        assert rewrite_tail_input(_named_decidable) is None
        globals()["_forms_path"] = _real_forms_path
        assert _execution_tail_body() is not None  # restored

        # (iv) END TO END, real subprocess, stdin JSON -> stdout JSON —
        # the same boundary agent-model-gate.py --test exercises for
        # its own rewrite lane, and the only way to prove main()'s
        # actual WIRING (mode consult, fire_log, updatedInput shape)
        # rather than its pieces in isolation.
        #
        # RED-FIRST baseline (recorded this session, not re-run here
        # since the pre-dg-46 source no longer exists in the working
        # tree): the identical payload below, run against the parent
        # commit's brief-reminder.py as a subprocess, exited 2 with a
        # "Blocked: dispatch brief without the §2 tail block" deny —
        # no updatedInput, no rewrite. This assertion block is the
        # green side of that pair.
        import subprocess as _sp2

        def _run_brief_hook(payload, env_extra=None):
            env = dict(os.environ)
            env["CLAUDE_DISPATCH_GUARDS_CONFIG"] = "/nonexistent"
            env["CLAUDE_DISPATCH_GUARDS_FIRELOG"] = os.path.join(
                tempfile.mkdtemp(), "fires.jsonl")
            if env_extra:
                env.update(env_extra)
            proc = _sp2.run(
                [sys.executable, os.path.realpath(__file__)],
                input=json.dumps(payload), capture_output=True, text=True,
                env=env)
            fires = []
            if os.path.isfile(env["CLAUDE_DISPATCH_GUARDS_FIRELOG"]):
                fires = [json.loads(_l) for _l in
                        open(env["CLAUDE_DISPATCH_GUARDS_FIRELOG"],
                             encoding="utf-8")]
            return proc, fires

        _e2e_decidable = {"tool_name": "Agent", "tool_input": {
            "name": "sonnet-x",
            "prompt": ("Do X.\n" + _WB_MARKER_TEXT + "\n"
                      "Report channel: SendMessage to the dispatcher "
                      "— your final text reaches no one.")}}
        _proc_a, _fires_a = _run_brief_hook(_e2e_decidable)
        assert _proc_a.returncode == 0, (_proc_a.returncode, _proc_a.stderr)
        _out_a = json.loads(_proc_a.stdout)
        _hso_a = _out_a["hookSpecificOutput"]
        assert "updatedInput" in _hso_a, _hso_a
        assert "permissionDecision" not in _hso_a, _hso_a  # wave0 b2/b3 shape
        assert _MAILBOX_CHANNEL_LINE in _hso_a["updatedInput"]["prompt"]
        assert any(f["mode"] == "rewrite" and f["guard"] == "brief-reminder"
                  for f in _fires_a), _fires_a

        # (iv-b) AMBIGUOUS class, default config -> still a hard DENY,
        # unchanged from pre-dg-46 behavior (never-staged record
        # carried forward).
        _e2e_ambiguous = {"tool_name": "Agent", "tool_input": {
            "name": "sonnet-x",
            "prompt": ("Do X and report back.\nReport channel: "
                      "SendMessage to the dispatcher — your final "
                      "text reaches no one.")}}
        _proc_b, _fires_b = _run_brief_hook(_e2e_ambiguous)
        assert _proc_b.returncode == 0
        _hso_b = json.loads(_proc_b.stdout)["hookSpecificOutput"]
        assert _hso_b.get("permissionDecision") == "deny", _hso_b
        assert any(f["mode"] == "deny" and f["guard"] == "brief-reminder"
                  for f in _fires_b), _fires_b

        # (iv-c) guard_modes["brief-reminder"] = "warn": the AMBIGUOUS
        # class softens to a warning-and-pass; the DECIDABLE class is
        # UNAFFECTED — it still rewrites, proving "repair is the
        # action, not a punishment grade".
        with tempfile.NamedTemporaryFile("w", suffix=".json",
                                         delete=False) as _wf:
            _wf.write(json.dumps({"guard_modes": {"brief-reminder": "warn"}}))
            _warn_cfg = _wf.name
        _proc_c, _fires_c = _run_brief_hook(
            _e2e_ambiguous, {"CLAUDE_DISPATCH_GUARDS_CONFIG": _warn_cfg})
        assert _proc_c.returncode == 0
        _hso_c = json.loads(_proc_c.stdout)["hookSpecificOutput"]
        assert "permissionDecision" not in _hso_c, _hso_c
        assert "additionalContext" in _hso_c, _hso_c
        assert any(f["mode"] == "warn" and f["guard"] == "brief-reminder"
                  for f in _fires_c), _fires_c
        _proc_d, _fires_d = _run_brief_hook(
            _e2e_decidable, {"CLAUDE_DISPATCH_GUARDS_CONFIG": _warn_cfg})
        assert _proc_d.returncode == 0
        _hso_d = json.loads(_proc_d.stdout)["hookSpecificOutput"]
        assert "updatedInput" in _hso_d, _hso_d   # still rewrites under warn
        assert any(f["mode"] == "rewrite" for f in _fires_d), _fires_d

        # (iv-d) guard_modes["brief-reminder"] = "off": the WHOLE lane
        # goes silent for BOTH classes — no rewrite, no deny, no warn.
        with tempfile.NamedTemporaryFile("w", suffix=".json",
                                         delete=False) as _of:
            _of.write(json.dumps({"guard_modes": {"brief-reminder": "off"}}))
            _off_cfg = _of.name
        _proc_e, _fires_e = _run_brief_hook(
            _e2e_decidable, {"CLAUDE_DISPATCH_GUARDS_CONFIG": _off_cfg})
        assert _proc_e.returncode == 0
        _hso_e = json.loads(_proc_e.stdout)["hookSpecificOutput"]
        assert "updatedInput" not in _hso_e, _hso_e
        assert "permissionDecision" not in _hso_e, _hso_e
        assert not any(f["mode"] in ("rewrite", "deny", "warn")
                      and f["guard"] == "brief-reminder" for f in _fires_e), \
            _fires_e
        _proc_f, _fires_f = _run_brief_hook(
            _e2e_ambiguous, {"CLAUDE_DISPATCH_GUARDS_CONFIG": _off_cfg})
        assert _proc_f.returncode == 0
        _hso_f = json.loads(_proc_f.stdout)["hookSpecificOutput"]
        assert "updatedInput" not in _hso_f, _hso_f
        assert "permissionDecision" not in _hso_f, _hso_f

        # ── Section lane (missing_sections) ────────────────────────
        # Section markers named in the dispatch skill §1 ("Grounding
        # basis as a mandatory section." / "Write boundaries.") —
        # literals here, never the detection constants, so the test
        # doesn't share parentage with what it's meant to catch.
        GROUNDING_SECTION = (
            "Grounding basis: read spec.md and the current module "
            "before building.")
        WRITE_BOUNDARIES_SECTION = (
            "Write boundaries: you own src/foo.py only; targeted git "
            "add, never -A.")

        # (i) execution-tail brief carrying both markers → False
        both_sections_brief = {"tool_name": "Agent", "tool_input": {
            "prompt": "Do X.\n" + GROUNDING_SECTION + "\n"
                      + WRITE_BOUNDARIES_SECTION + "\n"
                      + EXECUTION_TAIL_BG}}
        assert not missing_sections(both_sections_brief)

        # (ii) execution-tail brief missing "grounding" → True
        missing_grounding_brief = {"tool_name": "Agent", "tool_input": {
            "prompt": "Do X.\n" + WRITE_BOUNDARIES_SECTION + "\n"
                      + EXECUTION_TAIL_BG}}
        assert missing_sections(missing_grounding_brief)

        # (iii) execution-tail brief missing only "write boundar" → True
        missing_write_boundaries_brief = {
            "tool_name": "Agent", "tool_input": {
                "prompt": "Do X.\n" + GROUNDING_SECTION + "\n"
                          + EXECUTION_TAIL_BG}}
        assert missing_sections(missing_write_boundaries_brief)

        # (iii-b) deutsche Abschnitts-Etiketten (DEV-RUNBOOK-Formular:
        # GROUNDING-BASIS / SCHREIB-GRENZEN) → False — Literale, nie
        # die Erkennungs-Konstanten (keine geteilte Elternschaft)
        german_sections_brief = {"tool_name": "Agent", "tool_input": {
            "prompt": "Baue X.\n"
                      "GROUNDING-BASIS: lies spec.md vor dem Bau.\n"
                      "SCHREIB-GRENZEN: nur src/foo.py; gezieltes "
                      "git add, nie -A.\n" + EXECUTION_TAIL_BG}}
        assert not missing_sections(german_sections_brief)

        # (iv) READ-ONLY-tail brief with neither marker → False (exempt:
        # no execution-tail anchor present)
        readonly_neither_brief = {"tool_name": "Agent", "tool_input": {
            "prompt": "Do X.\n" + READONLY_TAIL_SYNC,
            "run_in_background": False}}
        assert not missing_sections(readonly_neither_brief)

        # (v) Task tool and parse-garbage payloads → never deny
        assert not missing_sections({"tool_name": "Task", "tool_input": {
            "prompt": "Do X.\n" + WRITE_BOUNDARIES_SECTION + "\n"
                      + EXECUTION_TAIL_BG}})
        assert not missing_sections({"tool_name": "Agent",
                                      "tool_input": {}})
        assert not missing_sections({"tool_name": "Bash", "tool_input": {
            "command": "ls"}})
        assert not missing_sections({})

        assert "Blocked" in missing_sections_deny_text(
            missing_grounding_brief)

        # ── verifier brief citing forms.md → EXEMPT (false fire) ───
        # forms.md carries BOTH tails verbatim and this guard reads
        # every .md the prompt names, so a verifier brief that merely
        # CITES the forms file inherited the execution anchor and was
        # denied for lacking §1 sections it is exempt from. Observed
        # live on a legitimate verifier dispatch. Expectation from §1
        # ("verifier dispatches stay exempt from the rich §1 brief
        # form ... artifact + question + that block"), not from code.
        _READONLY_TAIL_REAL = (
            "Report channel: SendMessage to the dispatcher — your "
            "final text reaches no one.\n"
            "Return your findings in ONE message where they fit "
            "(verifier: verdict + basis; discovery: the N named "
            "facts, sources actually read); past the message-size "
            "gate, labeled parts (1/N) — never a report file. A "
            "missing decision, file, or value is surfaced as a gap, "
            "never bridged with a guess. No repo writes, no report "
            "files, no interim messages; transient probe scratch in "
            "your OWN scratchpad is permitted and is not a report "
            "file.")
        # The citation is the REAL forms.md by ABSOLUTE path: the
        # fixture must actually read a file carrying the execution
        # anchor, or it tests nothing. A relative path here silently
        # resolved to no file (no cwd in the payload) and the case
        # passed against the unfixed code — caught by running it
        # red-first.
        _vet = {"tool_name": "Agent", "tool_input": {
            "name": "opus-vet",
            "prompt": ("Verifier dispatch. ARTIFACT: the diff. "
                       "QUESTION: is " + _forms_path() + " §2 "
                       "consistent with the hook?\n"
                       + _READONLY_TAIL_REAL)}}
        assert _SECTIONS_ANCHOR in _brief_text(_vet), (
            "fixture reads no execution-anchor file — it would pass "
            "regardless of the exemption")
        assert _tail_kind(_vet) == "readonly", _tail_kind(_vet)
        assert not missing_sections(_vet)
        assert not tail_mode_mismatch(_vet)
        assert not missing_channel(_vet)
        assert not missing_tail(_vet)
        # the lane still bites a real execution brief citing forms.md
        _exec_bad = {"tool_name": "Agent", "tool_input": {
            "name": "sonnet-x",
            "prompt": ("Do X per " + _forms_path() + ".\n"
                       + EXECUTION_TAIL_BG)}}
        assert _tail_kind(_exec_bad) == "execution"
        assert missing_sections(_exec_bad)
        # missing_commit_plan shares the exemption: it read
        # referenced-files-first after its twin was repaired, so it
        # still false-fired on the very brief shape the repair
        # exempted — a staged warn lane firing on legitimate work.
        assert not missing_commit_plan(_vet)
        assert missing_commit_plan(_exec_bad)
        # Each fire()-routed lane's SHIPPED MODE is a claim its
        # docstring makes about itself, and repo CLAUDE.md makes a
        # rule of it. Nothing asserted it once: flipping a default
        # left every net green — a mechanism's own words with no
        # predicate behind them.
        #
        # The former spelling was a bare `'default_mode="warn"' in
        # _main_src`, which stopped discriminating the day a SECOND
        # fire() lane landed: with one lane on "deny" and one on
        # "warn", a substring test over the whole function is
        # satisfied by either lane carrying either value — the
        # match-over-rendered-text shape. So the modes are read per
        # CALL SITE out of the parsed function, keyed by the text
        # helper each call passes, and the map is derived from the
        # running parser rather than restated here.
        import ast as _ast
        import inspect as _inspect
        import textwrap as _textwrap
        _main_src = _inspect.getsource(main)
        _fire_modes = {}
        for _node in _ast.walk(_ast.parse(_textwrap.dedent(_main_src))):
            if not (isinstance(_node, _ast.Call)
                    and isinstance(_node.func, _ast.Name)
                    and _node.func.id == "fire"):
                continue
            _text_fn = None
            if (_node.args and isinstance(_node.args[0], _ast.Call)
                    and isinstance(_node.args[0].func, _ast.Name)):
                _text_fn = _node.args[0].func.id
            _mode = None
            for _kw in _node.keywords:
                if _kw.arg == "default_mode":
                    _mode = getattr(_kw.value, "value", None)
            _fire_modes[_text_fn] = _mode
        # All THREE fire()-routed lanes present (missing_tail joined
        # 2026-09-15, dg-46), so a DELETED call site fails here too —
        # a mode map missing a key reads exactly like a lane set to
        # None otherwise.
        assert len(_fire_modes) == 3, _fire_modes
        assert _fire_modes.get("missing_commit_plan_deny_text") == "deny", (
            "the commit-plan lane ships DENY since 2026-09-15 "
            "(df-238 promotion; the evidence is in its docstring)",
            _fire_modes)
        assert _fire_modes.get("missing_devbook_pin_warn_text") == "warn", (
            "the devbook-pin lane must ship WARN (repo CLAUDE.md: a "
            "new lane earns deny through the fire-rate review, never "
            "by assertion)", _fire_modes)
        assert _fire_modes.get("missing_tail_deny_text") == "deny", (
            "the missing_tail AMBIGUOUS-class exit ships DENY (dg-46: "
            "a verb conversion carries the lane's existing never-"
            "staged record forward, so a fresh/unconfigured site sees "
            "exactly the pre-conversion behavior)", _fire_modes)

        # ── Commit-plan lane (missing_commit_plan), STAGED WARN ────
        # Slot named in the dispatch skill §1 skeleton ("## Commit
        # plan") — literal here, never the detection constant, so the
        # test doesn't share parentage with what it's meant to catch.
        COMMIT_PLAN_SECTION = (
            "Commit plan: the repo's payload-version gate compares "
            "against the release state, so the bump commit lands "
            "first; then the two payload commits by pathspec.")

        # (i) the PAIR that grades this lane: one brief carrying the
        # slot, one not. They must DIFFER — a pair both readings
        # satisfy grades nothing. Red-proven against the pre-change
        # module (a copy of the whole hooks dir at the parent commit),
        # where the predicate did not exist at all.
        commit_plan_absent_brief = {"tool_name": "Agent", "tool_input": {
            "prompt": "Do X.\n" + GROUNDING_SECTION + "\n"
                      + WRITE_BOUNDARIES_SECTION + "\n"
                      + EXECUTION_TAIL_BG}}
        commit_plan_present_brief = {"tool_name": "Agent", "tool_input": {
            "prompt": "Do X.\n" + GROUNDING_SECTION + "\n"
                      + WRITE_BOUNDARIES_SECTION + "\n"
                      + COMMIT_PLAN_SECTION + "\n"
                      + EXECUTION_TAIL_BG}}
        assert missing_commit_plan(commit_plan_absent_brief)
        assert not missing_commit_plan(commit_plan_present_brief)
        assert (missing_commit_plan(commit_plan_absent_brief)
                != missing_commit_plan(commit_plan_present_brief))

        # (ii) the pasted skeleton's own hard wrap ("Commit\nplan")
        # still counts — the normalization lane, applied here.
        assert not missing_commit_plan({"tool_name": "Agent", "tool_input": {
            "prompt": "Do X.\nGrounding basis: read spec.md first.\n"
                      "Write boundaries: src/foo.py only.\n"
                      "## Commit\nplan: bump first, then the payloads.\n"
                      + EXECUTION_TAIL_BG}})

        # (iii) a real dispatcher brief states the plan as numbered
        # prose, not as a `##` heading — the marker family is
        # label-shaped, not heading-anchored, so that form counts too.
        assert not missing_commit_plan({"tool_name": "Agent", "tool_input": {
            "prompt": "Do X.\n" + GROUNDING_SECTION + "\n"
                      + WRITE_BOUNDARIES_SECTION + "\n"
                      "1. COMMIT PLAN, ordered against this repo's "
                      "payload-version gate — THREE commits.\n"
                      + EXECUTION_TAIL_BG}})

        # (iv) scope negatives: READ-ONLY tail (no execution anchor),
        # Task tool, parse-garbage → never fires
        assert not missing_commit_plan(readonly_neither_brief)
        assert not missing_commit_plan({"tool_name": "Task", "tool_input": {
            "prompt": "Do X.\n" + EXECUTION_TAIL_BG}})
        assert not missing_commit_plan({"tool_name": "Agent",
                                        "tool_input": {}})
        assert not missing_commit_plan({"tool_name": "Bash", "tool_input": {
            "command": "ls"}})
        assert not missing_commit_plan({})

        # (v) the lane's own docstring, wrapped in a real execution
        # brief: in-domain adversarial text by the same author. This
        # predicate fires on ABSENCE, so a self-matching docstring can
        # only prove the silent direction — it bounds the true
        # negative, it is NOT a false-fire proof for this lane.
        assert not missing_commit_plan({"tool_name": "Agent", "tool_input": {
            "prompt": "Do X.\n" + (missing_commit_plan.__doc__ or "")
                      + "\n" + EXECUTION_TAIL_BG}})

        # A promoted lane's text is a DENY text, and this file's deny
        # texts all announce the block and name a repair that clears
        # on retry — the convention deny_text()'s own docstring states.
        assert "commit-plan section" in missing_commit_plan_deny_text()
        assert "Blocked" in missing_commit_plan_deny_text()
        assert "retry" in missing_commit_plan_deny_text()

        # ── Whitespace-normalization lane (false-fire 2026-07-30) ──
        # The §2 tails carry hard line wraps in references/forms.md
        # itself; a verbatim paste therefore wraps mid-anchor ("never
        # bridged\nwith a guess"). Replayed live deny: hookinput-probe3,
        # session 78b3e7fe (guard 0.1.7 went red on a conforming brief).
        WRAPPED_READONLY_TAIL = (
            "Report channel: your final text IS the report.\n"
            "Return your findings in ONE message (verifier: verdict + "
            "basis;\ndiscovery: the N named facts, sources actually "
            "read). A missing\ndecision, file, or value is surfaced as "
            "a gap, never bridged\nwith a guess. No file writes, no "
            "interim messages."
        )
        wrapped_sync_brief = {"tool_name": "Agent", "tool_input": {
            "prompt": "Do X.\n" + WRAPPED_READONLY_TAIL,
            "run_in_background": False}}
        assert not missing_tail(wrapped_sync_brief)
        assert not tail_mode_mismatch(wrapped_sync_brief)
        # Channel line wrapped mid-marker ("Report\nchannel") still
        # counts. TWO things make this bite, both learned by it not
        # biting: the payload needs a `name`, or missing_channel exits
        # at the mailbox_lane guard before any marker is matched; and
        # the wrapped marker must be the ONLY one present, or an
        # unwrapped "SendMessage" satisfies the check whatever
        # normalization does. As written before both, it passed with
        # the whole channel sentence deleted and under a mutant that
        # replaced _norm with plain .lower().
        _wrapped_only = {"tool_name": "Agent", "tool_input": {
            "name": "sonnet-x",
            "prompt": "Do X. Report\nchannel: deliver the report by "
                      "mailbox."}}
        assert not missing_channel(_wrapped_only)
        # positive control: the same brief with the marker text gone
        # must DENY, or the assert above is satisfied by something
        # other than the wrap surviving normalization.
        assert missing_channel({"tool_name": "Agent", "tool_input": {
            "name": "sonnet-x",
            "prompt": "Do X. Deliver the report by mailbox."}})
        # Section markers wrapped ("write\nboundaries") still count
        wrapped_sections_brief = {"tool_name": "Agent", "tool_input": {
            "prompt": "Do X.\nGrounding basis: read spec.md first.\n"
                      "Write\nboundaries: you own src/foo.py only.\n"
                      + EXECUTION_TAIL_BG}}
        assert not missing_sections(wrapped_sections_brief)

        # ── File-carried briefs (forms.md §2: inline tail required ──
        # when no file brief) — the wave-2 false-positive class:
        # four dispatches pointing at a tail-bearing brief file were
        # denied as tail-less (2026-07-30, sessions 633915a8/78b3e7fe).
        import tempfile as _tf
        _tmpdir = _tf.mkdtemp()
        _brief_with_tail = os.path.join(_tmpdir, "brief-with-tail.md")
        with open(_brief_with_tail, "w") as f:
            f.write("# Brief\nGrounding basis: read spec.md first.\n"
                    "Write boundaries: you own src/foo.py only.\n"
                    + EXECUTION_TAIL_BG)
        _brief_no_tail = os.path.join(_tmpdir, "brief-no-tail.md")
        with open(_brief_no_tail, "w") as f:
            f.write("# Brief\nDo the thing, no tail here.\n")

        _file_prompt = ("Execute the brief at " + _brief_with_tail
                        + " — read it top to bottom first.\n"
                        "Report channel: SendMessage to the dispatcher "
                        "— your final text reaches no one.")
        file_brief = {"tool_name": "Agent",
                      "tool_input": {"prompt": _file_prompt}}
        # (i) tail + sections live in the referenced file → allow
        assert not missing_tail(file_brief)
        assert not missing_sections(file_brief)
        # (ii) referenced file lacks the tail → still deny
        assert missing_tail({"tool_name": "Agent", "tool_input": {
            "prompt": "Execute the brief at " + _brief_no_tail
                      + "\nReport channel: SendMessage to the "
                      "dispatcher — your final text reaches no one."}})
        # (iii) nonexistent file contributes nothing → deny
        assert missing_tail({"tool_name": "Agent", "tool_input": {
            "prompt": "Execute " + os.path.join(_tmpdir, "gone.md")
                      + "\nReport channel: SendMessage to the "
                      "dispatcher — your final text reaches no one."}})
        # (iv) relative path resolves against hook-input cwd
        assert not missing_tail({"tool_name": "Agent",
                                 "cwd": _tmpdir,
                                 "tool_input": {"prompt":
            "Execute the brief at docs/../brief-with-tail.md\n"
            "Report channel: SendMessage to the dispatcher — your "
            "final text reaches no one."}})
        # (v) execution tail in file but sections missing → sections
        # lane still fires on the combined brief
        _brief_tail_only = os.path.join(_tmpdir, "brief-tail-only.md")
        with open(_brief_tail_only, "w") as f:
            f.write("# Brief\n" + EXECUTION_TAIL_BG)
        assert missing_sections({"tool_name": "Agent", "tool_input": {
            "prompt": "Execute the brief at " + _brief_tail_only
                      + "\nReport channel: SendMessage to the "
                      "dispatcher — your final text reaches no one."}})

        # ── Brief paths with spaces and non-ASCII letters ───────────
        # Expectation derived from the rule, never from this hook's
        # behavior — the §2 forms (references/forms.md): "The tail reaches the
        # executing agent pasted in the DISPATCH PROMPT or inside a
        # brief FILE the prompt names — inline required only when no
        # file brief exists." A prompt naming a tail-bearing brief file
        # is therefore CONFORMING whatever characters its path carries,
        # so the tail and section lanes must stay silent on it.
        _umlaut_dir = os.path.join(_tmpdir, "Planungsbüro-Test")
        os.makedirs(_umlaut_dir, exist_ok=True)
        _umlaut_brief = os.path.join(_umlaut_dir, "brief.md")
        _spaced_dir = os.path.join(_tmpdir, "Planungsbüro Projekte")
        os.makedirs(_spaced_dir, exist_ok=True)
        _spaced_brief = os.path.join(_spaced_dir, "mein brief.md")
        for _p in (_umlaut_brief, _spaced_brief):
            with open(_p, "w") as f:
                f.write("# Brief\nGrounding basis: read spec.md first.\n"
                        "Write boundaries: you own src/foo.py only.\n"
                        + EXECUTION_TAIL_BG)
        _channel = ("\nReport channel: SendMessage to the dispatcher "
                    "— your final text reaches no one.")

        # (i) bare path through an umlaut directory
        umlaut_brief_call = {"tool_name": "Agent", "tool_input": {
            "prompt": "Execute the brief at " + _umlaut_brief + _channel}}
        assert not missing_tail(umlaut_brief_call)
        assert not missing_sections(umlaut_brief_call)

        # (ii) quoted path carrying both a space and an umlaut, either
        # quote style — a path with a space has no unquoted form
        for _q in ('"', "'"):
            spaced_brief_call = {"tool_name": "Agent", "tool_input": {
                "prompt": "Execute the brief at " + _q + _spaced_brief
                          + _q + _channel}}
            assert not missing_tail(spaced_brief_call)
            assert not missing_sections(spaced_brief_call)

        # (ii-b) the sections lane reads the same file: a tail-only
        # brief under an umlaut path must still be caught for its
        # missing sections. Asserted in this direction because the
        # conforming case above passes for either reason — an unread
        # file leaves the brief without the execution-tail anchor,
        # which exempts the lane instead of clearing it.
        _umlaut_tail_only = os.path.join(_umlaut_dir, "nur-tail.md")
        with open(_umlaut_tail_only, "w") as f:
            f.write("# Brief\n" + EXECUTION_TAIL_BG)
        assert missing_sections({"tool_name": "Agent", "tool_input": {
            "prompt": "Execute " + _umlaut_tail_only + _channel}})

        # (iii) the extracted path is the WHOLE path: a class that
        # breaks at the first non-ASCII letter does not miss the
        # reference, it returns a different, shorter one that resolves
        # elsewhere — the failure the lanes above cannot see.
        assert _md_paths("siehe " + _umlaut_brief) == [_umlaut_brief]
        assert _md_paths('siehe "' + _spaced_brief + '"') == [_spaced_brief]
        assert _md_paths("siehe '" + _spaced_brief + "'") == [_spaced_brief]
        # (iv) a bare filename is not a path reference (unchanged):
        # the token must carry a separator or start at ~/ or /
        assert _md_paths("do X, see brief.md") == []
        assert _md_paths("read ~/notes/brief.md") == ["~/notes/brief.md"]
        # (v) a named-but-absent umlaut file still contributes nothing
        assert missing_tail({"tool_name": "Agent", "tool_input": {
            "prompt": "Execute " + os.path.join(_umlaut_dir, "weg.md")
                      + _channel}})

        # ── Deny payload shape (misattribution class 2026-07-30) ────
        # Both audiences must get the reason: permissionDecisionReason
        # reaches the model, systemMessage the user; source tag makes a
        # guard fire self-identifying. Live defect: fresh-session deny
        # (session 3741ed60) carried systemMessage only — the model saw
        # the harness's bare denial line and misattributed it to CC.
        from _dispatch_common import _deny_payload
        dp = _deny_payload("Blocked: test reason", source=_SOURCE)
        hso = dp["hookSpecificOutput"]
        assert hso["permissionDecision"] == "deny"
        assert hso["permissionDecisionReason"].startswith(
            "[dispatch-guards/brief-reminder] ")
        assert "Blocked: test reason" in hso["permissionDecisionReason"]
        assert dp["systemMessage"] == hso["permissionDecisionReason"]

        # ── Worktree-base advisory lane ────────────────────────────
        # Expectation derived from the observed incidents, not from
        # this hook: a harness worktree cut from an older snapshot
        # makes the executor's base check fail correctly, and the
        # brief is where the stated base + ff-recovery must live.
        # (i) fires on the isolation=worktree Agent call shape
        wt_call = {"tool_name": "Agent", "tool_input": {
            "prompt": "Do X.", "isolation": "worktree"}}
        assert worktree_advisory(wt_call) is not None
        assert "base commit" in worktree_advisory(wt_call)
        assert "ff-only" in worktree_advisory(wt_call)
        # all three classes named (the dispatcher's ruling: stale
        # session-repo cut, sibling-repo provisioning, sibling-repo
        # under isolation)
        assert "SESSION-repo" in worktree_advisory_text()
        assert "SIBLING repo" in worktree_advisory_text()
        assert "WITHOUT isolation" in worktree_advisory_text()
        # (ii) silent on every other call shape
        assert worktree_advisory({"tool_name": "Agent", "tool_input": {
            "prompt": "Do X."}}) is None
        assert worktree_advisory({"tool_name": "Agent", "tool_input": {
            "prompt": "Do X.", "isolation": "remote"}}) is None
        assert worktree_advisory({"tool_name": "Task", "tool_input": {
            "isolation": "worktree"}}) is None
        assert worktree_advisory({"tool_name": "Bash", "tool_input": {
            "command": "git worktree add /tmp/wt"}}) is None
        assert worktree_advisory({"tool_name": "Agent",
                                  "tool_input": {}}) is None
        assert worktree_advisory({}) is None
        # (iii) the advisory never blocks and never displaces the
        # existing reminder — both lanes answer on the same call
        assert check(wt_call) is not None

        # ── Tier-readiness register consult (register_lines) ───────
        # BACKLOG 2026-08-11 entry: "the §6 register consult has no
        # mechanism at the moment it is owed". Env override mirrors
        # _dispatch_common's fire-log/config idiom so this suite (and
        # the bench) never reads the operator's real
        # ~/.claude/readiness.json. Reset after each case so a bite
        # left pointing at a fixture cannot leak into the next.
        _reg_tmpdir = _tf.mkdtemp()
        _agent_call = {"tool_name": "Agent", "tool_input": {
            "prompt": "Do X."}}

        def _with_register(path, call=None):
            # `call or _agent_call` would treat an EMPTY dict call
            # (a real scope-negative case below) as falsy and swap in
            # the default payload — the sentinel must be identity,
            # not truthiness.
            if call is None:
                call = _agent_call
            os.environ["CLAUDE_DISPATCH_GUARDS_REGISTER"] = path
            try:
                return register_lines(call)
            finally:
                del os.environ["CLAUDE_DISPATCH_GUARDS_REGISTER"]

        # Fixture shape is the REAL global register's own shape
        # (`dotfiles/claude/readiness.json`, read directly to ground
        # _register_entries — no schema fixture exists anywhere in
        # THIS repo or in §6's prose): a top-level object wrapping the
        # class list under `prozesse`, each entry carrying its own
        # `id` — never a bare dict keyed by class id, which was this
        # suite's first (unverified) fixture shape and which the real
        # file's own metadata keys (`_hinweis`, `schema_version`,
        # `lineup_stand`) would have been misread as class ids under.
        def _prozesse(*entries):
            return {"schema_version": 2, "prozesse": list(entries)}

        # (i) THE red-first case: a fixture register carrying two
        # classes must show both rows. Red-proven against the
        # pre-change module (a copy of the whole hooks dir at the
        # parent commit, run as a live subprocess against this exact
        # payload+env): it showed NEITHER row, because the predicate
        # did not exist at all — this hook read no register.
        _two_class_reg = os.path.join(_reg_tmpdir, "readiness.json")
        with open(_two_class_reg, "w") as f:
            json.dump(_prozesse(
                {"id": "enumeration-fixed-schema",
                 "tier": "haiku", "status": "ready",
                 "klasse": "fixed-schema enumeration over a "
                           "closed value set"},
                {"id": "guard-checker-bau",
                 "tier": "sonnet", "status": "eval-open",
                 "klasse": "guard/checker build against the "
                           "fire-log corpus"},
            ), f)
        _two_rows = _with_register(_two_class_reg)
        assert len(_two_rows) == 3, _two_rows  # header + 2 class rows
        assert _two_rows[0] == _REGISTER_HEADER_LINE, _two_rows
        assert any("enumeration-fixed-schema" in r for r in _two_rows)
        assert any("haiku" in r for r in _two_rows)
        assert any("ready" in r for r in _two_rows)
        assert any("guard-checker-bau" in r for r in _two_rows)
        assert any("sonnet" in r for r in _two_rows)
        assert any("eval-open" in r for r in _two_rows)

        # (ii) register path pointing at a nonexistent file -> the
        # explicit absence line, not an empty block.
        _gone_reg = os.path.join(_reg_tmpdir, "gone.json")
        _absent = _with_register(_gone_reg)
        assert len(_absent) == 1, _absent
        assert "no readiness register was readable" in _absent[0]
        assert _gone_reg in _absent[0]

        # (iii) malformed JSON at a real path -> same absence line
        # class as (ii), never a crash and never an empty block.
        _bad_reg = os.path.join(_reg_tmpdir, "bad.json")
        with open(_bad_reg, "w") as f:
            f.write("{not valid json")
        _malformed = _with_register(_bad_reg)
        assert len(_malformed) == 1, _malformed
        assert "no readiness register was readable" in _malformed[0]

        # (iv) a JSON file whose top level is not an object (a list,
        # a bare string) is the same could-not-verify as malformed.
        _list_reg = os.path.join(_reg_tmpdir, "list.json")
        with open(_list_reg, "w") as f:
            json.dump(["not", "a", "dict"], f)
        _list_result = _with_register(_list_reg)
        assert len(_list_result) == 1, _list_result
        assert "no readiness register was readable" in _list_result[0]

        # (iv-b) THE regression this fix closes: a top-level OBJECT
        # (so isinstance-dict passes) whose `prozesse` key is absent
        # or not a list — exactly the real global register's own
        # metadata-only keys (_hinweis, schema_version, lineup_stand)
        # under the FIRST, unverified fixture shape, which read those
        # keys as class ids. Must be the absence line, never garbage
        # rows built from wrapper metadata.
        _no_prozesse_reg = os.path.join(_reg_tmpdir, "no-prozesse.json")
        with open(_no_prozesse_reg, "w") as f:
            json.dump({"_hinweis": "metadata, not a class",
                      "schema_version": 2, "lineup_stand": "2026-07-31"}, f)
        _no_prozesse = _with_register(_no_prozesse_reg)
        assert len(_no_prozesse) == 1, _no_prozesse
        assert "no readiness register was readable" in _no_prozesse[0]
        assert "_hinweis" not in _no_prozesse[0]
        assert "schema_version" not in _no_prozesse[0]
        _prozesse_not_list_reg = os.path.join(
            _reg_tmpdir, "prozesse-not-list.json")
        with open(_prozesse_not_list_reg, "w") as f:
            json.dump({"prozesse": "not-a-list"}, f)
        assert "no readiness register was readable" in _with_register(
            _prozesse_not_list_reg)[0]

        # (v) a valid but EMPTY register (zero certified classes) is
        # a different answer from could-not-verify — it must not
        # collapse to silence either, or an empty register reads
        # exactly like an absent one.
        _empty_reg = os.path.join(_reg_tmpdir, "empty.json")
        with open(_empty_reg, "w") as f:
            json.dump(_prozesse(), f)
        _empty_result = _with_register(_empty_reg)
        assert len(_empty_result) == 1, _empty_result
        assert "zero certified classes" in _empty_result[0]
        assert "no readiness register was readable" not in _empty_result[0]

        # (vi) a malformed ENTRY (not itself a dict, inside `prozesse`)
        # degrades that row to '?' fields rather than raising or
        # blanking the whole register.
        _bad_entry_reg = os.path.join(_reg_tmpdir, "bad-entry.json")
        with open(_bad_entry_reg, "w") as f:
            json.dump(_prozesse(
                "not-a-dict",
                {"id": "fine-class", "tier": "opus", "status": "ready"},
            ), f)
        _mixed = _with_register(_bad_entry_reg)
        assert len(_mixed) == 3, _mixed  # header + 2 rows
        assert _mixed[0] == _REGISTER_HEADER_LINE, _mixed
        assert any(r.startswith("? \xb7 ? \xb7 ? \xb7") for r in _mixed), \
            _mixed
        assert any(r.startswith("fine-class \xb7 opus \xb7 ready \xb7")
                  for r in _mixed), _mixed

        # (vi-b) an entry missing `id` (but a real dict) also degrades
        # to '?' for the id column alone, not a crash.
        _no_id_reg = os.path.join(_reg_tmpdir, "no-id.json")
        with open(_no_id_reg, "w") as f:
            json.dump(_prozesse(
                {"tier": "opus", "status": "ready", "klasse": "no id"}), f)
        _no_id = _with_register(_no_id_reg)
        assert len(_no_id) == 2  # header + 1 row
        assert _no_id[0] == _REGISTER_HEADER_LINE, _no_id
        assert _no_id[1].startswith("? \xb7 opus \xb7 ready \xb7"), _no_id

        # (vii) row truncation: a long klasse one-liner is cut, the
        # whole row stays <= _REGISTER_ROW_MAX, and id/tier/status
        # survive intact.
        _long_reg = os.path.join(_reg_tmpdir, "long.json")
        with open(_long_reg, "w") as f:
            json.dump(_prozesse({
                "id": "a-class", "tier": "sonnet", "status": "ready",
                "klasse": "x" * 300}), f)
        _long_rows = _with_register(_long_reg)
        assert len(_long_rows) == 2  # header + 1 row
        assert _long_rows[0] == _REGISTER_HEADER_LINE, _long_rows
        assert len(_long_rows[1]) <= _REGISTER_ROW_MAX, len(_long_rows[1])
        assert _long_rows[1].startswith("a-class \xb7 sonnet \xb7 ready \xb7")

        # (viii) scope: register_lines is silent on non-Agent/Task
        # tools, and on parse-garbage payloads, whatever the register
        # holds — it must never be the ONLY thing that fires.
        assert _with_register(_two_class_reg,
                              {"tool_name": "Bash",
                               "tool_input": {"command": "ls"}}) == []
        assert _with_register(_two_class_reg, {}) == []
        # Task tool is in scope, same as check()'s own gating
        assert len(_with_register(_two_class_reg,
                                  {"tool_name": "Task",
                                   "tool_input": {}})) == 3  # header + 2

        # (ix) the env override is what points at a fixture at all —
        # without it, the default path is the operator's real file,
        # never touched by this suite (isolation, mirrors
        # _dispatch_common's fire-log/config idiom).
        assert "CLAUDE_DISPATCH_GUARDS_REGISTER" not in os.environ
        assert _register_path() == os.path.expanduser(
            "~/.claude/readiness.json")

        # (x) LIVENESS NET: main() actually WIRES register_lines()
        # into its emitted additionalContext, exercised END TO END as
        # a real subprocess (stdin payload -> stdout JSON), the way
        # tools/replay-bench.py's run_case() does it — never a
        # hand-recomposition of main()'s pieces.
        #
        # Root cause this replaces (review 861241a..286484a, finding
        # 4): the PRIOR version of this bite called check() +
        # worktree_advisory() + register_lines() directly and
        # composed `_combined` itself, so deleting
        # `lines += register_lines(payload)` from main() left every
        # net green — the bench (61/61), the bench's own selftest,
        # this suite's former (x), and doc-drift — because none of
        # them ran main()'s actual wiring, only its pieces. Red-proven
        # by deleting that line from main() and re-running this bite
        # (reported alongside the implementation, restored after).
        #
        # A corpus 'context'-expecting payload is used deliberately: a
        # non-compliant brief (missing tail/sections) is DENIED before
        # the register block ever renders — a trap this very dispatch
        # fell into while first drafting a synthetic payload by hand,
        # so the payload is read from the real corpus instead.
        import subprocess as _sp
        _guards_corpus = os.path.normpath(os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            "..", "..", "tools", "corpus", "guards.jsonl"))
        _e2e_case = None
        with open(_guards_corpus, encoding="utf-8") as _cf:
            for _cline in _cf:
                _cline = _cline.strip()
                if not _cline or _cline.startswith("#"):
                    continue
                _cc = json.loads(_cline)
                if (_cc.get("hook") == "brief-reminder.py"
                        and _cc.get("expect") == "context"
                        and "payload" in _cc
                        and "cwd" not in _cc.get("payload", {})):
                    _e2e_case = _cc
                    break
        assert _e2e_case is not None, (
            "no cwd-free brief-reminder.py 'context' corpus case found "
            "— cannot build the liveness bite")
        _e2e_reg = os.path.join(_tf.mkdtemp(), "readiness.json")
        with open(_e2e_reg, "w") as f:
            json.dump(_prozesse({
                "id": "LIVENESS-NET-SENTINEL", "tier": "haiku",
                "status": "ready", "klasse": "end-to-end wiring probe"}), f)
        _e2e_env = dict(os.environ)
        _e2e_env["CLAUDE_DISPATCH_GUARDS_REGISTER"] = _e2e_reg
        _e2e_env["CLAUDE_DISPATCH_GUARDS_CONFIG"] = "/nonexistent"
        _e2e_env["CLAUDE_DISPATCH_GUARDS_FIRELOG"] = os.path.join(
            _tf.mkdtemp(), "fires.jsonl")
        _e2e_proc = _sp.run(
            [sys.executable, os.path.realpath(__file__)],
            input=json.dumps(_e2e_case["payload"]), env=_e2e_env,
            capture_output=True, text=True)
        assert _e2e_proc.returncode == 0, _e2e_proc
        _e2e_out = json.loads(_e2e_proc.stdout)
        _e2e_ctx = _e2e_out["hookSpecificOutput"]["additionalContext"]
        # the reminder line AND the register block both ride the one
        # additionalContext field main() emits
        assert "brief check" in _e2e_ctx, _e2e_ctx
        assert _REGISTER_HEADER_LINE in _e2e_ctx, _e2e_ctx
        assert "LIVENESS-NET-SENTINEL" in _e2e_ctx, _e2e_ctx

        # ── Devbook-pin lane (missing_devbook_pin), STAGED WARN ────
        # Motivating incident (dotfiles df-238): a build brief named a
        # registered devbook section amended the SAME DAY and pinned
        # nothing, so the lane worked from an ungraded snapshot.
        # Expectations derive from §6's fingerprint contract (a pin is
        # a 64-hex sha256 over the section) and from the register's
        # own shape — never from this lane's behavior.

        # (i) the pin token: both ends anchored. An unanchored 64-run
        # also matches INSIDE a longer hex blob, which would let a
        # 128-char digest of something else pass as a section pin.
        assert _HEX64_RE.search("a" * 64)
        assert not _HEX64_RE.search("a" * 63)
        assert not _HEX64_RE.search("a" * 65)
        assert not _HEX64_RE.search("z" * 64)          # not hex
        assert _HEX64_RE.search("sha256 " + "0f" * 32 + ".")

        # (ii) _registered_class_names: THREE answers. None is
        # could-not-verify; [] is a read register certifying zero
        # classes; a populated register yields ids AND heimat tails.
        _pin_tmpdir = _tf.mkdtemp()

        def _with_pin_register(path, fn):
            os.environ["CLAUDE_DISPATCH_GUARDS_REGISTER"] = path
            try:
                return fn()
            finally:
                del os.environ["CLAUDE_DISPATCH_GUARDS_REGISTER"]

        _pin_reg = os.path.join(_pin_tmpdir, "readiness.json")
        with open(_pin_reg, "w") as f:
            json.dump(_prozesse(
                {"id": "guard-checker-bau", "tier": "opus",
                 "status": "eval-open",
                 "heimat": "CLAUDE.md#Registered procedure",
                 "fingerprint": "b" * 64},
                {"id": "enumeration-fixed-schema", "tier": "haiku",
                 "status": "ready",
                 "heimat": "CLAUDE.md#Registered class: fixed-schema "
                           "enumeration"},
                "not-a-dict",
                {"tier": "opus"},           # no id, no heimat
            ), f)
        _names = _with_pin_register(_pin_reg, _registered_class_names)
        assert "guard-checker-bau" in _names, _names
        assert "Registered procedure" in _names, _names
        assert "Registered class: fixed-schema enumeration" in _names, \
            _names
        # the malformed entry is SKIPPED, never a crash and never a
        # row: four entries in, four names out (2 ids + 2 tails).
        assert len(_names) == 4, _names
        # could-not-verify, all three ways in
        assert _with_pin_register(os.path.join(_pin_tmpdir, "gone.json"),
                                  _registered_class_names) is None
        _pin_bad = os.path.join(_pin_tmpdir, "bad.json")
        with open(_pin_bad, "w") as f:
            f.write("{not json")
        assert _with_pin_register(_pin_bad,
                                  _registered_class_names) is None
        _pin_shape = os.path.join(_pin_tmpdir, "shape.json")
        with open(_pin_shape, "w") as f:
            json.dump({"schema_version": 2}, f)
        assert _with_pin_register(_pin_shape,
                                  _registered_class_names) is None
        # …and the READ-BUT-EMPTY answer is [], never None: a register
        # certifying zero classes is a measurement, not a blind spot.
        _pin_empty = os.path.join(_pin_tmpdir, "empty.json")
        with open(_pin_empty, "w") as f:
            json.dump(_prozesse(), f)
        assert _with_pin_register(_pin_empty,
                                  _registered_class_names) == []

        # (iii) THE PAIR that grades the lane — the same brief with and
        # without a pin. They must DIFFER; a pair both readings satisfy
        # grades nothing. Red-proven against the whole-repo snapshot at
        # the parent commit, where the predicate did not exist at all.
        _PIN_LINE = ("Devbook section sha256 "
                     "77c9bf3fd7dead9ae5256a7ad4df61d8e8299d4a1"
                     "7e9801422c2dab3d5d222b4 — recomputed from the "
                     "file.")

        def _pin_brief(*extra):
            return {"tool_name": "Agent", "tool_input": {
                "name": "sonnet-x",
                "prompt": "\n".join(("Do X.",) + extra
                                    + (GROUNDING_SECTION,
                                       WRITE_BOUNDARIES_SECTION,
                                       COMMIT_PLAN_SECTION,
                                       EXECUTION_TAIL_BG))}}

        _class_no_pin = _pin_brief(
            "REGISTERED-CLASS dispatch: guard-checker-bau, tier opus.")
        _class_with_pin = _pin_brief(
            "REGISTERED-CLASS dispatch: guard-checker-bau, tier opus.",
            _PIN_LINE)
        assert _with_pin_register(
            _pin_reg, lambda: missing_devbook_pin(_class_no_pin)) == \
            "guard-checker-bau"
        assert _with_pin_register(
            _pin_reg, lambda: missing_devbook_pin(_class_with_pin)) is None
        # (iv) the heimat SECTION-NAME tail is a second way in — a
        # brief names the devbook section at least as often as the id.
        _heimat_no_pin = _pin_brief(
            "Follow the Registered procedure devbook, steps 1-5.")
        assert _with_pin_register(
            _pin_reg, lambda: missing_devbook_pin(_heimat_no_pin)) == \
            "Registered procedure"
        # (v) scope negatives: no class named; Task tool; garbage
        assert _with_pin_register(
            _pin_reg, lambda: missing_devbook_pin(
                _pin_brief("Ordinary build, no registered class."))) is None
        assert _with_pin_register(_pin_reg, lambda: missing_devbook_pin(
            {"tool_name": "Task", "tool_input": dict(
                _class_no_pin["tool_input"])})) is None
        assert _with_pin_register(_pin_reg, lambda: missing_devbook_pin(
            {"tool_name": "Agent", "tool_input": {}})) is None
        assert _with_pin_register(
            _pin_reg, lambda: missing_devbook_pin({})) is None
        # (vi) the READ-ONLY tail exempts, exactly as for the two
        # sibling lanes — and the MUST-NOT-MOVE arm is asked of an
        # INDEPENDENT instrument (_tail_kind), never of the lane on
        # trial: a lane that returned None for the wrong reason would
        # satisfy an assertion phrased against itself.
        _vet_cites_class = {"tool_name": "Agent", "tool_input": {
            "name": "opus-vet",
            "prompt": ("Verifier dispatch. ARTIFACT: the diff. "
                       "QUESTION: does the guard-checker-bau devbook "
                       "still match the hook?\n"
                       + _READONLY_TAIL_REAL)}}
        assert _tail_kind(_vet_cites_class) == "readonly", \
            _tail_kind(_vet_cites_class)
        assert "guard-checker-bau" in _brief_text(_vet_cites_class), (
            "fixture names no registered class — it would pass "
            "regardless of the exemption")
        assert _with_pin_register(
            _pin_reg,
            lambda: missing_devbook_pin(_vet_cites_class)) is None
        # (vii) COULD NOT VERIFY is silent AND logged: an unreadable
        # register must not read as a clean brief. The log line is the
        # positive control — without it the silent branch is
        # indistinguishable from "checked, nothing found".
        _pin_firelog = os.path.join(_pin_tmpdir, "fires.jsonl")
        _prev_firelog = os.environ.get("CLAUDE_DISPATCH_GUARDS_FIRELOG")
        os.environ["CLAUDE_DISPATCH_GUARDS_FIRELOG"] = _pin_firelog
        try:
            assert _with_pin_register(
                os.path.join(_pin_tmpdir, "gone.json"),
                lambda: missing_devbook_pin(_class_no_pin)) is None
            _pin_fires = [json.loads(ln) for ln in
                          open(_pin_firelog, encoding="utf-8")
                          if ln.strip()]
            assert len(_pin_fires) == 1, _pin_fires
            assert _pin_fires[0]["mode"] == "could-not-verify", _pin_fires
            assert "could not verify" in _pin_fires[0]["reason"], _pin_fires
            # …and a brief that PINS never reaches the register at all,
            # so it logs nothing: the lane asks nothing more of it.
            assert _with_pin_register(
                os.path.join(_pin_tmpdir, "gone.json"),
                lambda: missing_devbook_pin(_class_with_pin)) is None
            _pin_fires2 = [ln for ln in open(_pin_firelog, encoding="utf-8")
                           if ln.strip()]
            assert len(_pin_fires2) == 1, _pin_fires2
        finally:
            if _prev_firelog is None:
                del os.environ["CLAUDE_DISPATCH_GUARDS_FIRELOG"]
            else:
                os.environ["CLAUDE_DISPATCH_GUARDS_FIRELOG"] = _prev_firelog

        # (viii) the warn text names all three things the brief
        # demands of it: the matched class, the recipe pointer, and
        # that the pin is recomputed from the FILE.
        _wt = missing_devbook_pin_warn_text("guard-checker-bau")
        assert "guard-checker-bau" in _wt
        assert "sha256" in _wt and "heading line" in _wt
        assert "FROM THE FILE" in _wt

        # ── END-TO-END exit decisions, both halves ─────────────────
        # The done-criterion is pinned on the EXIT DECISION, never the
        # message text, so these run the real script as a subprocess
        # (stdin payload -> stdout JSON) the way replay-bench does.
        def _e2e(payload, register):
            env = dict(os.environ)
            env["CLAUDE_DISPATCH_GUARDS_REGISTER"] = register
            env["CLAUDE_DISPATCH_GUARDS_CONFIG"] = "/nonexistent"
            env["CLAUDE_DISPATCH_GUARDS_FIRELOG"] = os.path.join(
                _tf.mkdtemp(), "fires.jsonl")
            proc = _sp.run([sys.executable, os.path.realpath(__file__)],
                           input=json.dumps(payload), env=env,
                           capture_output=True, text=True)
            assert proc.returncode == 0, proc
            out = json.loads(proc.stdout) if proc.stdout.strip() else {}
            hso = out.get("hookSpecificOutput") or {}
            return (hso.get("permissionDecision"),
                    hso.get("additionalContext") or "",
                    hso.get("permissionDecisionReason") or "")

        # half 1: the commit-plan-less execution brief now DENIES.
        # Against the snapshot at the parent commit the same payload
        # exited warn-shaped (additionalContext "WARN — staging mode",
        # no permissionDecision) — that is this arm's red.
        _no_plan = {"tool_name": "Agent", "tool_input": {
            "name": "sonnet-x",
            "prompt": "\n".join(("Do X.", GROUNDING_SECTION,
                                 WRITE_BOUNDARIES_SECTION,
                                 EXECUTION_TAIL_BG))}}
        _d, _ctx, _reason = _e2e(_no_plan, _pin_reg)
        assert _d == "deny", (_d, _ctx)
        assert "commit-plan section" in _reason, _reason
        # …and the compliant twin still passes: the pair must differ.
        _d2, _ctx2, _ = _e2e(_pin_brief("Ordinary build."), _pin_reg)
        assert _d2 is None, (_d2, _ctx2)
        assert "brief check" in _ctx2, _ctx2

        # half 2: class named, no pin -> WARN naming the class; the
        # same brief with a pin -> no warn; the verifier brief -> no
        # warn (exempt). Read off the exit decision + the staging
        # marker fire() emits, never off prose.
        _d3, _ctx3, _ = _e2e(_class_no_pin, _pin_reg)
        assert _d3 is None, (_d3, _ctx3)
        assert "WARN — staging mode" in _ctx3, _ctx3
        assert "guard-checker-bau" in _ctx3, _ctx3
        _d4, _ctx4, _ = _e2e(_class_with_pin, _pin_reg)
        assert _d4 is None, (_d4, _ctx4)
        assert "WARN — staging mode" not in _ctx4, _ctx4
        _d5, _ctx5, _ = _e2e(_vet_cites_class, _pin_reg)
        assert _d5 is None, (_d5, _ctx5)
        assert "WARN — staging mode" not in _ctx5, _ctx5
        # …and with NO register readable the lane is silent end to end
        # (could-not-verify), rather than warning on a guess.
        _d6, _ctx6, _ = _e2e(_class_no_pin,
                             os.path.join(_pin_tmpdir, "gone.json"))
        assert _d6 is None, (_d6, _ctx6)
        assert "WARN — staging mode" not in _ctx6, _ctx6

        print("brief-reminder: all tests passed")
        sys.exit(0)
    sys.exit(main())
