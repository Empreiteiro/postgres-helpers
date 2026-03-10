"""
Cenário RH (Recursos Humanos)
Tabelas: departments, employees, projects, employee_projects
"""

import random
from datetime import datetime, timedelta
from faker import Faker

fake = Faker("pt_BR")

DEPT_NAMES = ["Engenharia", "Marketing", "Vendas", "Financeiro", "RH", "Operações", "Jurídico"]
ROLES = [
    "Desenvolvedor Sênior", "Desenvolvedor Pleno", "Desenvolvedor Júnior",
    "Designer UX", "Analista de Dados", "Gerente de Produto", "Coordenador",
    "Especialista", "Assistente", "Diretor", "Analista de Negócios",
]
EP_ROLES = ["lead", "member", "reviewer", "observer"]


def create_schema(db):
    db.execute("""
        CREATE TABLE IF NOT EXISTS departments (
            id         SERIAL PRIMARY KEY,
            name       VARCHAR(100) NOT NULL,
            budget     DECIMAL(14,2) NOT NULL,
            manager_id INTEGER
        );

        CREATE TABLE IF NOT EXISTS employees (
            id            SERIAL PRIMARY KEY,
            department_id INTEGER REFERENCES departments(id),
            name          VARCHAR(100) NOT NULL,
            email         VARCHAR(150) UNIQUE NOT NULL,
            role          VARCHAR(100) NOT NULL,
            salary        DECIMAL(10,2) NOT NULL,
            hire_date     DATE NOT NULL
        );

        CREATE TABLE IF NOT EXISTS projects (
            id            SERIAL PRIMARY KEY,
            department_id INTEGER REFERENCES departments(id),
            name          VARCHAR(200) NOT NULL,
            description   TEXT,
            status        VARCHAR(30) DEFAULT 'active',
            deadline      DATE
        );

        CREATE TABLE IF NOT EXISTS employee_projects (
            employee_id INTEGER REFERENCES employees(id),
            project_id  INTEGER REFERENCES projects(id),
            role        VARCHAR(50) NOT NULL,
            joined_at   DATE DEFAULT CURRENT_DATE,
            PRIMARY KEY (employee_id, project_id)
        );
    """)


def seed_initial(db, n: int = 0):
    n_employees = n or 50
    n_projects = max(5, n // 5) if n else 15

    dept_names = DEPT_NAMES[:min(7, max(3, n_employees // 10))]

    # Departments
    for dept_name in dept_names:
        db.execute(
            "INSERT INTO departments (name, budget) VALUES (%s, %s)",
            (dept_name, round(random.uniform(100_000, 3_000_000), 2)),
        )

    dept_ids = [r["id"] for r in db.query("SELECT id FROM departments")]

    # Employees
    for _ in range(n_employees):
        hire_date = (datetime.now() - timedelta(days=random.randint(0, 3000))).date()
        db.execute(
            "INSERT INTO employees (department_id, name, email, role, salary, hire_date) VALUES (%s, %s, %s, %s, %s, %s)",
            (
                random.choice(dept_ids),
                fake.name(),
                fake.unique.email(),
                random.choice(ROLES),
                round(random.uniform(2_500, 30_000), 2),
                hire_date,
            ),
        )

    emp_ids = [r["id"] for r in db.query("SELECT id FROM employees")]

    # Set managers
    for dept_id in dept_ids:
        dept_emps = db.query("SELECT id FROM employees WHERE department_id = %s LIMIT 1", (dept_id,))
        if dept_emps:
            db.execute("UPDATE departments SET manager_id = %s WHERE id = %s", (dept_emps[0]["id"], dept_id))

    # Projects
    proj_statuses = ["active", "active", "active", "completed", "on-hold", "cancelled"]
    for _ in range(n_projects):
        deadline = (datetime.now() + timedelta(days=random.randint(-60, 500))).date()
        db.execute(
            "INSERT INTO projects (department_id, name, description, status, deadline) VALUES (%s, %s, %s, %s, %s)",
            (
                random.choice(dept_ids),
                fake.bs()[:190],
                fake.text(max_nb_chars=300),
                random.choice(proj_statuses),
                deadline,
            ),
        )

    proj_ids = [r["id"] for r in db.query("SELECT id FROM projects")]

    # Employee ↔ project assignments (no duplicates)
    pairs_seen: set[tuple] = set()
    target = min(len(emp_ids) * 2, len(emp_ids) * len(proj_ids))
    attempts = 0
    while len(pairs_seen) < target and attempts < target * 3:
        attempts += 1
        emp_id = random.choice(emp_ids)
        proj_id = random.choice(proj_ids)
        if (emp_id, proj_id) not in pairs_seen:
            pairs_seen.add((emp_id, proj_id))
            joined = (datetime.now() - timedelta(days=random.randint(0, 300))).date()
            db.execute(
                "INSERT INTO employee_projects (employee_id, project_id, role, joined_at) VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING",
                (emp_id, proj_id, random.choice(EP_ROLES), joined),
            )


def seed_incremental(db, n: int = 0):
    n_employees = n or 3
    n_projects = max(1, n // 5) if n else 1

    dept_ids = [r["id"] for r in db.query("SELECT id FROM departments")]
    if not dept_ids:
        raise ValueError("Sem dados iniciais. Execute sem --incremental primeiro.")

    for _ in range(n_employees):
        hire_date = datetime.now().date()
        db.execute(
            "INSERT INTO employees (department_id, name, email, role, salary, hire_date) VALUES (%s, %s, %s, %s, %s, %s)",
            (
                random.choice(dept_ids),
                fake.name(),
                fake.unique.email(),
                random.choice(ROLES),
                round(random.uniform(2_500, 20_000), 2),
                hire_date,
            ),
        )

    for _ in range(n_projects):
        deadline = (datetime.now() + timedelta(days=random.randint(30, 365))).date()
        db.execute(
            "INSERT INTO projects (department_id, name, description, status, deadline) VALUES (%s, %s, %s, 'active', %s)",
            (random.choice(dept_ids), fake.bs()[:190], fake.text(max_nb_chars=300), deadline),
        )
