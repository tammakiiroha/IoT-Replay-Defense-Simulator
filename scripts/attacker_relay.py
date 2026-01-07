#!/usr/bin/env python3
"""
Attacker Relay for 3-HackRF Setup.

Role: Mallory (Man-in-the-Middle / Sniffer-Replayer)

Topology:
  [HackRF 1 (Alice)] -> AIR -> [HackRF 3 (Mallory)] -> (Record)
                                    |
                                    v
                               (Replay Later) -> AIR -> [HackRF 2 (Bob)]

Usage:
  1. Setup GRC Flowgraph for Attacker:
     - Osmocom Source (RX) -> GFSK Demod -> Packet Decoder -> ZMQ PUSH (tcp://*:5557)
     - ZMQ PULL (tcp://*:5558) -> Packet Encoder -> GFSK Mod -> Osmocom Sink (TX)
  
  2. Run this script:
     python scripts/attacker_relay.py --rx-port 5557 --tx-port 5558 --strategy post

Strategy:
  - post: Record N packets, then blast them all.
  - inline: Randomly interleave (harder to do with single radio unless full duplex or fast switching).
    * Note: HackRF is Half-Duplex. It cannot RX and TX at exact same time.
    * This script assumes Mallory switches modes or uses two HackRFs (total 4) or 
    * Mallory receives, stops RX, then transmits.
"""
import argparse
import zmq
import time
import random
import logging
import json

def setup_logger():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [MALLORY] %(message)s')
    return logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rx-port", type=int, default=5557, help="ZMQ PULL port (From GRC RX)")
    parser.add_argument("--tx-port", type=int, default=5558, help="ZMQ PUSH port (To GRC TX)")
    parser.add_argument("--strategy", default="post", choices=["post", "random_delay"])
    parser.add_argument("--delay", type=float, default=2.0, help="Delay before replaying in random_delay mode")
    args = parser.parse_args()
    
    logger = setup_logger()
    context = zmq.Context()
    
    # RX from Radio (Sniffer)
    rx_socket = context.socket(zmq.PULL)
    rx_socket.connect(f"tcp://127.0.0.1:{args.rx_port}")
    
    # TX to Radio (Jammer/Replayer)
    tx_socket = context.socket(zmq.PUSH)
    tx_socket.bind(f"tcp://*:{args.tx_port}")
    
    logger.info(f"Mallory Active. Sniffing on {args.rx_port}, Replaying to {args.tx_port}")
    logger.info("Note: Ensure your GRC flograph handles Half-Duplex switching if using one SDR for Mallory.")
    
    captured_packets = []
    
    try:
        while True:
            # 1. Sniff
            if rx_socket.poll(100):
                msg = rx_socket.recv()
                try:
                    # Parse just to log
                    data = json.loads(msg.decode('utf-8'))
                    cnt = data.get("cnt", "?")
                    logger.info(f"Sniffed frame: cnt={cnt}")
                    
                    captured_packets.append(msg)
                    
                    # Strategy: Random Delay (Instant Replay)
                    if args.strategy == "random_delay":
                        time.sleep(args.delay + random.uniform(0, 1.0))
                        logger.info(f"Replaying frame: cnt={cnt}")
                        tx_socket.send(msg)
                        
                except Exception as e:
                    logger.error(f"Error parsing sniffed packet: {e}")
                    
            # Strategy: Post (Batch Replay) - Trigger manually or by count?
            # For automation, let's say after 10 packets we replay them all
            if args.strategy == "post" and len(captured_packets) >= 10:
                logger.info("Batch Replay Triggered! Blasting 10 packets...")
                for pkt in captured_packets:
                    tx_socket.send(pkt)
                    logger.info("  -> Replayed packet")
                    time.sleep(0.1)
                captured_packets.clear()
                
    except KeyboardInterrupt:
        logger.info("Mallory signing off.")
    finally:
        rx_socket.close()
        tx_socket.close()
        context.term()

if __name__ == "__main__":
    main()
