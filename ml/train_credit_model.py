"""
Script d'entraînement du modèle de scoring crédit.

- Charge un dataset tabulaire (CSV ou XLSX) depuis data/
- Prétraite (imputation numérique/catégorielle, encodage, scaling)
- Entraîne plusieurs modèles (logistique, arbre, forêt)
- Compare les métriques (accuracy, precision, recall, f1, roc_auc)
- Sérialise le meilleur pipeline (prépro + modèle) dans scoring/model_credit.pkl
"""

import argparse
from pathlib import Path
from typing import List, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier


def load_dataset(path: Path, sheet: str = None) -> pd.DataFrame:
    if path.suffix.lower() in {".xlsx", ".xls"}:
        return pd.read_excel(path, sheet_name=sheet, engine="openpyxl")
    return pd.read_csv(path)


def split_features_target(df: pd.DataFrame, target: str) -> Tuple[pd.DataFrame, pd.Series]:
    if target not in df.columns:
        raise ValueError(f"Colonne cible '{target}' introuvable dans le dataset.")
    df = df.copy()
    df = df.dropna(subset=[target])
    # Colonne identifiant souvent non pertinente
    if "Loan_ID" in df.columns:
        df = df.drop(columns=["Loan_ID"])
    y = df[target]
    # Normalisation binaire des labels si chaîne de caractères (ex: 'Y'/'N')
    if y.dtype == object or str(y.dtype).startswith("category"):
        uniques = sorted(y.dropna().unique())
        if len(uniques) == 2:
            mapping = {uniques[0]: 0, uniques[1]: 1}
            y = y.map(mapping)
        else:
            y = y.astype("category").cat.codes
    X = df.drop(columns=[target])
    return X, y


def build_preprocessor(X: pd.DataFrame) -> Tuple[ColumnTransformer, List[str], List[str]]:
    num_cols = [c for c in X.columns if pd.api.types.is_numeric_dtype(X[c])]
    cat_cols = [c for c in X.columns if c not in num_cols]

    numeric_transformer = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )
    categorical_transformer = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("encoder", OneHotEncoder(handle_unknown="ignore")),
        ]
    )

    preprocessor = ColumnTransformer(
        transformers=[
            ("num", numeric_transformer, num_cols),
            ("cat", categorical_transformer, cat_cols),
        ]
    )
    return preprocessor, num_cols, cat_cols


def evaluate_model(clf, X_test, y_test, average="binary") -> dict:
    proba = clf.predict_proba(X_test)[:, 1] if hasattr(clf, "predict_proba") else None
    preds = clf.predict(X_test)
    metrics = {
        "accuracy": accuracy_score(y_test, preds),
        "precision": precision_score(y_test, preds, zero_division=0),
        "recall": recall_score(y_test, preds, zero_division=0),
        "f1": f1_score(y_test, preds, zero_division=0),
    }
    if proba is not None:
        metrics["roc_auc"] = roc_auc_score(y_test, proba)
    return metrics


def main():
    parser = argparse.ArgumentParser(description="Entraînement du modèle de scoring crédit.")
    parser.add_argument("--input", required=True, help="Chemin vers le fichier CSV/XLSX du dataset.")
    parser.add_argument("--target", default="Loan_Status", help="Nom de la colonne cible.")
    parser.add_argument("--sheet", default=None, help="Nom de l'onglet Excel (optionnel).")
    parser.add_argument(
        "--output",
        default=str(Path("scoring") / "model_credit.pkl"),
        help="Chemin de sortie du modèle sérialisé.",
    )
    args = parser.parse_args()

    data_path = Path(args.input)
    if not data_path.exists():
        raise FileNotFoundError(f"Dataset introuvable : {data_path}")

    df = load_dataset(data_path, sheet=args.sheet)
    X, y = split_features_target(df, args.target)

    preprocessor, num_cols, cat_cols = build_preprocessor(X)

    # Modèles candidats
    models = {
        "log_reg": LogisticRegression(max_iter=1000),
        "decision_tree": DecisionTreeClassifier(random_state=42, max_depth=6),
        "random_forest": RandomForestClassifier(
            n_estimators=200, max_depth=None, random_state=42, n_jobs=-1
        ),
    }

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    results = {}
    best_name = None
    best_score = -np.inf
    best_pipeline = None

    for name, model in models.items():
        pipe = Pipeline(steps=[("preprocess", preprocessor), ("model", model)])
        pipe.fit(X_train, y_train)
        metrics = evaluate_model(pipe, X_test, y_test)
        results[name] = metrics
        score = metrics.get("roc_auc") or metrics["f1"]
        if score > best_score:
            best_score = score
            best_name = name
            best_pipeline = pipe

    if best_pipeline is None:
        raise RuntimeError("Aucun modèle entraîné.")

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    artifact = {
        "pipeline": best_pipeline,
        "features": list(X.columns),
        "target": args.target,
        "metrics": results,
        "best_model": best_name,
    }
    joblib.dump(artifact, output_path)

    print(f"Modèle '{best_name}' sauvegardé dans {output_path}")
    print("Métriques (test) :")
    for name, metrics in results.items():
        print(f"- {name}: {metrics}")
    print("\nClassification report (meilleur modèle) :")
    preds = best_pipeline.predict(X_test)
    print(classification_report(y_test, preds, zero_division=0))


if __name__ == "__main__":
    main()
