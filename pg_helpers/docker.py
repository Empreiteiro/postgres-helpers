"""Gerenciamento de containers Docker/Podman para PostgreSQL."""

import os
import sys
import time
import docker
import docker.errors


def _candidate_sockets() -> list[str]:
    """Retorna caminhos de socket candidatos para Podman, por plataforma."""
    if sys.platform == "win32":
        return [
            "npipe:////./pipe/podman-machine-default",
            "npipe:////./pipe/podman-machine-default-root",
        ]
    if sys.platform == "darwin":
        home = os.path.expanduser("~")
        xdg = os.environ.get("XDG_RUNTIME_DIR", "")
        return [
            f"unix://{home}/.local/share/containers/podman/machine/podman-machine-default/podman.sock",
            f"unix://{home}/.local/share/containers/podman/machine/qemu/podman.sock",
            *([ f"unix://{xdg}/podman/podman.sock"] if xdg else []),
        ]
    # Linux
    uid = os.getuid()
    xdg = os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{uid}")
    return [
        f"unix://{xdg}/podman/podman.sock",
        f"unix:///run/user/{uid}/podman/podman.sock",
        "unix:///run/podman/podman.sock",
    ]


def _client() -> docker.DockerClient:
    """
    Conecta ao runtime de containers disponível.
    Tenta, em ordem:
      1. docker.from_env()  — Docker padrão ou DOCKER_HOST customizado
      2. Caminhos de socket conhecidos do Podman
    """
    # 1. Variáveis de ambiente / Docker padrão
    try:
        client = docker.from_env()
        client.ping()
        return client
    except Exception:
        pass

    # 2. Sockets do Podman
    for url in _candidate_sockets():
        try:
            client = docker.DockerClient(base_url=url)
            client.ping()
            return client
        except Exception:
            continue

    raise RuntimeError(
        "Não foi possível conectar ao Docker nem ao Podman.\n"
        "  • Docker: verifique se o Docker Desktop está em execução.\n"
        "  • Podman: execute 'podman machine start' ou defina DOCKER_HOST "
        "apontando para o socket do Podman."
    )


def create_postgres(name: str, port: int, password: str = "postgres") -> bool:
    client = _client()
    container_name = f"pghelper_{name}"

    # Reusar container existente se parado
    try:
        existing = client.containers.get(container_name)
        if existing.status != "running":
            existing.start()
        return True
    except docker.errors.NotFound:
        pass

    client.containers.run(
        "postgres:16-alpine",
        name=container_name,
        environment={
            "POSTGRES_PASSWORD": password,
            "POSTGRES_USER": "postgres",
            "POSTGRES_DB": "postgres",
        },
        ports={"5432/tcp": port},
        detach=True,
        labels={"managed_by": "pg_helpers"},
    )
    return True


def wait_for_ready(name: str, port: int, timeout: int = 60) -> bool:
    import psycopg2

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            conn = psycopg2.connect(
                host="localhost",
                port=port,
                user="postgres",
                password="postgres",
                dbname="postgres",
                connect_timeout=2,
            )
            conn.close()
            return True
        except Exception:
            time.sleep(1)
    return False


def remove_postgres(name: str) -> bool:
    client = _client()
    container_name = f"pghelper_{name}"
    try:
        container = client.containers.get(container_name)
        container.stop(timeout=5)
        container.remove()
        return True
    except docker.errors.NotFound:
        return False


def list_postgres() -> list[dict]:
    client = _client()
    containers = client.containers.list(all=True, filters={"label": "managed_by=pg_helpers"})
    return [
        {
            "name": c.name,
            "status": c.status,
            "ports": c.ports,
        }
        for c in containers
    ]
