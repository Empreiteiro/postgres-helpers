#!/usr/bin/env python3
"""PG Helpers — CLI para criar e gerenciar instâncias PostgreSQL via Docker."""

import typer
from rich.console import Console
from rich.table import Table
from rich import box
from typing import Optional

app = typer.Typer(
    help="PG Helpers — Crie e gerencie instâncias PostgreSQL via Docker.",
    no_args_is_help=True,
)
console = Console()

VALID_SCENARIOS = ["ecommerce", "blog", "hr"]

from pg_helpers.names import random_name as _random_name


@app.command()
def create(
    name: Optional[str] = typer.Argument(None, help="Nome da instância (gerado automaticamente se omitido)"),
    port: Optional[int] = typer.Option(None, "--port", "-p", help="Porta (auto se não especificada)"),
    seed: Optional[str] = typer.Option(None, "--seed", "-s", help="Cenário de dados: ecommerce, blog, hr"),
    password: str = typer.Option("postgres", "--password", help="Senha do PostgreSQL"),
    rows: int = typer.Option(0, "--rows", "-r", help="Quantidade de linhas (0 = padrão do cenário)"),
):
    """Cria uma nova instância PostgreSQL via Docker."""
    from pg_helpers import instances, docker
    from pg_helpers.seeds import seed as do_seed
    from pg_helpers.database import DatabaseManager

    if seed and seed not in VALID_SCENARIOS:
        console.print(f"[red]Cenário inválido: '{seed}'. Opções: {', '.join(VALID_SCENARIOS)}[/red]")
        raise typer.Exit(1)

    existing = instances.load()
    if name is None:
        name = _random_name(set(existing.keys()))
        console.print(f"[dim]Nome gerado: [bold]{name}[/bold][/dim]")

    if name in existing:
        old_port = existing[name]["port"]
        console.print(f"[red]Já existe uma instância chamada '{name}' (porta {old_port}).[/red]")
        console.print(f"  Para criar outro banco: [cyan]python main.py create outro-nome --seed {seed or 'ecommerce'}[/cyan]")
        console.print(f"  Para recriar este:     [cyan]python main.py remove {name} && python main.py create {name}[/cyan]")
        raise typer.Exit(1)

    if port is None:
        port = instances.next_port()
    elif instances.is_port_in_use(port):
        new_port = instances.next_port(port)
        console.print(f"[yellow]Porta {port} em uso. Usando {new_port}.[/yellow]")
        port = new_port

    try:
        with console.status(f"[blue]Criando container '{name}' na porta {port}..."):
            docker.create_postgres(name, port, password)
    except Exception as e:
        console.print(f"[red]Erro ao criar container: {e}[/red]")
        console.print("[yellow]Verifique se o Docker está em execução.[/yellow]")
        raise typer.Exit(1)

    with console.status("[blue]Aguardando PostgreSQL iniciar..."):
        ready = docker.wait_for_ready(name, port, timeout=60)

    if not ready:
        console.print("[red]Timeout: PostgreSQL não iniciou a tempo.[/red]")
        docker.remove_postgres(name)
        raise typer.Exit(1)

    instances.add(name, port, password, seed)
    console.print(f"[green]Instância '{name}' criada na porta {port}.[/green]")

    if seed:
        db = DatabaseManager("localhost", port, "postgres", password, "postgres")
        kwargs = {"n": rows} if rows > 0 else {}
        with console.status(f"[blue]Aplicando dados do cenário '{seed}'..."):
            do_seed(db, seed, incremental=False, **kwargs)
        console.print(f"[green]Dados do cenário '{seed}' inseridos.[/green]")

    conn_str = f"postgresql://postgres:{password}@localhost:{port}/postgres"
    console.print(f"\n[bold]String de conexão:[/bold]")
    console.print(f"  [cyan]{conn_str}[/cyan]")


@app.command("create-many")
def create_many(
    count: int = typer.Argument(..., help="Número de instâncias a criar"),
    base_name: str = typer.Option("pg", "--base-name", "-n", help="Nome base (ex: 'pg' → pg-1, pg-2...)"),
    base_port: int = typer.Option(5432, "--base-port", "-p", help="Porta inicial"),
    seed: Optional[str] = typer.Option(None, "--seed", "-s", help="Cenário de dados: ecommerce, blog, hr"),
    password: str = typer.Option("postgres", "--password", help="Senha do PostgreSQL"),
):
    """Cria múltiplas instâncias PostgreSQL com portas sequenciais."""
    from pg_helpers import instances, docker
    from pg_helpers.seeds import seed as do_seed
    from pg_helpers.database import DatabaseManager

    if seed and seed not in VALID_SCENARIOS:
        console.print(f"[red]Cenário inválido: '{seed}'[/red]")
        raise typer.Exit(1)

    existing = instances.load()
    used_by_instances = {v["port"] for v in existing.values()}
    port = base_port
    created = []

    for i in range(1, count + 1):
        while port in used_by_instances or instances.is_port_in_use(port):
            port += 1

        name = f"{base_name}-{i}"
        if name in existing:
            console.print(f"[yellow]'{name}' já existe, pulando.[/yellow]")
            port += 1
            continue

        console.print(f"[blue]Criando '{name}' na porta {port}...[/blue]")
        try:
            docker.create_postgres(name, port, password)
        except Exception as e:
            console.print(f"[red]Erro em '{name}': {e}[/red]")
            port += 1
            continue

        with console.status(f"[blue]Aguardando '{name}'..."):
            ready = docker.wait_for_ready(name, port, timeout=60)

        if ready:
            instances.add(name, port, password, seed)
            if seed:
                db = DatabaseManager("localhost", port, "postgres", password, "postgres")
                with console.status(f"[blue]Aplicando seed em '{name}'..."):
                    do_seed(db, seed, incremental=False)
            console.print(f"[green]'{name}' criado na porta {port}.[/green]")
            created.append((name, port))
        else:
            console.print(f"[red]Timeout para '{name}', pulando.[/red]")
            docker.remove_postgres(name)

        used_by_instances.add(port)
        port += 1

    console.print(f"\n[bold green]{len(created)} instância(s) criada(s):[/bold green]")
    for n, p in created:
        conn_str = f"postgresql://postgres:{password}@localhost:{p}/postgres"
        console.print(f"  [cyan]{n}[/cyan] → {conn_str}")


@app.command("list")
def list_instances():
    """Lista todas as instâncias PostgreSQL gerenciadas."""
    from pg_helpers.instances import load
    from pg_helpers import docker

    data = load()
    if not data:
        console.print("[yellow]Nenhuma instância encontrada.[/yellow]")
        console.print("Use [cyan]python main.py create <nome>[/cyan] para criar uma.")
        return

    try:
        running = {c["name"] for c in docker.list_postgres() if c["status"] == "running"}
    except Exception:
        running = set()

    table = Table(box=box.ROUNDED, header_style="bold cyan", show_lines=True)
    table.add_column("Nome", style="bold")
    table.add_column("Porta", justify="right")
    table.add_column("Cenário")
    table.add_column("Criado em")
    table.add_column("Status")

    for name, inst in data.items():
        container = f"pghelper_{name}"
        status = "[green]rodando[/green]" if container in running else "[red]parado[/red]"
        table.add_row(
            name,
            str(inst["port"]),
            inst.get("scenario") or "—",
            inst.get("created_at", "")[:19],
            status,
        )

    console.print(table)


@app.command("seed")
def seed_db(
    name: str = typer.Argument(..., help="Nome da instância"),
    scenario: Optional[str] = typer.Option(None, "--scenario", "-s", help="Cenário: ecommerce, blog, hr"),
    rows: int = typer.Option(0, "--rows", "-r", help="Quantidade de linhas (0 = padrão)"),
):
    """Adiciona dados incrementais a uma instância existente."""
    from pg_helpers.instances import load
    from pg_helpers.database import DatabaseManager
    from pg_helpers.seeds import seed as do_seed

    data = load()
    if name not in data:
        console.print(f"[red]Instância '{name}' não encontrada.[/red]")
        raise typer.Exit(1)

    inst = data[name]
    scenario = scenario or inst.get("scenario")

    if not scenario:
        console.print("[red]Nenhum cenário especificado. Use --scenario ecommerce|blog|hr[/red]")
        raise typer.Exit(1)

    if scenario not in VALID_SCENARIOS:
        console.print(f"[red]Cenário inválido: '{scenario}'[/red]")
        raise typer.Exit(1)

    db = DatabaseManager(inst["host"], inst["port"], inst["user"], inst["password"], inst["dbname"])
    kwargs = {"n": rows} if rows > 0 else {}

    with console.status(f"[blue]Adicionando dados incrementais ({scenario}) em '{name}'..."):
        do_seed(db, scenario, incremental=True, **kwargs)

    console.print(f"[green]Dados incrementais adicionados a '{name}'.[/green]")


@app.command()
def view(
    host: str = typer.Option("127.0.0.1", help="Host do servidor web"),
    port: int = typer.Option(8080, "--port", "-p", help="Porta do servidor web"),
    debug: bool = typer.Option(False, help="Modo debug do Flask"),
):
    """Inicia o visualizador web dos bancos de dados."""
    from pg_helpers.viewer.app import run, find_free_port

    actual_port = find_free_port(port)
    if actual_port != port:
        console.print(f"[yellow]Porta {port} em uso. Usando porta {actual_port}.[/yellow]")
    console.print(f"[bold green]Visualizador em http://{host}:{actual_port}[/bold green]")
    console.print("Pressione [cyan]Ctrl+C[/cyan] para parar.\n")
    run(host=host, port=actual_port, debug=debug)


@app.command()
def remove(
    name: str = typer.Argument(..., help="Nome da instância"),
    force: bool = typer.Option(False, "--force", "-f", help="Remover sem confirmação"),
):
    """Remove uma instância PostgreSQL (container + registro)."""
    from pg_helpers import instances, docker

    data = instances.load()
    if name not in data:
        console.print(f"[red]Instância '{name}' não encontrada.[/red]")
        raise typer.Exit(1)

    if not force:
        confirm = typer.confirm(f"Remover '{name}' (porta {data[name]['port']})? Todos os dados serão perdidos.")
        if not confirm:
            console.print("[yellow]Cancelado.[/yellow]")
            raise typer.Exit(0)

    with console.status(f"[blue]Removendo '{name}'..."):
        docker.remove_postgres(name)
        instances.remove(name)

    console.print(f"[green]Instância '{name}' removida.[/green]")


@app.command("remove-all")
def remove_all(
    force: bool = typer.Option(False, "--force", "-f", help="Remover sem confirmação"),
):
    """Remove todas as instâncias PostgreSQL gerenciadas."""
    from pg_helpers import instances, docker

    data = instances.load()
    if not data:
        console.print("[yellow]Nenhuma instância para remover.[/yellow]")
        return

    names = list(data.keys())
    if not force:
        confirm = typer.confirm(f"Remover {len(names)} instância(s): {', '.join(names)}?")
        if not confirm:
            console.print("[yellow]Cancelado.[/yellow]")
            raise typer.Exit(0)

    for name in names:
        with console.status(f"[blue]Removendo '{name}'..."):
            docker.remove_postgres(name)
            instances.remove(name)
        console.print(f"[green]'{name}' removido.[/green]")


@app.command("drop-db")
def drop_db(
    name: str = typer.Argument(..., help="Nome da instância"),
    dbname: str = typer.Argument(..., help="Nome do banco a ser deletado"),
    force: bool = typer.Option(False, "--force", "-f", help="Deletar sem confirmação"),
):
    """Deleta um banco de dados dentro de uma instância PostgreSQL."""
    from pg_helpers.instances import load
    from pg_helpers.database import DatabaseManager

    data = load()
    if name not in data:
        console.print(f"[red]Instância '{name}' não encontrada.[/red]")
        raise typer.Exit(1)

    inst = data[name]
    db = DatabaseManager(inst["host"], inst["port"], inst["user"], inst["password"], "postgres")

    databases = db.list_databases()
    if dbname not in databases:
        console.print(f"[red]Banco '{dbname}' não encontrado na instância '{name}'.[/red]")
        console.print(f"Bancos disponíveis: {', '.join(databases)}")
        raise typer.Exit(1)

    if not force:
        confirm = typer.confirm(f"Deletar banco '{dbname}' em '{name}'? Todos os dados serão perdidos.")
        if not confirm:
            console.print("[yellow]Cancelado.[/yellow]")
            raise typer.Exit(0)

    try:
        db.drop_database(dbname)
        console.print(f"[green]Banco '{dbname}' deletado da instância '{name}'.[/green]")
    except Exception as e:
        console.print(f"[red]Erro ao deletar banco: {e}[/red]")
        raise typer.Exit(1)


@app.command("drop-table")
def drop_table(
    name: str = typer.Argument(..., help="Nome da instância"),
    table: str = typer.Argument(..., help="Nome da tabela a ser deletada"),
    dbname: str = typer.Option("postgres", "--db", "-d", help="Banco de dados (padrão: postgres)"),
    cascade: bool = typer.Option(False, "--cascade", "-c", help="Deletar com CASCADE (remove dependências)"),
    force: bool = typer.Option(False, "--force", "-f", help="Deletar sem confirmação"),
):
    """Deleta uma tabela dentro de um banco de dados."""
    from pg_helpers.instances import load
    from pg_helpers.database import DatabaseManager

    data = load()
    if name not in data:
        console.print(f"[red]Instância '{name}' não encontrada.[/red]")
        raise typer.Exit(1)

    inst = data[name]
    db = DatabaseManager(inst["host"], inst["port"], inst["user"], inst["password"], dbname)

    tables = db.list_tables()
    if table not in tables:
        console.print(f"[red]Tabela '{table}' não encontrada no banco '{dbname}' da instância '{name}'.[/red]")
        console.print(f"Tabelas disponíveis: {', '.join(tables) or '(nenhuma)'}")
        raise typer.Exit(1)

    cascade_note = " [dim](CASCADE)[/dim]" if cascade else ""
    if not force:
        confirm = typer.confirm(f"Deletar tabela '{table}' em '{name}/{dbname}'?{' Dependências também serão removidas.' if cascade else ''}")
        if not confirm:
            console.print("[yellow]Cancelado.[/yellow]")
            raise typer.Exit(0)

    try:
        db.drop_table(table, cascade=cascade)
        console.print(f"[green]Tabela '{table}' deletada do banco '{dbname}' em '{name}'.{cascade_note}[/green]")
    except Exception as e:
        console.print(f"[red]Erro ao deletar tabela: {e}[/red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
