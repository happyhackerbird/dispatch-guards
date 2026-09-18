# dispatch-guards

The dispatch discipline as a skill, plus the mechanical guards that
enforce its computable slice. Prose rules are best-effort; hooks are
not — this plugin carries both sides.

## Skills

- **`dispatch`** — the dispatch discipline itself: decision-complete
  briefs (§1), the closing-report form and brief tails
  (`references/forms.md`, §§2–3), dispatcher duties (§4),
  tier-readiness register (§6), Codex routing
  (`references/codex-routing.md`, §7). The `dispatch-skill-gate`
  hook demands this skill be loaded before any dispatch.
- **`executor`** — the receiving side: conduct of execution for a
  session running a brief or a repo devbook (§1 — grounding
  literalism, "done" is the check's own output, gaps surface never
  bridge, escalation returns the question), the under-report
  principle (§2), and the devbook form (§3) with its mechanical
  checker (`plugin/skills/executor/scripts/check_devbook_form.py`).
- **`worktree`** — portable git-worktree and git-hook mechanics for
  isolating agents and wiring hooks safely.

All three are model-invoked — they trigger from their descriptions;
`dispatch` is additionally hook-demanded before any dispatch call.

## Guards

| Guard | Event | What it enforces |
|---|---|---|
| `dispatch-skill-gate` | PreToolUse Agent\|Task\|Workflow | the `dispatch` skill must be loaded in the dispatching context's transcript (session-scoped) before any dispatch — replaces the old read-by-convention; read-type and declared small-write dispatches are exempt (`light_tiers`) |
| `agent-model-gate` | PreToolUse Agent\|Task\|Workflow | explicit `model` on generic agent types (still denies); a missing or wrongly-prefixed `<model>-` NAME is now **rewritten**, not denied — `hookSpecificOutput.updatedInput` sets `name` to `<model>-<slug>` (slug from the existing name when present, else the description, slugified; 2026-09-15 verb conversion, guard-rewrite arc item 1) so the call proceeds instead of bouncing back for recomposition; a legacy `<model>: ` title prefix, if present, must still mirror the model field and denies on mismatch — that check takes precedence over a pending name rewrite; per-policy deny/ask tiers; Workflow launches always ask; **escalation lane** — an ask-tier dispatch *from a subagent* is denied, not asked: escalation is the dispatcher's decision, the subagent returns the question |
| `brief-reminder` | PreToolUse Agent\|Task | **denies on the computable slice of §§1-2**, reminds on the judgment half. Light-tier dispatches (`light_tiers`, below) skip every form lane and pass after the channel and tail-mismatch checks. Three HARD deny lanes, all `Agent`-only, unaffected by `guard_modes`: a MAILBOX-lane (named) dispatch whose prompt names no report channel (a named agent's final text reaches no one); a pasted tail whose channel line contradicts the dispatch's lane — which `name` alone decides — either direction; an execution-tail brief missing its §1 grounding-basis or write-boundaries section. A brief lacking the §2 tail block — searched in the prompt *and* in any brief FILE the prompt names — is now MODE-AWARE and split by whether the brief's body DECLARES it writes (a write-boundary or commit-plan marker, the same body-marker idiom the section lane already uses): the DECIDABLE class is **rewritten**, not denied — `hookSpecificOutput.updatedInput` appends the shipped EXECUTION tail from `references/forms.md`, channel line filled from `name` presence, under both `deny` and `warn` (the repair is the action, not a punishment grade; 2026-09-15 verb conversion, guard-rewrite arc item 2); the AMBIGUOUS class (no such marker — read-only is never positively decided or auto-appended) keeps the deny, now demotable to `warn` for the first time. An execution-tail brief carrying no §1 commit-plan section stays a mode-aware deny (promoted from staged WARN 2026-09-15 on its fire record — 39 post-repair warn fires, no false fire recorded, df-238). Plus one staged WARN lane, ordered last so it can shadow no deny: an execution-tail brief naming a registered class devbook with no 64-hex fingerprint pin. The `guard_modes` key `brief-reminder` now governs THREE fire()-routed lanes (the missing-tail ambiguous-class exit, the promoted commit-plan deny, and the staged pin warn) — a site override moves all three together; `off` silences the missing-tail lane entirely for both its classes. Otherwise one reminder line before every dispatch (brief decision-complete? report channel named?), plus a non-blocking base advisory on `isolation: "worktree"` calls |
| `subagent-push-gate` | PreToolUse Bash | denies `git`/`gh` push in a subagent context — subagents commit unpushed, the dispatcher pushes after verification |
| `push-claim-reminder` | PreToolUse Bash | main-session push lanes: **denies a fused push** — one sharing its invocation with `git commit` or `git log`, since the read-then-decide seam only exists across separate invocations — and otherwise reminds to claim each outgoing commit (`git log origin/<branch>..<branch>`); subagent context excluded, `subagent-push-gate` already denies it |
| `amend-gate` | PreToolUse Bash | `git commit --amend` on a shared working copy: denies it flatly in a subagent context (amend is COMMIT-granular — it can swallow a co-writer's landed commit at HEAD; make a new commit instead), reminds in the main session (check `git log -1 --format=%(trailers)` shows your own trailer before amending) |
| `worktree-config-gate` | PreToolUse Bash | **staged, default-warn** — a shared-config write (`git remote add\|remove\|rename\|set-url\|set-head\|set-branches`, or a non-`--worktree` `git config` write) issued from inside a linked worktree, where it rewrites `.git/config` for every checkout including the main clone. `git remote` has no `--worktree` form at all, which is what makes it the trap. Worktree detection is git's own (`rev-parse --git-dir` vs `--git-common-dir`), run only after the token shape matches; the correct recipe (`git config --worktree …`) and writes aimed elsewhere (`--global`, `--system`, `--file`) never fire |
| `report-reminder` | PostToolUse Agent\|Task | one line next to every dispatch result: check the closing report, verify claims in the artifact |
| `report-enforcer` | SubagentStop | instructs a stopping subagent to actually SEND its closing report (a named/mailbox agent's final text reaches no one) |
| `message-payload-gate` | PreToolUse SendMessage | denies oversized string messages from a subagent to its dispatcher — payload belongs in a file, the message carries the pointer: an injected payload occupies the dispatcher's context for the rest of the session (it has also coincided with full prompt-cache rewrites — correlation recorded but unproven, `dev-notes/payload-cache-correlation.md`; the lane rests on context economy alone); dispatcher→subagent stays free |
| `dispatch-log` | PostToolUse Agent\|Task | appends one mechanical JSONL line per dispatch (`~/.local/share/claude/dispatch-log.jsonl`, `$CLAUDE_DISPATCH_LOG` override) |
| `discovery-volume-reminder` | PostToolUse Bash\|Grep\|Glob | advisory line when a search result ≥ `discovery_volume_bytes` lands in main-session context — the discovery-dispatch routing rule may apply; measures the harness's `persistedOutputSize`, since the hook-visible body is truncated |
| `report-form-gate` | PreToolUse SendMessage | **staged, default-warn** — a report-shaped subagent message (≥4 distinct `(a)`–`(h)` slot markers) missing required §2 slots a–g fires naming them; read-only (verifier/discovery) returns carry no markers and pass untouched |
| `writer-claims-gate` | PreToolUse+PostToolUse Write\|Edit | **staged, default-warn** — PostToolUse records subagent write claims (TTL `write_claim_ttl_hours`); PreToolUse fires on a cross-agent same-file write, and reminds (never denies) the main session when a live subagent claimed the file (§4 mirror duty). Claims store: `~/.local/share/claude/write-claims.jsonl` (`$CLAUDE_DISPATCH_GUARDS_CLAIMS` override) |
| `writer-reservation-gate` | PreToolUse Bash + PostToolUse Write\|Edit + Stop | **staged, default-warn** — reserves the whole WORKING COPY, not paths: PostToolUse claims it automatically on the first write, PreToolUse warns at `git commit` when a different, unexpired session holds it, Stop releases (90-min TTL otherwise). `git commit` takes the whole working-tree state of every path it names, so a disjoint path set is no defence — the commit is what serializes. Complements `writer-claims-gate`, which records SUBAGENT writes only and so cannot see a main-session co-writer. Record: `<git-dir>/writer-reservation.json`, never committed |

All guards fail open on hook-input parse errors and ship a `--test`
bite-test (`python3 hooks/<guard>.py --test`). Fail-open means a
broken guard goes quiet rather than bricking every call, so the
bite-tests are the compensation that matters — run them somewhere
that fails loudly (CI, a pre-push hook, or whatever health check you
already run on this machine).

## Fire log, guard modes, and the replay bench

Every guard fire — deny, ask, warn, block — appends one JSONL line
to `~/.local/share/claude/dispatch-guards-fires.jsonl`
(`$CLAUDE_DISPATCH_GUARDS_FIRELOG` override): ts, guard, mode,
session/agent, shape, truncated reason. Consumers: the fire-rate
review (fire rates become countable instead of remembered) and
warn→deny promotion decisions.

`shape` is what makes a fire *separable*: `reason` is constant per
lane, so counting fires never distinguished a false one from a true
one. It is a secret-free digest — verbs and flags only, operands
dropped, long flags stripped of any `=value` and short flags reduced
to their letter (a short flag can carry its value attached). So
`git remote set-url --push origin https://tok@host/r.git` logs as
`git remote set-url --push`, and `mysql -phunter2 -u root` as
`mysql -p -u`. Dispatch tools log their routing fields instead;
Write/Edit and SendMessage log no shape.

Per-guard modes via the `guard_modes` config key
(`{"<guard>": "deny"|"warn"|"off"}`): a lane in `warn` emits a
visible "would DENY" additionalContext line and logs, but does not
block — new speculative lanes ship default-warn and earn `deny`
through the fire-rate review against the log.

`tools/replay-bench.py` replays a curated corpus
(`tools/corpus/guards.jsonl`) of hook-input payloads through the
real guard scripts end-to-end (stdin → stdout JSON) and fails on
any missed catch or false fire — including the historical
false-fire regressions. It is both the deny-arm regression net and
the catch-rate/false-fire measurement; stateful guards
(writer-claims) carry their e2e inside their own `--test` instead.

## Optional site surfaces

A fresh install needs **none of these**. All three fail open to
working defaults — nothing below is required to run the guards; each
just lets you shape them to your site.

| Surface | Configures | When absent |
|---|---|---|
| `~/.claude/dispatch-guards.json` | tier policy — deny/ask tiers, guard modes, message/discovery thresholds (key-by-key reference: [Mechanism vs. policy](#mechanism-vs-policy), next section) | shipped defaults active: no tier denied, none forced to ask, every guard at its shipped mode |
| `~/.claude/readiness.json` | which recurring procedures are certified for a cheaper tier (dispatch skill §6) | loud, per dispatch: `brief-reminder` states no register was readable, treat as NO certified classes — dispatches still run, just without a certified cheap-tier shortcut ([What this does not ship](#what-this-does-not-ship)) |
| `references/routing.md`'s `## Site overlay` section | your concrete model lineup, cost/pool bindings, standing routing decisions ([a starter corpus](#a-starter-corpus--real-and-dated) below is a worked example; blank template: `references/routing-overlay-template.md`) | the portable tier-ROLE rules still apply — no concrete lineup, no stale numbers pretending to be yours |

Check what your install is actually running on:

```bash
python3 plugin/hooks/_dispatch_common.py --doctor
```

It prints, one surface at a time, the path consulted and the
effective state — reports only, never gates (exit 0 always).

## Mechanism vs. policy

The plugin ships generic defaults (no tiers denied, none forced to ask,
generic reminder wording). Site policy lives in
`~/.claude/dispatch-guards.json` (override path via
`$CLAUDE_DISPATCH_GUARDS_CONFIG`):

```json
{
  "models": ["sonnet", "opus", "haiku", "fable"],
  "deny_models": ["haiku"],
  "ask_models": ["fable"],
  "discipline_doc": "dispatch skill",
  "max_message_chars": 3000,
  "discovery_volume_bytes": 50000,
  "guard_modes": {"writer-claims-gate": "warn"},
  "write_claim_ttl_hours": 6,
  "light_tiers": true
}
```

- `models` — allowed lineup; drives the name-prefix check and the legacy title-prefix mirror.
- `deny_models` — dispatches to these tiers are refused with feedback.
- `ask_models` — every generic-type dispatch to these tiers forces the
  permission dialog (one operator yes/no per dispatch, before it starts).
  From a *subagent* the same tiers are denied outright (escalation lane):
  the dialog asks whether a dispatch is worth it, never whether the
  escalating agent should be the one deciding. Note the lane ignores the
  generic-type restriction — a pinned agent type is the same spend from
  the same context.
- `discipline_doc` — when set, reminder texts cite it (`… §1`, `… §2`);
  unset, wording stays generic.
- `max_message_chars` — payload-gate threshold for subagent→dispatcher
  messages (default 3000).
- `discovery_volume_bytes` — discovery-volume-reminder threshold for
  main-session search results (default 50000).
- `guard_modes` — per-guard deny-lane mode (`deny`/`warn`/`off`);
  unset guards keep their shipped default (`deny` for the
  established gates, `warn` for the staged report-form and
  writer-claims lanes).
- `write_claim_ttl_hours` — writer-claims freshness window
  (default 6).
- `light_tiers` — dispatch tiers (default `true`). A **read**
  dispatch (`subagent_type` Explore, Plan, claude-code-guide, or a
  feature-dev explorer/architect/reviewer, or any type whose brief
  carries `Writes: none` and no heavy word below) or a **small-write**
  dispatch (brief under 2000 chars, one `Writes: <path>[, <path>]`
  line naming at most two paths, and no push / publish / deploy /
  commit / release / merge / DB / artifact / served / email /
  delete word) skips `dispatch-skill-gate` and brief-reminder's form
  lanes (tail, sections, commit plan, devbook pin). The model gate
  and the mailbox channel lane still apply to every tier. Each light
  pass logs a `light-read` / `light-small-write` fire-log line.
  `false` puts every dispatch on the full tier.

## What this does not ship

This plugin is the mechanical half of a larger operating discipline;
the rest lives in its author's global instruction corpus and is
deliberately not bundled. None of it blocks use — the guards run on
their shipped defaults with no config file at all (verified: full
replay bench green under an empty policy path and a bare `HOME`, no
tier denied, no tier forced to ask). But two things the skills cite
have no local counterpart:

- **The model-routing table** — the concrete lineup. As of 0.7.0 the
  portable tier-choice RULES ship in the skill
  (`references/routing.md`, stated over tier roles: residual
  judgment, discovery's tier-insensitivity, review limits, the
  redo-one-tier-up correction); what still cannot ship is your
  overlay. The table is a measured, dated fact about one person's
  model lineup, so shipping the numbers as defaults would hand you
  someone else's stale cache. The shape travels, the numbers do not:
  rank the tiers you actually use on the axes that decide your
  dispatches — how hard a problem the tier handles unsupervised,
  output quality where taste matters, and what it costs you — then
  stamp it with a date and name what invalidates it (a lineup
  change, a pricing change). Add your standing decisions (review
  default, exceptions, denied tiers) and the always-loaded seam
  conventions routing.md's tail names, and keep all of it wherever
  your sessions already load instructions from. The `dispatch` skill
  still does not decide *whether* to delegate — that seam fires
  before any skill loads.
- **`~/.claude/readiness.json`**, the tier-readiness register behind
  skill §6. The plugin never creates it, by §6's own rule: a register
  nothing reads is dead weight. Ignore §6 until some recurring
  procedure actually earns certification, then create the file at
  that moment.
- **A spawn-depth cap.** The author additionally caps subagent
  nesting to one layer as site policy
  (`CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH=1`, against a harness
  default of 3). The guards neither require nor assume it — they are
  indifferent to depth — but a site adopting the routing layer
  generally wants it, since it is what keeps a dispatched agent from
  quietly becoming a dispatcher.

Citations reading "CLAUDE.md" inside the skills are provenance
labels — they mark where a rule came from, while the rule itself is
stated in full on the page. Without that corpus you lose the
footnote, not the rule. Two rules flipped direction in 0.10.0 and
are canonical HERE: the decision-complete bar (skill §1, with the
system-placement clause) and the veto-cheap naming conventions
(§1, the model rides the NAME). The author's corpus now points at
this skill for both; a site corpus keeps only the seam conventions
that fire before any skill loads (route line, intake gauge,
brief-family dispatch default) and the veto principle.

### A starter corpus — real, and dated

Rather than describe the missing layer abstractly, here is the
author's actual one, so the machinery is legible from a working
instance. Copy it and then correct it; do not adopt it unchanged.
**The numbers date fast** — they describe one model lineup on one
payment model, and the day either moves this table is wrong while
still reading as authoritative. That is the whole reason it is not a
shipped default.

The idea of scoring the tiers in a table like this comes from Theo
(<https://t3.gg>); the axes, the numbers, and the use made of them
here are this repo's own.

Routing table, 1–10, higher is better. Lineup as of 2026-07-31;
rankings as of 2026-07-18, unchanged pending operation evidence.

| model    | intelligence | taste |
|----------|--------------|-------|
| fable-5  | 9            | 9     |
| opus-5   | 7            | 8     |
| sonnet-5 | 5            | 7     |

*intelligence* = how hard a problem the tier handles unsupervised.
*taste* = code quality, API design, UI/UX, copy. **Cost is
deliberately not a column**: on a subscription the top tier may draw
from a separately capped pool, so cross-tier token comparisons are
the wrong currency — price your tiers by whichever budget runs out
first for you.

The rules the skills cite by name, in the shortest form that still
works. Your corpus can word them however it likes:

- **Dispatched work** — one writer per working copy; parallel
  writers need disjoint, brief-named ownership, and overlap means
  serialize. Integration (merge, push, publish) stays with the
  dispatcher, after verifying in the artifact itself. An agent's
  "done" is a claim; silence is never success.
- **Fresh-context verification** — a verifier receives the artifact
  and the question, never the dispatcher's reasoning, which would
  hand it the blind spot it exists to escape.
- **Done is the check's own output** — a completion claim carries
  the verifier's verbatim output, never a summary of it and never a
  launcher's exit status, which reports that a run happened rather
  than what it found.
- **Paraphrase drift** — a summary is a label over its body; book
  findings from the body, never from the label.
- **Whether to dispatch** — work whose design is already settled
  defaults to a dispatch, since the settled design is the brief
  already written; open judgment favours staying inline. This is the
  decision `dispatch` deliberately does not make for you.

## Install

```bash
claude plugin marketplace add <path-or-git-url of this repo>
claude plugin install dispatch-guards@dispatch-guards-marketplace
```

## Design notes

- One file per lifecycle event, shared logic in `_dispatch_common.py`.
- Fail-open by design: a broken guard must not brick every call — the
  bite-tests are the load-bearing compensation; register them in your
  machine-bootstrap doctor.
- Environment binding (as of 2026-07): a subagent context is marked by a
  non-empty `agent_id` in the hook input; if a harness change removes the
  field, the push gate silently treats everything as the main session.
