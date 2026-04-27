"""Gerenciamento de containers Docker/Podman para PostgreSQL."""

import os
import shutil
import subprocess
import sys
import time
import docker
import docker.errors


def _podman_socket_from_cli() -> str | None:
    """
    Consulta o Podman para descobrir o socket atual.
    Funciona com Podman 5+ (applehv, libkrun, qemu) e versões anteriores,
    pois o caminho exato varia por backend e por versão.
    Retorna a URL no formato 'unix://...' ou None se não conseguir descobrir.
    """
    if not shutil.which("podman"):
        return None

    # Podman 4+/5+: 'podman machine inspect' expõe o socket da máquina ativa
    try:
        out = subprocess.run(
            ["podman", "machine", "inspect", "--format",
             "{{.ConnectionInfo.PodmanSocket.Path}}"],
            capture_output=True, text=True, timeout=5,
        )
        path = out.stdout.strip().splitlines()[0] if out.stdout else ""
        if path and os.path.exists(path):
            return f"unix://{path}"
    except (subprocess.SubprocessError, OSError, IndexError):
        pass

    # Linux/rootless e fallback: 'podman info' expõe o RemoteSocket
    try:
        out = subprocess.run(
            ["podman", "info", "--format", "{{.Host.RemoteSocket.Path}}"],
            capture_output=True, text=True, timeout=5,
        )
        path = out.stdout.strip()
        if path:
            return path if path.startswith("unix://") else f"unix://{path}"
    except (subprocess.SubprocessError, OSError):
        pass

    return None


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
        tmpdir = os.environ.get("TMPDIR", "")
        candidates = [
            # Podman 5+ com applehv/libkrun (macOS)
            *([f"unix://{tmpdir.rstrip('/')}/podman/podman-machine-default-api.sock"] if tmpdir else []),
            # Podman QEMU clássico
            f"unix://{home}/.local/share/containers/podman/machine/podman-machine-default/podman.sock",
            f"unix://{home}/.local/share/containers/podman/machine/qemu/podman.sock",
            *([f"unix://{xdg}/podman/podman.sock"] if xdg else []),
        ]
        return candidates
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
      1. docker.from_env()       — Docker padrão ou DOCKER_HOST customizado
      2. Socket do Podman descoberto via 'podman machine inspect'/'podman info'
      3. Caminhos de socket conhecidos do Podman (fallback estático)
    """
    tried: list[str] = []

    # 1. Variáveis de ambiente / Docker padrão
    try:
        client = docker.from_env()
        client.ping()
        return client
    except Exception:
        tried.append("docker.from_env() / DOCKER_HOST")

    # 2. Socket do Podman descoberto dinamicamente
    discovered = _podman_socket_from_cli()
    if discovered:
        try:
            client = docker.DockerClient(base_url=discovered)
            client.ping()
            return client
        except Exception:
            tried.append(discovered)

    # 3. Sockets do Podman conhecidos (fallback)
    for url in _candidate_sockets():
        if url == discovered:
            continue
        try:
            client = docker.DockerClient(base_url=url)
            client.ping()
            return client
        except Exception:
            tried.append(url)
            continue

    tried_lines = "\n    ".join(tried) if tried else "(nenhum)"
    raise RuntimeError(
        "Não foi possível conectar ao Docker nem ao Podman.\n"
        "  • Docker: verifique se o Docker Desktop está em execução.\n"
        "  • Podman: execute 'podman machine start' ou defina DOCKER_HOST "
        "apontando para o socket do Podman.\n"
        f"  Caminhos tentados:\n    {tried_lines}"
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
