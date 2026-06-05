# Changelog

## v0.2.0 - 2026-06-05

- Fixed P0 replay-defense correctness issues: RFC-style sliding-window advancement, multiple outstanding challenge nonces, explicit `0.0` sweep values, public API secret redaction, simulation work-budget caps, lab subprocess timeout, and localhost-only ZMQ defaults.
- Added statistical rigor with raw counts, Wilson confidence intervals, sequential stopping, and paired scenario traces.
- Added realistic channel/cost/authentication extensions: IID, Gilbert-Elliott, trace loss, typed cost metrics, HSW-CR, OSCORE-like mode, `mac_tag_bits`, and optional Ascon profile.
- Added benchmark presets, advisor recommendations, Web scenario controls, generated core figures, CI workflow, Dockerfile, and citation metadata.
- Known limitations: trace loss is in-memory only; standards references are informative alignment, not certification; hardware validation covers controlled links.
