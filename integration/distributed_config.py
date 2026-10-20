#!/usr/bin/env python3
"""
distributed_config.py
---------------------
Dynamic Network Topology Configuration for Distributed Multi-PC and Docker Deployments.

Supports:
  1. Two physical PCs on the same LAN (e.g., PC 1 at 192.168.1.10, PC 2 at 192.168.1.20)
  2. Multi-container Docker deployment with bridge network aliases
  3. Single-machine local development cluster (127.0.0.1 with separate ports)
"""

from __future__ import annotations
import os
import json
from typing import Dict, Any

# Environment variable overrides
PC1_HOST = os.environ.get("PC1_HOST", "127.0.0.1")
PC1_PORT = int(os.environ.get("PC1_PORT", "8011"))

PC2_HOST = os.environ.get("PC2_HOST", "127.0.0.1")
PC2_PORT = int(os.environ.get("PC2_PORT", "8012"))
DB4_PORT = int(os.environ.get("DB4_PORT", "8001"))

MEDIATOR_PORT = int(os.environ.get("MEDIATOR_PORT", "8000"))

CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "network_topology.json")


def get_topology_config() -> Dict[str, Any]:
    """Returns current active network endpoints for all distributed nodes."""
    # Check if a persistent config file exists
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="ascii") as f:
                data = json.load(f)
                return data
        except Exception:
            pass

    return {
        "pc1_node": {
            "name": "PC 1: Retail & Logistics Edge Node",
            "host": PC1_HOST,
            "port": PC1_PORT,
            "services": ["DB1_Retail_POS_NoSQL", "DB2_Distributor_ERP_SQL"],
            "url": f"http://{PC1_HOST}:{PC1_PORT}"
        },
        "pc2_node": {
            "name": "PC 2: Regulatory Authority Cloud Node",
            "host": PC2_HOST,
            "port": PC2_PORT,
            "services": ["DB3_CDSCO_Master_Registry", "DB4_Ministry_Grievance_REST"],
            "url": f"http://{PC2_HOST}:{PC2_PORT}",
            "db4_url": f"http://{PC2_HOST}:{DB4_PORT}/api/v1"
        },
        "mediator_node": {
            "name": "Central GAV Mediator & Web Dashboard",
            "port": MEDIATOR_PORT,
            "url": f"http://127.0.0.1:{MEDIATOR_PORT}"
        }
    }


def save_topology_config(pc1_host: str, pc2_host: str, pc1_port: int = 8011, pc2_port: int = 8012) -> Dict[str, Any]:
    """Persists updated IP addresses and ports configured from dashboard or CLI."""
    cfg = {
        "pc1_node": {
            "name": "PC 1: Retail & Logistics Edge Node",
            "host": pc1_host.strip(),
            "port": int(pc1_port),
            "services": ["DB1_Retail_POS_NoSQL", "DB2_Distributor_ERP_SQL"],
            "url": f"http://{pc1_host.strip()}:{int(pc1_port)}"
        },
        "pc2_node": {
            "name": "PC 2: Regulatory Authority Cloud Node",
            "host": pc2_host.strip(),
            "port": int(pc2_port),
            "services": ["DB3_CDSCO_Master_Registry", "DB4_Ministry_Grievance_REST"],
            "url": f"http://{pc2_host.strip()}:{int(pc2_port)}",
            "db4_url": f"http://{pc2_host.strip()}:8001/api/v1"
        },
        "mediator_node": {
            "name": "Central GAV Mediator & Web Dashboard",
            "port": MEDIATOR_PORT,
            "url": f"http://127.0.0.1:{MEDIATOR_PORT}"
        }
    }
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="ascii") as f:
        json.dump(cfg, f, indent=2)
    return cfg
