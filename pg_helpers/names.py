"""Random instance name generation."""

import random

_ADJECTIVES = [
    "amber", "azure", "bold", "brave", "bright", "calm", "cedar", "clever",
    "coral", "crisp", "dawn", "eager", "ember", "fierce", "fleet", "foggy",
    "forest", "frosty", "gentle", "golden", "grand", "green", "hardy", "ivory",
    "jade", "keen", "lively", "lunar", "maple", "misty", "noble", "ocean",
    "pine", "polar", "proud", "quiet", "rapid", "rocky", "royal", "rustic",
    "sage", "sandy", "sharp", "silver", "sleek", "snowy", "solar", "stark",
    "steel", "stone", "storm", "sturdy", "swift", "tawny", "tidal", "verdant",
    "vivid", "warm", "wild", "windy", "winter", "wispy",
]
_NOUNS = [
    "anchor", "anvil", "arrow", "atlas", "aurora", "axiom", "beacon", "bear",
    "berg", "birch", "bison", "blade", "blaze", "brook", "bull", "canyon",
    "cedar", "cliff", "cloud", "comet", "crane", "creek", "delta", "dune",
    "eagle", "elm", "falcon", "ferry", "field", "fjord", "flint", "forge",
    "fox", "gale", "glacier", "grove", "harbor", "hawk", "helm", "heron",
    "hill", "horn", "iris", "isle", "jaguar", "kestrel", "lake", "larch",
    "ledge", "lynx", "marsh", "mesa", "mist", "moon", "moose", "moss",
    "oak", "orca", "osprey", "peak", "pine", "plains", "reef", "ridge",
    "rook", "rune", "shore", "sierra", "slate", "sparrow", "spruce", "summit",
    "swan", "tide", "timber", "torch", "trail", "vale", "vault", "vertex",
    "viper", "vista", "wolf", "wren",
]


def random_name(existing: set[str] | None = None) -> str:
    """Returns a unique adjective-noun name not present in `existing`."""
    existing = existing or set()
    for _ in range(200):
        name = f"{random.choice(_ADJECTIVES)}-{random.choice(_NOUNS)}"
        if name not in existing:
            return name
    return f"{random.choice(_ADJECTIVES)}-{random.choice(_NOUNS)}-{random.randint(2, 99)}"
