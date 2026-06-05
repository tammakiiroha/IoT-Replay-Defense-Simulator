# ReplayBench-IoT Overhaul Implementation Plan

**Goal:** Turn the existing IoT Replay-Defense Simulator into a research-grade, reproducible benchmark platform ("ReplayBench-IoT") by fixing P0 research-validity bugs, adding statistical rigor, modeling realistic channels/costs, introducing adaptive + standards-aligned defenses, and packaging it for public/academic use.

**Architecture:** The codebase is layered: `src/replay/core/` (pure simulation engine: sender/receiver/attacker/channel/experiment/stats), `src/replay/contracts/` (Pydantic models shared by CLI/API/Web), `src/replay/services/` (simulation + lab orchestration), `src/replay/api/` (FastAPI), `src/replay/cli/` (argparse CLI), and `web/` (Next.js demo). `sim/` and root wrappers (`main.py`, `api.py`) are thin re-export compatibility layers over `src/replay/core`. We extend the core engine with new strategy objects (channel models, authenticators, risk policy, cost model) behind protocols, surface them through contracts, and keep every change behind tests. Statistics utilities already prototyped in `physical_experiment/scripts/run_validation.py` (Wilson CI, Gilbert-Elliott) are promoted into `core`.

**Tech Stack:** Python 3.9+ (`from __future__ import annotations` everywhere), Pydantic v2, FastAPI, pytest, ruff, mypy, Next.js/TypeScript (ESLint), GitHub Actions. Optional: `ascon` (PyPI) for lightweight crypto profile, `PyYAML` (already a dependency) for presets.

---

## How To Use This Plan

- Execute tasks **in order**. Phases are gated: do not start Phase N+1 until Phase N's verification gate is green.
- Every code task follows TDD: write failing test → run it red → minimal implementation → run it green → commit.
- If the local shell lacks dev tools, bootstrap first: `python3 -m pip install -e ".[dev]"`. Do this before trusting any local `pytest`/`ruff`/`mypy` gate.
- **Always run tests with** `PYTHONPATH=src:. python3 -m pytest` (the package lives under `src/`, and legacy tests import the `sim.*` shim plus root modules).
- Keep `requires-python = ">=3.9"`. Do not use runtime generic subscripting (e.g. `list[int]()`); annotations are fine because of `from __future__ import annotations`.
- Reference skills with @ when helpful: @superpowers:test-driven-development, @superpowers:verification-before-completion, @superpowers:systematic-debugging.
- Commit message format: `<type>: <description>` (feat/fix/refactor/docs/test/chore/perf/ci). Attribution is disabled globally.

## Reconciliation Notes (differences from the original改造清单)

These are deliberate, evidence-based adjustments. They do **not** drop any checklist item; they correct premises.

1. **`._*` AppleDouble files:** none exist in this working copy (`find . -name '._*'` → 0) and none are git-tracked. The ESLint failure described in the checklist came from the uploaded tarball, not this repo. We still harden `.gitignore` and ESLint ignore as a guardrail (Tasks 1.1, 1.3) and add a cleanup script, but we will not claim to delete files that aren't there.
2. **Junk dirs in git:** `.venv/`, `web/node_modules/`, `web/.next/`, `web/out/`, `.mypy_cache/`, `.ruff_cache/`, `.pytest_cache/` are **not** tracked (verified via `git ls-files`). Only `.serena/` has 2 tracked files. So `git rm --cached` is mostly a no-op here; Task 1.2 runs it defensively with `--ignore-unmatch` and handles `.serena`.
3. **Wilson CI already exists** at `physical_experiment/scripts/run_validation.py:73` returning a `(lower, upper)` tuple, plus `StatisticalResult`. Task 3.1 promotes a typed `BinomialCI` into `core/stats.py` and refactors the physical script to import it (single source of truth).
4. **`GilbertElliottLoss` already exists** at `run_validation.py:150` with `should_drop(self)` owning its own RNG. Task 4.1 promotes a deterministic, RNG-injected variant into `core/channel_models.py` and refactors the physical script to reuse it.
5. **MAC length** is currently `8` **hex chars = 32 bits**. We migrate to a `mac_tag_bits` vocabulary (default 80) with a backward-compatible bridge so existing `mac_length` callers/tests keep working (Task 4.10).
6. **Receiver currently mutates `ReceiverState` in place.** Global coding-style prefers immutability, but the entire engine and its tests assume in-place mutation of a single `ReceiverState`. Rewriting to immutable state is out of scope and high-risk; we keep the existing mutation contract and isolate new fields additively. (Documented trade-off.)

---

## Post-Review Amendments (2026-06-05, three independent reviewers vs the real codebase)

> These amendments are **binding** and were produced by three independent reviewers who opened the real files. Every item is evidence-backed.
>
> **Status (2026-06-05):** all amendments A–I have now been **merged inline into the affected task bodies** (Tasks 2.1, 2.4, 3.3, 3.4, 4.2, 4.4, 4.6, 4.7b [new], 4.8, 4.9, 4.10, 5.1, and Risks). This section is retained as the consolidated change-log/rationale; the task bodies are authoritative and self-contained.

### A. TypeScript contracts are a HAND-WRITTEN template, not auto-generated (affects Tasks 2.4, 3.3, 3.4, 3.5, 4.2, 4.3, 4.4, 4.6, 4.8, 4.9, 4.10, 5.4) — **Critical**

`src/replay/contracts/typescript.py` has **no `__main__`/CLI entry**, and `render_typescript_contracts()` hard-codes the TS interfaces and `export type Mode = 'no_def' | 'rolling' | 'window' | 'challenge'` as string templates; only the bottom `jsonSchemas` block is auto-derived via `model_json_schema()`.

- **Do NOT** run `python3 -m replay.contracts.typescript > web/lib/contracts.ts` (it produces an empty file). Instead, after any model change: (1) hand-edit the template strings in `typescript.py` to add the new fields/enum members, then (2) call the existing `write_contract_artifacts(project_root)` (e.g. `PYTHONPATH=src python3 -c "from pathlib import Path; from replay.contracts.typescript import write_contract_artifacts; write_contract_artifacts(Path('.'))"`).
- **Every** task that adds a Pydantic field (2.4, 3.3, 3.4, 3.5, 4.2, 4.3, 4.4, 4.8, 4.10) or a `Mode` enum value (4.6 `hsw_cr`, 4.9 `oscore_like`) MUST include a sub-step: *"hand-edit `src/replay/contracts/typescript.py` template (interfaces + `export type Mode`) and regenerate via `write_contract_artifacts`."*
- `web/scripts/check-contracts.mjs` is a **substring check only** (asserts `contracts.ts` contains `"SimulationSpec"` and the manifest is non-empty). It does **not** validate fields, so it will **not** catch TS/Python drift. Treat green `test:contracts` as necessary-but-insufficient. Optionally strengthen the checker to assert the new field names exist; remove the plan's incorrect "if the checker hard-codes field lists" wording in Task 3.3.

### B. Task 2.4 must also fix the `_sample_batch` test helper — **Critical**

`tests/test_api.py:34` constructs `SimulationBatchResult(config=spec, ...)` with a **full `SimulationSpec`**. After `config` becomes `SimulationSpecPublic`, Pydantic v2 raises `ValidationError`, breaking `test_post_simulations_route_with_fake` (`:167`). Add an explicit step in Task 2.4: change the helper to `config=SimulationSpecPublic.from_spec(spec)`. (`from_spec` via `model_dump(exclude={"shared_key"})` + `model_validate` is verified correct and does not leak the key.)

### C. Task 4.2 Channel rewrite MUST preserve `flush()` and the `p_loss`/`p_reorder` attributes — **Critical**

The current `Channel` exposes `flush()` (`channel.py:46-52`), called at `experiment.py:107,116`. The proposed `__init__`/`send` replacement drops it → `AttributeError` in `simulate_one_run`. The amended `Channel` must keep `flush()` unchanged and keep `self.p_loss`/`self.p_reorder` (or audit and remove all readers). Full amended class:

```python
class Channel:
    def __init__(self, p_loss=0.0, p_reorder=0.0, rng=None, *,
                 loss_model=None, delay_model=None):
        from .channel_models import IidLoss, ReorderDelay
        self.p_loss = p_loss
        self.p_reorder = p_reorder
        self.rng = rng
        self.loss_model = loss_model if loss_model is not None else IidLoss(p_loss)
        self.delay_model = delay_model if delay_model is not None else ReorderDelay(p_reorder)
        self.pq: list[ScheduledFrame] = []
        self.current_tick = 0
        self.seq_counter = 0

    def send(self, frame):
        self.current_tick += 1
        if not self.loss_model.dropped(self.rng):
            delay = self.delay_model.delay(self.rng)
            heapq.heappush(self.pq, ScheduledFrame(self.current_tick + delay, self.seq_counter, frame))
            self.seq_counter += 1
        arrived = []
        while self.pq and self.pq[0].delivery_tick <= self.current_tick:
            arrived.append(heapq.heappop(self.pq).frame)
        return arrived

    def flush(self):  # UNCHANGED — must be kept
        arrived = []
        while self.pq:
            arrived.append(heapq.heappop(self.pq).frame)
        return arrived
```

### D. `test_web_engine_parity.py` does NOT guard RNG call order — **Important**

That file only tests contracts/manifest generation and reproducibility metadata. The plan's repeated claim (Tasks 4.1–4.3 and the Risks section) that it guards "byte-for-byte RNG order" is **false** — there is currently no test catching RNG-order drift. Amend Task 4.2 to **add a new test** `tests/test_channel.py::test_send_rng_call_order_unchanged` that fixes a seed, runs N `send()` calls through both the old-style (`Channel(p_loss=.., p_reorder=..)`) and the model-injected path, and asserts identical arrival sequences. Remove the false parity claims elsewhere.

### E. Authenticator abstraction must be WIRED into the verification main path — **Important** (architectural)

Tasks 4.7/4.8 build `Authenticator`/`HmacAuthenticator`/`AsconAuthenticator` in isolation, but nothing injects them into `receiver`/`experiment`; the main path still calls `security.compute_mac`, so the Ascon profile can never produce ASR/cost data. Amendments:
- Rename `AsconAuthenticator` → `AsconAeadAuthenticator` (match the checklist).
- Add **Task 4.7b: "Wire the HMAC Authenticator into the receiver/sender/experiment verification path"** — `Receiver`/`Sender` take an `authenticator: Authenticator` (default `HmacAuthenticator(key, mac_length * 4)`); `verify_with_rolling_mac`/`verify_with_window`/challenge/HSW-CR use `authenticator.tag/verify` instead of `compute_mac`/`constant_time_compare` directly. Keep Ascon out of 4.7b because `AsconAeadAuthenticator` is not defined until 4.8. Task 4.8 adds `auth_profile: Literal["hmac","ascon"] = "hmac"` plus the Ascon end-to-end test.

### F. Task 3.4 sequential stopping must not bypass the Task 2.5 budget cap — **Important**

`_validate_budget` uses `self.runs`, but sequential mode's real upper bound is `max_runs` (default 2000). Amend `_validate_budget` so the run factor is `max(self.runs, self.max_runs if self.target_ci_half_width is not None else 0)`; i.e. when `target_ci_half_width` is set, bound work by `max_runs`. Add a test asserting an oversized sequential spec (large `max_runs`) raises `ValidationError`.

### G. Tasks 4.6 (HSW-CR) and 4.9 (OSCORE-like) need concrete, TDD-able implementations — **Important**

These are the vaguest tasks and 4.6 is the most complex change (5 files, receiver state machine). Before executing, expand each into explicit code. For 4.6 specifically, pin down:
- **Attacker behavior on challenge frames:** the attacker records and replays frames; a replayed high-risk frame carries an *old* nonce that is now in `used_nonces` (or never outstanding) → rejected. State this in the test so the ASR≤0.05 assertion is derivable, not magical.
- **Decision rule:** receiver computes `risk = compute_risk(ctx, command_risk)`; if `risk >= risk_high` the command requires a fresh challenge nonce (issued that tick) and is verified via the challenge path; otherwise it flows through the sliding-window verifier. Document the exact `Receiver.process` HSW-CR branch and the experiment-side nonce issuance (mirror of the challenge loop at `experiment.py:83-84`) as real code, not prose.
- Treat the numeric thresholds as outcomes to *derive*, and if they cannot be met deterministically, weaken them to a comparative assertion (HSW-CR ASR ≤ rolling-counter ASR at the same loss) using @superpowers:systematic-debugging rather than tuning until green.

### H. Capability-downgrade disclosures (keep, but make explicit in the task bodies) — **Minor/Important**

- **Task 4.10:** the `mac_tag_bits ∈ {32,48,64,80,96,128}` sweep is currently only a sentence. Add a real `sweep_type="mac_tag_bits"` branch in `run_sweep` + a `SweepSpec` value path + a test, or explicitly mark it deferred with a `log`/README note. Do not present it as "done" if only documented.
- **Task 4.4:** promote `frr`, `energy_proxy`, `state_bytes`, `latency_ticks`, `challenge_round_trips`, `crypto_ops` to **typed `AggregateStats` fields** (not just `metadata` dict) since Task 5.3 (frontier figure) and 5.6 (advisor) consume them; a free-form dict is a fragile contract.
- **Task 4.3:** trace-driven loss is intentionally reduced to an in-memory `list[bool]`; the pcap/CSV trace loader is **out of scope** — say so in the README limitations (Task 5.1), don't imply real-trace ingestion.
- **Task 5.4 (web):** currently only glob-level; before executing, list the concrete components, state shape, and the request payload it sends. No front-end test beyond lint/contracts/build is planned — acceptable, but acknowledge the coverage gap.
- **Task 5.1 / standards:** NISTIR 8259A and ETSI EN 303 645 appear only as README "informative alignment" prose. If a standards→feature mapping table is wanted, add it as an explicit doc artifact; otherwise keep the honest "not a certification tool" framing.
- **Release (Task 5.9):** include GitHub Release-ready notes + `CHANGELOG.md`; a bare `git tag` is not enough for a real release.

### I. Minor accuracy fixes to apply when executing

- **Task 2.1:** `test_window_basic`'s `reason == "window_accept_new"` assertion already holds on the *old* code (the old `diff > window_size` branch returns the same reason). The genuine red→green comes from the replaced `test_window_too_far_ahead` and the new far-future test. Don't claim `test_window_basic` is the failing test.
- **`web/lib/contracts.ts` is currently untracked** by git; the first `git add` begins tracking it (no behavior change, just note it).

---

# PHASE 1 — Repository Hygiene & CI (make it public/CI-ready)

**Phase gate (must pass before Phase 2):**
```bash
python3 -m pip install -e ".[dev]"  # only needed once per environment
PYTHONPATH=src:. python3 -m pytest -q
npm --prefix web run lint
npm --prefix web run test:contracts
npm --prefix web run build   # may require a clean `npm ci` on Linux/CI; see Task 1.4
```

### Task 1.1: Harden `.gitignore`

**Files:**
- Modify: `.gitignore`

**Step 1: Append guardrail sections** (the file already has Python/venv/macOS blocks; add the missing explicit patterns and dedupe-safe entries). Append at end of `.gitignore`:

```gitignore

# === ReplayBench hardening (added 2026-06-05) ===
# macOS AppleDouble sidecars (anywhere in the tree)
._*
**/._*
.AppleDouble/
.LSOverride

# Python envs / caches (explicit, anywhere)
.venv/
**/__pycache__/
.ruff_cache/
.pytest_cache/
.mypy_cache/
.serena/cache/

# Web generated/dependency artifacts
web/node_modules/
web/.next/
web/out/
web/build/
web/tsconfig.tsbuildinfo

# Local env files
.env
.env.*
!.env.example
```

**Step 2: Verify nothing important is now ignored**

Run: `git status --porcelain | head -40` and `git check-ignore -v web/lib/contracts.ts`
Expected: `web/lib/contracts.ts` is NOT ignored (no output from check-ignore); tracked source files still appear normally.

**Step 3: Commit**

```bash
git add .gitignore
git commit -m "chore: harden gitignore for macOS sidecars, caches, and web build output"
```

### Task 1.2: One-shot working-tree cleanup + defensive untracking

**Files:**
- Create: `scripts/clean_repo.sh`

**Step 1: Write the cleanup script** `scripts/clean_repo.sh`:

```bash
#!/usr/bin/env bash
# Remove macOS sidecars and untrack generated/dependency dirs that should never be committed.
# Safe to run repeatedly. Does not touch source files.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "[clean_repo] deleting macOS sidecar files..."
find . -name '._*' -type f -not -path './.git/*' -delete || true
find . -name '.DS_Store' -type f -not -path './.git/*' -delete || true

echo "[clean_repo] untracking generated/dependency dirs (no-op if already untracked)..."
git rm -r --cached --ignore-unmatch \
  .venv \
  web/node_modules \
  web/.next \
  web/out \
  web/tsconfig.tsbuildinfo \
  .mypy_cache \
  .ruff_cache \
  .pytest_cache \
  .serena/cache >/dev/null 2>&1 || true

echo "[clean_repo] done. Review 'git status' before committing."
```

**Step 2: Make executable and run**

Run:
```bash
chmod +x scripts/clean_repo.sh && ./scripts/clean_repo.sh && git status --short
```
Expected: completes without error; only intended deletions/untrackings appear (likely just `.serena/cache` if present). No source `.py`/`.ts` files removed.

**Step 3: Commit**

```bash
git add scripts/clean_repo.sh
git add -A
git commit -m "chore: add repo cleanup script and untrack stray generated files"
```

### Task 1.3: Harden ESLint ignore

**Files:**
- Modify: `web/eslint.config.mjs:9-15`

**Step 1: Extend `globalIgnores`** so AppleDouble/DS_Store/node_modules can never break lint:

```javascript
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
    // ReplayBench hardening:
    "**/._*",
    "**/.DS_Store",
    "node_modules/**",
  ]),
```

**Step 2: Verify lint passes**

Run: `npm --prefix web run lint`
Expected: exits 0, no errors.

**Step 3: Commit**

```bash
git add web/eslint.config.mjs
git commit -m "chore(web): ignore macOS sidecars and node_modules in eslint"
```

### Task 1.4: Add GitHub Actions CI (python + web)

**Files:**
- Create: `.github/workflows/ci.yml`

**Step 1: Write the workflow** `.github/workflows/ci.yml`:

```yaml
name: ci

on:
  push:
  pull_request:

jobs:
  python:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: python -m pip install -e ".[dev]"
      - run: PYTHONPATH=src:. pytest -q
      - run: ruff check .
      - run: mypy src

  web:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: web
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: npm
          cache-dependency-path: web/package-lock.json
      - run: npm ci
      - run: npm run lint
      - run: npm run test:contracts
      - run: npm run build
```

**Step 2: Validate YAML locally**

Run: `python3 -c "import yaml,sys; yaml.safe_load(open('.github/workflows/ci.yml')); print('yaml-ok')"`
Expected: `yaml-ok`

**Step 3: Confirm `ruff check .` and `mypy src` pass locally before relying on CI**

Run: `ruff check . ; mypy src`
Expected: both exit 0. If pre-existing failures exist, fix them in a dedicated follow-up commit `fix: resolve pre-existing ruff/mypy findings` before merging CI (do not let CI start red).

**Step 4: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: add python (pytest/ruff/mypy) and web (lint/contracts/build) workflow"
```

### Task 1.5: Phase-1 verification gate

Run all four gate commands (top of Phase 1). Record results. If `npm run build` fails only due to SWC/registry/platform fetch in the local sandbox, note it and rely on the CI job (which runs `npm ci` on clean Linux). Do not proceed to Phase 2 until pytest + lint + contracts are green.

```bash
git commit --allow-empty -m "chore: phase-1 hygiene/CI gate verified"
```

---

# PHASE 2 — P0 Correctness (fixes that change research conclusions)

**Phase gate:** full test suite green, plus the new P0 tests below.

### Task 2.1: Standard sliding-window anti-replay semantics

**Problem:** `verify_with_window` rejects any counter more than `window_size` ahead (`counter_out_of_window`). Standard RFC-6479 sliding-window advances to an authenticated new right edge instead. This changes LAR/ASR under reordering and breaks the "RFC sliding window" claim.

**Files:**
- Modify: `src/replay/core/receiver.py:67-76`
- Modify/replace tests: `tests/test_receiver.py` (`test_window_basic`, `test_window_too_far_ahead`)
- Test: `tests/test_receiver.py` (add new cases)

**Step 1: Update the failing tests first.** Replace `test_window_too_far_ahead` (lines 90-99) and fix `test_window_basic` (lines 42-64). New/updated cases:

> **Note (review finding I):** the genuine red→green comes from the replaced `test_window_too_far_ahead` (old code returns `counter_out_of_window`; new code advances) and the new far-future test. `test_window_basic`'s `reason == "window_accept_new"` assertion already holds on the old code, so do not treat `test_window_basic` itself as the failing case.

```python
def test_window_basic(receiver_window):
    # Window size 5. Initial state last_counter = -1.
    f1 = create_frame(10)
    assert receiver_window.process(f1).accepted
    assert receiver_window.state.last_counter == 10

    # Standard sliding window: advancing forward is always accepted.
    f2 = create_frame(15)
    res = receiver_window.process(f2)
    assert res.accepted
    assert res.reason == "window_accept_new"
    assert receiver_window.state.last_counter == 15

    # Exact duplicate of the current right edge is a replay.
    res = receiver_window.process(create_frame(15))
    assert not res.accepted
    assert res.reason == "counter_replay"


def test_window_accepts_far_future_counter_and_advances(receiver_window):
    receiver_window.process(create_frame(10))

    res = receiver_window.process(create_frame(16))  # jump > window_size
    assert res.accepted
    assert res.reason == "window_accept_new"
    assert receiver_window.state.last_counter == 16

    # 10 is now far behind the right edge -> too old, not out-of-window.
    replay = receiver_window.process(create_frame(10))
    assert not replay.accepted
    assert replay.reason == "counter_too_old"
```

**Step 2: Run to verify failure**

Run: `PYTHONPATH=src:. python3 -m pytest tests/test_receiver.py -k window -v`
Expected: FAIL (`window_accept_new`/advance assertions fail; current code returns `counter_out_of_window`).

**Step 3: Implement standard sliding window.** Replace `src/replay/core/receiver.py` lines 67-76 (the `diff > 0` branch) with:

```python
    diff = frame.counter - state.last_counter
    if diff > 0:
        # Standard anti-replay sliding window (RFC 6479 semantics):
        # an authenticated counter ahead of the current right edge always
        # advances the window; it is never rejected for "jumping too far".
        if diff >= window_size:
            state.received_mask = 1
        else:
            state.received_mask = ((state.received_mask << diff) | 1) & mask_limit
        state.last_counter = frame.counter
        return VerificationResult(True, "window_accept_new", state)
```

(The `diff <= 0` old-packet branch on lines 78-86 is unchanged and remains correct.)

**Step 4: Run to verify pass**

Run: `PYTHONPATH=src:. python3 -m pytest tests/test_receiver.py -v`
Expected: PASS (including `test_window_out_of_order`, `test_window_too_old`, `test_window_mask_clamped`).

**Step 5: Commit**

```bash
git add src/replay/core/receiver.py tests/test_receiver.py
git commit -m "fix(core): implement standard RFC-6479 sliding-window anti-replay semantics"
```

> **Note on docs:** READMEs/PRESENTATION that previously described "bounded forward-gap" must be updated to "RFC-style sliding window" in Phase 5 (Task 5.1). If a bounded-gap variant is still wanted for low-cost devices, add it later as an explicit `max_forward_gap: int | None` extension — out of scope for this task.

### Task 2.2: Challenge-response with multiple outstanding nonces (+ caps/TTL)

**Problem:** `ReceiverState.expected_nonce` holds a single nonce; issuing a new challenge overwrites the previous one, so under reordering legitimate responses are wrongly rejected (observed LAR ≈ 0.72 at reorder=0.3). Add a bounded set of outstanding nonces with replay tracking and a TTL/size cap to prevent state-exhaustion abuse.

**Files:**
- Modify: `src/replay/core/types.py:45-51` (`ReceiverState`)
- Modify: `src/replay/core/defaults.py` (add caps)
- Modify: `src/replay/core/receiver.py:89-108` (`verify_challenge_response`) and `:148-155` (`issue_nonce`), `:114-119` (`Receiver.__init__`)
- Test: `tests/test_receiver.py` (add challenge cases)

**Step 1: Write failing tests** appended to `tests/test_receiver.py`:

```python
from sim.security import compute_mac as _compute_mac


def _challenge_frame(nonce, command="CMD"):
    return Frame(command=command, nonce=nonce,
                 mac=_compute_mac(nonce, command, SHARED_KEY, MAC_LENGTH))


def test_challenge_allows_two_outstanding_nonces_out_of_order():
    r = Receiver(Mode.CHALLENGE, shared_key=SHARED_KEY, mac_length=MAC_LENGTH)
    rng = random.Random(1)
    n1 = r.issue_nonce(rng)
    n2 = r.issue_nonce(rng)

    # Response for the *second* challenge arrives first, then the first.
    assert r.process(_challenge_frame(n2)).accepted
    assert r.process(_challenge_frame(n1)).accepted

    # Replaying n1 is rejected as a used nonce.
    replay = r.process(_challenge_frame(n1))
    assert not replay.accepted
    assert replay.reason == "challenge_replay"


def test_challenge_rejects_unknown_nonce():
    r = Receiver(Mode.CHALLENGE, shared_key=SHARED_KEY, mac_length=MAC_LENGTH)
    r.issue_nonce(random.Random(2))
    res = r.process(_challenge_frame("deadbeef"))
    assert not res.accepted
    assert res.reason == "challenge_mismatch"


def test_challenge_outstanding_cap_evicts_oldest():
    r = Receiver(Mode.CHALLENGE, shared_key=SHARED_KEY, mac_length=MAC_LENGTH,
                 max_outstanding_challenges=2)
    rng = random.Random(3)
    n1 = r.issue_nonce(rng)
    r.issue_nonce(rng)
    r.issue_nonce(rng)  # evicts n1 (oldest)
    res = r.process(_challenge_frame(n1))
    assert not res.accepted
    assert res.reason == "challenge_mismatch"
```

**Step 2: Run to verify failure**

Run: `PYTHONPATH=src:. python3 -m pytest tests/test_receiver.py -k challenge -v`
Expected: FAIL (`issue_nonce` overwrites; second outstanding nonce lost; `max_outstanding_challenges` kwarg unknown).

**Step 3: Extend `ReceiverState`** (`src/replay/core/types.py`):

```python
@dataclass
class ReceiverState:
    """Mutable state that the receiver persists across frames."""

    last_counter: int = -1
    expected_nonce: str | None = None  # legacy single-nonce / stop-and-wait compat
    received_mask: int = 0
    outstanding_nonces: dict[str, int] = field(default_factory=dict)  # nonce -> issue tick
    used_nonces: set[str] = field(default_factory=set)
```

**Step 4: Add caps to `defaults.py`:**

```python
DEFAULT_MAX_OUTSTANDING_CHALLENGES = 32
DEFAULT_CHALLENGE_TTL_TICKS = 100
```

Export them from `src/replay/core/__init__.py` (`from .defaults import (... DEFAULT_MAX_OUTSTANDING_CHALLENGES, DEFAULT_CHALLENGE_TTL_TICKS ...)` and add to `__all__`).

**Step 5: Rewrite `verify_challenge_response`** (`src/replay/core/receiver.py`):

```python
def verify_challenge_response(
    frame: Frame,
    state: ReceiverState,
    *,
    shared_key: str,
    mac_length: int,
) -> VerificationResult:
    if frame.nonce is None or frame.mac is None:
        return VerificationResult(False, "missing_challenge_fields", state)

    if frame.nonce in state.used_nonces:
        return VerificationResult(False, "challenge_replay", state)

    # Preferred path: bounded set of outstanding nonces (out-of-order safe).
    if state.outstanding_nonces:
        if frame.nonce not in state.outstanding_nonces:
            return VerificationResult(False, "challenge_mismatch", state)
        expected_mac = compute_mac(frame.nonce, frame.command, key=shared_key, mac_length=mac_length)
        if not constant_time_compare(expected_mac, frame.mac):
            return VerificationResult(False, "mac_mismatch", state)
        del state.outstanding_nonces[frame.nonce]
        state.used_nonces.add(frame.nonce)
        if frame.nonce == state.expected_nonce:
            state.expected_nonce = None
        return VerificationResult(True, "challenge_accept", state)

    # Legacy stop-and-wait fallback (single expected_nonce).
    if state.expected_nonce is None:
        return VerificationResult(False, "no_outstanding_challenge", state)
    if frame.nonce != state.expected_nonce:
        return VerificationResult(False, "challenge_mismatch", state)
    expected_mac = compute_mac(frame.nonce, frame.command, key=shared_key, mac_length=mac_length)
    if not constant_time_compare(expected_mac, frame.mac):
        return VerificationResult(False, "mac_mismatch", state)
    state.used_nonces.add(frame.nonce)
    state.expected_nonce = None
    return VerificationResult(True, "challenge_accept", state)
```

**Step 6: Update `Receiver.__init__` and `issue_nonce`** (`src/replay/core/receiver.py`):

```python
    def __init__(
        self,
        mode: Mode,
        *,
        shared_key: str,
        mac_length: int,
        window_size: int = 0,
        max_outstanding_challenges: int = DEFAULT_MAX_OUTSTANDING_CHALLENGES,
        challenge_ttl_ticks: int = DEFAULT_CHALLENGE_TTL_TICKS,
    ):
        self.mode = mode
        self.shared_key = shared_key
        self.mac_length = mac_length
        self.window_size = window_size
        self.max_outstanding_challenges = max_outstanding_challenges
        self.challenge_ttl_ticks = challenge_ttl_ticks
        self._issue_tick = 0
        self.state = ReceiverState()
```

```python
    def issue_nonce(self, rng: RandomLike, bits: int = 32, *, tick: int | None = None) -> str:
        if self.mode is not Mode.CHALLENGE:
            raise RuntimeError("Nonce issuance is only supported in challenge mode")
        nonce_int = rng.getrandbits(bits)
        hex_len = (bits + 3) // 4
        nonce_hex = f"{nonce_int:0{hex_len}x}"

        self._issue_tick = tick if tick is not None else self._issue_tick + 1
        # Expire stale outstanding nonces (TTL) before inserting.
        cutoff = self._issue_tick - self.challenge_ttl_ticks
        for stale in [n for n, t in self.state.outstanding_nonces.items() if t < cutoff]:
            del self.state.outstanding_nonces[stale]
        # Enforce size cap by evicting the oldest (FIFO on issue tick).
        while len(self.state.outstanding_nonces) >= self.max_outstanding_challenges:
            oldest = min(self.state.outstanding_nonces, key=self.state.outstanding_nonces.get)
            del self.state.outstanding_nonces[oldest]

        self.state.outstanding_nonces[nonce_hex] = self._issue_tick
        self.state.expected_nonce = nonce_hex  # keep legacy field meaningful
        return nonce_hex
```

Import the new defaults at the top of `receiver.py`:
`from .defaults import DEFAULT_MAX_OUTSTANDING_CHALLENGES, DEFAULT_CHALLENGE_TTL_TICKS`

**Step 7: Run to verify pass**

Run: `PYTHONPATH=src:. python3 -m pytest tests/test_receiver.py -v`
Expected: PASS (new challenge tests + existing `test_challenge_nonce_hex_length_rounds_up`).

**Step 8: Run full suite (regression check on experiment/services)**

Run: `PYTHONPATH=src:. python3 -m pytest -q`
Expected: PASS. (The simulation loop in `experiment.py:83-84` issues one nonce per legit frame; with the new set semantics it still accepts the matching response. Verify `test_experiment.py` LAR for challenge under reorder improves or stays valid.)

**Step 9: Commit**

```bash
git add src/replay/core/types.py src/replay/core/defaults.py src/replay/core/receiver.py src/replay/core/__init__.py tests/test_receiver.py
git commit -m "fix(core): support multiple outstanding challenge nonces with TTL and size cap"
```

### Task 2.3: Fix `run_sweep` falsy `0.0` handling

**Problem:** `simulation.py:48` `spec.fixed_p_loss or 0.10` turns an explicit `fixed_p_loss=0.0` into `0.10`. Same falsy risk for `fixed_p_reorder` (`:42`).

**Files:**
- Modify: `src/replay/services/simulation.py:33-63`
- Test: `tests/test_replay_services.py`

**Step 1: Write failing test** in `tests/test_replay_services.py`:

```python
def test_run_sweep_respects_explicit_zero_fixed_p_loss():
    from replay.contracts import SimulationSpec, SweepSpec
    from replay.services.simulation import run_sweep

    spec = SweepSpec(
        sweep_type="p_reorder",
        values=[0.0, 0.2],
        simulation=SimulationSpec(modes=["no_def"], runs=2, num_legit=3, num_replay=3, seed=1),
        fixed_p_loss=0.0,
    )
    points = run_sweep(spec, show_progress=False)
    assert all(p.result.p_loss == 0.0 for p in points)
```

**Step 2: Run to verify failure**

Run: `PYTHONPATH=src:. python3 -m pytest tests/test_replay_services.py -k explicit_zero -v`
Expected: FAIL (`p_loss == 0.10`).

**Step 3: Fix `run_sweep`** (`src/replay/services/simulation.py`) — replace the two branches:

```python
        if spec.sweep_type == "p_loss":
            scenario = simulation.model_copy(
                update={
                    "p_loss": float(value),
                    "p_reorder": (
                        spec.fixed_p_reorder if spec.fixed_p_reorder is not None else 0.0
                    ),
                }
            )
        elif spec.sweep_type == "p_reorder":
            scenario = simulation.model_copy(
                update={
                    "p_reorder": float(value),
                    "p_loss": (
                        spec.fixed_p_loss if spec.fixed_p_loss is not None else 0.10
                    ),
                }
            )
```

**Step 4: Run to verify pass**

Run: `PYTHONPATH=src:. python3 -m pytest tests/test_replay_services.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add src/replay/services/simulation.py tests/test_replay_services.py
git commit -m "fix(services): preserve explicit 0.0 fixed sweep params (is-not-None check)"
```

### Task 2.4: Stop echoing `shared_key` in API responses

**Problem:** `SimulationBatchResult.config` is a full `SimulationSpec`, which includes `shared_key`. The API returns it to clients. Introduce a public spec without the secret.

**Files:**
- Modify: `src/replay/contracts/models.py` (add `SimulationSpecPublic`, change `SimulationBatchResult.config`)
- Modify: `src/replay/services/simulation.py:simulate_batch`
- Modify: `tests/test_api.py` — **also fix the `_sample_batch` helper (`:34`)**: change `SimulationBatchResult(config=spec, ...)` to `config=SimulationSpecPublic.from_spec(spec)`, else Pydantic v2 raises `ValidationError` and `test_post_simulations_route_with_fake` (`:167`) breaks (review finding B).
- Modify: `src/replay/contracts/typescript.py`, `web/lib/contracts.ts`, `web/public/data/contracts.json` — **hand-edit the TS template** (`typescript.py` is NOT auto-generated; see Task 3.3 amended Step 3). Add `SimulationSpecPublic` and change `interface SimulationBatchResult` from `config: SimulationSpec` to `config: SimulationSpecPublic`.
- Test: `tests/test_api.py`

**Step 1: Write failing test** in `tests/test_api.py`:

```python
def test_simulation_response_redacts_shared_key():
    from fastapi.testclient import TestClient
    from replay.api.app import app

    client = TestClient(app)
    resp = client.post("/api/v1/simulations", json={
        "modes": ["no_def"], "runs": 2, "num_legit": 3, "num_replay": 3,
        "seed": 1, "shared_key": "TOP_SECRET_KEY",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert "TOP_SECRET_KEY" not in resp.text
    assert "shared_key" not in body["config"]
```

**Step 2: Run to verify failure**

Run: `PYTHONPATH=src:. python3 -m pytest tests/test_api.py -k redacts -v`
Expected: FAIL (key present in `config`).

**Step 3: Add `SimulationSpecPublic`** to `contracts/models.py` (place after `SimulationSpec`):

```python
class SimulationSpecPublic(ReplayBaseModel):
    """Public, secret-free view of a SimulationSpec for API/Web responses."""

    schema_version: SchemaVersion = "2026-03-16"
    modes: list[Mode]
    runs: int
    seed: int | None = None
    p_loss: float
    p_reorder: float
    window_size: int
    num_legit: int
    num_replay: int
    attack_mode: AttackMode
    mac_length: int
    attacker_record_loss: float
    inline_attack_probability: float
    inline_attack_burst: int
    challenge_nonce_bits: int
    target_commands: list[str] | None = None
    command_sequence: list[str] | None = None
    command_set: list[str] | None = None

    @classmethod
    def from_spec(cls, spec: "SimulationSpec") -> "SimulationSpecPublic":
        return cls.model_validate(spec.model_dump(exclude={"shared_key"}))
```

Change `SimulationBatchResult`:

```python
class SimulationBatchResult(ReplayBaseModel):
    schema_version: SchemaVersion = "2026-03-16"
    generated_at: datetime = Field(default_factory=_utc_now)
    config: SimulationSpecPublic
    results: list[SimulationResultRecord]
    metadata: dict[str, Any] = Field(default_factory=dict)
```

Export `SimulationSpecPublic` from `src/replay/contracts/__init__.py`.

**Step 4: Update `simulate_batch`** (`src/replay/services/simulation.py`):

```python
from replay.contracts import (
    SimulationBatchResult,
    SimulationResultRecord,
    SimulationSpec,
    SimulationSpecPublic,
    SweepPoint,
    SweepSpec,
)
...
    return SimulationBatchResult(
        generated_at=datetime.now(timezone.utc),
        config=SimulationSpecPublic.from_spec(spec),
        results=[SimulationResultRecord.from_aggregate(entry) for entry in stats],
        metadata={"mode_count": len(spec.modes)},
    )
```

Also update `app.py` legacy `/simulate` handler (`api/app.py:71-77`) — it already serializes `batch.config`, which is now public; no change needed beyond confirming the test for `/simulate` still passes.

**Step 5: Update TS contract template + regenerate artifacts**

Hand-edit `src/replay/contracts/typescript.py`:

- import/include `SimulationSpecPublic` in the schema bundle if needed.
- add an `export interface SimulationSpecPublic` that mirrors `SimulationSpec` minus `shared_key`.
- change `SimulationBatchResult.config` to `SimulationSpecPublic`.

Regenerate:

```bash
PYTHONPATH=src python3 -c "from pathlib import Path; from replay.contracts.typescript import write_contract_artifacts; write_contract_artifacts(Path('.'))"
npm --prefix web run test:contracts
```

Expected: `contracts-ok`. Manually confirm `web/lib/contracts.ts` contains no `shared_key` inside `SimulationSpecPublic`.

**Step 6: Run to verify pass + full suite**

Run: `PYTHONPATH=src:. python3 -m pytest tests/test_api.py -v && PYTHONPATH=src:. python3 -m pytest -q`
Expected: PASS. Update any existing test that asserted `config["shared_key"]` exists (it must now assert absence).

**Step 7: Commit**

```bash
git add src/replay/contracts/models.py src/replay/contracts/__init__.py src/replay/services/simulation.py tests/test_api.py src/replay/contracts/typescript.py web/lib/contracts.ts web/public/data/contracts.json
git commit -m "fix(api): redact shared_key from simulation responses via public spec schema"
```

### Task 2.5: Work-budget cap + field upper bounds on `SimulationSpec`

**Problem:** `runs`/`num_legit`/`num_replay` have only lower bounds; a public demo/API can be DoS'd with huge values.

**Files:**
- Modify: `src/replay/contracts/models.py:43-76`
- Test: `tests/test_replay_services.py`

**Step 1: Write failing test** in `tests/test_replay_services.py`:

```python
def test_simulation_spec_rejects_oversized_workload():
    import pytest
    from pydantic import ValidationError
    from replay.contracts import SimulationSpec

    with pytest.raises(ValidationError):
        SimulationSpec(modes=["no_def", "rolling"], runs=10000,
                       num_legit=10000, num_replay=10000)
```

**Step 2: Run to verify failure**

Run: `PYTHONPATH=src:. python3 -m pytest tests/test_replay_services.py -k oversized -v`
Expected: FAIL (no error raised).

**Step 3: Add caps** to `contracts/models.py`. Add a module constant and a validator; tighten fields:

```python
MAX_WORK_UNITS = 2_000_000
```

```python
    runs: int = Field(default=DEFAULT_RUNS, ge=1, le=10_000)
    ...
    num_legit: int = Field(default=DEFAULT_NUM_LEGIT, ge=0, le=10_000)
    num_replay: int = Field(default=DEFAULT_NUM_REPLAY, ge=0, le=10_000)
```

Extend the existing `_validate_window_size` validator (rename to `_validate_spec`) or add a second `model_validator(mode="after")`:

```python
    @model_validator(mode="after")
    def _validate_budget(self) -> "SimulationSpec":
        work_units = self.runs * max(1, len(self.modes)) * (self.num_legit + self.num_replay)
        if work_units > MAX_WORK_UNITS:
            raise ValueError(
                f"simulation too large: work_units={work_units} > {MAX_WORK_UNITS}"
            )
        return self
```

**Step 4: Run to verify pass + ensure defaults still valid**

Run: `PYTHONPATH=src:. python3 -m pytest tests/test_replay_services.py tests/test_api.py -q`
Expected: PASS. Default spec (200×4×120 = 96,000) is well under the cap.

**Step 5: Commit**

```bash
git add src/replay/contracts/models.py tests/test_replay_services.py
git commit -m "fix(contracts): cap simulation workload and field upper bounds to prevent DoS"
```

### Task 2.6: Subprocess timeout in lab service

**Problem:** `lab.py:119` `subprocess.run(..., check=True)` has no timeout; a hung hardware script blocks the API worker indefinitely.

**Files:**
- Modify: `src/replay/contracts/models.py` (`LabValidationSpec`)
- Modify: `src/replay/services/lab.py:103-119`
- Modify: `src/replay/api/app.py` (504 mapping)
- Test: `tests/test_replay_services.py`

**Step 1: Add `timeout_seconds` to `LabValidationSpec`:**

```python
    timeout_seconds: int = Field(default=600, ge=1, le=7200)
```

**Step 2: Write failing test** (asserts the field exists):

```python
def test_lab_spec_has_timeout_default():
    from replay.contracts import LabValidationSpec
    assert LabValidationSpec().timeout_seconds == 600
```

Run: `PYTHONPATH=src:. python3 -m pytest tests/test_replay_services.py -k timeout -v` → Expected: FAIL.

**Step 3: Pass timeout in `lab.py`:**

```python
        subprocess.run(command, cwd=root, check=True, timeout=spec.timeout_seconds)
```

And handle `subprocess.TimeoutExpired` in `api/app.py:post_lab_validations` by mapping it to HTTP 504:

```python
        except subprocess.TimeoutExpired as exc:
            raise HTTPException(status_code=504, detail=f"validation timed out: {exc}") from exc
```

(Add `import subprocess` at top of `api/app.py`.)

**Step 4: Run to verify pass**

Run: `PYTHONPATH=src:. python3 -m pytest tests/test_replay_services.py -k timeout -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add src/replay/contracts/models.py src/replay/services/lab.py src/replay/api/app.py tests/test_replay_services.py
git commit -m "fix(lab): add subprocess timeout and 504 mapping for validation runs"
```

### Task 2.7: ZMQ bind to localhost by default

**Problem:** Hardware scripts bind `tcp://*` (all interfaces): `experiment_runner.py:332,340`, `tx_flowgraph.py:148`, `attacker_flowgraph.py:67`, and `grc_generator.py` templates.

**Files:**
- Modify: `physical_experiment/scripts/experiment_runner.py:~332,340` (+ arg parsing)
- Modify: `physical_experiment/flowgraphs/tx_flowgraph.py:148`
- Modify: `physical_experiment/flowgraphs/attacker_flowgraph.py:67`
- Modify: `physical_experiment/flowgraphs/grc_generator.py:278,404`
- Test: `tests/test_physical_portability.py` (add a static-source assertion)

**Step 1: Add a `--bind-all` CLI flag** to `experiment_runner.py` argument parser (default localhost). At the parser:

```python
    parser.add_argument(
        "--bind-all", action="store_true",
        help="Bind ZMQ sockets to all interfaces (0.0.0.0). Default: localhost only.",
    )
```

Compute a bind host where the sockets are created and replace `tcp://*`:

```python
        bind_host = "*" if getattr(self, "bind_all", False) else "127.0.0.1"
        self.tx_socket.bind(f"tcp://{bind_host}:{self.tx_port}")
        ...
        self.rx_socket.bind(f"tcp://{bind_host}:{self.rx_port}")
```

(Thread `bind_all` into the runner object from parsed args. For `tx_flowgraph.py`/`attacker_flowgraph.py`, add an optional `bind_host: str = "127.0.0.1"` constructor parameter and use it in the `.bind(...)` calls; default localhost. For `grc_generator.py` templates, parameterize the host with a generator argument defaulting to `127.0.0.1`.)

**Step 2: Write a portability guard test** in `tests/test_physical_portability.py`:

```python
def test_zmq_sources_default_to_localhost():
    import pathlib
    root = pathlib.Path(__file__).resolve().parents[1] / "physical_experiment"
    checked = [
        root / "scripts" / "experiment_runner.py",
        root / "flowgraphs" / "tx_flowgraph.py",
        root / "flowgraphs" / "attacker_flowgraph.py",
        root / "flowgraphs" / "grc_generator.py",
    ]
    for path in checked:
        source = path.read_text(encoding="utf-8")
        assert 'bind("tcp://*:' not in source
        assert "bind('tcp://*:" not in source
        assert 'bind(f"tcp://*:' not in source
        assert "bind(f'tcp://*:" not in source
        assert "127.0.0.1" in source
    assert "--bind-all" in (root / "scripts" / "experiment_runner.py").read_text(encoding="utf-8")
```

Run: `PYTHONPATH=src:. python3 -m pytest tests/test_physical_portability.py -k localhost -v` → Expected: FAIL first, PASS after edits.

**Step 3: Commit**

```bash
git add physical_experiment/scripts/experiment_runner.py physical_experiment/flowgraphs/tx_flowgraph.py physical_experiment/flowgraphs/attacker_flowgraph.py physical_experiment/flowgraphs/grc_generator.py tests/test_physical_portability.py
git commit -m "fix(physical): default ZMQ binds to localhost with opt-in --bind-all"
```

### Task 2.8: Phase-2 verification gate

Run: `PYTHONPATH=src:. python3 -m pytest -q && ruff check . && mypy src`
Expected: all green. Then:

```bash
git commit --allow-empty -m "chore: phase-2 P0 correctness gate verified"
```

---

# PHASE 3 — Statistical Rigor (CIs, raw counts, sequential stopping, paired traces)

### Task 3.1: Promote Wilson CI into `core/stats.py` (typed `BinomialCI`)

**Files:**
- Create: `src/replay/core/stats.py`
- Modify: `src/replay/core/__init__.py` (export)
- Refactor: `physical_experiment/scripts/run_validation.py:73-143` to import from core
- Test: `tests/test_stats.py` (new)

**Step 1: Write failing test** `tests/test_stats.py`:

```python
import math
from replay.core.stats import BinomialCI, wilson_ci


def test_wilson_ci_zero_trials_is_full_interval():
    ci = wilson_ci(0, 0)
    assert ci.lower == 0.0 and ci.upper == 1.0 and ci.trials == 0


def test_wilson_ci_matches_reference_for_half():
    ci = wilson_ci(50, 100)  # p=0.5, n=100, z=1.96
    assert math.isclose(ci.point, 0.5)
    assert math.isclose(ci.lower, 0.4038, abs_tol=1e-3)
    assert math.isclose(ci.upper, 0.5962, abs_tol=1e-3)


def test_wilson_ci_bounds_are_clamped():
    ci = wilson_ci(100, 100)
    assert 0.0 <= ci.lower <= ci.upper <= 1.0
```

**Step 2: Run to verify failure**

Run: `PYTHONPATH=src:. python3 -m pytest tests/test_stats.py -v` → Expected: FAIL (module missing).

**Step 3: Implement `core/stats.py`:**

```python
"""Binomial-proportion statistics (Wilson score interval)."""
from __future__ import annotations

import math
from dataclasses import dataclass

_Z = {0.90: 1.645, 0.95: 1.96, 0.99: 2.576}


@dataclass(frozen=True)
class BinomialCI:
    point: float
    lower: float
    upper: float
    successes: int
    trials: int

    @property
    def half_width(self) -> float:
        return (self.upper - self.lower) / 2.0


def wilson_ci(successes: int, trials: int, confidence: float = 0.95) -> BinomialCI:
    if trials <= 0:
        return BinomialCI(0.0, 0.0, 1.0, 0, 0)
    z = _Z.get(confidence, 1.96)
    p = successes / trials
    denom = 1 + z * z / trials
    center = (p + z * z / (2 * trials)) / denom
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * trials)) / trials) / denom
    return BinomialCI(
        point=p,
        lower=max(0.0, center - margin),
        upper=min(1.0, center + margin),
        successes=successes,
        trials=trials,
    )


def ci_overlap(a: BinomialCI, b: BinomialCI) -> bool:
    return a.lower <= b.upper and b.lower <= a.upper
```

Export `BinomialCI`, `wilson_ci`, `ci_overlap` from `src/replay/core/__init__.py`.

**Step 4: Run to verify pass**

Run: `PYTHONPATH=src:. python3 -m pytest tests/test_stats.py -v` → Expected: PASS.

**Step 5: Refactor the physical script to reuse core** (single source of truth). In `physical_experiment/scripts/run_validation.py`, replace the local `wilson_ci`/`StatisticalResult` body with a thin adapter that calls `replay.core.stats.wilson_ci` and keeps the legacy `(lower, upper)` tuple return for existing callers:

```python
from replay.core.stats import wilson_ci as _core_wilson_ci

def wilson_ci(successes, trials, confidence=0.95):
    ci = _core_wilson_ci(successes, trials, confidence)
    return (ci.lower, ci.upper)
```

Run: `PYTHONPATH=src:. python3 -m pytest tests/test_physical_validation.py -q` → Expected: PASS (behavior preserved).

**Step 6: Commit**

```bash
git add src/replay/core/stats.py src/replay/core/__init__.py physical_experiment/scripts/run_validation.py tests/test_stats.py
git commit -m "feat(core): promote Wilson CI into core stats and reuse in physical script"
```

### Task 3.2: Track raw successes/trials + CIs through the engine

**Files:**
- Modify: `src/replay/core/types.py` (`AggregateStats` fields + `as_dict`)
- Modify: `src/replay/core/experiment.py` (accumulate raw counts, compute CI)
- Test: `tests/test_experiment.py`

**Step 1: Write failing test** in `tests/test_experiment.py`:

```python
def test_aggregate_exposes_raw_counts_and_ci():
    from replay.core import Mode, SimulationConfig, run_many_experiments
    cfg = SimulationConfig(mode=Mode.NO_DEFENSE, num_legit=5, num_replay=5, p_loss=0.0)
    stats = run_many_experiments(cfg, modes=[Mode.NO_DEFENSE], runs=10, seed=1, show_progress=False)
    s = stats[0]
    assert s.legit_total == 50 and s.legit_accepted == 50
    assert 0.0 <= s.lar_ci_low <= s.avg_legit_rate <= s.lar_ci_high <= 1.0
    assert "asr_ci_low" in s.as_dict()
```

**Step 2: Run to verify failure**

Run: `PYTHONPATH=src:. python3 -m pytest tests/test_experiment.py -k raw_counts -v` → Expected: FAIL.

**Step 3: Extend `AggregateStats`** (`core/types.py`) with additive fields (keep existing ones):

```python
    legit_accepted: int = 0
    legit_total: int = 0
    attack_accepted: int = 0
    attack_total: int = 0
    lar_ci_low: float = 0.0
    lar_ci_high: float = 0.0
    asr_ci_low: float = 0.0
    asr_ci_high: float = 0.0
```

Add these to `as_dict()` output.

**Step 4: Accumulate in `experiment.py`.** In `run_many_experiments`, maintain per-mode totals:

```python
    legit_acc: dict[Mode, int] = {m: 0 for m in modes}
    legit_tot: dict[Mode, int] = {m: 0 for m in modes}
    attack_acc: dict[Mode, int] = {m: 0 for m in modes}
    attack_tot: dict[Mode, int] = {m: 0 for m in modes}
```

Inside the run loop, after `result = simulate_one_run(...)`:

```python
            legit_acc[mode] += result.legit_accepted
            legit_tot[mode] += result.legit_sent
            attack_acc[mode] += result.attack_success
            attack_tot[mode] += result.attack_attempts
```

When building each `AggregateStats`, compute CIs:

```python
        from .stats import wilson_ci
        lar_ci = wilson_ci(legit_acc[mode], legit_tot[mode])
        asr_ci = wilson_ci(attack_acc[mode], attack_tot[mode])
        ... AggregateStats(
            ...,
            legit_accepted=legit_acc[mode], legit_total=legit_tot[mode],
            attack_accepted=attack_acc[mode], attack_total=attack_tot[mode],
            lar_ci_low=lar_ci.lower, lar_ci_high=lar_ci.upper,
            asr_ci_low=asr_ci.lower, asr_ci_high=asr_ci.upper,
        )
```

**Step 5: Run to verify pass + full suite**

Run: `PYTHONPATH=src:. python3 -m pytest tests/test_experiment.py -q && PYTHONPATH=src:. python3 -m pytest -q`
Expected: PASS.

**Step 6: Commit**

```bash
git add src/replay/core/types.py src/replay/core/experiment.py tests/test_experiment.py
git commit -m "feat(core): track raw legit/attack counts and Wilson CIs in aggregates"
```

### Task 3.3: Surface CIs through contracts, API, and web

**Files:**
- Modify: `src/replay/contracts/models.py` (`SimulationResultRecord`)
- Modify: `src/replay/contracts/typescript.py` (**hand-edit the TS interface template strings** — not auto-generated; see Step 3)
- Modify: `web/lib/contracts.ts` (regenerated via `write_contract_artifacts`, after the template edit)
- Test: `tests/test_api.py`, `tests/test_web_engine_parity.py`

**Step 1: Add fields to `SimulationResultRecord`** (`contracts/models.py`) and `from_aggregate`:

```python
    legit_accepted: int = 0
    legit_total: int = 0
    attack_accepted: int = 0
    attack_total: int = 0
    lar_ci_low: float = 0.0
    lar_ci_high: float = 0.0
    asr_ci_low: float = 0.0
    asr_ci_high: float = 0.0
```

In `from_aggregate`, map them from `entry.*`.

**Step 2: Write failing API test** asserting CI present:

```python
def test_simulation_result_includes_ci():
    from fastapi.testclient import TestClient
    from replay.api.app import app
    client = TestClient(app)
    body = client.post("/api/v1/simulations", json={
        "modes": ["no_def"], "runs": 5, "num_legit": 4, "num_replay": 4, "seed": 1,
    }).json()
    r0 = body["results"][0]
    assert "lar_ci_low" in r0 and "asr_ci_high" in r0
```

Run it red, then it passes once Step 1 lands.

**Step 3: Update the TS contracts (HAND-EDIT — they are NOT auto-generated; review finding A).** `src/replay/contracts/typescript.py` has **no `__main__`/CLI entry**, and `render_typescript_contracts()` hard-codes the `interface` blocks and `export type Mode = ...` as string templates (only the bottom `jsonSchemas` is auto via `model_json_schema()`). So:

1. Hand-edit the `SimulationResultRecord` interface template string in `typescript.py` to add `legit_accepted/legit_total/attack_accepted/attack_total/lar_ci_low/lar_ci_high/asr_ci_low/asr_ci_high`.
2. Regenerate the artifacts:
   `PYTHONPATH=src python3 -c "from pathlib import Path; from replay.contracts.typescript import write_contract_artifacts; write_contract_artifacts(Path('.'))"`
3. Run: `npm --prefix web run test:contracts`

Expected: `contracts-ok`. ⚠️ `web/scripts/check-contracts.mjs` only does a **substring check** (asserts `contracts.ts` contains `"SimulationSpec"` and the manifest is non-empty); it does **not** validate fields, so it will not catch TS/Python drift. Manually diff the interface against the Pydantic model. If you strengthen the checker to assert the new field names, add `web/scripts/check-contracts.mjs` to the commit; otherwise leave it untouched.

**Step 4: Run parity + commit**

Run: `PYTHONPATH=src:. python3 -m pytest tests/test_web_engine_parity.py tests/test_api.py -q`
Expected: PASS.

```bash
git add src/replay/contracts/models.py src/replay/contracts/typescript.py web/lib/contracts.ts web/public/data/contracts.json tests/test_api.py
git commit -m "feat(contracts): expose Wilson CIs and raw counts to API and web"
```

### Task 3.4: Sequential stopping (run until CI half-width ≤ ε)

**Files:**
- Modify: `src/replay/core/experiment.py` (new `run_until_precision`)
- Modify: `src/replay/contracts/models.py` (`SimulationSpec` optional `target_ci_half_width`, `max_runs`)
- Modify: `src/replay/contracts/typescript.py`, `web/lib/contracts.ts`, `web/public/data/contracts.json` (hand-edit + regenerate for the new spec fields)
- Modify: `src/replay/services/simulation.py`
- Test: `tests/test_experiment.py`

**Step 1: Write failing test:**

```python
def test_sequential_stopping_halts_when_precise():
    from replay.core import Mode, SimulationConfig
    from replay.core.experiment import run_until_precision
    cfg = SimulationConfig(mode=Mode.NO_DEFENSE, num_legit=10, num_replay=10, p_loss=0.0)
    stats, runs_used = run_until_precision(
        cfg, mode=Mode.NO_DEFENSE, target_half_width=0.02, max_runs=500, seed=1, min_runs=20,
    )
    assert runs_used <= 500
    assert stats.lar_ci_high - stats.lar_ci_low <= 0.04 + 1e-9 or runs_used == 500
```

**Step 2: Run red**, then implement `run_until_precision(config, *, mode, target_half_width, max_runs, seed, min_runs=30, metric="asr")` in `experiment.py`:

```python
def run_until_precision(config, *, mode, target_half_width, max_runs, seed,
                        min_runs=30, metric="asr"):
    """Run single-mode trials until the chosen metric's Wilson CI half-width
    drops to target_half_width, or max_runs is reached. Returns (AggregateStats, runs_used)."""
    from .stats import wilson_ci
    cfg = dataclasses.replace(config, mode=mode)
    mode_rng = DeterministicRNG(seed)
    la = lt = aa = at = 0
    legit_rates: list[float] = []
    attack_rates: list[float] = []
    runs_used = 0
    for _ in range(max_runs):
        runs_used += 1
        scenario_rng = DeterministicRNG(mode_rng.randint(0, 2**31 - 1))
        r = simulate_one_run(cfg, rng=scenario_rng)
        la += r.legit_accepted; lt += r.legit_sent
        aa += r.attack_success; at += r.attack_attempts
        legit_rates.append(r.legit_accept_rate); attack_rates.append(r.attack_success_rate)
        if runs_used >= min_runs:
            ci = wilson_ci(aa, at) if metric == "asr" else wilson_ci(la, lt)
            if ci.half_width <= target_half_width:
                break
    lar_ci = wilson_ci(la, lt); asr_ci = wilson_ci(aa, at)
    stats = AggregateStats(
        mode=mode, runs=runs_used,
        avg_legit_rate=_mean(legit_rates), std_legit_rate=_std(legit_rates),
        avg_attack_rate=_mean(attack_rates), std_attack_rate=_std(attack_rates),
        p_loss=cfg.p_loss, p_reorder=cfg.p_reorder,
        window_size=cfg.window_size if mode is Mode.WINDOW else 0,
        num_legit=cfg.num_legit, num_replay=cfg.num_replay, attack_mode=cfg.attack_mode,
        legit_accepted=la, legit_total=lt, attack_accepted=aa, attack_total=at,
        lar_ci_low=lar_ci.lower, lar_ci_high=lar_ci.upper,
        asr_ci_low=asr_ci.lower, asr_ci_high=asr_ci.upper,
        metadata={"stopping": "sequential", "target_half_width": target_half_width},
    )
    return stats, runs_used
```

**Step 3: Wire an optional spec field** `target_ci_half_width: float | None = None` and `max_runs: int = Field(default=2000, ge=1, le=20000)` into `SimulationSpec`; in `simulate_batch`, when set, loop modes through `run_until_precision`. Keep `runs` as the fixed-N path when the field is None.

**Step 3b: Close the budget bypass (review finding F).** Sequential mode's real run bound is `max_runs`, not `runs`, so the Task 2.5 `_validate_budget` must account for it — otherwise a large `max_runs` sails past `MAX_WORK_UNITS`. This **supersedes** the simpler validator from Task 2.5:

```python
    @model_validator(mode="after")
    def _validate_budget(self) -> "SimulationSpec":
        run_bound = max(self.runs, self.max_runs) if self.target_ci_half_width is not None else self.runs
        work_units = run_bound * max(1, len(self.modes)) * (self.num_legit + self.num_replay)
        if work_units > MAX_WORK_UNITS:
            raise ValueError(f"simulation too large: work_units={work_units} > {MAX_WORK_UNITS}")
        return self
```

Add a test asserting an oversized sequential spec (e.g. `target_ci_half_width=0.01, max_runs=20000, num_legit=200, num_replay=0`) raises `ValidationError`.

**Step 4: Update TS contract template + regenerate artifacts**

Add `target_ci_half_width?: number | null`, `max_runs: number`, and any returned `runs_used`/metadata fields you expose to the `typescript.py` templates; regenerate with `write_contract_artifacts(Path('.'))`; run `npm --prefix web run test:contracts`.

**Step 5: Run green + commit**

Run: `PYTHONPATH=src:. python3 -m pytest tests/test_experiment.py -q`
```bash
git add src/replay/core/experiment.py src/replay/contracts/models.py src/replay/contracts/typescript.py src/replay/services/simulation.py web/lib/contracts.ts web/public/data/contracts.json tests/test_experiment.py
git commit -m "feat(core): add sequential stopping by Wilson CI precision target"
```

### Task 3.5: Paired scenario traces (common random numbers)

**Problem:** Each mode consumes RNG differently (challenge draws nonces), so per-mode seeds drift; cross-mode comparisons carry avoidable noise. Generate one `ScenarioTrace` per run and replay all modes against it.

**Files:**
- Create: `src/replay/core/trace.py` (`ScenarioTrace`, `generate_trace`)
- Modify: `src/replay/core/experiment.py` (`simulate_one_run_with_trace`, `run_paired_experiments`)
- Modify: `src/replay/contracts/models.py`, `src/replay/contracts/typescript.py`, `web/lib/contracts.ts`, `web/public/data/contracts.json` (`SimulationSpec.paired`)
- Test: `tests/test_trace.py` (new)

**Step 1: Write failing test** `tests/test_trace.py`:

```python
def test_paired_runs_share_identical_channel_trace():
    from replay.core import Mode, SimulationConfig
    from replay.core.experiment import run_paired_experiments
    cfg = SimulationConfig(mode=Mode.NO_DEFENSE, num_legit=8, num_replay=8,
                           p_loss=0.3, p_reorder=0.3)
    stats = run_paired_experiments(cfg, modes=[Mode.ROLLING_MAC, Mode.WINDOW],
                                   runs=20, seed=7, show_progress=False)
    rolling = next(s for s in stats if s.mode is Mode.ROLLING_MAC)
    window = next(s for s in stats if s.mode is Mode.WINDOW)
    # This must not be a tautology like comparing legit_total (which is fixed by config).
    # The paired runner exposes per-run trace digests/drop counts as test hooks; these
    # prove both modes consumed the same generated trace.
    assert rolling.metadata["paired"] is True
    assert rolling.metadata["trace_digests"] == window.metadata["trace_digests"]
    assert rolling.metadata["legit_drop_counts_by_run"] == window.metadata["legit_drop_counts_by_run"]
    assert len(rolling.metadata["trace_digests"]) == 20
```

**Step 2: Run red**, then implement `core/trace.py`:

```python
"""Pre-generated per-run scenario traces for paired (common-random-number) comparison."""
from __future__ import annotations

from dataclasses import dataclass

from .rng import DeterministicRNG, RandomLike
from .types import SimulationConfig


@dataclass(frozen=True)
class ScenarioTrace:
    commands: list[str]
    legit_dropped: list[bool]
    legit_delay: list[int]
    attacker_record_dropped: list[bool]
    replay_pick: list[int]          # raw bits; resolved modulo recorded length at run time
    replay_dropped: list[bool]
    replay_delay: list[int]


def _draws(rng: RandomLike, p: float) -> bool:
    return p > 0 and rng.random() < p


def generate_trace(config: SimulationConfig, seed: int) -> ScenarioTrace:
    rng = DeterministicRNG(seed)
    commands, l_drop, l_delay, rec_drop = [], [], [], []
    space = list(config.effective_command_set())
    for i in range(config.num_legit):
        cmd = (config.command_sequence[i % len(config.command_sequence)]
               if config.command_sequence else rng.choice(space))
        commands.append(cmd)
        l_drop.append(_draws(rng, config.p_loss))
        l_delay.append(rng.randint(1, 3) if _draws(rng, config.p_reorder) else 0)
        rec_drop.append(_draws(rng, config.attacker_record_loss))
    r_pick, r_drop, r_delay = [], [], []
    for _ in range(config.num_replay):
        r_pick.append(rng.getrandbits(31))
        r_drop.append(_draws(rng, config.p_loss))
        r_delay.append(rng.randint(1, 3) if _draws(rng, config.p_reorder) else 0)
    return ScenarioTrace(commands, l_drop, l_delay, rec_drop, r_pick, r_drop, r_delay)
```

Then add `simulate_one_run_with_trace(config, trace)` to `experiment.py` that consumes the trace's pre-drawn loss/delay/command/pick decisions deterministically (no fresh RNG for channel/attacker), plus `run_paired_experiments(base_config, modes, runs, seed, show_progress)` that, for each run, builds one trace from a per-run seed and evaluates every mode against it, aggregating identically to `run_many_experiments`. Include metadata test hooks on every `AggregateStats`: `paired=True`, `trace_digests` (one stable hash per run), and `legit_drop_counts_by_run`.

> Keep `run_many_experiments` as-is for backward compatibility; `run_paired_experiments` is the new, statistically preferred entry point. Expose a `paired: bool = False` flag in `SimulationSpec` and route `simulate_batch` accordingly.

Hand-edit `typescript.py` to add `paired: boolean` to `SimulationSpec`, regenerate `web/lib/contracts.ts` and `web/public/data/contracts.json`, then run `npm --prefix web run test:contracts`.

**Step 3: Run green + full suite + commit**

Run: `PYTHONPATH=src:. python3 -m pytest tests/test_trace.py -q && PYTHONPATH=src:. python3 -m pytest -q`
```bash
git add src/replay/core/trace.py src/replay/core/experiment.py src/replay/core/__init__.py src/replay/contracts/models.py src/replay/contracts/typescript.py src/replay/services/simulation.py web/lib/contracts.ts web/public/data/contracts.json tests/test_trace.py
git commit -m "feat(core): add paired scenario traces for common-random-number comparison"
```

### Task 3.6: Phase-3 gate

Run: `PYTHONPATH=src:. python3 -m pytest -q && ruff check . && mypy src` → all green.
```bash
git commit --allow-empty -m "chore: phase-3 statistical-rigor gate verified"
```

---

# PHASE 4 — Realism & Innovation (channels, costs, adaptive + standards-aligned defenses)

### Task 4.1: Channel-model protocols + IID + Gilbert-Elliott (in core)

**Files:**
- Create: `src/replay/core/channel_models.py`
- Modify: `src/replay/core/__init__.py` (exports)
- Refactor: `physical_experiment/scripts/run_validation.py:150-245` to reuse core GE model (adapter keeping its `should_drop(self)` API)
- Test: `tests/test_channel_models.py` (new)

**Step 1: Write failing test** `tests/test_channel_models.py`:

```python
from replay.core.channel_models import IidLoss, GilbertElliottLoss
from replay.core.rng import DeterministicRNG


def test_iid_loss_is_deterministic_under_seed():
    rng_a, rng_b = DeterministicRNG(1), DeterministicRNG(1)
    a = [IidLoss(0.5).dropped(rng_a) for _ in range(50)]
    b = [IidLoss(0.5).dropped(rng_b) for _ in range(50)]
    assert a == b


def test_gilbert_elliott_bursts_more_than_iid_mean():
    rng = DeterministicRNG(2)
    ge = GilbertElliottLoss(p_good_to_bad=0.05, p_bad_to_good=0.3,
                            loss_good=0.0, loss_bad=1.0)
    drops = [ge.dropped(rng) for _ in range(2000)]
    assert any(drops) and max(_run_lengths(drops)) >= 2


def _run_lengths(flags):
    runs, cur = [], 0
    for f in flags:
        cur = cur + 1 if f else 0
        runs.append(cur)
    return runs
```

**Step 2: Run red**, then implement `core/channel_models.py`:

```python
"""Pluggable loss/delay models for the simulation channel."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .rng import RandomLike


class LossModel(Protocol):
    def dropped(self, rng: RandomLike) -> bool: ...


class DelayModel(Protocol):
    def delay(self, rng: RandomLike) -> int: ...


@dataclass
class IidLoss:
    p_loss: float

    def dropped(self, rng: RandomLike) -> bool:
        return self.p_loss > 0 and rng.random() < self.p_loss


@dataclass
class GilbertElliottLoss:
    """Two-state burst-loss Markov model. RNG is injected for reproducibility."""

    p_good_to_bad: float = 0.05
    p_bad_to_good: float = 0.30
    loss_good: float = 0.01
    loss_bad: float = 0.60
    in_bad_state: bool = False

    def dropped(self, rng: RandomLike) -> bool:
        if self.in_bad_state:
            if rng.random() < self.p_bad_to_good:
                self.in_bad_state = False
        else:
            if rng.random() < self.p_good_to_bad:
                self.in_bad_state = True
        p = self.loss_bad if self.in_bad_state else self.loss_good
        return rng.random() < p

    @property
    def steady_state_loss(self) -> float:
        denom = self.p_good_to_bad + self.p_bad_to_good
        p_bad = self.p_good_to_bad / denom if denom else 0.0
        return (1 - p_bad) * self.loss_good + p_bad * self.loss_bad


@dataclass
class ReorderDelay:
    p_reorder: float
    max_delay: int = 3

    def delay(self, rng: RandomLike) -> int:
        if self.p_reorder > 0 and rng.random() < self.p_reorder:
            return rng.randint(1, self.max_delay)
        return 0
```

Export the classes from `src/replay/core/__init__.py`.

**Step 3: Run green + refactor physical GE adapter** (keep its `should_drop()` API by wrapping a core `GilbertElliottLoss` + its own `random.Random`). Run `tests/test_physical_validation.py` to confirm parity.

**Step 4: Commit**

```bash
git add src/replay/core/channel_models.py src/replay/core/__init__.py physical_experiment/scripts/run_validation.py tests/test_channel_models.py
git commit -m "feat(core): add pluggable IID/Gilbert-Elliott loss and reorder-delay models"
```

### Task 4.2: Channel uses injected loss/delay models; config + API wiring

**Files:**
- Modify: `src/replay/core/channel.py`
- Modify: `src/replay/core/types.py` (`SimulationConfig`: `channel_model` + burst params)
- Modify: `src/replay/core/experiment.py` (build the right models from config)
- Modify: `src/replay/contracts/models.py` (`SimulationSpec` channel fields + `to_runtime_config`)
- Modify: `src/replay/contracts/typescript.py`, `web/lib/contracts.ts`, `web/public/data/contracts.json` (hand-edit + regenerate for channel fields)
- Test: `tests/test_channel.py`, `tests/test_experiment.py`

**Step 1: Write failing test** in `tests/test_channel.py`:

```python
def test_channel_accepts_explicit_loss_model():
    from replay.core.channel import Channel
    from replay.core.channel_models import IidLoss, ReorderDelay
    from replay.core.rng import DeterministicRNG
    from replay.core.types import Frame
    rng = DeterministicRNG(1)
    ch = Channel(loss_model=IidLoss(0.0), delay_model=ReorderDelay(0.0), rng=rng)
    arrived = ch.send(Frame(command="X"))
    assert len(arrived) == 1
```

**Step 2: Run red**, then refactor `Channel.__init__` to accept models while staying backward compatible:

```python
class Channel:
    def __init__(self, p_loss=0.0, p_reorder=0.0, rng=None, *,
                 loss_model=None, delay_model=None):
        from .channel_models import IidLoss, ReorderDelay
        self.p_loss = p_loss          # KEEP: read by callers/metadata
        self.p_reorder = p_reorder    # KEEP
        self.rng = rng
        self.loss_model = loss_model if loss_model is not None else IidLoss(p_loss)
        self.delay_model = delay_model if delay_model is not None else ReorderDelay(p_reorder)
        self.pq: list[ScheduledFrame] = []
        self.current_tick = 0
        self.seq_counter = 0

    def send(self, frame):
        self.current_tick += 1
        if not self.loss_model.dropped(self.rng):
            delay = self.delay_model.delay(self.rng)
            heapq.heappush(self.pq, ScheduledFrame(self.current_tick + delay, self.seq_counter, frame))
            self.seq_counter += 1
        arrived = []
        while self.pq and self.pq[0].delivery_tick <= self.current_tick:
            arrived.append(heapq.heappop(self.pq).frame)
        return arrived

    def flush(self):  # CRITICAL: must be kept — experiment.py:107,116 call it
        arrived = []
        while self.pq:
            arrived.append(heapq.heappop(self.pq).frame)
        return arrived
```

> **Review finding C:** the current `Channel` exposes `flush()` (`channel.py:46-52`) and `p_loss`/`p_reorder`. The earlier draft dropped them → `AttributeError` in `simulate_one_run`. The block above restores both.

> **RNG-order note (review finding D):** the new `IidLoss.dropped` and `ReorderDelay.delay` preserve the original call order (loss `random()`, then conditional reorder `random()`+`randint()`), so seeded IID output is unchanged. **But `tests/test_web_engine_parity.py` does NOT guard RNG call order** (it only tests contracts/manifest generation) — it will not catch drift. You MUST add the explicit regression test in Step 3c below.

**Step 3: Add config + spec fields.** `SimulationConfig`: `channel_model: str = "iid"`, `burst_p_good_to_bad: float = 0.05`, `burst_p_bad_to_good: float = 0.30`, `loss_good: float = 0.01`, `loss_bad: float = 0.60`. `SimulationSpec`: same fields with `Field(..., ge=0, le=1)` validation and `Literal["iid","gilbert_elliott","trace"]` for `channel_model`; thread through `to_runtime_config`. In `experiment.simulate_one_run`, build `loss_model` from config (`IidLoss` vs `GilbertElliottLoss`).

**Step 3c: Add the RNG-order regression test** (review finding D) in `tests/test_channel.py`:

```python
def test_send_rng_call_order_unchanged():
    # The model-injected IID path must consume RNG in the exact same order
    # as the legacy p_loss/p_reorder path, or seeded results silently drift.
    from replay.core.channel import Channel
    from replay.core.channel_models import IidLoss, ReorderDelay
    from replay.core.rng import DeterministicRNG
    from replay.core.types import Frame

    def run(make_channel):
        rng = DeterministicRNG(12345)
        ch = make_channel(rng)
        out = []
        for i in range(50):
            out += [f.command for f in ch.send(Frame(command=str(i)))]
        out += [f.command for f in ch.flush()]
        return out

    legacy = run(lambda rng: Channel(p_loss=0.3, p_reorder=0.3, rng=rng))
    injected = run(lambda rng: Channel(rng=rng, loss_model=IidLoss(0.3), delay_model=ReorderDelay(0.3)))
    assert legacy == injected
```

**Step 4: Update TS contract template + regenerate artifacts**

Add `channel_model`, `burst_p_good_to_bad`, `burst_p_bad_to_good`, `loss_good`, and `loss_bad` to the `SimulationSpec` interface in `typescript.py`; regenerate via `write_contract_artifacts(Path('.'))`; run `npm --prefix web run test:contracts`.

**Step 5: Run green + commit**

Run: `PYTHONPATH=src:. python3 -m pytest tests/test_channel.py tests/test_experiment.py -q`
```bash
git add src/replay/core/channel.py src/replay/core/types.py src/replay/core/experiment.py src/replay/contracts/models.py src/replay/contracts/typescript.py web/lib/contracts.ts web/public/data/contracts.json tests/test_channel.py
git commit -m "feat(core): inject loss/delay models into channel; expose Gilbert-Elliott via config"
```

### Task 4.3: Trace-driven loss model

**Files:**
- Modify: `src/replay/core/channel_models.py` (`TraceLoss`)
- Modify: `src/replay/core/experiment.py` (select `TraceLoss` when `channel_model == "trace"`)
- Modify: `src/replay/contracts/models.py` (`SimulationSpec.loss_trace: list[bool] | None`)
- Modify: `src/replay/contracts/typescript.py`, `web/lib/contracts.ts`, `web/public/data/contracts.json` (hand-edit + regenerate for `loss_trace`)
- Test: `tests/test_channel_models.py`

**Step 1: Write failing test:**

```python
def test_trace_loss_follows_provided_sequence():
    from replay.core.channel_models import TraceLoss
    from replay.core.rng import DeterministicRNG
    t = TraceLoss([True, False, True])
    rng = DeterministicRNG(0)
    assert [t.dropped(rng) for _ in range(4)] == [True, False, True, True]  # holds last on overflow
```

**Step 2: Run red**, then implement (decide wrap vs hold-last — test expects hold-last on overflow):

```python
@dataclass
class TraceLoss:
    drops: list[bool]
    _i: int = 0

    def dropped(self, rng: RandomLike) -> bool:
        if not self.drops:
            return False
        idx = min(self._i, len(self.drops) - 1)
        self._i += 1
        return self.drops[idx]
```

**Step 3:** Wire `loss_trace` from spec → config → `TraceLoss`. (A CSV/pcap trace loader can be added later; out of scope here.) Add `loss_trace?: boolean[] | null` to `typescript.py`, regenerate `web/lib/contracts.ts` and `web/public/data/contracts.json`, run `npm --prefix web run test:contracts`, then run green + commit:

```bash
git add src/replay/core/channel_models.py src/replay/core/experiment.py src/replay/contracts/models.py src/replay/contracts/typescript.py web/lib/contracts.ts web/public/data/contracts.json tests/test_channel_models.py
git commit -m "feat(core): add trace-driven loss model"
```

### Task 4.4: Cost / energy / latency model + metrics

**Files:**
- Create: `src/replay/core/cost.py`
- Modify: `src/replay/core/experiment.py` (accumulate byte/crypto/latency proxies)
- Modify: `src/replay/core/types.py` (`AggregateStats` typed cost fields)
- Modify: `src/replay/contracts/models.py` (`SimulationResultRecord` typed cost fields)
- Modify: `src/replay/contracts/typescript.py`, `web/lib/contracts.ts`, `web/public/data/contracts.json` (hand-edit + regenerate for typed cost fields)
- Test: `tests/test_cost.py` (new)

**Step 1: Write failing test** `tests/test_cost.py`:

```python
from replay.core.cost import CostModel, CostStats, estimate_energy


def test_estimate_energy_sums_components():
    stats = CostStats(tx_bytes=100, rx_bytes=100, hmac_ops=10, state_bytes_peak=8)
    e = estimate_energy(stats, CostModel())
    assert e > 0
    e2 = estimate_energy(CostStats(tx_bytes=200, rx_bytes=100, hmac_ops=10, state_bytes_peak=8), CostModel())
    assert e2 > e  # linear in tx bytes
```

**Step 2: Run red**, then implement `core/cost.py`:

```python
"""Energy/bandwidth/latency proxy model for low-cost IoT constraints."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CostModel:
    tx_energy_per_byte: float = 1.0
    rx_energy_per_byte: float = 0.8
    hmac_energy: float = 5.0
    ascon_energy: float = 4.0
    state_byte_cost: float = 0.01


@dataclass
class CostStats:
    tx_bytes: int = 0
    rx_bytes: int = 0
    hmac_ops: int = 0
    ascon_ops: int = 0
    state_bytes_peak: int = 0
    challenge_round_trips: int = 0
    latency_ticks_sum: int = 0
    accepted_frames: int = 0


def estimate_energy(stats: CostStats, model: CostModel = CostModel()) -> float:
    return (
        stats.tx_bytes * model.tx_energy_per_byte
        + stats.rx_bytes * model.rx_energy_per_byte
        + stats.hmac_ops * model.hmac_energy
        + stats.ascon_ops * model.ascon_energy
        + stats.state_bytes_peak * model.state_byte_cost
    )
```

**Step 3:** Instrument `simulate_one_run` to accumulate `CostStats` (frame byte sizes: counter 4B, nonce `nonce_bits/8`, tag `mac_tag_bits/8`; one crypto op per MAC compute; state bytes = window bitmap bytes or outstanding-nonce bytes; challenge round trips = nonce issues).

**Step 3b: promote cost metrics to TYPED `AggregateStats` fields, not a free-form dict (review finding I5).** Tasks 5.3 (frontier figure) and 5.6 (advisor) consume these, so `metadata` is too fragile a contract. Add to `AggregateStats` (and mirror in `SimulationResultRecord` + the `typescript.py` template per Task 3.3):

```python
    frr: float = 0.0
    energy_proxy: float = 0.0
    bytes_overhead: float = 0.0
    state_bytes: float = 0.0
    latency_ticks: float = 0.0
    crypto_ops: float = 0.0
    challenge_round_trips: float = 0.0
```

Include them in `as_dict()`; average each per-run value into the aggregate. (`frr = 1 - LAR`.)

**Step 4:** Add a metrics test in `tests/test_experiment.py` asserting `stats.frr` and `stats.energy_proxy` are populated and appear in `as_dict()`. Add the same fields to `SimulationResultRecord.from_aggregate`, hand-edit the `SimulationResultRecord` interface in `typescript.py`, regenerate artifacts, and run `npm --prefix web run test:contracts`.

**Step 5: Run green + commit**

```bash
git add src/replay/core/cost.py src/replay/core/experiment.py src/replay/core/types.py src/replay/contracts/models.py src/replay/contracts/typescript.py web/lib/contracts.ts web/public/data/contracts.json tests/test_cost.py tests/test_experiment.py
git commit -m "feat(core): add cost/energy/latency proxy metrics (FRR, bytes, state, energy)"
```

### Task 4.5: Risk policy module

**Files:**
- Create: `src/replay/core/risk.py`
- Modify: `src/replay/core/__init__.py`
- Test: `tests/test_risk.py` (new)

**Step 1: Write failing test** `tests/test_risk.py`:

```python
from replay.core.risk import RiskContext, compute_risk, choose_defense_mode


def test_high_value_command_forces_high_risk():
    ctx = RiskContext(command="UNLOCK", counter_gap=0, duplicate_rate=0.0,
                      recent_loss_rate=0.0, recent_reorder_rate=0.0, is_high_value_state=True)
    risk = compute_risk(ctx, command_risk={"UNLOCK": 1.0})
    assert risk >= 0.4
    assert choose_defense_mode(risk) in {"challenge", "lockdown"}


def test_low_risk_picks_window():
    ctx = RiskContext("PING", 0, 0.0, 0.0, 0.0, False)
    assert choose_defense_mode(compute_risk(ctx, {"PING": 0.1})) == "window"
```

**Step 2: Run red**, then implement `core/risk.py` using the checklist's `CommandRisk`, `RiskContext`, `RiskWeights` (frozen dataclasses), `compute_risk`, and `choose_defense_mode(risk, low=0.4, high=0.8)`. Export from `__init__`.

**Step 3: Run green + commit**

```bash
git add src/replay/core/risk.py src/replay/core/__init__.py tests/test_risk.py
git commit -m "feat(core): add adaptive risk scoring and defense-mode selection policy"
```

### Task 4.6: `Mode.HSW_CR` adaptive receiver path

**Files:**
- Modify: `src/replay/core/types.py` (`Mode.HSW_CR = "hsw_cr"`)
- Modify: `src/replay/core/receiver.py` (hybrid verifier using `risk`)
- Modify: `src/replay/core/sender.py` (counter+MAC normally; nonce when challenged)
- Modify: `src/replay/core/experiment.py` (risk-based challenge issuance)
- Modify: `src/replay/contracts/models.py` (`command_risk`, thresholds)
- Modify: `src/replay/contracts/typescript.py`, `web/lib/contracts.ts`, `web/public/data/contracts.json` (`Mode` enum + HSW-CR fields)
- Test: `tests/test_receiver.py`, `tests/test_experiment.py`

**Step 1: Write failing behavior test** in `tests/test_experiment.py`:

```python
def test_hsw_cr_blocks_replay_on_high_risk_command():
    from replay.core import Mode, SimulationConfig, run_many_experiments
    cfg = SimulationConfig(mode=Mode.HSW_CR, num_legit=20, num_replay=40,
                           p_loss=0.0, p_reorder=0.0, target_commands=["UNLOCK"])
    stats = run_many_experiments(cfg, modes=[Mode.HSW_CR], runs=20, seed=1, show_progress=False)
    assert stats[0].avg_attack_rate <= 0.05
    assert stats[0].avg_legit_rate >= 0.95
```

**Step 2: Run red**, then implement with this **explicit, derivable** design (review finding G — no hand-waving):

*Why the assertion holds (attacker behavior, state it in the test):* the attacker records legit frames and replays them post-run. A replayed **high-risk** frame carries the nonce it was originally sent with; by replay time that nonce is in `used_nonces` (consumed) → rejected as `challenge_replay`. A replayed **low-risk** frame carries an old counter ≤ the window's right edge → rejected by the sliding window. So ASR→0 for both, making `ASR ≤ 0.05` a *derived* outcome, not a tuned number.

- Add `Mode.HSW_CR = "hsw_cr"`.
- Add spec/config fields `command_risk: dict[str, float] | None`, `risk_high: float = 0.8` (pass them into `Receiver`).
- `Receiver` HSW-CR branch:

```python
def verify_hsw_cr(frame, state, *, shared_key, mac_length, window_size,
                  command_risk, risk_high):
    is_high_risk = (command_risk or {}).get(frame.command, 0.0) >= risk_high
    if is_high_risk or frame.nonce is not None:
        return verify_challenge_response(frame, state, shared_key=shared_key, mac_length=mac_length)
    return verify_with_window(frame, state, shared_key=shared_key,
                              mac_length=mac_length, window_size=window_size)
```

- `Receiver.issue_nonce` must allow both challenge modes; otherwise HSW-CR cannot issue a nonce:

```python
    def issue_nonce(self, rng: RandomLike, bits: int = 32, *, tick: int | None = None) -> str:
        if self.mode not in {Mode.CHALLENGE, Mode.HSW_CR}:
            raise RuntimeError("Nonce issuance is only supported in challenge-capable modes")
        ...
```

- `Sender.next_frame` must branch on whether a nonce was supplied, not only on `Mode.CHALLENGE`; otherwise HSW-CR silently emits counter frames for high-risk commands. Replace the start of `next_frame` with:

```python
    def next_frame(self, command: str, *, nonce: str | None = None) -> Frame:
        if self.mode is Mode.NO_DEFENSE:
            return Frame(command=command)

        if nonce is not None:
            mac = compute_mac(nonce, command, key=self.shared_key, mac_length=self.mac_length)
            return Frame(command=command, nonce=nonce, mac=mac)

        if self.mode is Mode.CHALLENGE:
            raise ValueError("Challenge mode requires a nonce for each frame")

        self.tx_counter += 1
        mac = compute_mac(self.tx_counter, command, key=self.shared_key, mac_length=self.mac_length)
        return Frame(command=command, counter=self.tx_counter, mac=mac)
```

- `experiment.simulate_one_run` (HSW-CR): for each legit frame, if `command_risk.get(cmd, 0) >= risk_high`, the receiver issues a nonce (mirror of the challenge loop at `experiment.py:83-84`) and the sender emits a challenge frame (nonce+MAC over `nonce|command`); else the sender emits counter+MAC. The attacker records whatever was actually sent.

> Decision rule (document inline): `risk = command_risk.get(cmd, 0)`; `risk >= risk_high` → challenge path; otherwise sliding-window path. Anomaly-driven escalation (counter-gap / duplicate-rate feeding `compute_risk`) is an optional refinement; keep the command-risk rule as the testable core. If the ASR/LAR thresholds can't be met deterministically, weaken to a *comparative* assertion (HSW-CR ASR ≤ rolling-counter ASR at the same loss) and debug with @superpowers:systematic-debugging rather than tuning until green.

Add receiver/sender unit tests for the two boundary cases above:

- `Receiver(Mode.HSW_CR, ...).issue_nonce(...)` succeeds and stores the nonce in `outstanding_nonces`.
- `Sender(Mode.HSW_CR, ...).next_frame("UNLOCK", nonce=n)` returns a frame with `nonce` and no `counter`; `next_frame("PING")` returns a counter frame.

Hand-edit `typescript.py` to add `'hsw_cr'` to `export type Mode` and add `command_risk`/`risk_high` to `SimulationSpec`; regenerate artifacts and run `npm --prefix web run test:contracts`.

**Step 3: Run green + full suite + commit**

```bash
git add src/replay/core/types.py src/replay/core/receiver.py src/replay/core/sender.py src/replay/core/experiment.py src/replay/contracts/models.py src/replay/contracts/typescript.py web/lib/contracts.ts web/public/data/contracts.json tests/test_receiver.py tests/test_sender.py tests/test_experiment.py
git commit -m "feat(core): add HSW-CR adaptive sliding-window + challenge defense mode"
```

### Task 4.7: Authenticator protocol + HMAC implementation

**Files:**
- Create: `src/replay/core/auth.py`
- Modify: `src/replay/core/__init__.py`
- Test: `tests/test_auth.py` (new)

**Step 1: Write failing test** `tests/test_auth.py`:

```python
from replay.core.auth import HmacAuthenticator


def test_hmac_authenticator_roundtrip():
    a = HmacAuthenticator(key="k", tag_bits=80)
    tag = a.tag(5, "CMD")
    assert a.verify(5, "CMD", tag)
    assert not a.verify(6, "CMD", tag)
    assert len(tag) == 80 // 4
```

**Step 2: Run red**, then implement `core/auth.py` with the `Authenticator` Protocol and `HmacAuthenticator` (wraps `security.compute_mac` with `tag_bits//4` hex chars + `constant_time_compare`). Export from `__init__`.

**Step 3: Run green + commit**

```bash
git add src/replay/core/auth.py src/replay/core/__init__.py tests/test_auth.py
git commit -m "feat(core): add Authenticator protocol and HMAC implementation"
```

### Task 4.7b: Wire the HMAC Authenticator into the verification main path (review finding E)

**Problem:** without this task the `Authenticator` abstraction is a dangling module — `receiver`/`sender`/`experiment` still call `security.compute_mac` directly. This task wires the default HMAC authenticator only. The Ascon profile switch is added in Task 4.8 after `AsconAeadAuthenticator` actually exists.

**Files:**
- Modify: `src/replay/core/receiver.py`, `src/replay/core/sender.py` (accept `authenticator: Authenticator`, default `HmacAuthenticator(shared_key, tag_bits)`)
- Modify: `src/replay/core/experiment.py` (build the default HMAC authenticator from `shared_key` + `mac_length * 4`; pass to Sender/Receiver)
- Test: `tests/test_experiment.py`

**Step 1: Write failing test:**

```python
def test_hmac_authenticator_is_wired_into_main_path():
    from replay.core import Mode, SimulationConfig, run_many_experiments
    cfg = SimulationConfig(mode=Mode.WINDOW, num_legit=10, num_replay=10, window_size=5)
    stats = run_many_experiments(cfg, modes=[Mode.WINDOW], runs=5, seed=1, show_progress=False)
    assert stats[0].avg_legit_rate >= 0.99
    assert stats[0].metadata.get("auth_profile") == "hmac"
```

**Step 2:** Replace direct `compute_mac`/`constant_time_compare` calls in the rolling/window/challenge/HSW-CR verifiers with `authenticator.tag(...)`/`authenticator.verify(...)`. Build `HmacAuthenticator(key=config.shared_key, tag_bits=config.mac_length * 4)` in `simulate_one_run` and pass the same authenticator to `Sender` and `Receiver`. Keep HMAC the only available main-path profile in this task so all existing tests are unaffected.

**Step 3: Run green + full suite + commit**

```bash
git add src/replay/core/receiver.py src/replay/core/sender.py src/replay/core/experiment.py tests/test_experiment.py
git commit -m "feat(core): wire HMAC Authenticator into sender/receiver verification path"
```

### Task 4.8: Ascon AEAD authenticator profile (optional dependency)

**Files:**
- Modify: `pyproject.toml` (optional extra `crypto = ["ascon>=1.3"]`)
- Modify: `src/replay/core/auth.py` (`AsconAeadAuthenticator` with lazy import — name matches checklist; review finding E)
- Modify: `src/replay/core/types.py`, `src/replay/core/experiment.py` (`auth_profile` runtime switch)
- Modify: `src/replay/contracts/models.py`, `src/replay/contracts/typescript.py`, `web/lib/contracts.ts`, `web/public/data/contracts.json` (`auth_profile: Literal["hmac","ascon"] = "hmac"`)
- Test: `tests/test_auth.py`, `tests/test_experiment.py` (skip Ascon-specific tests if `ascon` unavailable)

**Step 1: Write skip-guarded test:**

```python
import pytest


def test_ascon_authenticator_roundtrip_if_available():
    pytest.importorskip("ascon")
    from replay.core.auth import AsconAeadAuthenticator
    a = AsconAeadAuthenticator(key=b"0" * 16)
    tag = a.tag(5, "CMD")
    assert a.verify(5, "CMD", tag)
```

**Step 2: Implement `AsconAeadAuthenticator`** with `import ascon` inside `__init__` (raise a friendly `RuntimeError("pip install replay[crypto]")` if absent). Map token+command to associated data / plaintext and produce a hex tag. (Wired into the verification path by Task 4.7b.)

**Step 3: Expose and wire the `auth_profile` switch now that Ascon exists.** Add `auth_profile: Literal["hmac","ascon"] = "hmac"` to `SimulationConfig` and `SimulationSpec`; in `simulate_one_run`, build `HmacAuthenticator` for `"hmac"` and `AsconAeadAuthenticator` for `"ascon"`. Add this end-to-end test:

```python
def test_ascon_profile_runs_end_to_end_if_available():
    import dataclasses
    import pytest

    pytest.importorskip("ascon")
    from replay.core import Mode, SimulationConfig, run_many_experiments

    cfg = SimulationConfig(mode=Mode.WINDOW, num_legit=10, num_replay=10, window_size=5)
    cfg = dataclasses.replace(cfg, auth_profile="ascon")
    stats = run_many_experiments(cfg, modes=[Mode.WINDOW], runs=5, seed=1, show_progress=False)
    assert stats[0].avg_legit_rate >= 0.99
    assert stats[0].metadata.get("auth_profile") == "ascon"
```

Hand-edit `typescript.py` to add `auth_profile` to `SimulationSpec`, regenerate artifacts, and run `npm --prefix web run test:contracts`.

**Step 4:** Add the extra to `pyproject.toml` `[project.optional-dependencies]`:

```toml
crypto = ["ascon>=1.3"]
```

**Step 5: Run (Ascon tests skip if not installed) + commit**

```bash
git add pyproject.toml src/replay/core/auth.py src/replay/core/types.py src/replay/core/experiment.py src/replay/contracts/models.py src/replay/contracts/typescript.py web/lib/contracts.ts web/public/data/contracts.json tests/test_auth.py tests/test_experiment.py
git commit -m "feat(core): add optional Ascon AEAD authenticator profile"
```

### Task 4.9: OSCORE-like replay-window profile

**Files:**
- Modify: `src/replay/core/types.py` (`Mode.OSCORE_LIKE = "oscore_like"`; optional `sender_id`, `partial_iv`)
- Modify: `src/replay/core/receiver.py` (reuse sliding-window verifier; Partial IV plays the counter role)
- Modify: `src/replay/contracts/models.py`, `src/replay/contracts/typescript.py`, `web/lib/contracts.ts`, `web/public/data/contracts.json` (`Mode` enum includes `oscore_like`)
- Test: `tests/test_receiver.py`

**Step 1: Write failing test** in `tests/test_receiver.py` (review finding G — concrete, not prose):

```python
def test_oscore_like_accepts_in_window_and_rejects_replay():
    r = Receiver(Mode.OSCORE_LIKE, shared_key=SHARED_KEY, mac_length=MAC_LENGTH, window_size=5)
    assert r.process(create_frame(10)).accepted          # Partial IV = 10
    assert r.process(create_frame(12)).accepted           # advances right edge
    replay = r.process(create_frame(12))
    assert not replay.accepted and replay.reason == "counter_replay"
    assert r.process(create_frame(11)).accepted           # in-window older PIV
```

**Step 2: Run red**, then add `Mode.OSCORE_LIKE = "oscore_like"` and dispatch it in `Receiver.process` to `verify_with_window` (the OSCORE Partial IV plays the counter role; `sender_id` would select a per-peer `ReceiverState` — for the single-peer simulation this is exactly the existing window verifier). Hand-edit `typescript.py` to add `'oscore_like'` to `export type Mode`, regenerate artifacts, and run `npm --prefix web run test:contracts`. Run green.

**Step 3: Commit**

```bash
git add src/replay/core/types.py src/replay/core/receiver.py src/replay/contracts/models.py src/replay/contracts/typescript.py web/lib/contracts.ts web/public/data/contracts.json tests/test_receiver.py
git commit -m "feat(core): add OSCORE-like replay-window defense profile"
```

### Task 4.10: Migrate MAC vocabulary to `mac_tag_bits` (backward compatible)

**Files:**
- Modify: `src/replay/core/security.py` (add `compute_mac_bits`)
- Modify: `src/replay/core/types.py` (`SimulationConfig`: add `mac_tag_bits: int = 80`, keep `mac_length` bridge)
- Modify: `src/replay/core/defaults.py` (`DEFAULT_MAC_TAG_BITS = 80`)
- Modify: `src/replay/contracts/models.py` (spec accepts `mac_tag_bits`, derives hex chars)
- Modify: `src/replay/contracts/typescript.py`, `web/lib/contracts.ts`, `web/public/data/contracts.json` (`SimulationSpec.mac_tag_bits`, `SweepSpec.sweep_type`)
- Modify: `src/replay/services/simulation.py` (`run_sweep` supports `mac_tag_bits`)
- Test: `tests/test_security.py` (new), `tests/test_replay_services.py`

**Step 1: Write failing test:**

```python
def test_compute_mac_bits_length():
    import pytest
    from replay.core.security import compute_mac_bits
    tag = compute_mac_bits(5, "CMD", key="k", tag_bits=80)
    assert len(tag) == 20
    with pytest.raises(ValueError):
        compute_mac_bits(5, "CMD", key="k", tag_bits=81)  # not divisible by 4
```

**Step 2: Run red**, then implement `compute_mac_bits` in `security.py`:

```python
def compute_mac_bits(token: int | str, command: str, *, key: str, tag_bits: int = 80) -> str:
    if tag_bits % 4 != 0:
        raise ValueError("tag_bits must be divisible by 4 for hex encoding")
    return compute_mac(token, command, key=key, mac_length=tag_bits // 4)
```

**Step 3: Bridge in config/spec.** Add `mac_tag_bits` (default 80) with a derived `mac_hex_chars` property. Honor explicit `mac_length` when set (legacy/educational 32-bit profile). Document: "32-bit (`mac_length=8`) retained only as a low-cost stress profile; default security profile is 80-bit."

**Step 3b: actually IMPLEMENT the `mac_tag_bits` sweep, don't just document it (review finding I5).** Add `"mac_tag_bits"` to `SweepSpec.sweep_type`'s `Literal`, handle it in `run_sweep` (`scenario = simulation.model_copy(update={"mac_tag_bits": int(value)})`), and add a test sweeping `[32, 48, 64, 80, 96, 128]` that asserts one `SweepPoint` per value and that each point records its `mac_tag_bits`. (Do not assume ASR monotonicity in tag bits — just that the sweep runs and is recorded.) Hand-edit `typescript.py` to add `mac_tag_bits` to `SimulationSpec` and `'mac_tag_bits'` to `SweepSpec.sweep_type`, regenerate artifacts, and run `npm --prefix web run test:contracts`. If you defer it, `log()`/README-note it as not-yet-implemented — do not present it as done.

**Step 4: Run green + full suite + commit**

```bash
git add src/replay/core/security.py src/replay/core/types.py src/replay/core/defaults.py src/replay/contracts/models.py src/replay/contracts/typescript.py src/replay/services/simulation.py web/lib/contracts.ts web/public/data/contracts.json tests/test_security.py tests/test_replay_services.py
git commit -m "feat(core): introduce mac_tag_bits (default 80) with backward-compatible bridge"
```

### Task 4.11: Phase-4 gate

Run: `PYTHONPATH=src:. python3 -m pytest -q && ruff check . && mypy src` → all green.
```bash
git commit --allow-empty -m "chore: phase-4 realism/innovation gate verified"
```

---

# PHASE 5 — External Presentation & Adoption

### Task 5.1: Rebrand to ReplayBench-IoT (READMEs first screen, 3 languages)

**Files:**
- Modify: `README.md`, `README_CH.md`, `README_JP.md`

**Step 1:** Replace the first screen with the ReplayBench-IoT positioning, the defense list (no defense / rolling counter / RFC sliding window / challenge-response / HSW-CR adaptive / OSCORE-like), and the metrics list (LAR, ASR, FRR, latency, bytes overhead, state memory, energy proxy, 95% CIs). **Correct the prior "bounded forward-gap" wording to "RFC-style sliding window"** (consistency with Task 2.1). Add a "Limitations / what this is not" section (not a crypto proof, not a certification tool, hardware covers controlled links only). Add a "How to cite" block and badge placeholders. Reference standards honestly (RFC 6479 sliding window, RFC 2104 HMAC truncation ≥80 bits, NIST SP 800-232 Ascon, RFC 8613 OSCORE, NISTIR 8259A, ETSI EN 303 645) as *informative alignment*, not compliance claims. **In Limitations, explicitly state (review finding H):** (a) the trace-driven channel ingests only in-memory `list[bool]` sequences — there is no pcap/CSV trace loader yet; (b) NISTIR 8259A / ETSI EN 303 645 alignment is narrative only — there is no standards→feature mapping table and no certification.

**Step 2: Markdown lint**

Run: `npx markdownlint-cli 'README*.md' --ignore node_modules` (fix issues).

**Step 3: Commit**

```bash
git add README.md README_CH.md README_JP.md
git commit -m "docs: rebrand to ReplayBench-IoT and correct sliding-window description"
```

### Task 5.2: Benchmark presets

**Files:**
- Create: `presets/smart_lock.yaml`, `presets/garage_door.yaml`, `presets/toy_robot.yaml`, `presets/industrial_relay.yaml`, `presets/low_power_sensor.yaml`
- Create: `src/replay/core/presets.py` (loader → `SimulationSpec`)
- Modify: `src/replay/cli/app.py` (`--preset` option)
- Test: `tests/test_presets.py` (new)

**Step 1: Write failing test** `tests/test_presets.py`:

```python
def test_smart_lock_preset_loads_and_marks_unlock_high_risk():
    from replay.core.presets import load_preset
    spec = load_preset("smart_lock")
    assert "UNLOCK" in (spec.command_set or [])
    assert (spec.command_risk or {}).get("UNLOCK", 0) >= 0.9
```

**Step 2: Run red**, then write `presets/smart_lock.yaml` (and the other four) using this schema:

```yaml
name: smart_lock
commands: [PING, STATUS, LOCK, UNLOCK]
risk:
  PING: 0.1
  STATUS: 0.2
  LOCK: 0.7
  UNLOCK: 1.0
channel:
  model: gilbert_elliott
  loss_good: 0.01
  loss_bad: 0.40
defense:
  mode: hsw_cr
  window_size: 8
  mac_tag_bits: 80
  challenge_for: [UNLOCK]
```

Implement `load_preset(name)` mapping YAML → `SimulationSpec` (commands → `command_set`, risk → `command_risk`, channel → channel fields, defense → modes/window/mac_tag_bits). Use `PyYAML`.

**Step 3: Wire CLI `--preset`** in `cli/app.py`. Run green + commit:

```bash
git add presets src/replay/core/presets.py src/replay/cli/app.py tests/test_presets.py
git commit -m "feat: add device benchmark presets and loader with CLI --preset"
```

### Task 5.3: Three core figures + generation scripts

**Files:**
- Create: `scripts/plot_asr_vs_loss.py`, `scripts/plot_lar_vs_reorder.py`, `scripts/plot_security_cost_frontier.py`
- Output: `docs/figures/asr_vs_loss.png`, `docs/figures/lar_vs_reorder.png`, `docs/figures/security_cost_frontier.png`

**Step 1:** Each script runs a sweep via the services layer, plots with matplotlib (error bars from Wilson CIs), and writes a PNG to `docs/figures/`. The frontier script plots security (1-ASR) vs energy_proxy/round-trips per mode — the headline research figure.

> If figure work warrants journal-grade output, consider the `nature-figure` skill (ask Python vs R first).

**Step 2: Generate + sanity check**

Run each script; confirm PNGs exist and non-empty (`ls -la docs/figures/*.png`).

**Step 3: Embed in README (Task 5.1 placeholders) + commit**

```bash
git add scripts/plot_asr_vs_loss.py scripts/plot_lar_vs_reorder.py scripts/plot_security_cost_frontier.py docs/figures/*.png
git commit -m "docs: add ASR/LAR/security-cost-frontier figures and generators"
```

### Task 5.4: Web demo scenario selection

**Files:**
- Modify: `web/components/simulator-panel.tsx` (scenario selector, attacker/channel/defense controls, request payload)
- Modify: `web/components/results-overview.tsx` (render CI + security/cost summary for static artifacts)
- Modify: `web/lib/data.ts` (optional helper for preset request construction; keep API call path unchanged)
- Modify: `web/app/simulator/page.tsx` only if heading copy must mention presets; no layout rewrite
- Modify: `web/lib/contracts.ts` only through the generated artifact from earlier contract tasks

**Step 1: Add concrete UI state in `SimulatorPanel`**

Use the generated `SimulationSpec` type. Add these local constants/state:

```typescript
const DEVICE_PRESETS = {
  smart_lock: {
    label: 'Smart lock',
    command_set: ['PING', 'STATUS', 'LOCK', 'UNLOCK'],
    command_risk: { PING: 0.1, STATUS: 0.2, LOCK: 0.7, UNLOCK: 1.0 },
    modes: ['window', 'hsw_cr', 'oscore_like'],
    window_size: 8,
    channel_model: 'gilbert_elliott',
    loss_good: 0.01,
    loss_bad: 0.4,
    auth_profile: 'hmac',
    mac_tag_bits: 80,
  },
  toy_robot: {
    label: 'Toy robot',
    command_set: ['FWD', 'BACK', 'LEFT', 'RIGHT', 'STOP'],
    command_risk: { STOP: 0.8 },
    modes: ['rolling', 'window', 'hsw_cr'],
    window_size: 5,
    channel_model: 'iid',
    auth_profile: 'hmac',
    mac_tag_bits: 80,
  },
} satisfies Record<string, Partial<SimulationSpec> & { label: string }>;
```

Add exact controls:

- preset `<select>`: applies the preset patch to `spec`.
- attacker `<select>`: `post` / `inline`, updates `attack_mode`.
- channel `<select>`: `iid` / `gilbert_elliott` / `trace`, updates `channel_model`.
- defense multi-select buttons using the generated `Mode` union, now including `hsw_cr` and `oscore_like`.
- numeric inputs for `runs`, `p_loss`, `p_reorder`, `window_size`, `mac_tag_bits`, `risk_high`.

The request payload remains the existing `runSimulation(spec)` body in `web/lib/data.ts`; do not add browser-side simulation logic.

**Step 2: Render result metrics with typed CI/cost fields**

In the last-run result cards, show:

- LAR: `avg_legit_rate` with `[lar_ci_low, lar_ci_high]`.
- ASR: `avg_attack_rate` with `[asr_ci_low, asr_ci_high]`.
- cost row: `energy_proxy`, `bytes_overhead`, `state_bytes`, `latency_ticks`, `challenge_round_trips`.

Add a small inline SVG or CSS bar chart inside `SimulatorPanel` for security/cost: x = `energy_proxy`, y = `1 - avg_attack_rate`; one point/bar per result mode. Keep this chart purely presentational from returned API fields.

**Step 3: Update `ResultsOverview` static cards**

When static artifacts include the new typed fields in `summary`/`metrics`, prefer displaying `security_cost_frontier.png`; otherwise keep the existing figures and do not fabricate missing metrics.

**Step 4: Verify**

Run: `npm --prefix web run lint && npm --prefix web run test:contracts && npm --prefix web run build`

Coverage note: no Playwright/frontend interaction test is planned in this task. The acceptance bar is type safety + lint + contracts + production build.

**Step 5: Commit**

```bash
git add web/components/simulator-panel.tsx web/components/results-overview.tsx web/lib/data.ts web/app/simulator/page.tsx
git commit -m "feat(web): scenario/attacker/channel/defense selectors with CI and cost charts"
```

### Task 5.5: Citation metadata

**Files:**
- Create: `CITATION.cff`

**Step 1:** Add a valid `CITATION.cff` (software citation) matching the README "How to cite" block (author, year, title, URL).

**Step 2: Validate**

Run: `python3 -c "import yaml; yaml.safe_load(open('CITATION.cff')); print('cff-ok')"`

**Step 3: Commit**

```bash
git add CITATION.cff
git commit -m "docs: add CITATION.cff"
```

### Task 5.6: Developer recommendation tool

**Files:**
- Create: `src/replay/services/advisor.py` (`recommend(device_profile) -> Recommendation`)
- Modify: `src/replay/cli/app.py` (`advise` subcommand) and/or `src/replay/api/app.py` (`POST /api/v1/advise`)
- Test: `tests/test_advisor.py` (new)

**Step 1: Write failing tests**

```python
def test_recommend_challenges_high_risk_unlock():
    from replay.services.advisor import DeviceProfile, recommend

    rec = recommend(DeviceProfile(
        commands=["PING", "STATUS", "LOCK", "UNLOCK"],
        command_risk={"PING": 0.1, "STATUS": 0.2, "LOCK": 0.7, "UNLOCK": 1.0},
        p_loss=0.05,
        p_reorder=0.05,
        ram_budget_bytes=128,
        max_latency_ticks=2,
        target_asr=0.05,
        seed=1,
    ))
    assert "UNLOCK" in rec.challenge_for
    assert rec.mode == "hsw_cr"
    assert rec.mac_tag_bits in {80, 96, 128}
    assert rec.predicted_asr <= 0.05 or rec.constraint_status == "best_effort"


def test_recommend_respects_tiny_state_budget():
    from replay.services.advisor import DeviceProfile, recommend

    rec = recommend(DeviceProfile(
        commands=["PING", "UNLOCK"],
        command_risk={"PING": 0.1, "UNLOCK": 1.0},
        p_loss=0.0,
        p_reorder=0.0,
        ram_budget_bytes=8,
        max_latency_ticks=1,
        target_asr=0.05,
        seed=2,
    ))
    assert rec.state_bytes <= 8
```

Run: `PYTHONPATH=src:. python3 -m pytest tests/test_advisor.py -v` → Expected: FAIL (module missing).

**Step 2: Implement exact data models in `advisor.py`**

```python
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DeviceProfile:
    commands: list[str]
    command_risk: dict[str, float]
    p_loss: float
    p_reorder: float
    ram_budget_bytes: int
    max_latency_ticks: int
    target_asr: float = 0.05
    seed: int | None = None


@dataclass(frozen=True)
class Recommendation:
    mode: str
    window_size: int
    mac_tag_bits: int
    challenge_for: list[str] = field(default_factory=list)
    predicted_lar: float = 0.0
    predicted_asr: float = 1.0
    energy_proxy: float = 0.0
    state_bytes: float = 0.0
    latency_ticks: float = 0.0
    constraint_status: str = "met"  # "met" | "best_effort"
```

**Step 3: Implement deterministic bounded search**

Search only this small grid so it remains under `MAX_WORK_UNITS`:

- modes: `["window", "hsw_cr", "oscore_like"]`
- window sizes: `[3, 5, 8, 16]`
- tag bits: `[80, 96, 128]`
- challenge_for: commands with `risk >= 0.8`

For each candidate, run `SimulationSpec(runs=50, num_legit=20, num_replay=50, paired=True, ...)` through `simulate_batch(show_progress=False)`. Discard candidates whose returned `state_bytes > ram_budget_bytes` or `latency_ticks > max_latency_ticks`. Pick the lowest `energy_proxy` among candidates with `avg_attack_rate <= target_asr`; if none meet target, return the lowest-ASR candidate with `constraint_status="best_effort"`. Never bypass the `SimulationSpec` budget validator.

**Step 4: Wire one interface**

Prefer the CLI first to keep scope small:

```bash
replay advise --profile presets/smart_lock.yaml
```

Add `advise` as a top-level subcommand in `src/replay/cli/app.py`. It loads the same YAML shape as Task 5.2 presets, calls `recommend`, and prints JSON. Add an API endpoint only if the web demo needs live recommendations; otherwise leave it out of this task.

**Step 5: Run green**

Run: `PYTHONPATH=src:. python3 -m pytest tests/test_advisor.py tests/test_main_cli.py -q`

**Step 6: Commit**

```bash
git add src/replay/services/advisor.py src/replay/cli/app.py tests/test_advisor.py tests/test_main_cli.py
git commit -m "feat: add developer defense-parameter recommendation tool"
```

### Task 5.7: Packaging — one-command run (pipx + Docker) + badges/limitations

**Files:**
- Modify: `pyproject.toml` (ensure `replay` console script covers `sim run --preset`)
- Create: `Dockerfile`
- Modify: `README*.md` (badges, limitations, quickstart, release notes pointer)

**Step 1:** Confirm `pipx install .` then `replay sim run --preset smart_lock --runs 1000` works. Add a minimal `Dockerfile` (python:3.11-slim, install `.`, entrypoint `replay`).

**Step 2: Verify**

Run: `pip install -e . && replay --help`. Run: `docker build -t replaybench/iot:dev .` (if Docker available; else rely on CI).

**Step 3: Commit**

```bash
git add pyproject.toml Dockerfile README.md README_CH.md README_JP.md
git commit -m "chore: add Docker image and one-command quickstart; README badges/limitations"
```

### Task 5.8: Short technical article (optional content asset)

**Files:**
- Create: `docs/articles/why-replay-defense-fails-under-lossy-iot-links.md`

**Step 1:** Write the article tying the benchmark results (sliding-window vs challenge vs HSW-CR under Gilbert-Elliott loss) to the Task 5.3 figures. Use the `markdown-to-visual-html` skill if an HTML reading version is wanted.

**Step 2: Commit**

```bash
git add docs/articles/why-replay-defense-fails-under-lossy-iot-links.md
git commit -m "docs: add ReplayBench-IoT technical article"
```

### Task 5.9: Final verification gate

**Files:**
- Create: `CHANGELOG.md`
- Create: `docs/releases/v0.2.0.md`

Run the full gate:
```bash
PYTHONPATH=src:. python3 -m pytest -q
ruff check .
mypy src
npm --prefix web run lint
npm --prefix web run test:contracts
npm --prefix web run build
npx markdownlint-cli 'README*.md' 'docs/**/*.md' --ignore node_modules
```
Expected: all green.

Then create `CHANGELOG.md` with a `## v0.2.0 - 2026-06-05` entry summarizing P0 correctness fixes, statistical rigor, channel/cost models, HSW-CR/OSCORE-like profiles, web demo updates, packaging, and limitations. Create `docs/releases/v0.2.0.md` with GitHub Release-ready notes:

- headline
- breaking/behavior changes
- reproducibility commands
- known limitations
- citation note

Commit and tag:

```bash
git add CHANGELOG.md docs/releases/v0.2.0.md
git commit -m "docs: add v0.2.0 changelog and release notes"
git commit --allow-empty -m "chore: phase-5 presentation gate verified"
git tag -a v0.2.0 -m "ReplayBench-IoT: research-grade replay-defense benchmark"
```

---

## Checklist Coverage Map (every改造清单 item → task)

| 改造清单 item | Task(s) |
|---|---|
| 仓库卫生：`._*`/`.DS_Store`/`.venv`/`node_modules`/`.next`/`out` | 1.1, 1.2 (reconciliation: mostly absent/untracked here) |
| `.gitignore` 强化 | 1.1 |
| ESLint ignore `**/._*` 等 | 1.3 |
| GitHub Actions CI（python+web） | 1.4, 1.5 |
| P0：window 标准 sliding-window 语义 + 改测试 | 2.1 |
| P0：challenge 多 outstanding nonce + cap/TTL | 2.2 |
| P0：`run_sweep` 显式 `0.0` bug | 2.3 |
| P0：API `shared_key` 回显 → public schema | 2.4 |
| P0：仿真工作量上限 + 字段硬上限 | 2.5 |
| `lab.py` subprocess timeout | 2.6 |
| ZMQ 默认 localhost + `--bind-all` | 2.7 |
| Wilson CI 移入 core | 3.1 |
| raw successes/trials + CI 输出 | 3.2, 3.3 |
| sequential stopping | 3.4 |
| paired scenario trace（common random numbers） | 3.5 |
| Gilbert-Elliott burst channel 入 core | 4.1, 4.2 |
| trace-driven channel | 4.3 |
| cost/energy/latency model + FRR/bytes/state metrics | 4.4 |
| HSW-CR 自适应 risk function | 4.5, 4.6 |
| Authenticator 抽象 | 4.7 |
| Ascon profile | 4.8 |
| OSCORE-like profile | 4.9 |
| `mac_length` → `mac_tag_bits`(80) + 32–128 扫描 | 4.10 |
| README 改 ReplayBench-IoT 第一屏（3 语言） | 5.1 |
| benchmark presets | 5.2 |
| 3 张核心图（含 security-cost frontier） | 5.3 |
| Web demo 场景选择 | 5.4 |
| citation | 5.5 |
| 开发者检查/推荐工具 | 5.6 |
| pipx/Docker 一键运行 + badges + limitations + release | 5.7 |
| 短技术文章 | 5.8 |
| NIST/ETSI/RFC/标准对接表述 | 5.1 (README claims) + inline docstrings in 2.1/4.8/4.9/4.10 |

---

## Risks & Sequencing Rules

- **Do not reorder phases.** Statistical and presentation work depends on the P0 correctness fixes producing valid numbers.
- **Seeded-output regressions:** Tasks 4.1–4.3 must preserve RNG call order. **`test_web_engine_parity.py` does NOT guard this** (it only tests contracts/manifest generation) — the real guard is the new `test_send_rng_call_order_unchanged` added in Task 4.2 (review finding D). Debug breaks with @superpowers:systematic-debugging.
- **Contracts drift:** `web/lib/contracts.ts` is **hand-maintained** via the `typescript.py` string template (no auto-gen), and `npm run test:contracts` is only a substring check that will NOT catch field drift. Any contract field/enum change (2.4, 3.3, 3.4, 3.5, 4.2, 4.3, 4.4, 4.6, 4.8, 4.9, 4.10) requires hand-editing `typescript.py` + `write_contract_artifacts` and manually verifying the interface matches the Pydantic model (review finding A).
- **py3.9 target:** keep `from __future__ import annotations`; avoid runtime generic subscripts.
- **`sim/` shim:** changing `src/replay/core/*` is intentionally visible to legacy `sim.*` imports in tests — update both sides together.
- **Honesty:** when a gate step can't run in the local sandbox (e.g. `npm run build` needing network), say so and rely on CI; never claim a green you didn't observe (@superpowers:verification-before-completion).
