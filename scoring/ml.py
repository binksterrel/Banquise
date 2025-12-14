"""
Module de prédiction crédit Banquise.

Charge le pipeline scikit-learn sérialisé et expose une fonction predict_credit
qui reçoit un dictionnaire du formulaire Django (colonnes françaises) et retourne
la probabilité d'acceptation et la décision.

IMPORTANT : Les features sont recalculées EXACTEMENT comme lors de l'entraînement.
"""

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

import joblib
import pandas as pd
import numpy as np
import sklearn  # Nécessaire pour désérialiser le pipeline

LOGGER = logging.getLogger(__name__)
MODEL_PATH = Path(__file__).resolve().parent / "model_credit.pkl"


class ModelNotLoaded(Exception):
    """Le modèle n'a pas pu être chargé."""


@lru_cache(maxsize=1)
def _load_artifact(path: Path = MODEL_PATH) -> Dict[str, Any]:
    """
    Charge et cache l'artifact du modèle.
    """
    if not path.exists():
        raise ModelNotLoaded(f"Modèle non trouvé : {path}")
    
    try:
        artifact = joblib.load(path)
    except Exception as e:
        raise ModelNotLoaded(f"Erreur de chargement : {e}")
    
    if "pipeline" not in artifact or "features" not in artifact:
        raise ModelNotLoaded("Artifact invalide : pipeline/features manquants.")
    
    return artifact


def is_model_available() -> bool:
    """
    Vérifie si le modèle est disponible et chargeable.
    """
    try:
        _load_artifact()
        return True
    except ModelNotLoaded:
        return False
    except Exception as e:
        LOGGER.exception(f"Erreur ML : {e}")
        return False


def predict_credit(form_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Prédit la probabilité d'acceptation d'un crédit.

    :param form_data: Dictionnaire provenant du formulaire Django avec les clés :
        - revenus_mensuels: Decimal ou float
        - montant_souhaite: Decimal ou float
        - duree_souhaitee_annees ou duree_mois: int
        - historique_credit: 0 ou 1 (optionnel, défaut 1)
        - personnes_a_charge ou enfants_a_charge: int (optionnel, défaut 0)
        - marie: 0 ou 1 (optionnel)
        - diplome: 0 ou 1 (optionnel)
        - independant: 0 ou 1 (optionnel)

    :return: Dict avec proba_good, proba_bad, label, score_0_100 ou None si erreur.
    """
    try:
        artifact = _load_artifact()
    except ModelNotLoaded as e:
        LOGGER.warning(f"Modèle non chargé : {e}")
        return None

    pipeline = artifact["pipeline"]
    expected_features = artifact["features"]

    # --- EXTRACTION & CONVERSION DES DONNÉES ---
    def to_float(val, default=0.0):
        try:
            return float(val) if val is not None else default
        except (TypeError, ValueError):
            return default

    def to_int(val, default=0):
        try:
            return int(val) if val is not None else default
        except (TypeError, ValueError):
            return default

    revenus_mensuels = to_float(form_data.get("revenus_mensuels", 0))
    montant_souhaite = to_float(form_data.get("montant_souhaite", 0))
    
    # Durée : priorité à duree_mois, sinon conversion depuis années
    duree_mois = to_float(form_data.get("duree_mois"))
    if duree_mois == 0:
        duree_annees = to_float(form_data.get("duree_souhaitee_annees", 10))
        duree_mois = duree_annees * 12
    duree_mois = max(1, duree_mois)  # Éviter division par zéro

    historique_credit = to_int(form_data.get("historique_credit", 1))
    
    # Personnes à charge (alias : enfants_a_charge)
    personnes_a_charge = to_int(
        form_data.get("personnes_a_charge") or form_data.get("enfants_a_charge", 0)
    )

    marie = to_int(form_data.get("marie", 0))
    diplome = to_int(form_data.get("diplome", 1))  # Défaut = diplômé
    independant = to_int(form_data.get("independant", 0))

    # --- CALCUL DES FEATURES DÉRIVÉES (identique à l'entraînement) ---
    # Formule PMT rigoureuse (Taux 3.5%)
    r_monthly = 0.035 / 12
    n_months = max(1, duree_mois)
    if r_monthly > 0:
        mensualite_approx = montant_souhaite * r_monthly / (1 - (1 + r_monthly)**(-n_months))
    else:
        mensualite_approx = montant_souhaite / n_months
    
    # DTI
    if revenus_mensuels > 0:
        dti = mensualite_approx / revenus_mensuels
    else:
        dti = 1.0  # Revenus nuls = risque max
    dti = min(max(dti, 0), 2)  # Clamp [0, 2]

    # Ratio montant/revenus
    if revenus_mensuels > 0:
        ratio_montant_revenus = montant_souhaite / revenus_mensuels
    else:
        ratio_montant_revenus = 100
    ratio_montant_revenus = min(max(ratio_montant_revenus, 0), 100)

    # --- CONSTRUCTION DU DATAFRAME ---
    row = {
        "revenus_mensuels": revenus_mensuels,
        "montant_souhaite": montant_souhaite,
        "duree_mois": duree_mois,
        "historique_credit": historique_credit,
        "personnes_a_charge": personnes_a_charge,
        "marie": marie,
        "diplome": diplome,
        "independant": independant,
        "dti": dti,
        "ratio_montant_revenus": ratio_montant_revenus,
    }

    # Vérification - s'assurer que toutes les colonnes attendues sont présentes
    df_row = {k: row.get(k, 0) for k in expected_features}
    df = pd.DataFrame([df_row])

    # --- PRÉDICTION ---
    try:
        proba = pipeline.predict_proba(df)[0]
        proba_bad, proba_good = float(proba[0]), float(proba[1])
        label = "ACCEPTEE" if proba_good >= 0.5 else "REFUSEE"
        score_0_100 = int(round(proba_good * 100))

        return {
            "proba_good": proba_good,
            "proba_bad": proba_bad,
            "label": label,
            "score_0_100": score_0_100,
            "features_used": expected_features,
            "computed_dti": dti,
            "model_name": artifact.get("best_model"),
        }
    except Exception as e:
        LOGGER.exception(f"Erreur de prédiction : {e}")
        return None
