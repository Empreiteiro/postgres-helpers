"""Visualizador web das instâncias PostgreSQL."""

import math
from flask import Flask, render_template, request, abort, redirect, url_for, flash
from pg_helpers.instances import load as load_instances
from pg_helpers import instances as inst_store, docker
from pg_helpers.database import DatabaseManager
from pg_helpers.names import random_name
from pg_helpers.seeds import SCENARIOS, seed as do_seed

VALID_SCENARIOS = list(SCENARIOS.keys())

app = Flask(__name__, template_folder="templates")
app.secret_key = "pg-helpers-dev-key"


def _get_instance(name: str) -> dict:
    instances = load_instances()
    if name not in instances:
        abort(404)
    return instances[name]


def _db(inst: dict) -> DatabaseManager:
    return DatabaseManager(
        host=inst["host"],
        port=inst["port"],
        user=inst["user"],
        password=inst["password"],
        dbname=inst["dbname"],
    )


@app.route("/")
def index():
    instances = load_instances()
    stats = {}
    for name, inst in instances.items():
        try:
            db = _db(inst)
            tables = db.list_tables()
            total_rows = sum(db.count(t) for t in tables)
            stats[name] = {"tables": len(tables), "rows": total_rows, "ok": True}
        except Exception as e:
            stats[name] = {"tables": "?", "rows": "?", "ok": False, "error": str(e)}
    return render_template("index.html", instances=instances, stats=stats, current=None)


@app.route("/create", methods=["POST"])
def create_instance():
    name = request.form.get("name", "").strip() or None
    seed_scenario = request.form.get("seed", "").strip() or None
    port_str = request.form.get("port", "").strip()
    password = request.form.get("password", "postgres").strip() or "postgres"
    rows_str = request.form.get("rows", "").strip()

    port = int(port_str) if port_str.isdigit() else None
    rows = int(rows_str) if rows_str.isdigit() else 0

    if seed_scenario and seed_scenario not in VALID_SCENARIOS:
        flash(f"Invalid scenario: '{seed_scenario}'.", "danger")
        return redirect(url_for("index"))

    instances = load_instances()
    if name is None:
        name = random_name(set(instances.keys()))
    elif name in instances:
        flash(f"Instance '{name}' already exists.", "danger")
        return redirect(url_for("index"))

    if port is None:
        port = inst_store.next_port()
    elif inst_store.is_port_in_use(port):
        port = inst_store.next_port(port)

    try:
        docker.create_postgres(name, port, password)
    except Exception as e:
        flash(f"Failed to create container: {e}", "danger")
        return redirect(url_for("index"))

    if not docker.wait_for_ready(name, port, timeout=60):
        docker.remove_postgres(name)
        flash("Timeout: PostgreSQL did not start in time.", "danger")
        return redirect(url_for("index"))

    inst_store.add(name, port, password, seed_scenario)

    if seed_scenario:
        try:
            db = DatabaseManager("localhost", port, "postgres", password, "postgres")
            kwargs = {"n": rows} if rows > 0 else {}
            do_seed(db, seed_scenario, incremental=False, **kwargs)
        except Exception as e:
            flash(f"Instance '{name}' created but seeding failed: {e}", "warning")
            return redirect(url_for("index"))

    conn_str = f"postgresql://postgres:{password}@localhost:{port}/postgres"
    flash(f"Instance <strong>{name}</strong> created on port {port}. <code>{conn_str}</code>", "success")
    return redirect(url_for("index"))


@app.route("/db/<instance_name>")
def database(instance_name):
    instances = load_instances()
    inst = _get_instance(instance_name)
    db = _db(inst)
    tables = []
    try:
        for t in db.list_tables():
            try:
                count = db.count(t)
            except Exception:
                count = "?"
            tables.append({"name": t, "count": count})
    except Exception as e:
        return render_template(
            "database.html",
            instances=instances,
            instance=inst,
            instance_name=instance_name,
            tables=[],
            error=str(e),
            current=instance_name,
        )
    return render_template(
        "database.html",
        instances=instances,
        instance=inst,
        instance_name=instance_name,
        tables=tables,
        error=None,
        current=instance_name,
    )


@app.route("/db/<instance_name>/<table_name>")
def table_view(instance_name, table_name):
    instances = load_instances()
    inst = _get_instance(instance_name)
    db = _db(inst)

    valid_tables = db.list_tables()
    if table_name not in valid_tables:
        abort(404)

    per_page = request.args.get("per_page", 50, type=int)
    page = request.args.get("page", 1, type=int)
    per_page = max(10, min(per_page, 500))

    rows, total = db.paginate(table_name, page=page, per_page=per_page)
    columns = db.columns(table_name)
    total_pages = math.ceil(total / per_page) if total > 0 else 1
    page = max(1, min(page, total_pages))

    half = 3
    p_start = max(1, page - half)
    p_end = min(total_pages, page + half)
    page_range = list(range(p_start, p_end + 1))

    return render_template(
        "table.html",
        instances=instances,
        instance=inst,
        instance_name=instance_name,
        table_name=table_name,
        rows=rows,
        columns=columns,
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
        page_range=page_range,
        current=instance_name,
    )


@app.route("/db/<instance_name>/sql", methods=["GET"])
def sql_editor(instance_name):
    instances = load_instances()
    inst = _get_instance(instance_name)
    sql = request.args.get("q", "").strip()
    return render_template(
        "sql.html",
        instances=instances,
        instance=inst,
        instance_name=instance_name,
        current=instance_name,
        sql=sql,
        result=None,
    )


@app.route("/db/<instance_name>/sql", methods=["POST"])
def sql_editor_run(instance_name):
    instances = load_instances()
    inst = _get_instance(instance_name)
    sql = request.form.get("sql", "").strip()
    result = _db(inst).run_query(sql) if sql else None
    return render_template(
        "sql.html",
        instances=instances,
        instance=inst,
        instance_name=instance_name,
        current=instance_name,
        sql=sql,
        result=result,
    )


@app.route("/db/<instance_name>/drop-table/<table_name>", methods=["POST"])
def drop_table(instance_name, table_name):
    inst = _get_instance(instance_name)
    db = _db(inst)
    valid_tables = db.list_tables()
    if table_name not in valid_tables:
        abort(404)
    cascade = request.form.get("cascade") == "1"
    db.drop_table(table_name, cascade=cascade)
    flash(f"Table <strong>{table_name}</strong> dropped.", "success")
    return redirect(url_for("database", instance_name=instance_name))


@app.route("/db/<instance_name>/delete", methods=["POST"])
def delete_instance(instance_name):
    instances = load_instances()
    if instance_name not in instances:
        abort(404)
    docker.remove_postgres(instance_name)
    inst_store.remove(instance_name)
    flash(f"Instance <strong>{instance_name}</strong> deleted.", "success")
    return redirect(url_for("index"))


def run(host: str = "127.0.0.1", port: int = 8080, debug: bool = False):
    app.run(host=host, port=port, debug=debug)
