"""
Cenário E-commerce
Tabelas: customers, products, orders, order_items
"""

import random
from datetime import datetime, timedelta
from faker import Faker

fake = Faker("pt_BR")


def create_schema(db):
    db.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id        SERIAL PRIMARY KEY,
            name      VARCHAR(100) NOT NULL,
            email     VARCHAR(150) UNIQUE NOT NULL,
            phone     VARCHAR(20),
            city      VARCHAR(100),
            created_at TIMESTAMP DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS products (
            id        SERIAL PRIMARY KEY,
            name      VARCHAR(200) NOT NULL,
            category  VARCHAR(60) NOT NULL,
            price     DECIMAL(10,2) NOT NULL,
            stock     INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS orders (
            id          SERIAL PRIMARY KEY,
            customer_id INTEGER REFERENCES customers(id),
            status      VARCHAR(20) NOT NULL DEFAULT 'pending',
            total       DECIMAL(10,2) NOT NULL DEFAULT 0,
            created_at  TIMESTAMP DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS order_items (
            id          SERIAL PRIMARY KEY,
            order_id    INTEGER REFERENCES orders(id),
            product_id  INTEGER REFERENCES products(id),
            quantity    INTEGER NOT NULL,
            unit_price  DECIMAL(10,2) NOT NULL
        );
    """)


def seed_initial(db, n: int = 0):
    n_customers = n or 80
    n_products = max(20, n // 2) if n else 40
    n_orders = n * 2 if n else 150

    # Customers
    customers = []
    emails_seen = set()
    while len(customers) < n_customers:
        email = fake.unique.email()
        if email not in emails_seen:
            emails_seen.add(email)
            customers.append((
                fake.name(),
                email,
                fake.phone_number()[:20],
                fake.city(),
            ))
    db.execute_many(
        "INSERT INTO customers (name, email, phone, city) VALUES (%s, %s, %s, %s)",
        customers,
    )

    # Products
    categories = ["Eletrônicos", "Roupas", "Alimentos", "Livros", "Casa", "Esporte", "Beleza"]
    product_names = [fake.catch_phrase()[:190] for _ in range(n_products)]
    products = [
        (name, random.choice(categories), round(random.uniform(10, 1500), 2), random.randint(0, 300))
        for name in product_names
    ]
    db.execute_many(
        "INSERT INTO products (name, category, price, stock) VALUES (%s, %s, %s, %s)",
        products,
    )

    customer_ids = [r["id"] for r in db.query("SELECT id FROM customers")]
    product_rows = db.query("SELECT id, price FROM products")
    statuses = ["pending", "confirmed", "shipped", "delivered", "cancelled"]
    weights = [10, 20, 20, 40, 10]

    for _ in range(n_orders):
        customer_id = random.choice(customer_ids)
        status = random.choices(statuses, weights=weights)[0]
        created_at = datetime.now() - timedelta(days=random.randint(0, 365))

        row = db.query(
            "INSERT INTO orders (customer_id, status, total, created_at) VALUES (%s, %s, 0, %s) RETURNING id",
            (customer_id, status, created_at),
        )
        order_id = row[0]["id"]

        sample = random.sample(product_rows, min(random.randint(1, 5), len(product_rows)))
        total = 0.0
        items = []
        for p in sample:
            qty = random.randint(1, 4)
            price = float(p["price"])
            total += qty * price
            items.append((order_id, p["id"], qty, price))

        db.execute_many(
            "INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES (%s, %s, %s, %s)",
            items,
        )
        db.execute("UPDATE orders SET total = %s WHERE id = %s", (round(total, 2), order_id))


def seed_incremental(db, n: int = 0):
    n_orders = n or 10

    customer_ids = [r["id"] for r in db.query("SELECT id FROM customers")]
    product_rows = db.query("SELECT id, price FROM products")

    if not customer_ids or not product_rows:
        raise ValueError("Sem dados iniciais. Execute sem --incremental primeiro.")

    statuses = ["pending", "confirmed", "shipped"]

    for _ in range(n_orders):
        customer_id = random.choice(customer_ids)
        status = random.choice(statuses)

        row = db.query(
            "INSERT INTO orders (customer_id, status, total) VALUES (%s, %s, 0) RETURNING id",
            (customer_id, status),
        )
        order_id = row[0]["id"]

        sample = random.sample(product_rows, min(random.randint(1, 4), len(product_rows)))
        total = 0.0
        items = []
        for p in sample:
            qty = random.randint(1, 3)
            price = float(p["price"])
            total += qty * price
            items.append((order_id, p["id"], qty, price))

        db.execute_many(
            "INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES (%s, %s, %s, %s)",
            items,
        )
        db.execute("UPDATE orders SET total = %s WHERE id = %s", (round(total, 2), order_id))
