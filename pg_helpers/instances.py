"""Gerenciamento do estado das instâncias PostgreSQL (instances.json)."""

import json
import socket
from pathlib import Path
from datetime import datetime

INSTANCES_FILE = Path(__file__).parent.parent / "instances.json"


def load() -> dict:
    if INSTANCES_FILE.exists():
        return json.loads(INSTANCES_FILE.read_text(encoding="utf-8"))
    return {}


def save(data: dict):
    INSTANCES_FILE.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def add(name: str, port: int, password: str, scenario: str | None) -> dict:
    data = load()
    data[name] = {
        "container_name": f"pghelper_{name}",
        "host": "localhost",
        "port": port,
        "user": "postgres",
        "password": password,
        "dbname": "postgres",
        "scenario": scenario,
        "created_at": datetime.now().isoformat(),
    }
    save(data)
    return data[name]


def remove(name: str):
    data = load()
    data.pop(name, None)
    save(data)


def is_port_in_use(port: int) -> bool:
    """Verifica se uma porta TCP está em uso por qualquer processo."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex(("localhost", port)) == 0


def next_port(base: int = 5432) -> int:
    """Retorna a próxima porta livre: não usada por instâncias gerenciadas nem por outro processo."""
    used_by_instances = {v["port"] for v in load().values()}
    port = base
    while port in used_by_instances or is_port_in_use(port):
        port += 1
    return port
