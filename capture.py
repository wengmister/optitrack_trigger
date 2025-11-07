#!/usr/bin/env python3
"""
OptiTrack interactive capture

- Streams OptiTrack rigid body data from Motive (NatNet).
- Captures one sample each time the user presses Enter.
- Type 'q' (or Ctrl+C) to end the session and save to CSV.

Requirements:
  - Motive 2.x running with NatNet streaming enabled
  - NatNet Python client files in your PYTHONPATH:
      NatNetClient.py, MoCapData.py, DataDescriptions.py

Typical usage:
  python capture.py --local-ip 127.0.0.1 --server-ip 127.0.0.1 --rbid 1 --outfile sess.csv --position-scale 1.0

Notes on units:
  - Natnet streams in meters.

Windows firewall:
  - Ensure UDP ports used by NatNet are allowed (commonly 1510/1511).
"""

import atexit
import csv
import sys
import time
import threading
import argparse
from dataclasses import dataclass
from typing import List, Optional
from NatNetClient import NatNetClient  # from OptiTrack NatNet Python SDK


@dataclass
class OptitrackRigidBodyData:
    timestamp: float        # seconds since epoch (float)
    position: List[float]   # [x, y, z]
    orientation: List[float]  # quaternion [qx, qy, qz, qw]


class OptitrackReceiver:
    """
    Maintains the most recent rigid body data via NatNet callbacks.
    """
    def __init__(self, local_ip_address: str, server_ip_address: str,
                 rigid_body_streaming_id: int, position_scale: float = 1.0):
        self.local_ip_address = local_ip_address
        self.server_ip_address = server_ip_address
        self.rigid_body_streaming_id = rigid_body_streaming_id
        self.position_scale = position_scale

        self._latest: Optional[OptitrackRigidBodyData] = None
        self._lock = threading.Lock()

        self.client = NatNetClient()
        self.client.local_ip_address = self.local_ip_address
        self.client.server_ip_address = self.server_ip_address

        # Register callback for rigid body frames.
        # Some NatNet versions add extra params to this callback; accept *args safely.
        self.client.rigid_body_listener = self._on_rigid_body_frame

        atexit.register(self.stop)

    def start(self):
        """Start receiving data in the client’s internal thread."""
        self.client.run()

    def stop(self):
        """Shutdown the NatNet client."""
        try:
            self.client.shutdown()
        except Exception:
            pass

    def _on_rigid_body_frame(self, rigid_body_id, position, rotation_quat, *args):
        """
        Callback invoked by NatNet for each rigid body each frame.

        Accepts extra trailing args for compatibility across NatNet versions.
        """
        if rigid_body_id != self.rigid_body_streaming_id:
            # Ignore other bodies
            return

        now = time.time()
        try:
            px, py, pz = position
            qx, qy, qz, qw = rotation_quat
        except Exception:
            # Malformed frame; ignore
            return

        scaled_position = [px * self.position_scale,
                           py * self.position_scale,
                           pz * self.position_scale]

        data = OptitrackRigidBodyData(
            timestamp=now,
            position=scaled_position,
            orientation=[qx, qy, qz, qw]
        )
        with self._lock:
            self._latest = data

    def get_latest(self) -> Optional[OptitrackRigidBodyData]:
        with self._lock:
            return self._latest


def save_samples_to_csv(samples: List[dict], outfile: str):
    """
    Save a list of dict samples to CSV. Each dict must have identical keys.
    """
    if not samples:
        print("No samples to save.")
        return

    fieldnames = list(samples[0].keys())
    # newline='' for correct CSV on Windows
    with open(outfile, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(samples)
    print(f"Saved {len(samples)} samples to: {outfile}")


def main():
    parser = argparse.ArgumentParser(description="Interactive OptiTrack capture (press Enter to sample, 'q' to quit).")
    parser.add_argument("--local-ip", required=True, help="Local adapter IP (the laptop that runs this script).")
    parser.add_argument("--server-ip", required=True, help="Motive host IP (the PC running Motive).")
    parser.add_argument("--rbid", required=True, type=int, help="Rigid body streaming ID to capture.")
    parser.add_argument("--outfile", default=None, help="CSV output path. Default uses timestamp.")
    parser.add_argument("--position-scale", type=float, default=1000.0,
                        help="Scale applied to positions from NatNet. "
                             "1.0 for m; 1000.0 for mm")
    args = parser.parse_args()

    if args.outfile is None:
        ts = time.strftime("%Y%m%d_%H%M%S")
        args.outfile = f"optitrack_samples_{ts}.csv"

    receiver = OptitrackReceiver(
        local_ip_address=args.local_ip,
        server_ip_address=args.server_ip,
        rigid_body_streaming_id=args.rbid,
        position_scale=args.position_scale
    )

    print("\n--- OptiTrack Interactive Capture ---")
    print(f" Local IP   : {args.local_ip}")
    print(f" Server IP  : {args.server_ip}")
    print(f" RB ID      : {args.rbid}")
    print(f" Outfile    : {args.outfile}")
    print(f" Pos scale  : {args.position_scale}")
    print("-------------------------------------")
    print("Instructions:")
    print("  • Press Enter to capture the most recent rigid body sample.")
    print("  • Type 'p' + Enter to peek at the current pose without recording.")
    print("  • Type 'q' + Enter (or Ctrl+C) to finish and save.\n")

    receiver.start()
    samples: List[dict] = []
    sample_idx = 0

    try:
        while True:
            user_in = input("[Enter]=capture   'p'=peek   'q'=quit & save > ").strip().lower()
            if user_in == 'q':
                break
            elif user_in == 'p':
                latest = receiver.get_latest()
                if latest is None:
                    print("No data yet. Waiting for Motive stream...")
                else:
                    age_ms = (time.time() - latest.timestamp) * 1000.0
                    px, py, pz = latest.position
                    qx, qy, qz, qw = latest.orientation
                    print(f"Current pose (age ~{age_ms:.1f} ms): "
                          f"pos=[{px:.3f}, {py:.3f}, {pz:.3f}]  "
                          f"quat=[{qx:.5f}, {qy:.5f}, {qz:.5f}, {qw:.5f}]")
                continue
            else:
                # Treat anything else (including empty string / Enter) as "capture"
                latest = receiver.get_latest()
                if latest is None:
                    print("No data yet to capture. Try again in a moment (stream starting?)")
                    continue

                now = time.time()
                age_ms = (now - latest.timestamp) * 1000.0
                px, py, pz = latest.position
                qx, qy, qz, qw = latest.orientation

                # Record a flat row for CSV
                row = {
                    "event_time": now,
                    "frame_time": latest.timestamp,
                    "age_ms": age_ms,
                    "x": px, "y": py, "z": pz,
                    "qx": qx, "qy": qy, "qz": qz, "qw": qw,
                    "rigid_body_id": args.rbid
                }
                samples.append(row)
                sample_idx += 1
                print(f"Captured sample #{sample_idx} (age ~{age_ms:.1f} ms)")

    except KeyboardInterrupt:
        print("\nInterrupted by user (Ctrl+C).")

    finally:
        # Always attempt a clean shutdown and save
        try:
            receiver.stop()
        except Exception:
            pass
        save_samples_to_csv(samples, args.outfile)


if __name__ == "__main__":
    # On Windows, avoid printing traceback on Ctrl+C
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)