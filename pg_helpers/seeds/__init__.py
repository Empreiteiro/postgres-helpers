"""Orquestração dos cenários de dados de exemplo."""

from . import ecommerce, blog, hr

SCENARIOS = {
    "ecommerce": ecommerce,
    "blog": blog,
    "hr": hr,
}


def seed(db, scenario: str, incremental: bool = False, **kwargs):
    """
    Aplica um cenário de dados em um DatabaseManager.

    Args:
        db: DatabaseManager conectado
        scenario: 'ecommerce', 'blog' ou 'hr'
        incremental: False = cria schema + dados iniciais; True = adiciona dados extras
        **kwargs: n= para controlar quantidade de linhas
    """
    if scenario not in SCENARIOS:
        raise ValueError(f"Cenário inválido: '{scenario}'. Opções: {', '.join(SCENARIOS)}")

    module = SCENARIOS[scenario]
    if incremental:
        module.seed_incremental(db, **kwargs)
    else:
        module.create_schema(db)
        module.seed_initial(db, **kwargs)
