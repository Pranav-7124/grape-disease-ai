"""
trainer.py – Daily self-training pipeline
Loads prediction_logs from MySQL + original dataset.csv,
retrains disease and risk models, saves updated .pkl files.
"""
import pickle
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
from datetime import datetime
import os

def run_training(trigger_type="scheduled"):
    """
    Merges DB logs with seed dataset, retrains both models,
    saves .pkl files, logs result to DB. Returns accuracy float.
    """
    print(f"[TRAINER] Starting self-training at {datetime.now()} ({trigger_type})")

    # Import here to avoid circular imports
    from db import get_all_prediction_logs, log_training

    # -----------------------------------------
    # 1. Load original seed dataset
    # -----------------------------------------
    base_path = os.path.dirname(os.path.abspath(__file__))
    seed_df = pd.read_csv(os.path.join(base_path, "dataset.csv"))
    print(f"[TRAINER] Seed data: {len(seed_df)} rows")

    # -----------------------------------------
    # 2. Load prediction logs from MySQL
    # -----------------------------------------
    logs = get_all_prediction_logs()
    if logs:
        log_df = pd.DataFrame(logs)
        log_df = log_df.rename(columns={
            "predicted_disease": "disease",
            "predicted_risk":    "risk"
        })
        # Ensure column alignment with seed dataset
        required_cols = ["temperature", "humidity", "rainfall", "growth_stage", "disease", "risk"]
        log_df = log_df[[c for c in required_cols if c in log_df.columns]]
        combined_df = pd.concat([seed_df, log_df], ignore_index=True)
        print(f"[TRAINER] DB logs: {len(log_df)} rows → Total: {len(combined_df)} rows")
    else:
        combined_df = seed_df.copy()
        print("[TRAINER] No DB logs yet — using seed data only")

    combined_df.dropna(inplace=True)

    # -----------------------------------------
    # 3. Encode features
    # -----------------------------------------
    stage_enc   = LabelEncoder()
    disease_enc = LabelEncoder()
    risk_enc    = LabelEncoder()

    combined_df["stage_enc"]   = stage_enc.fit_transform(combined_df["growth_stage"])
    combined_df["disease_enc"] = disease_enc.fit_transform(combined_df["disease"])
    combined_df["risk_enc"]    = risk_enc.fit_transform(combined_df["risk"])

    X = combined_df[["temperature", "humidity", "rainfall", "stage_enc"]].values
    y_disease = combined_df["disease_enc"].values
    y_risk    = combined_df["risk_enc"].values

    # -----------------------------------------
    # 4. Train-test split
    # -----------------------------------------
    X_tr, X_te, yd_tr, yd_te, yr_tr, yr_te = train_test_split(
        X, y_disease, y_risk, test_size=0.2, random_state=42
    )

    # -----------------------------------------
    # 5. Retrain Random Forest models
    # -----------------------------------------
    disease_model = RandomForestClassifier(n_estimators=100, random_state=42)
    disease_model.fit(X_tr, yd_tr)
    disease_acc = accuracy_score(yd_te, disease_model.predict(X_te))

    risk_model = RandomForestClassifier(n_estimators=100, random_state=42)
    risk_model.fit(X_tr, yr_tr)
    risk_acc = accuracy_score(yr_te, risk_model.predict(X_te))

    avg_acc = (disease_acc + risk_acc) / 2
    print(f"[TRAINER] Disease accuracy: {disease_acc:.2%} | Risk accuracy: {risk_acc:.2%}")

    # -----------------------------------------
    # 6. Atomically save .pkl files
    # -----------------------------------------
    with open(os.path.join(base_path, "disease_model.pkl"), "wb") as f:
        pickle.dump(disease_model, f)
    with open(os.path.join(base_path, "risk_model.pkl"), "wb") as f:
        pickle.dump(risk_model, f)
    with open(os.path.join(base_path, "stage_encoder.pkl"), "wb") as f:
        pickle.dump(stage_enc, f)
    with open(os.path.join(base_path, "disease_encoder.pkl"), "wb") as f:
        pickle.dump(disease_enc, f)
    with open(os.path.join(base_path, "risk_encoder.pkl"), "wb") as f:
        pickle.dump(risk_enc, f)

    print("[TRAINER] Model .pkl files saved.")

    # -----------------------------------------
    # 7. Log training event to DB
    # -----------------------------------------
    try:
        log_training(len(combined_df), avg_acc, trigger_type)
    except Exception as e:
        print(f"[TRAINER] Could not log to DB: {e}")

    print(f"[TRAINER] Done. Accuracy: {avg_acc:.2%} on {len(combined_df)} samples.")
    return avg_acc, len(combined_df)
