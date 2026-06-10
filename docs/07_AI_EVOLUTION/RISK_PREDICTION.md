# Risk Prediction Module (XGBoost Classifier)
- **Current State:** Deterministic trust scoring.
- **Target State:** Probability of Default classifier.
- **Gap Analysis:** Code is missing.
- **Recommended Actions:** Train XGBoost on features (`avg_repayment_days`, `overdue_120p_amount`, etc.).
- **Priority:** High
- **Risk:** Medium (overfitting)
- **Dependencies:** Feature store
- **Expected Outcome:** Accurate 90-day risk prediction.
