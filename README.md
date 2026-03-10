# postgres-helpers

Python CLI to create and manage PostgreSQL instances via Docker, with sample data seeding and a web viewer.

## Requirements

- Python 3.11+
- Docker Desktop running

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```bash
python main.py [COMMAND] [OPTIONS]
```

### Create a blank database

The instance name is **optional** — if omitted, a random readable name is generated automatically (e.g. `silver-hawk`, `frosty-ridge`).

```bash
python main.py create                        # random name, auto port
python main.py create my-db                  # explicit name
python main.py create my-db --port 5433      # explicit port
```

If the requested port is already in use by any process, the script automatically moves to the next available port.

After creation, the connection string is printed:

```
postgresql://postgres:postgres@localhost:5432/postgres
```

### Create a database with sample data

```bash
python main.py create --seed ecommerce
python main.py create --seed blog
python main.py create --seed hr
```

Use `--rows N` to control the amount of data generated:

```bash
python main.py create --seed ecommerce --rows 200
```

### Create multiple sequential databases

Creates `pg-1`, `pg-2`, `pg-3` on sequential ports, skipping any that are already in use:

```bash
python main.py create-many 3
python main.py create-many 3 --seed blog
python main.py create-many 5 --base-name store --base-port 6000
```

### Add incremental data

```bash
python main.py seed my-db
python main.py seed my-db --rows 50
python main.py seed my-db --scenario ecommerce
```

### List instances

```bash
python main.py list
```

### Start the web viewer

```bash
python main.py view
# Open http://localhost:8080
python main.py view --port 9000
```

The web viewer shows:

- **Home** — cards for each instance with table/row counts, connection string, and a one-click copy button
- **Instance page** — cards for each table with row count
- **Table page** — paginated data with page size selector

### Remove instances

```bash
python main.py remove my-db
python main.py remove my-db --force
python main.py remove-all
```

## Seed scenarios

| Scenario | Tables |
|---|---|
| `ecommerce` | `customers`, `products`, `orders`, `order_items` |
| `blog` | `users`, `tags`, `posts`, `post_tags`, `comments` |
| `hr` | `departments`, `employees`, `projects`, `employee_projects` |

Data is generated with [Faker](https://faker.readthedocs.io/) using the `pt_BR` locale.

## Project structure

```
postgres-helpers/
├── main.py                    # CLI entry point (Typer)
├── requirements.txt
└── pg_helpers/
    ├── instances.py           # State persisted in instances.json
    ├── docker.py              # Docker container management
    ├── database.py            # PostgreSQL operations via psycopg2
    ├── seeds/
    │   ├── ecommerce.py
    │   ├── blog.py
    │   └── hr.py
    └── viewer/
        ├── app.py             # Flask web server
        └── templates/
```

## Technical details

- Docker image: `postgres:16-alpine`
- Containers named `pghelper_<name>`
- Default credentials: user `postgres`, password `postgres`
- Default port: `5432`, auto-incremented if occupied by any process (checked via TCP socket)
- Instance state saved in `instances.json` at the project root

## Dependencies

| Package | Purpose |
|---|---|
| `typer` | CLI |
| `docker` | Docker SDK |
| `psycopg2-binary` | PostgreSQL connection |
| `flask` | Web viewer |
| `faker` | Data generation |
| `rich` | Formatted terminal output |
