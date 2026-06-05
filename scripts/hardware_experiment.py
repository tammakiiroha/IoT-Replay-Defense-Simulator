#!/usr/bin/env python3
"""
Hardware Experiment Runner (ZMQ + GNURadio)

This script allows you to run experiments EXACTLY like 'main.py' (Monte Carlo loops),
but using Real Hardware (GNURadio/HackRF) as the channel.

Architecture:
    [Experiment Script]
       |         ^
       v (TX)    | (RX)
    [ZMQ PUSH] [ZMQ PULL]
       |         |
    [GNU Radio Flowgraph]
       |         ^
       v (RF)    | (RF)
    [HackRF A]  [HackRF B]

Usage:
    1. Start your GNURadio flowgraph (with ZMQ Pull=5555, ZMQ Push=5556).
    2. Run this script:
       python scripts/hardware_experiment.py --runs 10 --mode window --window-size 5
"""
import argparse
import json
import logging
import random
import sys
import time
import zmq
import os
from dataclasses import dataclass
from typing import List, Tuple

# Path setup
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from sim.sender import Sender
from sim.receiver import Receiver
from sim.types import Mode, Frame

# Configuration
TX_PORT = 5555
RX_PORT = 5556
TIMEOUT_MS = 2000  # How long to wait for a packet to return (2 seconds)

@dataclass
class HardwareStats:
    legit_sent: int = 0
    legit_accepted: int = 0
    
    replay_sent: int = 0
    replay_success: int = 0
    
    timeouts: int = 0
    artificial_drops: int = 0

def run_hardware_experiment(args, logger):
    """
    Runs an automated experiment loop over the hardware channel.
    Supports:
    - Mixed Legit/Replay traffic (inline or post)
    - Artificial p_loss/p_reorder injection
    """
    context = zmq.Context()
    tx_socket = context.socket(zmq.PUSH)
    bind_host = "*" if getattr(args, "bind_all", False) else "127.0.0.1"
    tx_socket.bind(f"tcp://{bind_host}:{TX_PORT}")
    rx_socket = context.socket(zmq.PULL)
    rx_socket.connect(f"tcp://127.0.0.1:{RX_PORT}")
    
    logger.info(f"Connected. TX:{TX_PORT}, RX:{RX_PORT}")
    logger.info(f"Config: runs={args.runs}, legit={args.num_legit}, replay={args.num_replay}, mode={args.mode}")
    if args.p_loss > 0 or args.p_reorder > 0:
        logger.info(f"Artificial Impairments: p_loss={args.p_loss}, p_reorder={args.p_reorder}")

    rng = random.Random(args.seed)
    overall_stats = HardwareStats()
    
    try:
        for run_idx in range(1, args.runs + 1):
            logger.info(f"--- Run {run_idx}/{args.runs} ---")
            run_rng = random.Random(args.seed + run_idx)
            
            sender = Sender(
                mode=Mode(args.mode),
                shared_key="hw_key",
                mac_length=args.mac_length,
            )
            receiver = Receiver(
                mode=Mode(args.mode),
                shared_key="hw_key",
                mac_length=args.mac_length,
                window_size=args.window_size,
            )
            
            # Build a schedule of traffic types and generate concrete frames at send time.
            # This keeps challenge-mode nonce issuance aligned with the current receiver state.
            schedule = [False] * args.num_legit
            if args.attack_mode == "post":
                schedule.extend([True] * args.num_replay)
            else:
                for _ in range(args.num_replay):
                    if schedule and args.num_legit > 0:
                        insert_idx = run_rng.randint(1, len(schedule))
                    else:
                        insert_idx = 0
                    schedule.insert(insert_idx, True)

            logger.info(
                f"Scheduled {len(schedule)} frames "
                f"({args.num_legit} legit, {args.num_replay} replay)"
            )

            # Delay-and-release queue used to emulate packet reordering at the
            # application boundary after RF reception.
            reorder_buffer: List[Tuple[bytes, bool, Frame, int]] = []

            def process_received_packet(packet_msg: bytes, is_replay_packet: bool, sent_frame: Frame, msg_index: int) -> None:
                try:
                    data = json.loads(packet_msg.decode('utf-8'))
                    rx_frame = Frame(
                        command=data.get("c"),
                        counter=data.get("cnt"),
                        mac=data.get("mac"),
                        nonce=data.get("n")
                    )

                    verification = receiver.process(rx_frame)
                    accepted = verification.accepted

                    status = "ACCEPTED" if accepted else "REJECTED"
                    icon = "✅" if accepted else "❌"
                    type_str = "REPLAY" if is_replay_packet else "LEGIT"

                    logger.info(
                        f"[{type_str}] Msg={msg_index} Sent={sent_frame.counter} Recv={rx_frame.counter} "
                        f"-> {status} {icon} ({verification.reason})"
                    )

                    if is_replay_packet:
                        if accepted:
                            overall_stats.replay_success += 1
                    else:
                        if accepted:
                            overall_stats.legit_accepted += 1
                except Exception as e:
                    logger.error(f"Bad packet: {e}")

            captured_frames = []
            for i, is_replay in enumerate(schedule):
                if is_replay:
                    if not captured_frames:
                        logger.info(f"Msg {i} skipped (no captured frame yet for replay)")
                        continue
                    frame = run_rng.choice(captured_frames).clone()
                    frame.is_attack = True
                else:
                    cmd = "FWD"
                    if sender.mode is Mode.CHALLENGE:
                        nonce = receiver.issue_nonce(run_rng)
                        frame = sender.next_frame(cmd, nonce=nonce)
                    else:
                        frame = sender.next_frame(cmd)
                    captured_frames.append(frame.clone())

                # --- SENDING ---
                payload = json.dumps({
                    "c": frame.command,
                    "cnt": frame.counter,
                    "mac": frame.mac,
                    "n": frame.nonce,
                    # We send 'is_replay' metadata to help us debug, 
                    # but in real world receiver doesn't see this!
                    # We will strip it before receiver sees it.
                    "_dbg_replay": is_replay 
                }).encode('utf-8')
                
                tx_socket.send(payload)
                if is_replay:
                    overall_stats.replay_sent += 1
                else:
                    overall_stats.legit_sent += 1
                
                # --- RECEIVING ---
                # Wait with timeout
                if rx_socket.poll(TIMEOUT_MS):
                    msg = rx_socket.recv()
                    
                    # --- ARTIFICIAL IMPAIRMENTS (Software Channel) ---
                    # 1. Loss
                    if args.p_loss > 0 and rng.random() < args.p_loss:
                        overall_stats.artificial_drops += 1
                        logger.info(f"Msg {i} artificially dropped (p_loss)")
                        continue

                    packet = (msg, is_replay, frame.clone(), i)

                    # 2. Reordering: delay processing of some received packets.
                    if args.p_reorder > 0 and rng.random() < args.p_reorder:
                        reorder_buffer.append(packet)
                        logger.info(f"Msg {i} delayed in reorder buffer (p_reorder)")
                    else:
                        process_received_packet(*packet)

                        # Opportunistically release one delayed packet to create
                        # out-of-order delivery at the app layer.
                        if reorder_buffer and rng.random() < 0.5:
                            delayed_idx = rng.randrange(len(reorder_buffer))
                            delayed_packet = reorder_buffer.pop(delayed_idx)
                            process_received_packet(*delayed_packet)
                else:
                    overall_stats.timeouts += 1
                    logger.info(f"Msg {i} TIMEOUT (Real Loss) ⚠️")
                
                time.sleep(0.05) # Rate limiting

            # Flush delayed packets at end of each run.
            while reorder_buffer:
                delayed_idx = rng.randrange(len(reorder_buffer))
                delayed_packet = reorder_buffer.pop(delayed_idx)
                process_received_packet(*delayed_packet)
                
    except KeyboardInterrupt:
        logger.info("Stopping...")
    finally:
        tx_socket.close()
        rx_socket.close()
        context.term()

    # Report
    print("\n=== HARDWARE RESULTS ===")
    print(f"Legit: {overall_stats.legit_accepted}/{overall_stats.legit_sent} Accepted")
    print(f"Attack: {overall_stats.replay_success}/{overall_stats.replay_sent} Successful")
    print(f"Real Timeouts: {overall_stats.timeouts}")
    print(f"Artificial Drops: {overall_stats.artificial_drops}")
    
    if overall_stats.legit_sent > 0:
        print(f"Legit Acceptance Rate: {overall_stats.legit_accepted/overall_stats.legit_sent:.2%}")
    if overall_stats.replay_sent > 0:
        print(f"Attack Success Rate: {overall_stats.replay_success/overall_stats.replay_sent:.2%}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--num-legit", type=int, default=20)
    parser.add_argument("--num-replay", type=int, default=10)
    parser.add_argument("--mode", default="window", choices=[m.value for m in Mode])
    parser.add_argument("--window-size", type=int, default=5)
    parser.add_argument("--mac-length", type=int, default=8)
    parser.add_argument("--p-loss", type=float, default=0.0, help="Artificial extra loss")
    parser.add_argument("--p-reorder", type=float, default=0.0, help="Probability of delayed packet processing to emulate reordering")
    parser.add_argument("--attack-mode", default="post", choices=["inline", "post"])
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--bind-all", action="store_true", help="Bind TX ZMQ to all interfaces")
    
    args = parser.parse_args()
    if not 0.0 <= args.p_loss <= 1.0:
        parser.error("--p-loss must be in [0.0, 1.0]")
    if not 0.0 <= args.p_reorder <= 1.0:
        parser.error("--p-reorder must be in [0.0, 1.0]")
    if args.runs <= 0:
        parser.error("--runs must be a positive integer")
    if args.num_legit < 0 or args.num_replay < 0:
        parser.error("--num-legit and --num-replay must be non-negative")
    if args.window_size < 0:
        parser.error("--window-size must be non-negative")

    logging.basicConfig(format='%(message)s', level=logging.INFO)
    logger = logging.getLogger("HW")
    run_hardware_experiment(args, logger)


if __name__ == "__main__":
    main()
