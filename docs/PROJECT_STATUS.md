# ReplayBench-IoT Project Status

Last reviewed: 2026-06-05

## Current Position

ReplayBench-IoT is a reproducible research benchmark for comparing IoT replay-defense mechanisms under packet loss, packet reordering, and low-cost device constraints.

The public contract is the Python benchmark core. The deployed website is a static, artifact-backed showcase, while local interactive runs submit work to the Python backend.

## What Is Complete

| Area | Status |
| --- | --- |
| Core replay defenses | No defense, rolling counter + MAC, RFC-style sliding window, challenge-response, HSW-CR, and OSCORE-like replay-window profiles are implemented. |
| Statistical reporting | LAR, ASR, FRR, raw counts, Wilson 95% confidence intervals, and paired scenario traces are available. |
| Channel and cost model | IID loss, Gilbert-Elliott burst loss, reordering, latency ticks, byte overhead, receiver-state bytes, and energy proxy are modeled. |
| Web surface | GitHub Pages serves a static showcase backed by generated artifacts; the local app delegates authoritative runs to the Python backend. |
| CI | Python tests, lint, type checks, and web lint/contract/build checks are covered by GitHub Actions. |
| Release metadata | `CITATION.cff`, `CHANGELOG.md`, and `docs/releases/v0.2.0.md` are present for v0.2.0. |

## Verification Contract

Use these commands before treating a branch as release-ready:

```bash
PYTHONPATH=src:. python3 -m pytest -q
ruff check .
mypy src
npm --prefix web run lint
npm --prefix web run test:contracts
npm --prefix web run build
```

CI is the source of truth for the public default branch.

## Evidence Boundary

This repository supports reproducible comparison and thesis evidence, but it is not:

- A cryptographic proof.
- A standards certification package.
- A production firmware implementation.
- A complete RF channel emulator.

Hardware-validation artifacts cover controlled lab links only. The benchmark currently accepts trace-driven loss as in-memory `list[bool]` sequences; pcap/CSV trace ingestion is not implemented.

## Primary Entry Points

- [README](../README.md): first-pass project overview.
- [Web demo](https://tammakiiroha.github.io/IoT-Replay-Defense-Simulator/): static public showcase.
- [Release notes](releases/v0.2.0.md): v0.2.0 change summary.
- [Metrics tables](metrics_tables.md): generated metric summaries.
- [Figures](figures): generated result figures.
- [CITATION.cff](../CITATION.cff): citation metadata.

## Sensible Next Improvements

- Add pcap/CSV trace loaders for externally recorded packet-loss traces.
- Expand the physical-validation matrix beyond controlled lab links.
- Add a compact reproducibility notebook for the headline figures.
- Add benchmark-version provenance into each generated artifact.
