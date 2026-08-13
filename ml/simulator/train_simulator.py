import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, r2_score

from degradation_model import calculate_daily_delta

np.random.seed(42)

N_SAMPLES = 5000

# Generate random realistic input ranges
current_severity = np.random.uniform(0, 8, N_SAMPLES)          # 0-8 damage scale
daily_vehicles = np.random.uniform(500, 20000, N_SAMPLES)      # low to high traffic
rainfall_mm = np.random.uniform(0, 50, N_SAMPLES)              # daily rainfall
avg_temp = np.random.uniform(-10, 40, N_SAMPLES)               # celsius range
road_age_years = np.random.uniform(0, 30, N_SAMPLES)
last_repair_days = np.random.uniform(0, 3650, N_SAMPLES)       # up to 10 years since repair
material_type = np.random.randint(0, 4, N_SAMPLES)             # 0-3 encoded categories

# Derive freeze_thaw_cycles roughly from temperature (more cycles near freezing point)
freeze_thaw_cycles = np.where(
    (avg_temp > -5) & (avg_temp < 5),
    np.random.uniform(0.1, 0.5, N_SAMPLES),
    np.random.uniform(0, 0.05, N_SAMPLES)
)

# Compute target: severity after 30 days using the same formula from Step 7
future_severity = np.zeros(N_SAMPLES)
for i in range(N_SAMPLES):
    delta_per_day = calculate_daily_delta(
        daily_vehicles[i], rainfall_mm[i], freeze_thaw_cycles[i], road_age_years[i]
    )
    future_severity[i] = current_severity[i] + delta_per_day * 30

# Build dataframe
df = pd.DataFrame({
    "current_severity": current_severity,
    "daily_vehicles": daily_vehicles,
    "rainfall_mm": rainfall_mm,
    "avg_temp": avg_temp,
    "road_age_years": road_age_years,
    "last_repair_days": last_repair_days,
    "material_type": material_type,
    "future_severity": future_severity
})

print("Sample of generated data:")
print(df.head())
print(f"\nTotal rows: {len(df)}")

# Train/test split
feature_cols = ["current_severity", "daily_vehicles", "rainfall_mm", "avg_temp",
                 "road_age_years", "last_repair_days", "material_type"]
X = df[feature_cols]
y = df["future_severity"]

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Train XGBoost
model = xgb.XGBRegressor(n_estimators=200, max_depth=6, random_state=42)
model.fit(X_train, y_train)

# Evaluate
y_pred = model.predict(X_test)
rmse = np.sqrt(mean_squared_error(y_test, y_pred))
r2 = r2_score(y_test, y_pred)

print(f"\nRMSE: {rmse:.4f}")
print(f"R2 Score: {r2:.4f}")

# Save model
model.save_model("xgb_simulator.json")
print("\nModel saved as xgb_simulator.json")