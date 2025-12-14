"""
Entraînement du modèle de scoring crédit Banquise.

Charge le dataset réel (loan_prediction_dataset.csv), nettoie les données,
crée les features francisées correspondant au modèle Django, et entraîne
un RandomForestClassifier.

Usage:
    python ml/train_credit_model.py
"""

import os
import sys
from pathlib import Path

import pandas as pd
import numpy as np
import joblib
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, classification_report


def train_model():
    base_dir = Path(__file__).resolve().parent.parent
    data_path = base_dir / "data" / "loan_prediction_dataset.csv"
    output_path = base_dir / "scoring" / "model_credit.pkl"

    print(f"📂 Chargement du dataset : {data_path}")

    if not data_path.exists():
        print(f"❌ Dataset non trouvé : {data_path}")
        sys.exit(1)

    # --- 1. CHARGEMENT ---
    df = pd.read_csv(data_path)
    print(f"✅ Dataset chargé : {len(df)} lignes")

    # --- 2. NETTOYAGE ---
    # Suppression de la colonne ID
    if "Loan_ID" in df.columns:
        df = df.drop(columns=["Loan_ID"])

    # Conversion Dependents : "3+" -> 3
    if "Dependents" in df.columns:
        df["Dependents"] = df["Dependents"].replace("3+", 3)
        df["Dependents"] = pd.to_numeric(df["Dependents"], errors="coerce")

    # Target : Loan_Status (Y=1, N=0)
    if "Loan_Status" not in df.columns:
        print("❌ Colonne 'Loan_Status' manquante.")
        sys.exit(1)

    df["target"] = df["Loan_Status"].map({"Y": 1, "N": 0})
    df = df.dropna(subset=["target"])
    df["target"] = df["target"].astype(int)

    # --- 3. FEATURE ENGINEERING (Mapping EN -> FR) ---
    # Revenus mensuels = ApplicantIncome + CoapplicantIncome
    df["revenus_mensuels"] = (
        df["ApplicantIncome"].fillna(0) + df["CoapplicantIncome"].fillna(0)
    )

    # Montant souhaité = LoanAmount * 1000 (dataset en milliers)
    df["montant_souhaite"] = df["LoanAmount"].fillna(0) * 1000

    # Durée en mois
    df["duree_mois"] = df["Loan_Amount_Term"].fillna(360)

    # Historique crédit (1 = bon, 0 = mauvais/inconnu)
    df["historique_credit"] = df["Credit_History"].fillna(0).astype(int)

    # Nombre de personnes à charge
    df["personnes_a_charge"] = df["Dependents"].fillna(0).astype(int)

    # Marié (1 = Yes, 0 = No)
    df["marie"] = df["Married"].map({"Yes": 1, "No": 0}).fillna(0).astype(int)

    # Diplômé (1 = Graduate, 0 = Not Graduate)
    df["diplome"] = (
        df["Education"].map({"Graduate": 1, "Not Graduate": 0}).fillna(0).astype(int)
    )

    # Indépendant (1 = Yes, 0 = No)
    df["independant"] = (
        df["Self_Employed"].map({"Yes": 1, "No": 0}).fillna(0).astype(int)
    )

    # --- 4. CALCUL DES RATIOS ---
    # Mensualité approximative (Formule PMT rigoureuse avec taux moyen 3.5%)
    # P * r / (1 - (1+r)^-n)
    def calculate_pmt_vectorized(principal, months, rate=0.035):
        r = rate / 12
        months = np.maximum(months, 1)
        pmt = principal * r / (1 - (1 + r)**(-months))
        return pmt

    df["mensualite_approx"] = calculate_pmt_vectorized(df["montant_souhaite"], df["duree_mois"])

    # DTI = mensualité / revenus (ratio d'endettement)
    df["dti"] = df["mensualite_approx"] / df["revenus_mensuels"].replace(0, 1)
    # Clamp DTI to reasonable range
    df["dti"] = df["dti"].clip(0, 2)

    # Ratio montant/revenus
    df["ratio_montant_revenus"] = df["montant_souhaite"] / df["revenus_mensuels"].replace(0, 1)
    df["ratio_montant_revenus"] = df["ratio_montant_revenus"].clip(0, 100)

    # --- 5. SELECTION DES FEATURES ---
    feature_columns = [
        "revenus_mensuels",
        "montant_souhaite",
        "duree_mois",
        "historique_credit",
        "personnes_a_charge",
        "marie",
        "diplome",
        "independant",
        "dti",
        "ratio_montant_revenus",
    ]

    X = df[feature_columns].copy()
    y = df["target"]

    # Imputation des valeurs manquantes
    imputer = SimpleImputer(strategy="median")
    X_imputed = pd.DataFrame(imputer.fit_transform(X), columns=feature_columns)

    # --- 6. SPLIT & ENTRAINEMENT ---
    X_train, X_test, y_train, y_test = train_test_split(
        X_imputed, y, test_size=0.2, random_state=42, stratify=y
    )

    print(f"📊 Train: {len(X_train)}, Test: {len(X_test)}")
    print(f"📈 Taux positif (acceptés) : {y.mean() * 100:.1f}%")

    # Pipeline : Scaling + RandomForest
    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("classifier", RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            min_samples_leaf=5,
            random_state=42,
            class_weight="balanced",
        )),
    ])

    print("🔄 Entraînement du modèle...")
    pipeline.fit(X_train, y_train)

    # --- 7. EVALUATION ---
    y_pred = pipeline.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    print(f"\n🎯 Accuracy: {accuracy:.4f}")
    print("\n" + classification_report(y_test, y_pred, target_names=["Refusé", "Accepté"]))

    # --- 8. SAUVEGARDE ---
    artifact = {
        "pipeline": pipeline,
        "features": feature_columns,
        "best_model": "RandomForestClassifier",
        "metrics": {
            "accuracy": accuracy,
            "train_size": len(X_train),
            "test_size": len(X_test),
        },
    }

    joblib.dump(artifact, output_path)
    print(f"\n✅ Modèle sauvegardé : {output_path}")


if __name__ == "__main__":
    train_model()
