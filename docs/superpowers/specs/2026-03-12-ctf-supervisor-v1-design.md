# CTF Supervisor V1 Design

Date: 2026-03-12
Status: Validated design, ready for implementation planning

## Summary

This spec defines a first supervisor layer for CTF Destroyer that can import a challenge board, filter eligible challenges, prioritize the easiest actionable work first, run multiple challenge solvers in parallel when safe, and stop difficult challenges as `needs_human` without blocking the rest of the campaign.

The design keeps the existing mono-challenge orchestration model intact. The main change is the addition of a campaign-level state store and scheduler above the current `ctf-import` and `ctf-orchestrator` flows.

## Goals

- Add a `ctf-supervisor` entry point that imports a board source and executes a full point-in-time campaign run.
- Reuse existing challenge import and mono-challenge orchestration logic through Python services, not shelling out between CLIs.
- Support concurrent solving with two capacity controls:
  - maximum total parallel challenges
  - maximum parallel challenges that require a started remote instance
- Prioritize the simplest actionable challenges first.
- Allow simple human targeting controls:
  - repeated `--category`
  - repeated `--challenge` with exact or partial title matching
  - `--max-difficulty`
  - `--max-parallel-challenges`
  - `--max-instance-challenges`
  - `--retry-needs-human`
- Persist campaign state and resume correctly across repeated runs on the same board.
- Improve observability in CLI and Discord, including challenge-level command activity from workers.

## Non-Goals

- No automatic flag submission to the CTF platform.
- No rich web application in V1.
- No continuous daemon mode. V1 is run-once only.
- No autonomous second wave or repeated automatic requeueing of hard challenges. If a challenge reaches its budget, it becomes `needs_human`.
- No rewrite of the existing LangGraph mono-challenge flow into a new async engine.

## Product Decisions Captured

- V1 scope is the supervisor core only. Human UI beyond CLI and Discord is deferred.
- The supervisor must be able to drive board import, not just consume pre-made JSON files.
- A challenge is considered solved when a worker provides a plausible flag and supporting evidence. Humans submit flags manually.
- Challenges that require instance startup consume from a configurable parallel capacity pool.
- Challenges that exceed their budget become `needs_human` and are not retried automatically unless explicitly requested later.
- Prioritization is metadata-driven first: explicit difficulty when available, then points, then solves, then actionability, with previous failures reducing priority.
- The supervisor runs once per invocation, processes all matching work, and stops.
- Resume behavior:
  - skip `solved`
  - skip `needs_human` unless `--retry-needs-human`
  - resume `running` as `interrupted`
- Observability is CLI plus enriched Discord, with command activity posted in a dedicated thread per challenge.

## Existing System Baseline

The current project already has solid mono-challenge foundations:

- challenge normalization in [ctf_destroyer/challenges.py](/Users/tj/Documents/CTF-Destroyer/ctf_destroyer/challenges.py)
- workspace preparation in [ctf_destroyer/workspace.py](/Users/tj/Documents/CTF-Destroyer/ctf_destroyer/workspace.py)
- mono-challenge orchestration in [ctf_destroyer/cli.py](/Users/tj/Documents/CTF-Destroyer/ctf_destroyer/cli.py) and [ctf_destroyer/graph.py](/Users/tj/Documents/CTF-Destroyer/ctf_destroyer/graph.py)
- worker backends and command event parsing in [ctf_destroyer/workers.py](/Users/tj/Documents/CTF-Destroyer/ctf_destroyer/workers.py)
- challenge import in [ctf_destroyer/import_cli.py](/Users/tj/Documents/CTF-Destroyer/ctf_destroyer/import_cli.py) and [ctf_destroyer/importers/](/Users/tj/Documents/CTF-Destroyer/ctf_destroyer/importers)
- Discord thread creation and publishing in [ctf_destroyer/discord_sync.py](/Users/tj/Documents/CTF-Destroyer/ctf_destroyer/discord_sync.py)

The main architectural gap is not challenge solving. It is campaign-level coordination across many challenges.

## Recommended Architecture

The project should adopt Approach B:

- keep `ctf-import` and `ctf-orchestrator` as user-facing CLIs
- extract their business logic into reusable services
- add a campaign domain and supervisor runtime above them

The architecture becomes:

1. `Import service`
   Normalizes a board or challenge source into imported challenge records and enriched metadata.
2. `Challenge run service`
   Runs the existing mono-challenge orchestration for one challenge and emits structured events.
3. `Campaign domain`
   Stores campaign state, tracks challenge records, computes priority, handles resume.
4. `Supervisor runtime`
   Applies filters, manages concurrency, launches challenge runs, aggregates events, and produces final summaries.
5. `Observers`
   CLI output and Discord publishing subscribe to campaign and challenge events. They do not own state.

## Module Boundaries

### 1. Import Service

Responsibility:
- load a source board or challenge source
- discover candidate challenges
- import selected challenges into the canonical project payload format
- enrich imported metadata needed by the supervisor

Required extraction:
- `ctf-import` becomes a wrapper around internal functions instead of owning the flow

Recommended API:

```python
@dataclass(frozen=True)
class BoardImportRequest:
    source: str | None
    input_file: Path | None
    session_cookie: str | None
    cookie_file: Path | None
    start_instance: bool

def discover_board_candidates(request: BoardImportRequest) -> list[DiscoveredChallenge]: ...
def import_board(request: BoardImportRequest) -> list[ImportedChallenge]: ...
def import_selected_candidates(
    request: BoardImportRequest,
    categories: list[str] | None = None,
    challenge_filters: list[str] | None = None,
) -> list[ImportedChallenge]: ...
```

Supervisor-specific metadata to add during import:

- `import_metadata.instance_required`: `true | false | "unknown"`
- `import_metadata.instance_source`: `ctfd_container | none | unknown`
- `import_metadata.start_instance_supported`: `true | false`
- `import_metadata.explicit_difficulty`: normalized value when clearly present in metadata or source text
- `import_metadata.board_source_key`: stable key derived from board origin for campaign resume

The import service must expose instance-related facts explicitly. The scheduler must not infer instance need by scraping free-form challenge descriptions.

### 2. Challenge Run Service

Responsibility:
- validate a challenge is actionable
- prepare or reopen the challenge workspace
- load challenge-local resume state
- run the existing LangGraph orchestration for one challenge
- emit challenge lifecycle and worker command events
- generate writeup when solved
- publish challenge-local side effects such as Discord thread creation

Required extraction:
- the current `main()` flow in [ctf_destroyer/cli.py](/Users/tj/Documents/CTF-Destroyer/ctf_destroyer/cli.py) becomes an internal service plus CLI wrapper

Recommended API:

```python
@dataclass(frozen=True)
class ChallengeRunRequest:
    challenge_payload: dict[str, Any]
    backend_sequence: list[str]
    max_attempts: int
    skills_root: Path
    workspace_root: Path
    thread_id: str
    discord_config: DiscordConfig | None

@dataclass(frozen=True)
class ChallengeRunResult:
    challenge_key: str
    workspace: Path
    solved: bool
    final_flag: str | None
    stop_reason: str
    attempts: int
    final_summary: str
    history: list[dict[str, Any]]
    working_memory: dict[str, Any]

def run_challenge(
    request: ChallengeRunRequest,
    event_sink: Callable[[str, dict[str, Any]], None] | None = None,
) -> ChallengeRunResult: ...
```

The existing LangGraph challenge flow should remain the source of truth for one challenge. The supervisor must call this service, not bypass it.

### 3. Campaign Domain

Responsibility:
- model campaign state
- map imported challenges to tracked campaign records
- compute priority
- determine eligibility
- handle resume and final summaries

Recommended package layout:

- `ctf_destroyer/campaign/models.py`
- `ctf_destroyer/campaign/state.py`
- `ctf_destroyer/campaign/priorities.py`
- `ctf_destroyer/campaign/filters.py`
- `ctf_destroyer/campaign/persistence.py`

### 4. Supervisor Runtime

Responsibility:
- execute a run-once campaign loop
- honor global and instance-bound capacity limits
- keep work moving when some challenges are blocked by scarce instance slots
- create campaign-level events for CLI and Discord

Recommended package layout:

- `ctf_destroyer/supervisor.py`
- `ctf_destroyer/supervisor_cli.py`

### 5. Observers

Responsibility:
- render campaign state for humans
- never own scheduling logic

Outputs:
- CLI progress lines and final summary
- campaign-level Discord summary thread or message stream
- challenge-level Discord thread updates and worker command activity

## Data Model

### Campaign Workspace

Each board key targets one persistent campaign directory reused across repeated run-once invocations:

```text
.campaigns/<board-slug>-<hash>/
```

This directory is separate from `.challenges/`. A new supervisor invocation for the same board key reopens and updates the same campaign directory instead of creating a fresh one.

Recommended files:

- `campaign.json`
  Canonical campaign state and challenge table
- `events.jsonl`
  Append-only campaign event log
- `imported-board.json`
  Last imported canonical board snapshot used to build the backlog
- `summary.md`
  Human-readable campaign summary after completion
- `.discord-campaign-thread.json`
  Local binding for campaign-level Discord thread if enabled

### Tracked Challenge Record

Each tracked challenge in `campaign.json` should contain:

```json
{
  "challenge_key": "board-key:patient-portal:31",
  "challenge_name": "Patient Portal",
  "workspace": "/abs/path/.challenges/patient-portal-12345678",
  "category": "web",
  "explicit_difficulty": "easy",
  "points": 100,
  "solves": 250,
  "instance_required": true,
  "instance_source": "ctfd_container",
  "status": "pending",
  "priority_score": 120,
  "priority_tuple": [0, 100, -250, 0, 0],
  "campaign_attempts": 0,
  "previous_failures": 0,
  "last_summary": "",
  "final_flag": null,
  "import_metadata": {},
  "challenge_payload": {}
}
```

### Challenge Statuses

The campaign-level status machine is:

- `pending`
  Eligible and not running yet
- `running`
  Currently executing a mono-challenge run
- `solved`
  Flag found and recorded locally
- `needs_human`
  Challenge exhausted its budget and should not be retried automatically
- `skipped`
  Imported but excluded by filters or policy
- `import_failed`
  Board import discovered the challenge but could not produce a usable payload
- `interrupted`
  Previously running challenge whose supervisor run ended unexpectedly

These statuses are campaign-level and do not replace challenge-local run history in `.challenges/.../.runs`.

## Priority and Eligibility Model

### Eligibility

A challenge is eligible when all of the following are true:

- it matches category filters if any were supplied
- it matches title filters if any were supplied
- it does not exceed `--max-difficulty` when explicit difficulty is known
- it is not `solved`
- it is not `needs_human`, unless `--retry-needs-human` is set
- it is not currently `running`
- it is actionable enough to launch

`skipped` is a persistent classification in the campaign snapshot, but skipped challenges may be reevaluated on later runs if the filter set changes.

`--max-difficulty` applies only to challenges with a clearly normalized explicit difficulty. Unknown difficulty remains eligible by default, because the product requirement is to enforce a maximum only when difficulty is clearly defined.

### Difficulty Normalization

Difficulty rank for V1:

- `easy`
- `medium`
- `hard`
- unknown difficulty sorts after explicit easy and medium, but before hard only if other actionability signals are clearly favorable

Normalization sources:

- explicit metadata values already present in imported payload
- textual labels such as `easy`, `medium`, `hard` if clearly isolated and trustworthy

The import layer should not guess exotic difficulty ladders in V1. Ambiguous values remain unknown.

### Priority Ordering

Priority should be deterministic and explainable.

Recommended tuple sort:

1. `difficulty_rank`
2. `points` ascending
3. `solves` descending
4. `actionability_rank`
5. `previous_failures` ascending
6. stable tiebreaker based on challenge name

Where:

- lower `difficulty_rank` is better
- lower `points` means likely easier and preferred first
- higher `solves` means likely easier and preferred first
- better `actionability_rank` means:
  - easiest: offline or with clear artifacts
  - next: clear `target_host`
  - next: challenge text only
  - worst: incomplete or weakly actionable imports
- `previous_failures` lowers priority to avoid repeatedly spending capacity on bad bets

The campaign should store both the normalized score and a human-readable explanation string for each challenge, because the CLI summary must make scheduling decisions understandable under competition pressure.

## Capacity Model

The supervisor enforces two independent limits:

- `--max-parallel-challenges`
  Maximum number of challenges running simultaneously
- `--max-instance-challenges`
  Maximum number of `instance_required` challenges running simultaneously

Behavior:

- a challenge that does not require an instance only consumes the global limit
- a challenge that requires an instance consumes both limits
- if the highest-priority challenge cannot start because the instance pool is full, the scheduler must continue scanning the queue for the next eligible non-instance or otherwise schedulable challenge
- a blocked instance-bound challenge must not stall the full campaign

This is intentionally a capacity gate, not a lock per platform or host. The product decision for V1 is a configurable shared pool.

## Scheduler Behavior

### Run-Once Campaign Flow

1. Load source and import board candidates.
2. Convert candidates into canonical imported challenges.
3. Merge imported results with the existing campaign state for the same board key.
4. Reclassify stale `running` entries as `interrupted`.
5. Recompute eligibility and priority.
6. Build a priority queue of `pending` work.
7. Launch challenges while capacity permits.
8. Consume challenge completion events and update campaign state.
9. Continue until:
   - no pending work remains
   - no running work remains
10. Write final campaign summary and return exit status.

### Budget Model

V1 uses a single campaign launch per challenge per run.

That means:

- the mono-challenge orchestrator still owns worker-level retries through its existing `--max-attempts`
- the supervisor does not requeue the same challenge automatically within the same campaign run
- if the challenge finishes unsolved after its mono-challenge budget, the campaign status becomes `needs_human`

This is intentionally simple. It prevents silent waste and keeps state easy to reason about during a CTF.

### Interruption Semantics

If the supervisor process exits unexpectedly:

- all currently `running` challenges become `interrupted` in `campaign.json`
- their challenge-local workspaces remain intact
- the next run treats `interrupted` as eligible for relaunch

This avoids losing work while keeping campaign state honest.

## Resume Model

Resume key:

- a stable board-level campaign key derived from source origin and imported board metadata

On rerun with the same board key:

- `solved` challenges are skipped
- `needs_human` challenges are skipped unless `--retry-needs-human` is set
- `running` is rewritten to `interrupted`
- `interrupted` becomes eligible again
- priority is recalculated from current metadata plus previous failures

The challenge-local resume model already present in `.challenges/.../.runs` remains active. The campaign-level resume decides whether to relaunch. The challenge-level resume decides what context the next mono-challenge run sees.

## Streaming Event Model

The supervisor requires an event stream that is richer than the current attempt-completed publishing.

Recommended event types:

- `campaign_started`
- `campaign_import_completed`
- `campaign_challenge_discovered`
- `campaign_challenge_skipped`
- `campaign_challenge_enqueued`
- `campaign_challenge_started`
- `campaign_challenge_completed`
- `campaign_completed`
- `challenge_route_resolved`
- `challenge_attempt_completed`
- `worker_command_started`
- `worker_command_completed`
- `worker_stdout_excerpt`

The event stream serves three goals:

- CLI progress output
- Discord publishing
- persistent audit trail in `events.jsonl`

Observers receive events. They never mutate scheduling state.

## Worker Command Activity

The user explicitly wants visibility into the effective work being performed by workers.

Current baseline:

- worker subprocesses already capture event streams and can parse command execution events
- command events are only fully available after a worker attempt finishes

V1 requirement:

- when possible, publish command activity during execution, not only after completion

Design change:

- extend worker invocation to accept an optional live event callback
- while streaming subprocess stdout, parse command events incrementally
- emit:
  - `worker_command_started`
  - `worker_command_completed`
- preserve existing post-run command extraction as fallback for providers or runs where live parsing is unavailable

This keeps Discord and CLI closer to real-time without changing the worker result contract.

## Discord Design

Discord stays an observer, not the system of record.

### Campaign-Level Publishing

Add a campaign-level thread or summary stream that includes:

- board source
- applied filters
- capacity configuration
- counts of pending, running, solved, needs_human, skipped
- campaign completion summary

### Challenge-Level Publishing

Continue the existing thread-per-challenge model, but enrich it with:

- challenge start from the supervisor
- route resolution
- command activity during worker execution when available
- attempt completion summary
- final solved or needs_human status
- writeup on solved challenges

Command posting rules:

- stream high-signal commands only
- deduplicate repeated commands when a worker emits noisy retried shells
- truncate aggressively to avoid Discord spam

Campaign and challenge Discord publishing should share the same event bus but use separate renderers.

## CLI Design

### New CLI

Add `ctf-supervisor` with flags:

- `--source <url|file|->`
- `--input-file <path>` when applicable
- `--session-cookie <value>`
- `--cookie-file <path>`
- `--start-instance-when-needed`
- `--category <value>` repeatable
- `--challenge <value>` repeatable
- `--max-difficulty easy|medium|hard`
- `--max-challenges <n>`
- `--max-parallel-challenges <n>`
- `--max-instance-challenges <n>`
- `--retry-needs-human`
- `--backend-sequence <providers>`
- `--max-attempts <n>`
- `--workspace <path>`
- `--skills-root <path>`
- `--env-file <path>`
- Discord flags reused from current CLIs

### CLI Output

V1 CLI should provide:

- import summary
- filtered challenge count
- queue ordering preview
- capacity changes and challenge launch decisions
- running challenge table with status snapshots
- completion lines for solved and needs_human outcomes
- final campaign summary

The summary must be fast to scan in a terminal during active competition.

## Error Handling

### Import Errors

- If board import fails completely, the campaign exits with a non-zero status and writes a failure summary.
- If an individual challenge import fails, that challenge becomes `import_failed` and the campaign continues.
- If `--start-instance-when-needed` was requested and a needed instance cannot be acquired during import, the imported challenge should be marked not actionable and excluded from launch.

### Challenge Launch Errors

- If challenge workspace preparation fails, the challenge becomes `needs_human` only if the error is challenge-specific and persistent.
- If the failure is clearly transient infrastructure or configuration, the campaign marks the challenge `interrupted` and surfaces the error in the summary.

### Worker Errors

- Existing worker timeout and blocked semantics remain unchanged at the mono-challenge layer.
- After a mono-challenge run ends unsolved, the supervisor marks `needs_human`.

### Supervisor Errors

- On uncaught termination, persist campaign state before exit whenever possible.
- Mark all active challenges as `interrupted`.

## Testing Strategy

### Unit Tests

- difficulty normalization
- title/category filter behavior
- partial title matching
- priority ordering
- actionability ranking
- resume state transitions
- capacity gate enforcement
- queue scanning when a high-priority instance-bound challenge is blocked by the instance pool

### Integration Tests

- import board and schedule only crypto challenges
- import board and schedule only a repeated set of challenge names
- skip solved and needs_human by default on rerun
- re-enable needs_human with `--retry-needs-human`
- run multiple offline challenges in parallel
- enforce instance-bound pool limit
- preserve mono-challenge resume behavior
- emit campaign and challenge Discord events
- stream or fallback-publish worker commands correctly

### Regression Tests

- `ctf-import` standalone behavior remains unchanged for existing workflows
- `ctf-orchestrator` standalone behavior remains unchanged for existing workflows
- existing writeup generation behavior remains unchanged for solved challenges

## Refactor Strategy

The implementation should be a targeted refactor, not a rewrite.

Recommended sequence:

1. Extract import service from `ctf-import`.
2. Extract challenge run service from `ctf-orchestrator`.
3. Introduce campaign models and persistence.
4. Build the scheduler and supervisor CLI on top of those services.
5. Extend eventing for live worker command visibility.
6. Layer campaign-level Discord publishing on the same event bus.

This order preserves working functionality while exposing stable internal seams.

## Why This Design Is the Right Trade-Off

- It adds the missing campaign-level coordination without destabilizing the proven mono-challenge flow.
- It keeps scheduling deterministic and operator-readable.
- It models scarce instance capacity explicitly without overengineering platform-specific locks in V1.
- It prepares the project for a future web app by introducing an event bus and a clean campaign state model now.
- It preserves backward compatibility for `ctf-import` and `ctf-orchestrator`.

## Final Design Statement

V1 should add a persistent campaign domain and a run-once supervisor runtime above the existing import and mono-challenge services. The supervisor imports a board, filters eligible work, prioritizes the easiest actionable challenges first, respects both total and instance-bound concurrency limits, launches challenge runs through the existing orchestration service, emits structured events for CLI and Discord, and marks unsolved work as `needs_human` for explicit human follow-up.
