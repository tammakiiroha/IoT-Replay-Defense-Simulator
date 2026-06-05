from __future__ import annotations

import dataclasses
import random

import pytest
from pydantic import ValidationError

from replay.api.app import app
from replay.contracts import SimulationSpec, SweepSpec
from replay.core import Mode, SimulationConfig, run_many_experiments
from replay.core.receiver import Receiver
from replay.core.security import compute_mac
from replay.core.sender import Sender
from replay.core.types import Frame
from replay.services.simulation import run_sweep

SHARED_KEY = "test_key"
MAC_LENGTH = 8


def create_frame(counter: int, command: str = "CMD", key: str = SHARED_KEY) -> Frame:
    return Frame(
        command=command,
        counter=counter,
        mac=compute_mac(counter, command, key, MAC_LENGTH),
    )


def challenge_frame(nonce: str, command: str = "CMD") -> Frame:
    return Frame(
        command=command,
        nonce=nonce,
        mac=compute_mac(nonce, command, SHARED_KEY, MAC_LENGTH),
    )


def test_window_accepts_far_future_counter_and_advances() -> None:
    receiver = Receiver(Mode.WINDOW, shared_key=SHARED_KEY, mac_length=MAC_LENGTH, window_size=5)
    receiver.process(create_frame(10))

    res = receiver.process(create_frame(16))
    assert res.accepted
    assert res.reason == "window_accept_new"
    assert receiver.state.last_counter == 16

    replay = receiver.process(create_frame(10))
    assert not replay.accepted
    assert replay.reason == "counter_too_old"


def test_challenge_allows_two_outstanding_nonces_out_of_order() -> None:
    receiver = Receiver(Mode.CHALLENGE, shared_key=SHARED_KEY, mac_length=MAC_LENGTH)
    rng = random.Random(1)
    n1 = receiver.issue_nonce(rng)
    n2 = receiver.issue_nonce(rng)

    assert receiver.process(challenge_frame(n2)).accepted
    assert receiver.process(challenge_frame(n1)).accepted

    replay = receiver.process(challenge_frame(n1))
    assert not replay.accepted
    assert replay.reason == "challenge_replay"


def test_run_sweep_respects_explicit_zero_fixed_p_loss() -> None:
    spec = SweepSpec(
        sweep_type="p_reorder",
        values=[0.0, 0.2],
        simulation=SimulationSpec(modes=["no_def"], runs=2, num_legit=3, num_replay=3, seed=1),
        fixed_p_loss=0.0,
    )
    points = run_sweep(spec, show_progress=False)
    assert all(point.result.p_loss == 0.0 for point in points)


def test_simulation_response_redacts_shared_key() -> None:
    from fastapi.testclient import TestClient

    client = TestClient(app)
    resp = client.post(
        "/api/v1/simulations",
        json={
            "modes": ["no_def"],
            "runs": 2,
            "num_legit": 3,
            "num_replay": 3,
            "seed": 1,
            "shared_key": "TOP_SECRET_KEY",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "TOP_SECRET_KEY" not in resp.text
    assert "shared_key" not in body["config"]


def test_simulation_spec_rejects_oversized_workload() -> None:
    with pytest.raises(ValidationError):
        SimulationSpec(
            modes=["no_def", "rolling"],
            runs=10_000,
            num_legit=10_000,
            num_replay=10_000,
        )


def test_aggregate_exposes_raw_counts_and_ci() -> None:
    cfg = SimulationConfig(mode=Mode.NO_DEFENSE, num_legit=5, num_replay=5, p_loss=0.0)
    stats = run_many_experiments(cfg, modes=[Mode.NO_DEFENSE], runs=10, seed=1, show_progress=False)
    entry = stats[0]
    assert entry.legit_total == 50
    assert entry.legit_accepted == 50
    assert 0.0 <= entry.lar_ci_low <= entry.avg_legit_rate <= entry.lar_ci_high <= 1.0
    assert "asr_ci_low" in entry.as_dict()


def test_hsw_cr_nonce_path_and_sender_shapes() -> None:
    receiver = Receiver(Mode.HSW_CR, shared_key=SHARED_KEY, mac_length=MAC_LENGTH)
    nonce = receiver.issue_nonce(random.Random(1))
    assert nonce in receiver.state.outstanding_nonces

    sender = Sender(Mode.HSW_CR, shared_key=SHARED_KEY, mac_length=MAC_LENGTH)
    challenge = sender.next_frame("UNLOCK", nonce=nonce)
    assert challenge.nonce == nonce
    assert challenge.counter is None

    normal = sender.next_frame("PING")
    assert normal.counter == 1
    assert normal.nonce is None


def test_ascon_profile_runs_end_to_end_if_available() -> None:
    pytest.importorskip("ascon")
    cfg = SimulationConfig(mode=Mode.WINDOW, num_legit=10, num_replay=10, window_size=5)
    cfg = dataclasses.replace(cfg, auth_profile="ascon")
    stats = run_many_experiments(cfg, modes=[Mode.WINDOW], runs=5, seed=1, show_progress=False)
    assert stats[0].avg_legit_rate >= 0.99
    assert stats[0].metadata.get("auth_profile") == "ascon"
