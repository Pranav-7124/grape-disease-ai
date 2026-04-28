import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
import pickle
import os

print("Starting training...")

# Show current working directory
print("Current Directory:", os.getcwd())

# Load dataset
df = pd.read_csv("dataset.csv")
print("Dataset loaded successfully")

# Encode categorical columns
le_stage = LabelEncoder()
df["growth_stage"] = le_stage.fit_transform(df["growth_stage"])

le_disease = LabelEncoder()
df["disease"] = le_disease.fit_transform(df["disease"])

le_risk = LabelEncoder()
df["risk"] = le_risk.fit_transform(df["risk"])

# Features
X = df[["temperature", "humidity", "rainfall", "growth_stage"]]

# Targets
y_disease = df["disease"]
y_risk = df["risk"]

# Train models
disease_model = RandomForestClassifier()
risk_model = RandomForestClassifier()

disease_model.fit(X, y_disease)
risk_model.fit(X, y_risk)

print("Models trained")

# Save models
with open("disease_model.pkl", "wb") as f:
    pickle.dump(disease_model, f)

with open("risk_model.pkl", "wb") as f:
    pickle.dump(risk_model, f)

# Save encoders
with open("stage_encoder.pkl", "wb") as f:
    pickle.dump(le_stage, f)

with open("disease_encoder.pkl", "wb") as f:
    pickle.dump(le_disease, f)

with open("risk_encoder.pkl", "wb") as f:
    pickle.dump(le_risk, f)

print("Files saved successfully")

# List files in current directory
print("Files in directory:", os.listdir())