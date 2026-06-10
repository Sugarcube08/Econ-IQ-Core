# Machine Learning Serving Architecture
- **Current State:** No ML model serving system.
- **Target State:** Lightweight ML model scoring (XGBoost, LightGBM) inside the FastAPI backend.
- **Gap Analysis:** Pipeline lacks model binary load steps.
- **Recommended Actions:** Implement background model load; feed feature vectors to classifiers.
- **Priority:** Critical
- **Risk:** Medium (model loading memory footprint)
- **Dependencies:** Prediction Engine
- **Expected Outcome:** Sub-10ms ML inference execution.
