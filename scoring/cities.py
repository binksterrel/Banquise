import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import List, Set

# Fichier texte listant toutes les communes françaises (une par ligne)
CITY_DATA_PATH = Path(__file__).resolve().parent / "data" / "communes_france.txt"


def _normalize(value: str) -> str:
    """Supprime accents/ponctuation pour comparer deux noms de ville."""
    value = unicodedata.normalize("NFD", value or "")
    value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
    value = value.lower()
    value = value.replace("-", " ").replace("'", " ").replace("’", " ")
    value = re.sub(r"[^a-z\s]", " ", value)
    return " ".join(value.split())


@lru_cache(maxsize=1)
def _load_city_set() -> Set[str]:
    """Charge les villes valides en mémoire (normalisées)."""
    try:
        lines = CITY_DATA_PATH.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return set()

    cities = set()
    for raw in lines:
        norm = _normalize(raw)
        if norm:
            cities.add(norm)
    return cities


def is_valid_french_city(city_name: str) -> bool:
    """Vérifie qu'une ville existe dans la liste officielle des communes françaises."""
    normalized = _normalize(city_name)
    if not normalized:
        return False
    return normalized in _load_city_set()


@lru_cache(maxsize=1)
def _load_city_list() -> List[str]:
    """Retourne la liste brute des communes pour affichage."""
    try:
        return [line.strip() for line in CITY_DATA_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    except FileNotFoundError:
        return []


def search_cities(prefix: str, limit: int = 15) -> List[str]:
    """Renvoie jusqu'à `limit` communes commençant par le préfixe saisi (insensible aux accents)."""
    norm_prefix = _normalize(prefix)
    if len(norm_prefix) < 3:
        return []
    results: List[str] = []
    for city in _load_city_list():
        if _normalize(city).startswith(norm_prefix):
            results.append(city)
        if len(results) >= limit:
            break
    return results
