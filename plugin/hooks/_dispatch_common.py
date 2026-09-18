"""Shared helpers for the dispatch-guards plugin (one file per lifecycle event).

Mirrors the _restrict_common.py pattern: small hooks per lifecycle
event, shared logic here.

Standing rules for every guard in this plugin (canonical home —
formerly dispatch-discipline.md §5, merged here with the skill-ify
move): each guard ships a `--test` self-check (bite-test),
registered in the machine-bootstrap doctor (dotfiles
bootstrap/doctor.py), so a harness change that silently breaks a
guard fails loudly. Guards stay FAIL-OPEN on hook-input parse
errors (verified per guard 2026-07-23 over the then-six guards;
later guards join the invariant through their own --test
parse-error bites; a broken guard must not brick every call, and
the enforced rules keep their non-hook safety nets) — the bite-tests
are the load-bearing compensation. Harness-dependent fields are
environment bindings, stamped with an as-of date where used. A
guard that EXTRACTS a value from its input (a path, an identifier)
distinguishes "could not extract" from "extracted, and clean": a
character class that silently truncates at an unexpected byte
(umlauts, spaces) yields a value whose negative verdict is
indistinguishable from a legitimate clean finding — extraction
failure maps to could-not-verify (fail-open or WARN per the
guard's error direction), never to a pass.
A guard that shells out to git against a working copy uses
`--no-optional-locks`: a plain `git status` REWRITES the index
(measured 2026-08-10), so an unflagged read-shaped call takes
index.lock and mutates shared state on every evaluation — the same
shared-index hazard that forbids `git add` for dispatched writers,
arriving through a command that reads as read-only. And a guard
`--test` fixture that runs `git commit` pins
`-c core.hooksPath=/nonexistent` (plus `--no-verify`): fixture repos
inherit the machine's GLOBAL core.hooksPath, so an unpinned fixture
silently runs the operator's real hook battery inside the tempdir.
Pinning hooksPath controls ONE of the two paths: because
core.hooksPath REPLACES `.git/hooks`, a dispatcher-style hook
commonly CHAINS back into `.git/hooks/<name>` so repo-local hooks
survive — so a fixture that swaps hook versions must clear that
file too. Measured 2026-08-10: an old-vs-new proof left a copy of
the NEW hook in `.git/hooks/pre-commit`, and the OLD side emitted
the new lane's message — a vacuous green wearing a red costume,
which is the harder direction to notice because the expected
result had arrived.

Environment binding (as-of 2026-07-18, Claude Code hooks): a subagent
context is marked by the presence of a non-empty `agent_id` field in the
hook input JSON; the main session has none — confirmed live in a
subagent context as of 2026-07-28 (observed, not merely bite-tested).
If a harness change removes
the field, the guards silently treat everything as the main session
(fail-open) — the --test bite-tests registered in the machine-bootstrap
doctor are the tripwire for that.
"""
from __future__ import annotations

import json
import sys


def is_subagent(payload: dict) -> bool:
    """True when the hook input comes from a subagent context."""
    return bool(payload.get("agent_id"))


# The 2026-08-11 incident (BACKLOG): a command chained `printf >>
# msg.txt && git commit && git push` was denied WHOLE by
# push-claim-reminder's fused-push lane. The deny text explained the
# push rule correctly and said nothing about the two earlier links —
# so the session re-ran the commit believing the trailer had been
# appended, and only the repo's own commit-msg hook caught it. Fixed
# text, one copy, so every Bash deny inherits it at once.
_CHAIN_NOTE = (
    "Nothing in this command ran — including any earlier links "
    "that chained into the denied one. Re-check their effects before "
    "assuming them."
)


def _has_chain_operator(cmd: str) -> bool:
    """True iff `cmd` contains a shell chaining operator (`&&`, `||`,
    `;`, or a bare newline) OUTSIDE quotes.

    A conservative scan, not a shell parser: it tracks single/double
    quote state and backslash escapes character by character, and on
    any doubt — an unbalanced quote left open at end of string — it
    returns True. The failure direction is toward telling the reader
    more, never less: a docstring false-fire probe elsewhere in this
    repo that instead bailed SILENT on an odd apostrophe count proved
    nothing, which is the shape this function is built not to repeat.
    Over-firing inside a command substitution or a heredoc body is
    accepted residue — the sentence is harmless where it does not
    strictly apply, unlike its silent omission."""
    quote: str | None = None
    i, n = 0, len(cmd)
    while i < n:
        c = cmd[i]
        if quote == "'":
            if c == "'":
                quote = None
            i += 1
            continue
        if quote == '"':
            if c == "\\" and i + 1 < n:
                i += 2
                continue
            if c == '"':
                quote = None
            i += 1
            continue
        # unquoted
        if c in ("'", '"'):
            quote = c
            i += 1
            continue
        if c == "\\" and i + 1 < n:
            i += 2
            continue
        if c == "\n" or c == ";":
            return True
        if c == "&" and cmd[i:i + 2] == "&&":
            return True
        if c == "|" and cmd[i:i + 2] == "||":
            return True
        i += 1
    if quote is not None:
        return True  # unbalanced quote: could not determine -> emit
    return False


def _deny_payload(reason: str, source: str = "dispatch-guards",
                  payload: dict | None = None) -> dict:
    """Build the deny JSON. Source-tagged and dual-field by design:
    permissionDecisionReason reaches the MODEL, systemMessage the user's
    UI — a deny carrying only one of them leaves the other audience with
    the harness's bare "Hook PreToolUse:<tool> denied this tool", which
    two sessions misattributed to a Claude Code permission bug (live
    finding 2026-07-30).

    Why the tag is load-bearing: CC builds the denial with the hook's
    identity (decisionReason.hookName/hookSource) but does not persist it
    to the transcript, so a guard fire is not attributable after the fact
    unless the guard names itself. The transcript's toolDenialKind is NOT
    the missing discriminator — the client documents "permission-rule" as
    covering hooks (verified in the shipped binary, 2.1.220), so it is
    working as designed. This tag is the only self-identification a guard
    fire gets.

    payload, when it carries a Bash `tool_input.command` containing a
    chaining operator, gets `_CHAIN_NOTE` appended to reason (never
    replacing or reordering the lane's own text) — the single render
    site every Bash deny lane passes through, so the note ships without
    a per-hook copy to drift. No payload, or a command with no chaining
    operator, leaves reason untouched."""
    cmd = (payload or {}).get("tool_input", {}).get("command")
    if isinstance(cmd, str) and _has_chain_operator(cmd):
        reason = f"{reason} {_CHAIN_NOTE}"
    tagged = f"[{source}] {reason}"
    return {
        "systemMessage": tagged,
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": tagged,
        },
    }


def deny(reason: str, source: str = "dispatch-guards",
         payload: dict | None = None) -> None:
    """Emit a clean PreToolUse deny (exit-0 JSON) and exit.

    Logs the fire FIRST. A hard deny is a fire, and the fire-rate
    review counts denies alongside asks and warns — this was the one
    exit that wrote nothing, so every lane calling it directly was
    invisible to the very log the review reads, while the same
    guard's fire()-routed lanes appeared normally. Measured on the
    shipped payload: brief-reminder's four deny lanes and
    push-claim-reminder's had zero log entries all-time, against 673
    for one fire()-routed lane.

    payload is optional so a caller with no hook input still denies;
    passing it is what fills session/agent/tool/shape in the record,
    and is also what lets _deny_payload append the chained-command
    note when the denied command warrants it."""
    fire_log(source, "deny", reason, payload)
    print(json.dumps(_deny_payload(reason, source, payload)))
    sys.exit(0)


def ask(reason: str, source: str = "dispatch-guards",
        payload: dict | None = None) -> None:
    """Emit an 'ask' payload (force the permission dialog) and exit 0.

    reason is duplicated as systemMessage: the dialog does not visibly
    render permissionDecisionReason (live finding 2026-07-18, see
    _restrict_common.ask). Logged to the fire log (an ask is a fire —
    the fire-rate review counts dialogs too)."""
    fire_log(source, "ask", reason, payload)
    print(json.dumps({
        "systemMessage": reason,
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": reason,
        }
    }))
    sys.exit(0)


# ── Fire log + guard modes (harvest 2026-08-06, dev-notes) ───────────────
# Every guard fire — deny, ask, warn, block — appends one JSONL line.
# Consumers: the fire-rate review (corpus Calibration: a guard firing on
# legitimate work trains the override reflex — the log is the instrument
# that makes fire rates countable instead of remembered) and warn→deny
# promotion decisions for staged lanes. Data home OUTSIDE any repo,
# mirroring dispatch-log.py.
_REASON_MAX = 300


def fire_log_path():
    from pathlib import Path
    if env := os.environ.get("CLAUDE_DISPATCH_GUARDS_FIRELOG"):
        return Path(env).expanduser()
    xdg = os.environ.get("XDG_DATA_HOME") or "~/.local/share"
    return Path(xdg).expanduser() / "claude" / "dispatch-guards-fires.jsonl"


def fire_log(source: str, mode: str, reason: str,
             payload: dict | None = None) -> None:
    """Append one fire record. Fail-open on every error — logging must
    never brick a call, and a fire that goes unlogged still fires."""
    try:
        from datetime import datetime, timezone
        payload = payload or {}
        rec = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "guard": source.rsplit("/", 1)[-1],
            "mode": mode,
            "session_id": payload.get("session_id"),
            "agent_id": payload.get("agent_id"),
            "tool_name": payload.get("tool_name"),
            "shape": command_shape(payload),
            "reason": reason[:_REASON_MAX],
        }
        pfad = fire_log_path()
        pfad.parent.mkdir(parents=True, exist_ok=True)
        with pfad.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass


def guard_mode(source: str, default: str = "deny") -> str:
    """Effective mode for a guard's deny lane: site policy `guard_modes`
    keyed by guard name (the source tag's last segment), else the
    guard's own shipped default. Modes: deny | warn | off. A malformed
    value falls back to the default (fail toward the shipped behavior,
    not toward silence)."""
    modes = policy().get("guard_modes")
    if not isinstance(modes, dict):
        return default
    v = modes.get(source.rsplit("/", 1)[-1], default)
    return v if v in ("deny", "warn", "off") else default


def fire(reason: str, source: str = "dispatch-guards",
         payload: dict | None = None, default_mode: str = "deny") -> None:
    """Mode-aware deny: the single exit for every deny lane.

    deny → the standard deny JSON (exit). warn → additionalContext
    "WARN (staging…)" (exit) — the lane is visible and logged but does
    not block; how staged lanes earn promotion: dev-notes harvest note.
    off → logged, silent (exit). Every mode logs to the fire log
    first, so a staged lane's false-fire rate is countable before it
    ever denies real work."""
    mode = guard_mode(source, default_mode)
    fire_log(source, mode, reason, payload)
    if mode == "deny":
        print(json.dumps(_deny_payload(reason, source, payload)))
    elif mode == "warn":
        print(json.dumps({
            "systemMessage": f"[{source}] WARN (staging): {reason}",
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": (
                    f"[{source}] WARN — staging mode, this lane would "
                    f"DENY: {reason}"),
            }
        }))
    sys.exit(0)


# ── Policy (mechanism/policy split) ──────────────────────────────────────
# The plugin ships generic defaults; site policy is merged from
# $CLAUDE_DISPATCH_GUARDS_CONFIG, else ~/.claude/dispatch-guards.json.
# Fail-open: an unreadable config yields the defaults.
import os

_DEFAULTS: dict = {
    "models": ["sonnet", "opus", "haiku", "fable"],
    "deny_models": [],
    "ask_models": [],
    "discipline_doc": None,
    "max_message_chars": 3000,
    "discovery_volume_bytes": 50000,
    "guard_modes": {},
    "write_claim_ttl_hours": 6,
    "light_tiers": True,
}
_POLICY_CACHE: dict | None = None
_POLICY_META: dict | None = None


def policy() -> dict:
    global _POLICY_CACHE, _POLICY_META
    if _POLICY_CACHE is None:
        cfg = dict(_DEFAULTS)
        pfad = os.environ.get("CLAUDE_DISPATCH_GUARDS_CONFIG") or os.path.expanduser(
            "~/.claude/dispatch-guards.json")
        read_ok = False
        try:
            with open(pfad, encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                cfg.update({k: loaded[k] for k in _DEFAULTS if k in loaded})
            read_ok = True
        except (OSError, json.JSONDecodeError, ValueError):
            pass  # fail-open: defaults
        _POLICY_CACHE = cfg
        _POLICY_META = {"path": pfad, "read": read_ok}
    return _POLICY_CACHE


def _policy_meta() -> dict:
    """Path consulted and whether it was successfully read — a side
    effect of policy()'s own (sole) config read, never a second open().
    Doctor's only consumer; guards have no use for it."""
    policy()
    return _POLICY_META


def _reset_policy_cache() -> None:
    """Test helper: forget the cached config (used by --test bite-tests)."""
    global _POLICY_CACHE, _POLICY_META
    _POLICY_CACHE = None
    _POLICY_META = None


# ── Dispatch tiers ───────────────────────────────────────────────────────
import re as _re  # noqa: E402

# Types whose harness tool roster is built for reading. Explore and
# claude-code-guide still carry Bash — accepted residue: a type that
# advertises read-only and then writes is a harness-level surprise the
# brief form would not have caught either.
LIGHT_READ_TYPES = frozenset({
    "Explore", "Plan", "claude-code-guide",
    "feature-dev:code-explorer", "feature-dev:code-architect",
    "feature-dev:code-reviewer",
})
LIGHT_MAX_WRITES = 2
LIGHT_MAX_PROMPT_CHARS = 2000
_LIGHT_WRITES_RE = _re.compile(r"^\s*writes:\s*(\S.*)$",
                               _re.IGNORECASE | _re.MULTILINE)
# Any of these words in a small-write brief sends it to the full tier:
# the outward, shared-state and irreversible class the full brief form
# exists for. Word-boundary match — "commit" hits, "committee" not.
_LIGHT_HEAVY_RE = _re.compile(
    r"\b(push\w*|publish\w*|deploy\w*|commit\w*|release\w*|merge\w*|"
    r"database|db|sqlite|supabase|postgres\w*|migrat\w*|prod|"
    r"production|artifact\w*|served|serve|email\w*|"
    r"delete\w*|drop|rm)\b",
    _re.IGNORECASE)


def dispatch_tier(tool_input: dict) -> str:
    """"read" | "small-write" | "full" — how much brief discipline a
    dispatch owes. Light tiers are exempt from the skill-load gate and
    brief-reminder's form lanes (tail, sections, commit plan, devbook
    pin); the model gate and the mailbox channel lane apply to every
    tier, since a light dispatch can burn the wrong quota or report
    into the void as easily as a heavy one.

    read — subagent_type in LIGHT_READ_TYPES, or any type whose brief
      carries `Writes: none` and no _LIGHT_HEAVY_RE word.
    small-write — the brief carries a `Writes: <path>[, <path>]` line
      naming 1..LIGHT_MAX_WRITES paths, the prompt stays under
      LIGHT_MAX_PROMPT_CHARS, and it names nothing in _LIGHT_HEAVY_RE.
      No commit: the dispatcher reviews and commits.
    full — everything else, and every dispatch when site policy sets
      `light_tiers: false`.

    Occasion (2026-09-18, scope-agent): a one-file draft swap took four
    blocked retries — skill gate, tail, sections, model — for a brief
    longer than the work. Fails toward "full" on any doubt."""
    if not policy().get("light_tiers", True):
        return "full"
    if not isinstance(tool_input, dict):
        return "full"
    if tool_input.get("subagent_type") in LIGHT_READ_TYPES:
        return "read"
    prompt = tool_input.get("prompt") or ""
    if not isinstance(prompt, str):
        return "full"
    m = _LIGHT_WRITES_RE.findall(prompt)
    if len(m) != 1:
        return "full"
    if _re.fullmatch(r"none\b.*", m[0].strip(), _re.IGNORECASE):
        # Declared read-only, any agent type (2026-09-19: a Codex
        # review via codex:codex-rescue had no light path — a writing
        # type doing read-only work had nothing to declare). No length
        # cap: reviews carry context; the heavy-word check still holds.
        return "full" if _LIGHT_HEAVY_RE.search(prompt) else "read"
    if len(prompt) > LIGHT_MAX_PROMPT_CHARS:
        return "full"
    paths = [p.strip() for p in m[0].split(",") if p.strip()]
    if not 1 <= len(paths) <= LIGHT_MAX_WRITES:
        return "full"
    if _LIGHT_HEAVY_RE.search(prompt):
        return "full"
    return "small-write"


def light_tier_hint() -> str:
    """One sentence appended to form-lane denies so the cheap path is
    visible at the moment of need, not only in docs."""
    return (
        " Read-only? Add a line `Writes: none` (any agent type) and "
        "retry. Small edit? A brief under "
        f"{LIGHT_MAX_PROMPT_CHARS} chars with one line `Writes: "
        f"<path>[, <path>]` (max {LIGHT_MAX_WRITES}). Either way no "
        "push/publish/deploy/commit/DB/delete words."
    )


def doc_ref(section: str) -> str:
    """A citable pointer into the site's discipline doc, or generic wording."""
    doc = policy().get("discipline_doc")
    return f"{doc} {section}" if doc else "your dispatch discipline"


# ── Command shape + push detection ───────────────────────────────────────
import re     # noqa: E402
import shlex  # noqa: E402

_SHAPE_MAX = 120
# A safe word: lowercase verb-ish, no separators, no case mixing. Values
# and secrets (URLs, tokens, paths, messages) fail it by construction.
_SHAPE_WORD = re.compile(r"^[a-z][a-z0-9-]*$")
_SHAPE_LONG_FLAG = re.compile(r"^--[a-z][a-z0-9-]*$")
_SHAPE_SEPS = frozenset({"&&", "||", ";", "|", "&", "(", ")", "{", "}"})


def command_shape(payload: dict) -> str | None:
    """A secret-free discriminator for WHAT a guard fired on.

    The fire log's `reason` is CONSTANT per lane, so a reviewer
    counting fires cannot separate a false fire from a true one. The
    `--push` false fire (a `git remote set-url --push` config write
    denied as a push) logged identically to a real push from the day
    its arm was minted, and was found by accident rather than from the
    log — the instrument for the warn→deny promotion criterion could
    not answer the question the criterion asks. This field is the
    missing half.

    Operands carry the secrets — tokens in URLs, `-p<password>`,
    commit messages, paths — so the shape keeps only VERBS and FLAGS.
    Per command-position invocation: the command's basename, up to two
    following subcommand words, and its flags — long flags with any
    `=value` stripped, short flags reduced to their letter, because a
    short flag can carry its value attached (`-p<password>`) in a form
    that passes any looks-like-a-flag pattern. Words stop at the first
    flag, since what follows a flag is its value. Anything failing the
    safe-word pattern degrades to `?` rather than being emitted. So
    `git remote set-url --push origin https://tok@host/r.git` reduces
    to `git remote set-url --push`, `git commit -m "<message>"` to
    `git commit -m`, and `SECRET=x curl -H "<auth>" <url>` to
    `? curl -H`.

    Dispatch tools report their routing fields instead (both
    non-secret and the discriminator that matters for a model gate).
    Every other tool returns None: adding a shape for Write/Edit or
    SendMessage means deciding what of a path or a message body is
    safe, which no evidence yet demands.
    """
    tool = payload.get("tool_name")
    tool_input = payload.get("tool_input") or {}
    if tool in ("Agent", "Task", "Workflow"):
        bits = [str(tool_input.get(k)) for k in ("subagent_type", "model")
                if tool_input.get(k)]
        return " ".join(bits)[:_SHAPE_MAX] or None
    if tool != "Bash":
        return None
    try:
        tokens = shlex.split(tool_input.get("command", "") or "")
    except ValueError:
        return None

    shape: list = []
    at_cmd, words = True, 0
    for t in tokens:
        if t in _SHAPE_SEPS or t.endswith(";"):
            shape.append(";")
            at_cmd, words = True, 0
            continue
        if at_cmd:
            name = os.path.basename(t)
            shape.append(name if _SHAPE_WORD.match(name) else "?")
            at_cmd, words = False, 0
            continue
        if t.startswith("--"):
            flag = t.split("=", 1)[0]
            shape.append(flag if _SHAPE_LONG_FLAG.match(flag) else "--?")
            words = 99          # what follows a flag is its VALUE
        elif t.startswith("-"):
            # A SHORT flag can carry its value attached and unseparated
            # (`-p<password>`, `-uroot`), and that form passes any
            # "looks like a flag" pattern — the leak this keeps out.
            # Only the letter survives; one character cannot be a secret.
            shape.append(f"-{t[1]}" if t[1:2].isalnum() else "-?")
            words = 99
        elif words < 2 and _SHAPE_WORD.match(t):
            shape.append(t)
            words += 1
        else:
            words = 99          # first operand ends the subcommand run
    return " ".join(shape)[:_SHAPE_MAX] or None


def _push_in_tokens(tokens: list) -> bool:
    """The argv-position predicate, in ONE home: a `git`/`gh` token plus
    a standalone `push` (or `--push`) token, minus the two exemptions.
    Both callers of it — the shlex path and the parse-failure path —
    share this scan so the token rule cannot grow two copies that drift
    apart. Contract is on ARGV POSITION, so it holds for any tokenizer
    that yields argv-shaped words."""
    if not any(t in ("git", "gh") for t in tokens):
        return False
    prev = ""
    seen_remote = False
    for t in tokens:
        if t == "remote":
            seen_remote = True
        if t == "push" and prev != "stash":
            return True
        if t == "--push" and not seen_remote:
            return True
        prev = t
    return False


def is_push_command(cmd: str) -> bool:
    """True iff the command actually invokes a push: a `git`/`gh` token
    plus a standalone `push` (or `--push`) token, split with shlex so
    QUOTED text — commit messages, quoted paths — never matches. The
    2026-08-01 false-fire class: a standing commit-message line ("rides
    the next code push") fired the reminder on every commit of a repo,
    and the same substring match would false-DENY a subagent's commit —
    a deny on legitimate work trains the override reflex.

    Two exemptions, each a token that reads as a push and is not one:

    - a `push` directly after `stash` — the purely-local `git stash push`.
    - a `--push` anywhere after a `remote` token — `git remote set-url
      --push` is a CONFIG WRITE, not a push. The `--push` arm exists for
      `gh pr create --push`; its only other real git referent is that
      set-url form, so before the exemption the arm denied a subagent's
      config write with a push-discipline message, and reminded the main
      session of a claim check for a command that publishes nothing.
      (What that command DOES warrant — it rewrites the shared config
      from a worktree — is worktree-config-gate's lane.) Scoped to the
      token, not the command: `git remote set-url --push … && git push`
      still matches on the later bare `push`.

    Unparseable quoting does NOT change the verdict class. An
    unbalanced apostrophe — in a commit message, in a heredoc body —
    makes shlex raise, and the command is then re-tokenized on
    WHITESPACE and put through the SAME argv-position predicate
    (_push_in_tokens), exemptions included. It is never substring
    matched: the old fallback turned a parse failure into a weaker
    matcher whose false fires were invisible to author and subject
    alike. The 2026-08-10 class it closes: `git commit -F -` with a
    heredoc body carrying both an apostrophe and the word pre-push was
    DENIED, because the apostrophe raised and the substring fallback
    then matched the literal pre-push (a hyphen is a word boundary to
    the regex, but is not a token break). Whitespace tokens keep their
    quote characters attached, so on that path a quoted word matches
    only when it would have matched bare.

    Accepted residue unchanged: unquoted standalone `push` words
    (`git log --grep push`) still match on both paths; deliberate
    obfuscation stays the session-cut check's net."""
    try:
        tokens = shlex.split(cmd)
    except ValueError:
        tokens = cmd.split()
    return _push_in_tokens(tokens)


# ── Git working-copy reads (shared; one home for the flags) ──────────────
import subprocess  # noqa: E402

_GIT_STATUS_TIMEOUT = 10.0


def git_status_lines(directory: str, pathspec: str | None = None,
                     include_ignored: bool = False,
                     timeout: float = _GIT_STATUS_TIMEOUT) -> list | None:
    """Porcelain status lines for a working copy, or None = COULD NOT
    ANSWER. One home for the flags, because two guards now ask a
    git-status question and the flags below each cost a fix to get right.

    None is the third answer and never collapses into "clean": a path
    outside any repo, a missing directory, git unrunnable, slow, or
    exiting non-zero all return None. Each CALLER maps that to its own
    conservative direction — relief and release both take POSITIVE
    evidence, so both read None as "do not act".

    `--no-optional-locks` is not optional: a plain `git status` REWRITES
    the index (measured 2026-08-10), so an unflagged read-shaped call
    takes index.lock and mutates state shared with the very co-writers
    these guards exist for.

    `include_ignored` is the caller's question, not a default, and the
    two live callers genuinely differ (both measured 2026-08-10):

    - PER-PATH, "is there in-flight content at this file?"
      (writer-claims-gate's relief) needs include_ignored=True. A
      GITIGNORED file reports empty under plain status even with live
      content, so without it the predicate relieves exactly where
      evidence is absent.
    - PER-COPY, "could a commit here absorb someone's work?"
      (writer-reservation-gate's release) needs include_ignored=False.
      `git commit` never stages an ignored file, so an ignored artifact
      is by definition unabsorbable; counting it would make "clean"
      unreachable in any repo with a build directory — measured on a
      copy where git itself reported "nothing to commit, working tree
      clean" while `--ignored=matching` reported `!! build/`.

    Passing a `pathspec` scopes the answer to one path; omitting it asks
    about the whole copy. Note that the per-path form must be run with
    `directory` INSIDE the repo — `git -C <parent-of-repo>` exits 128
    and yields None, which is the honest answer, not a clean one.
    """
    cmd = ["git", "-C", directory, "--no-optional-locks", "status",
           "--porcelain"]
    if include_ignored:
        cmd.append("--ignored=matching")
    if pathspec is not None:
        cmd += ["--", pathspec]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    return [ln for ln in r.stdout.splitlines() if ln.strip()]


# ── Doctor (self-diagnosis; build dg-38) ──────────────────────────────────
# `python3 _dispatch_common.py --doctor` reports the three OPTIONAL site
# surfaces — site policy, the readiness register, the routing site
# overlay — so a fresh install reads as unconfigured-and-working rather
# than silently configured-with-someone-else's-bindings. Exit 0 always:
# this REPORTS, it never gates.


def _doctor_format_value(key: str, value) -> str:
    if key == "guard_modes":
        if not value:
            return "none overridden"
        return ", ".join(f"{g}: {m}" for g, m in sorted(value.items()))
    return repr(value)


def _doctor_site_policy() -> list:
    """Site policy surface. Reuses policy()'s own (sole) config read via
    _policy_meta() — no second open() of the config file."""
    meta = _policy_meta()
    cfg = policy()
    out = [
        "Site policy (dispatch-guards.json)",
        f"  path consulted: {meta['path']}",
    ]
    if not meta["read"]:
        out.append("  config file: not read (absent or unreadable)")
        out.append("  shipped defaults active:")
        for k in _DEFAULTS:
            out.append(f"    {k}: {_doctor_format_value(k, cfg[k])}")
    else:
        out.append("  config file: read")
        for k in _DEFAULTS:
            tag = "overridden" if cfg[k] != _DEFAULTS[k] else "default"
            out.append(f"    {k}: {_doctor_format_value(k, cfg[k])} ({tag})")
    return out


def _load_brief_reminder():
    """brief-reminder.py imported by path — the hyphen rules out a plain
    import (mirrors tools/check-doc-drift.py's `_brief_reminder`, the
    only other cross-file load in this repo). Returns None rather than
    raising: the doctor reports, it never gates on its own machinery."""
    import importlib.util
    here = os.path.dirname(os.path.realpath(__file__))
    path = os.path.join(here, "brief-reminder.py")
    spec = importlib.util.spec_from_file_location(
        "_brief_reminder_doctor", path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception:
        return None
    return module


def _doctor_register() -> list:
    """Readiness register surface. Path comes from brief-reminder's own
    `_register_path` helper — no new path-resolution logic here."""
    out = ["Tier-readiness register (readiness.json)"]
    mod = _load_brief_reminder()
    if mod is None or not hasattr(mod, "_register_path"):
        out.append("  path consulted: could not resolve "
                    "(brief-reminder.py not importable)")
        return out
    pfad = mod._register_path()
    out.append(f"  path consulted: {pfad}")
    if os.path.isfile(pfad):
        out.append("  register file: present")
    else:
        out.append("  register file: absent")
        out.append("  no certified classes — cheap-tier certification "
                    "unavailable, dispatches still run")
    return out


def _doctor_routing_overlay() -> list:
    """Routing site-overlay surface: whether routing.md's own
    `## Site overlay` section is present in THIS installed payload —
    resolved next to this file, never the caller's cwd, since hooks run
    from the installed plugin cache."""
    here = os.path.dirname(os.path.realpath(__file__))
    routing_path = os.path.normpath(os.path.join(
        here, "..", "skills", "dispatch", "references", "routing.md"))
    template_path = os.path.normpath(os.path.join(
        here, "..", "skills", "dispatch", "references",
        "routing-overlay-template.md"))
    out = ["Routing site overlay (dispatch skill references/routing.md)",
           f"  file consulted: {routing_path}"]
    try:
        with open(routing_path, encoding="utf-8") as f:
            present = "## Site overlay" in f.read()
    except OSError:
        out.append("  routing.md: not readable")
        present = None
    if present is True:
        out.append("  site-overlay section: present")
    elif present is False:
        out.append("  site-overlay section: absent — portable tier-role "
                    "rules only, no concrete lineup")
    out.append(f"  fill in your own bindings via: {template_path}")
    return out


def run_doctor() -> int:
    lines: list = []
    lines += _doctor_site_policy()
    lines.append("")
    lines += _doctor_register()
    lines.append("")
    lines += _doctor_routing_overlay()
    print("\n".join(lines))
    return 0


if __name__ == "__main__" and "--doctor" in sys.argv:
    sys.exit(run_doctor())


if __name__ == "__main__" and "--test" in sys.argv:
    # Bite-test for the shared machinery itself (fire log, guard modes,
    # fire() routing). The per-guard files test their own lanes; this
    # block owns what they all share. Auto-discovered by the doctor's
    # content-based "--test" scan like every guard file.
    import contextlib
    import io
    import tempfile
    from pathlib import Path

    os.environ["CLAUDE_DISPATCH_GUARDS_CONFIG"] = "/nonexistent"
    _reset_policy_cache()

    with tempfile.TemporaryDirectory() as td:
        os.environ["CLAUDE_DISPATCH_GUARDS_FIRELOG"] = td + "/f/fires.jsonl"

        # ── guard_mode: defaults, site override, malformed values ──
        assert guard_mode("dispatch-guards/x") == "deny"
        assert guard_mode("dispatch-guards/x", default="warn") == "warn"
        with tempfile.NamedTemporaryFile("w", suffix=".json",
                                         delete=False, dir=td) as tf:
            tf.write('{"guard_modes": {"amend-gate": "warn",'
                     ' "push-gate": "bogus", "x-gate": "off"}}')
            cfg = tf.name
        os.environ["CLAUDE_DISPATCH_GUARDS_CONFIG"] = cfg
        _reset_policy_cache()
        assert guard_mode("dispatch-guards/amend-gate") == "warn"
        assert guard_mode("dispatch-guards/x-gate") == "off"
        # malformed value → shipped default, never silence
        assert guard_mode("dispatch-guards/push-gate") == "deny"
        assert guard_mode("dispatch-guards/unlisted") == "deny"

        # ── fire(): deny / warn / off routing, each logged ──
        def run_fire(default_mode="deny", source="dispatch-guards/amend-gate"):
            buf = io.StringIO()
            code = None
            with contextlib.redirect_stdout(buf):
                try:
                    fire("R" * 400, source=source,
                         payload={"session_id": "s1", "agent_id": "a1",
                                  "tool_name": "Bash"},
                         default_mode=default_mode)
                except SystemExit as e:
                    code = e.code
            return code, buf.getvalue()

        code, out = run_fire()  # amend-gate is warn per config above
        assert code == 0
        j = json.loads(out)
        assert "additionalContext" in j["hookSpecificOutput"], j
        assert "would DENY" in j["hookSpecificOutput"]["additionalContext"]
        assert "permissionDecision" not in j["hookSpecificOutput"]

        code, out = run_fire(source="dispatch-guards/unlisted")  # deny
        assert code == 0
        j = json.loads(out)
        assert j["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert j["systemMessage"].startswith("[dispatch-guards/unlisted]")

        code, out = run_fire(source="dispatch-guards/x-gate")  # off
        assert code == 0 and out == "", (code, repr(out))

        # ── ask(): logged and emitting the dialog payload ──
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            try:
                ask("dialog?", source="dispatch-guards/model-gate",
                    payload={"session_id": "s2", "tool_name": "Agent"})
            except SystemExit as e:
                assert e.code == 0
        j = json.loads(buf.getvalue())
        assert j["hookSpecificOutput"]["permissionDecision"] == "ask"

        # ── deny(): a HARD deny is a fire and must reach the log ──
        # The fire-rate review reads the log; a lane that denies
        # without logging is invisible to it while its fire()-routed
        # siblings appear normally. Expectation from the log's own
        # declared contract ("Every guard fire — deny, ask, warn,
        # block — appends one JSONL line"), which deny() did not meet.
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            try:
                deny("hard no", source="dispatch-guards/brief-reminder",
                     payload={"session_id": "s3", "tool_name": "Agent",
                              "agent_id": "a9"})
            except SystemExit as e:
                assert e.code == 0
        j = json.loads(buf.getvalue())
        assert j["hookSpecificOutput"]["permissionDecision"] == "deny"

        # ── the log: one line per fire, fields + truncation ──
        lines = [json.loads(ln) for ln in
                 Path(td + "/f/fires.jsonl").read_text().splitlines()]
        assert len(lines) == 5, len(lines)
        modes = [ln["mode"] for ln in lines]
        assert modes == ["warn", "deny", "off", "ask", "deny"], modes
        assert lines[4]["guard"] == "brief-reminder"
        assert lines[4]["session_id"] == "s3"
        assert lines[4]["agent_id"] == "a9"
        assert lines[0]["guard"] == "amend-gate"
        assert lines[0]["agent_id"] == "a1"
        assert len(lines[0]["reason"]) == _REASON_MAX  # truncated
        assert lines[3]["guard"] == "model-gate"
        assert lines[3]["session_id"] == "s2"

        # ── fail-open: unwritable log path never raises or blocks ──
        os.environ["CLAUDE_DISPATCH_GUARDS_FIRELOG"] = "/proc/nope/f.jsonl"
        fire_log("dispatch-guards/x", "deny", "r", {})  # must not raise
        code, out = run_fire(source="dispatch-guards/unlisted")
        assert code == 0 and "deny" in out  # fire still denies unlogged

        del os.environ["CLAUDE_DISPATCH_GUARDS_FIRELOG"]
        os.environ["CLAUDE_DISPATCH_GUARDS_CONFIG"] = "/nonexistent"
        _reset_policy_cache()

    # ── command_shape: the discriminator, and the secrets it must not
    # carry. Expectations derived from what the fire-rate review needs
    # to ANSWER (which arm fired) and from what the log must never
    # become (a plaintext secret store) — not from the implementation.
    def S(cmd, tool="Bash"):
        return command_shape({"tool_name": tool,
                              "tool_input": {"command": cmd}})

    # (i) THE motivating case: the two records that were identical
    poison = "git remote set-url --push origin https://tok@host/r.git"
    assert S(poison) == "git remote set-url --push", S(poison)
    assert S("git push origin main") != S(poison)
    assert S("gh pr create --push") == "gh pr create --push"
    # (ii) operands dropped, flags kept, `=value` stripped
    assert S("git commit -m 'a long secret message'") == "git commit -m"
    assert S("git config --unset-all remote.origin.pushurl") == \
        "git config --unset-all"
    assert S("curl --header=Authorization:Bearer-xyz https://h/p") == \
        "curl --header"
    # (iii) SECRETS NEVER SURVIVE — the load-bearing claim, one case
    # per carrier shape. Each string below must be absent from the
    # shape entirely.
    for cmd, secret in [
        (poison, "tok"),
        ("git commit -m 'password is hunter2'", "hunter2"),
        ("mysql -phunter2 -u root", "hunter2"),
        ("curl -H 'Authorization: Bearer sk-abc123' https://h", "sk-abc123"),
        ("curl https://user:pw@host/path", "pw"),
        ("SECRET=abc123 git push", "abc123"),
        ("aws s3 cp /home/g/private/keys.txt s3://b", "keys"),
        ("git clone https://x-token:ghp_AAA@github.com/o/r", "ghp_AAA"),
        ("echo 'ssh-rsa AAAAB3Nza' >> ~/.ssh/authorized_keys", "AAAAB3Nza"),
    ]:
        got = S(cmd) or ""
        assert secret not in got, f"LEAK: {secret!r} survived in {got!r}"
    # (iii-b) PROPERTY, stronger than any case list: every emitted
    # token is a separator, a degraded marker, a safe word, or a
    # normalized flag. A secret can therefore only survive by BEING
    # one of those — which the case list above pins separately.
    _ok = {";", "?", "-?", "--?"}
    for cmd in [
        poison, "mysql -phunter2 -u root", "SECRET=abc123 git push",
        "curl -H 'Bearer sk-AAA' https://u:pw@h/p?t=SEKRET#frag",
        "psql 'postgres://u:p@h:5432/db' -c 'SELECT 1'",
        "docker run -e API_KEY=sk-XYZ img:tag /bin/sh -c 'echo $X'",
        "ssh -i ~/.ssh/id_ed25519 deploy@10.0.0.1 'sudo rm -rf /srv'",
        "openssl enc -aes-256-cbc -k Passw0rd! -in a -out b",
        "git -c http.extraHeader='Authorization: Basic QUJD' push",
        "find / -name '*.pem' -exec cat {} \\;",
        "printf '%s' \"$TOKEN\" | gh auth login --with-token",
    ]:
        for tok in (S(cmd) or "").split():
            assert (tok in _ok or _SHAPE_WORD.match(tok)
                    or _SHAPE_LONG_FLAG.match(tok)
                    or (len(tok) == 2 and tok[0] == "-"
                        and tok[1].isalnum())), \
                f"unconstrained token {tok!r} from {cmd!r}"
    # (iv) command position hardened: env prefixes and paths
    assert S("SECRET=abc123 git push").startswith("?")
    assert S("/usr/local/bin/git push") == "git push"      # basename
    # (v) sequencing preserved, so a fused command stays readable
    assert S("git commit -m x && git push") == "git commit -m ; git push"
    # (vi) non-Bash: dispatch tools report routing, others nothing
    assert command_shape({"tool_name": "Agent", "tool_input": {
        "subagent_type": "general-purpose", "model": "fable"}}) == \
        "general-purpose fable"
    assert command_shape({"tool_name": "Write",
                          "tool_input": {"file_path": "/secret/x"}}) is None
    assert command_shape({"tool_name": "SendMessage"}) is None
    # (vii) degenerate input never raises
    assert S("") is None
    assert S("git config --get x 'unterminated") is None   # unparseable
    assert command_shape({}) is None
    assert len(S("git " + " ".join(f"--flag{i}" for i in range(60))) or "") \
        <= _SHAPE_MAX

    # ── is_push_command: the verdict CLASS must not move with
    # PARSEABILITY. Expectations derived from what the guard's
    # consumers mean (does this command publish?), not from either
    # tokenizer: adding an apostrophe to a command changes how it
    # parses and must not change whether it is a push.
    P = is_push_command
    # (i) THE motivating case (2026-08-10): a commit whose heredoc body
    # carries an apostrophe AND the word pre-push. shlex raises on the
    # apostrophe; the old substring fallback then matched the literal
    # pre-push and DENIED a legitimate commit. Second line is the same
    # command minus the apostrophe — it parses, and was already False,
    # so the pair isolates the fallback as the cause.
    denied = "git commit -F - <<'EOF'\npre-push: the guard's fallback\nEOF"
    twin = "git commit -F - <<'EOF'\npre-push: the guard fallback\nEOF"
    assert not P(denied)
    assert not P(twin)
    assert not P("git commit -m 'the gate's false fire'")
    # (ii) the half that forbids answering a bare False on ValueError:
    # a GENUINE push wearing the same unbalanced apostrophe must still
    # be caught, or the guard opens a hole where it is load-bearing.
    assert P("echo 'it's fine' && git push")
    assert P("git push origin main # the lane's push")
    # (iii) ONE predicate, so both exemptions hold on the parse-failure
    # path exactly as on the parsed one — including the second red the
    # motivating case exposed: the old fallback's \bpush\b matched the
    # `--push` of a remote config write once an apostrophe was present.
    assert not P("git stash push -m 'wip's draft'")
    assert P("git stash push && git push # jane's")
    assert not P("git remote set-url --push origin /x # jane's")
    assert P("git remote set-url --push origin /x && git push # jane's")
    # (iv) an apostrophe cannot manufacture the git/gh token either
    assert not P("echo 'it's push time'")

    # ── git_status_lines: the shared working-copy read, against REAL
    # git. Expectations derived from what each CALLER's question means
    # (can a commit absorb this? is there content at this path?), not
    # from this implementation.
    import tempfile as _tf

    with _tf.TemporaryDirectory() as _td:
        _env = {**os.environ, "GIT_CONFIG_GLOBAL": _td + "/gc",
                "GIT_CONFIG_SYSTEM": _td + "/gs"}
        _copy = os.path.realpath(_td) + "/copy"
        os.makedirs(_copy)

        def _g(*a):
            return subprocess.run(
                ["git", "-C", _copy, "-c", "user.email=t@t",
                 "-c", "user.name=t", "-c", "core.hooksPath=/nonexistent",
                 *a], env=_env, capture_output=True, text=True)

        _g("init", "-q", ".")
        open(_copy + "/f.py", "w").write("x = 1\n")
        open(_copy + "/.gitignore", "w").write("build/\n")
        _g("add", "--", "f.py", ".gitignore")
        assert _g("commit", "-q", "--no-verify", "-m", "b").returncode == 0

        # committed-clean copy: no lines, and that is an ANSWER
        assert git_status_lines(_copy) == []
        # a modified tracked file shows up
        open(_copy + "/f.py", "w").write("x = 2\n")
        assert git_status_lines(_copy) == [" M f.py"]
        # …and scoping by pathspec still sees it, from INSIDE the repo
        assert git_status_lines(_copy, pathspec=_copy + "/f.py") == [" M f.py"]
        open(_copy + "/f.py", "w").write("x = 1\n")
        assert git_status_lines(_copy) == []

        # THE FLAG SPLIT, measured: an ignored artifact is unabsorbable
        # (git itself: "nothing to commit, working tree clean") but IS
        # content at its path.
        os.makedirs(_copy + "/build")
        open(_copy + "/build/out.o", "w").write("artifact\n")
        assert git_status_lines(_copy) == [], git_status_lines(_copy)
        assert git_status_lines(_copy, include_ignored=True) == ["!! build/"]
        assert "nothing to commit" in _g("commit", "--no-verify", "-m",
                                         "x").stdout

        # untracked, non-ignored work counts for BOTH questions
        open(_copy + "/new.py", "w").write("y = 1\n")
        assert git_status_lines(_copy) == ["?? new.py"]
        os.unlink(_copy + "/new.py")

        # ── COULD NOT ANSWER is None, never [] ────────────────────────
        assert git_status_lines(_td + "/nodir") is None       # missing dir
        os.environ["GIT_CEILING_DIRECTORIES"] = os.path.realpath(_td)
        assert git_status_lines(_td) is None                  # not a repo
        del os.environ["GIT_CEILING_DIRECTORIES"]
        # the per-path form run from the repo's PARENT: git exits 128, so
        # the honest answer is None — NOT an empty (clean-looking) list
        assert git_status_lines(os.path.dirname(_copy),
                                pathspec=_copy) is None
        # a timeout that cannot complete is could-not-answer, not clean
        assert git_status_lines(_copy, timeout=0.000001) is None

    print("_dispatch_common: all tests passed")
    sys.exit(0)

