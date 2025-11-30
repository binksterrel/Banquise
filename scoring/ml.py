"""
Module de prédiction crédit Banquise.

Charge le pipeline scikit-learn sérialisé (préprocessing + modèle) et expose une
fonction predict_credit(features: dict) qui retourne probabilité et décision.
"""

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

import joblib
import pandas as pd

LOGGER = logging.getLogger(__name__)
MODEL_PATH = Path(__file__).resolve().parent / "model_credit.pkl"


class ModelNotLoaded(Exception):
    """Le modèle n'a pas pu être chargé."""


@lru_cache(maxsize=1)
def _load_artifact(path: Path = MODEL_PATH) -> Dict[str, Any]:
    if not path.exists():
        raise ModelNotLoaded(f"Modèle non trouvé : {path}")
    artifact = joblib.load(path)
    if "pipeline" not in artifact or "features" not in artifact:
        raise ModelNotLoaded("Artifact invalide : pipeline/features manquants.")
    return artifact


def is_model_available() -> bool:
    try:
        _load_artifact()
        return True
    except ModelNotLoaded:
        return False
    except Exception:
        LOGGER.exception("Erreur lors du chargement du modèle ML.")
        return False


def predict_credit(features: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calcule la probabilité d'un bon payeur et la décision associée.

    :param features: dict des features d'entrée (clés = colonnes du modèle).
    :return: dict avec proba_good, proba_bad, label (ACCEPTEE/REFUSEE), score_0_100.
    """
    artifact = _load_artifact()
    pipeline = artifact["pipeline"]
    expected = artifact["features"]

    # Garantir toutes les colonnes attendues, même si certaines valeurs manquent.
    row = {k: features.get(k) for k in expected}
    df = pd.DataFrame([row])

    proba = pipeline.predict_proba(df)[0]
    proba_bad, proba_good = float(proba[0]), float(proba[1])
    label = "ACCEPTEE" if proba_good >= 0.5 else "REFUSEE"
    score_0_100 = int(round(proba_good * 100))

    return {
        "proba_good": proba_good,
        "proba_bad": proba_bad,
        "label": label,
        "score_0_100": score_0_100,
        "features_used": expected,
        "model_name": artifact.get("best_model"),
        "metrics": artifact.get("metrics"),
    }
