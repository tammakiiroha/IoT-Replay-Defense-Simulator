# Why Replay Defense Fails Under Lossy IoT Links

ReplayBench-IoT evaluates replay defenses under the constraints that make low-cost IoT links difficult: packet loss, reordering, short authentication tags, bounded receiver state, and commands with different safety risk.

The main lesson is that replay protection is not a single mechanism. A rolling counter is simple and cheap, but it treats delayed legitimate frames as stale once a later frame has advanced the counter. RFC-style sliding windows reduce that false rejection by retaining a bitmap of recent authenticated counters. Challenge-response reduces replay risk for high-value commands, but it adds round trips and nonce state.

HSW-CR combines both paths. Low-risk traffic uses the sliding-window verifier. High-risk commands such as `UNLOCK`, `OPEN`, or `ENABLE` require a fresh nonce, so a recorded command replay carries a nonce already consumed by the receiver and is rejected. This gives developers a practical policy knob: spend latency and state only where command risk justifies it.

The figures in `docs/figures/` summarize three views:

- `asr_vs_loss.png`: attack success rate under increasing packet loss.
- `lar_vs_reorder.png`: legitimate acceptance under reordering.
- `security_cost_frontier.png`: replay resistance against the energy proxy.

The trace-driven channel model currently accepts in-memory boolean loss traces only. It is useful for deterministic sensitivity tests, but it is not yet a pcap or CSV ingestion pipeline.
