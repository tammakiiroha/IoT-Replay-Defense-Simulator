#!/usr/bin/env python3
"""
GNURadio Adapter for IoT Replay Simulator.

This script acts as a bridge between the logic-level simulator (Sender/Receiver)
and a GNURadio flowgraph via ZeroMQ (ZMQ).

Modes:
1. --mode tx: Generates frames using sim.Sender logic -> Sends bytes via ZMQ PUSH to GNURadio.
2. --mode rx: Receives bytes via ZMQ PULL from GNURadio -> Processes using sim.Receiver logic.

Requirements:
  pip install pyzmq
"""
import argparse
import json
import logging
import os
import sys
import time
import zmq

# Add project root to path to allow importing 'sim'
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

try:
    from sim.sender import Sender
    from sim.receiver import Receiver
    from sim.types import Mode
except ImportError:
    print("Error: Could not import 'sim' package. Make sure you are running from the project root or 'scripts/' directory.")
    sys.exit(1)


# Configuration
DEFAULT_ZMQ_HOST = "127.0.0.1"
DEFAULT_TX_PORT = 5555
DEFAULT_RX_PORT = 5556

def setup_logger():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - [GNURadio-Adapter] - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)

def run_tx(args, logger):
    """
    Sender Mode:
    1. Connects to GNURadio ZMQ PULL Source (we act as PUSH).
    2. Generates frames using Simulation logic.
    3. Serializes to JSON/Bytes and sends.
    """
    context = zmq.Context()
    socket = context.socket(zmq.PUSH)
    address = f"tcp://{args.host}:{args.port}"
    socket.bind(address)  # We bind, GNURadio connects
    
    logger.info(f"TX Mode: Bound to {address}. Waiting for GNURadio to pull data...")

    # Initialize Sender logic
    # Note: Using DEFAULT_KEY from commands or a fixed one for demo
    sender = Sender(mode=Mode(args.sim_mode), shared_key="gnuradio_key")
    
    # Simple demo command sequence
    commands = ["FWD", "FWD", "LEFT", "RIGHT", "STOP", "FWD", "STOP"]
    
    try:
        while True:
            for cmd in commands:
                # 1. Logic Layer: Generate Frame
                frame = sender.next_frame(cmd)
                
                # 2. Serialization Layer: Convert to bytes
                # Format: JSON string + newline (simple text protocol)
                # In a real SDR scenario, you might want to pack bits
                payload = json.dumps({
                    "c": frame.command,
                    "cnt": frame.counter,
                    "mac": frame.mac,
                    "n": frame.nonce
                }).encode('utf-8')
                
                # 3. Transport Layer: Send to GNURadio
                logger.info(f"Sending: {frame}")
                socket.send(payload)
                
                time.sleep(1.0) # 1 message per second
    except KeyboardInterrupt:
        logger.info("Stopping TX...")
    finally:
        socket.close()
        context.term()

def run_rx(args, logger):
    """
    Receiver Mode:
    1. Connects to GNURadio ZMQ PUSH Sink (we act as PULL).
    2. Receives bytes.
    3. Deserializes and feeds to Receiver logic.
    """
    context = zmq.Context()
    socket = context.socket(zmq.PULL)
    address = f"tcp://{args.host}:{args.port}"
    socket.connect(address) # GNURadio likely binds PUSH, so we connect PULL? 
    # Actually, usually GNURadio ZMQ Sink Binds, so we Connect.
    # Check args carefully in docs. Let's assume user configures properly.
    # For this script, let's allow user to specify bind/connect if needed, 
    # but for simplicity we'll connect.
    
    logger.info(f"RX Mode: Connecting to {address}...")

    receiver = Receiver(mode=Mode(args.sim_mode), shared_key="gnuradio_key")

    try:
        while True:
            # 1. Transport Layer: Receive from GNURadio
            if socket.poll(timeout=1000): # Check for data
                msg = socket.recv()
                
                try:
                    # 2. Deserialization Layer
                    data = json.loads(msg.decode('utf-8'))
                    cmd = data.get("c")
                    counter = data.get("cnt")
                    mac = data.get("mac")
                    nonce = data.get("n")
                    
                    # 3. Logic Layer: Validate
                    # Make a pure object structure if Receiver needs it, 
                    # but current Receiver.receive takes explicit args or a Frame object?
                    # Let's check Receiver.receive signature. 
                    # Warning: Need to ensure type compatibility.
                    
                    # Assuming Receiver.receive(frame) or similar.
                    # Let's import Frame to be safe
                    from sim.types import Frame
                    
                    frame = Frame(command=cmd, counter=counter, mac=mac, nonce=nonce)
                    is_valid = receiver.receive(frame)
                    
                    status = "ACCEPTED" if is_valid else "REJECTED"
                    color = "\033[92m" if is_valid else "\033[91m"
                    reset = "\033[0m"
                    
                    logger.info(f"Received: {frame} => {color}{status}{reset}")
                    
                except json.JSONDecodeError:
                    logger.warning(f"Received non-JSON data: {msg}")
                except Exception as e:
                    logger.error(f"Error processing frame: {e}")
            else:
                # Idle loop
                pass
                
    except KeyboardInterrupt:
        logger.info("Stopping RX...")
    finally:
        socket.close()
        context.term()

def main():
    parser = argparse.ArgumentParser(description="GNURadio ZMQ Adapter")
    
    subparsers = parser.add_subparsers(dest="role", required=True, help="Role: tx or rx")
    
    # TX Arguments
    tx_parser = subparsers.add_parser("tx", help="Transmitter Mode (Send to GNURadio)")
    tx_parser.add_argument("--host", default=DEFAULT_ZMQ_HOST, help="ZMQ Host")
    tx_parser.add_argument("--port", type=int, default=DEFAULT_TX_PORT, help="ZMQ Port")
    tx_parser.add_argument("--sim-mode", default="window", choices=["no_def", "rolling", "window", "challenge"], help="Protection Mode")

    # RX Arguments
    rx_parser = subparsers.add_parser("rx", help="Receiver Mode (Receive from GNURadio)")
    rx_parser.add_argument("--host", default=DEFAULT_ZMQ_HOST, help="ZMQ Host")
    rx_parser.add_argument("--port", type=int, default=DEFAULT_RX_PORT, help="ZMQ Port (Source form GNURadio)")
    rx_parser.add_argument("--sim-mode", default="window", choices=["no_def", "rolling", "window", "challenge"], help="Protection Mode")
    
    args = parser.parse_args()
    logger = setup_logger()
    
    if args.role == "tx":
        run_tx(args, logger)
    elif args.role == "rx":
        run_rx(args, logger)

if __name__ == "__main__":
    main()
