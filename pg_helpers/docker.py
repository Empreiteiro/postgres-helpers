"""Gerenciamento de containers Docker para PostgreSQL."""

import time
import docker
import docker.errors


def _client():
    try:
        return docker.from_env()
    except Exception as e:
        raise RuntimeError(
            "Não foi possível conectar ao Docker. Verifique se o Docker Desktop está em execução."
        ) from e


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
