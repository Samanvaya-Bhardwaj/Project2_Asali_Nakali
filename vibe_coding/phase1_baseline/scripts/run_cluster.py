#!/usr/bin/env python3
"""
run_cluster.py
--------------
Distributed Node Cluster Launcher for Multi-PC and Local Simulation Environments.

Modes:
  --mode pc1     : Starts PC 1 Node Server (DB1 NoSQL + DB2 Relational SQL) on Port 8011
  --mode pc2     : Starts PC 2 Node Server (DB3 CDSCO MDM + DB4 Ministry REST) on Port 8012
  --mode all     : Concurrently starts both PC 1 and PC 2 servers on the local machine
  --check-health : Pings all distributed node endpoints and displays cluster status
"""

from __future__ import annotations
import sys
import os
import time
import urllib.request
import urllib.error
import json
import argparse
import subprocess
import threading

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from integration.distributed_config import get_topology_config


def check_node_health() -> bool:
    cfg = get_topology_config()
    print("=" * 72)
    print("  DISTRIBUTED MULTI-PC CLUSTER HEALTH CHECK")
    print("=" * 72)

    all_ok = True
    nodes = [
        ("PC 1 Node (Retail & Supply Chain)", f"{cfg['pc1_node']['url']}/health"),
        ("PC 2 Node (Regulatory Authority)", f"{cfg['pc2_node']['url']}/health")
    ]

    for name, url in nodes:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ClusterHealth/1.0"})
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                data = json.loads(resp.read().decode("ascii"))
                print(f"  [ONLINE]  {name}")
                print(f"            Endpoint: {url}")
                print(f"            Services: {len(data.get('hosted_services', []))} active")
        except Exception as e:
            print(f"  [OFFLINE] {name}")
            print(f"            Endpoint: {url} ({e})")
            all_ok = False

    print("=" * 72)
    return all_ok


def start_pc1():
    from api.node_pc1 import run_node_pc1
    cfg = get_topology_config()
    run_node_pc1(host="0.0.0.0", port=cfg["pc1_node"]["port"])


def start_pc2():
    from api.node_pc2 import run_node_pc2
    cfg = get_topology_config()
    run_node_pc2(host="0.0.0.0", port=cfg["pc2_node"]["port"])


def start_cluster():
    cfg = get_topology_config()
    print("=" * 72)
    print("  LAUNCHING ASALI-NAKALI DISTRIBUTED MULTI-NODE CLUSTER")
    print("=" * 72)
    print(f"  * Node PC 1 : {cfg['pc1_node']['url']}  (DB1 NoSQL + DB2 Relational SQL)")
    print(f"  * Node PC 2 : {cfg['pc2_node']['url']}  (DB3 Central MDM + DB4 Ministry REST)")
    print("=" * 72)

    t1 = threading.Thread(target=start_pc1, daemon=True)
    t2 = threading.Thread(target=start_pc2, daemon=True)
    t1.start()
    t2.start()

    time.sleep(0.5)
    check_node_health()

    print("\n[+] Cluster is operational. Press Ctrl+C to stop.\n")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[!] Cluster stopped.")


def stop_cluster() -> None:
    """
    Stops node servers started from this project, including ones left running in
    the background where Ctrl+C has nothing to interrupt.
    """
    import signal

    me = os.getpid()
    killed = []

    try:
        out = subprocess.run(
            ["ps", "-eo", "pid,command"], capture_output=True, text=True, check=False
        ).stdout
    except Exception as e:
        print(f"  Could not list processes: {e}")
        return

    for line in out.splitlines()[1:]:
        line = line.strip()
        if not line:
            continue
        pid_str, _, command = line.partition(" ")
        try:
            pid = int(pid_str)
        except ValueError:
            continue
        if pid == me:
            continue
        # Only our own launcher and node modules, never an unrelated python
        if ("run_cluster.py" in command or "node_pc1" in command or "node_pc2" in command) \
                and "--stop" not in command:
            try:
                os.kill(pid, signal.SIGTERM)
                killed.append(pid)
            except ProcessLookupError:
                pass
            except PermissionError:
                print(f"  No permission to stop PID {pid}")

    if killed:
        time.sleep(0.6)
        for pid in killed:
            try:
                os.kill(pid, 0)          # still alive? insist
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
        print(f"  Stopped {len(killed)} node process(es): {', '.join(str(p) for p in killed)}")
    else:
        print("  No running node processes found.")


def main():
    parser = argparse.ArgumentParser(description="Distributed Cluster Runner for Asali-Nakali")
    parser.add_argument("--mode", choices=["pc1", "pc2", "all"], default="all", help="Node to start (pc1, pc2, or all)")
    parser.add_argument("--check-health", action="store_true", help="Check status of all distributed nodes")
    parser.add_argument("--stop", action="store_true", help="Stop node servers, including detached ones")
    args = parser.parse_args()

    if args.stop:
        stop_cluster()
        return

    if args.check_health:
        check_node_health()
        return

    if args.mode == "pc1":
        start_pc1()
    elif args.mode == "pc2":
        start_pc2()
    else:
        start_cluster()


if __name__ == "__main__":
    main()
