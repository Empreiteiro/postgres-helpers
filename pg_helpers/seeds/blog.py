"""
Cenário Blog
Tabelas: users, tags, posts, post_tags, comments
"""

import random
from datetime import datetime, timedelta
from faker import Faker

fake = Faker("pt_BR")

TAG_NAMES = [
    "python", "javascript", "typescript", "data", "devops", "segurança",
    "mobile", "web", "inteligência-artificial", "banco-de-dados", "cloud",
    "tutorial", "opinião", "review", "notícias", "dicas", "carreira",
    "linux", "open-source", "arquitetura",
]


def create_schema(db):
    db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id         SERIAL PRIMARY KEY,
            username   VARCHAR(60) UNIQUE NOT NULL,
            email      VARCHAR(150) UNIQUE NOT NULL,
            bio        TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS tags (
            id   SERIAL PRIMARY KEY,
            name VARCHAR(60) UNIQUE NOT NULL
        );

        CREATE TABLE IF NOT EXISTS posts (
            id           SERIAL PRIMARY KEY,
            user_id      INTEGER REFERENCES users(id),
            title        VARCHAR(200) NOT NULL,
            content      TEXT NOT NULL,
            status       VARCHAR(20) DEFAULT 'published',
            published_at TIMESTAMP DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS post_tags (
            post_id INTEGER REFERENCES posts(id),
            tag_id  INTEGER REFERENCES tags(id),
            PRIMARY KEY (post_id, tag_id)
        );

        CREATE TABLE IF NOT EXISTS comments (
            id         SERIAL PRIMARY KEY,
            post_id    INTEGER REFERENCES posts(id),
            user_id    INTEGER REFERENCES users(id),
            content    TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        );
    """)


def seed_initial(db, n: int = 0):
    n_users = n or 20
    n_posts = n * 4 if n else 80
    n_comments = n * 10 if n else 250

    # Users
    users = []
    while len(users) < n_users:
        try:
            users.append((fake.unique.user_name()[:60], fake.unique.email(), fake.text(max_nb_chars=200)))
        except Exception:
            break
    db.execute_many("INSERT INTO users (username, email, bio) VALUES (%s, %s, %s)", users)

    # Tags
    db.execute_many(
        "INSERT INTO tags (name) VALUES (%s) ON CONFLICT DO NOTHING",
        [(t,) for t in TAG_NAMES],
    )

    user_ids = [r["id"] for r in db.query("SELECT id FROM users")]
    tag_ids = [r["id"] for r in db.query("SELECT id FROM tags")]
    statuses = ["published", "published", "published", "draft"]

    # Posts + post_tags
    for _ in range(n_posts):
        user_id = random.choice(user_ids)
        pub_at = datetime.now() - timedelta(days=random.randint(0, 730))

        row = db.query(
            """INSERT INTO posts (user_id, title, content, status, published_at)
               VALUES (%s, %s, %s, %s, %s) RETURNING id""",
            (
                user_id,
                fake.sentence(nb_words=random.randint(5, 12))[:200],
                fake.text(max_nb_chars=1500),
                random.choice(statuses),
                pub_at,
            ),
        )
        post_id = row[0]["id"]

        chosen_tags = random.sample(tag_ids, random.randint(1, 4))
        db.execute_many(
            "INSERT INTO post_tags (post_id, tag_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            [(post_id, tid) for tid in chosen_tags],
        )

    # Comments
    post_ids = [r["id"] for r in db.query("SELECT id FROM posts")]
    comments = [
        (random.choice(post_ids), random.choice(user_ids), fake.text(max_nb_chars=400))
        for _ in range(n_comments)
    ]
    db.execute_many("INSERT INTO comments (post_id, user_id, content) VALUES (%s, %s, %s)", comments)


def seed_incremental(db, n: int = 0):
    n_posts = n or 5
    n_comments = (n * 3) if n else 15

    user_ids = [r["id"] for r in db.query("SELECT id FROM users")]
    tag_ids = [r["id"] for r in db.query("SELECT id FROM tags")]

    if not user_ids:
        raise ValueError("Sem dados iniciais. Execute sem --incremental primeiro.")

    for _ in range(n_posts):
        user_id = random.choice(user_ids)
        row = db.query(
            "INSERT INTO posts (user_id, title, content, status) VALUES (%s, %s, %s, 'published') RETURNING id",
            (user_id, fake.sentence(nb_words=8)[:200], fake.text(max_nb_chars=1000)),
        )
        post_id = row[0]["id"]
        chosen_tags = random.sample(tag_ids, random.randint(1, 3))
        db.execute_many(
            "INSERT INTO post_tags (post_id, tag_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            [(post_id, tid) for tid in chosen_tags],
        )

    post_ids = [r["id"] for r in db.query("SELECT id FROM posts")]
    comments = [
        (random.choice(post_ids), random.choice(user_ids), fake.text(max_nb_chars=400))
        for _ in range(n_comments)
    ]
    db.execute_many("INSERT INTO comments (post_id, user_id, content) VALUES (%s, %s, %s)", comments)
