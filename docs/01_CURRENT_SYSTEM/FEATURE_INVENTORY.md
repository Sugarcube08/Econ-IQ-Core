# Feature Store Inventory
- **Current State:** Rolling features calculated in [engineer.py](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/ref/app/features/engineer.py) over 365d and 14d periods.
- **Target State:** Vectorized, cached feature vectors ready for ML training.
- **Gap Analysis:** Features are recalculated in bulk during recomputations without temporal sequences persistence.
- **Recommended Actions:** Cache features in Redis for dynamic API requests; export feature matrices for XGBoost training.
- **Priority:** High
- **Risk:** Medium (memory spikes during Polars rolling window operations)
- **Dependencies:** Polars optimization
- **Expected Outcome:** Ultra-fast feature loading interface.
