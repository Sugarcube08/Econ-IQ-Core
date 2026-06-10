# Econiq Codebase Compatibility Matrix

**Version:** 1.0.0  
**Status:** Completed  
**Author:** Technical Due Diligence Auditor  
**Owner:** Core Engineering Team

---

## Econiq Compatibility & Reuse Blueprint

This matrix maps every module in the reference codebase (`/ref/app`) to its target role in the **Econiq AI-powered Commercial Decision Infrastructure**:

| Current Module | Purpose | Econiq Equivalent | Compatibility | Reuse | Action | Owner | Priority |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Auth Service** (`api/auth.py`) | Handles user login/logout & OTP validation. | Authentication Core | 100% | 100% | Keep As-Is | Security Lead | Low |
| **User Service** (`services/user.py`)| Manages User CRUD operations. | User Profile Registry | 98% | 100% | Keep As-Is | Core Backend | Low |
| **API Keys API** (`api/api_keys.py`) | Manages client API keys. | API Key Gateway | 100% | 100% | Keep As-Is | Security Lead | Low |
| **DB Ingestion** (`ingestion/db_provider`)| Scraping raw transactions. | Ingestion Scraper | 90% | 95% | Modify `is_ok` mappers | Data Platform | High |
| **Sync Daemon** (`services/sync_pipeline`)| Run ingestion cycles. | Ingestion Pipeline | 85% | 90% | Refactor SQL locks | Data Platform | Medium |
| **Feature Eng** (`features/engineer.py`) | Compiles temporal averages. | Feature Cache Hydrator | 80% | 85% | Refactor Polars queries | ML Platform | High |
| **Ledger Rec** (`intelligence/ledger`) | Computes exposure. | exposure Engine | 70% | 80% | Modify `is_ok` filters | Core Backend | Critical |
| **Trust Engine** (`intelligence/trust`) | Fuses behavior scores. | Health Scoring Engine | 60% | 70% | Refactor weights | Analytics Lead | Critical |
| **State Engine** (`intelligence/states`) | Assigns customer state. | Risk Prediction Router | 50% | 60% | Replace with XGBoost | ML Platform | Critical |
| **Causal Engine** (`intelligence/causal`) | Explains score changes. | SHAP Driver Parser | 40% | 50% | Refactor into Copilot | AI Architect | High |
| **Email Service** (`services/email.py`)| Dispatches raw reports. | None | 0% | 0% | Delete | Core Backend | Low |
| **Audit Log** (`models/state_models.py`)| Logs recomputations. | Decision Audit Log | 90% | 100% | Keep As-Is | Core Backend | Low |
| **Dashboard API** (`api/dashboard.py`)| Serves aggregate views. | Dashboard Gateway | 80% | 90% | Modify SQL queries | Frontend Lead | Medium |
| **Redis Cache** (`storage/redis.py`) | Manages key-value stores. | Feature Store Cache | 95% | 100% | Keep As-Is | Data Platform | Medium |
