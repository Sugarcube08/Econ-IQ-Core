# Econiq Core Platform

Econiq Core is a production-grade, stateful commercial intelligence and behavioral scoring platform designed for B2B trade networks (manufacturers, distributors, wholesalers, and importers). It transforms raw transactional signals into real-time risk, growth, trust, and relationship scoring.

This repository is **ML-Ready** (supporting XGBoost, LightGBM, and CatBoost models) but runs out-of-the-box using rules-based baseline estimators.

---

## 1. System Architecture

```
   Raw Ledger Events (SALE, PAYMENT, RETURN, etc.)
                          │
                          ▼
            Stateful Ingestion Pipeline
                          │
                          ▼
               Feature Store Engine
         (24 longitudinal rolling features)
                          │
                          ▼

              8 Consolidated B2B Dimensions
      (Activity, Discipline, Credit, Growth, etc.)
                          │
                          ▼
              8 Consolidated Public Scores
         (Trust, Health, Risk, Opportunity, etc.)
                          │
       ┌──────────────────┴──────────────────┐
       ▼                                     ▼
Action Recommendations               Model Inference
  (Credit, Terms, Churn)           (Swappable ML Registry)
```

---

## 2. Directory Structure

* [core/](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/core/): Primary source package for Econiq Core.
  * [auth/](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/core/auth/): JWT, User, and API key authentication layers.
  * [config/](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/core/config/): Application configurations (`settings.py` loading from env).
  * [customers/](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/core/customers/): API routers for customer datatables, detail profiles, predictions, and recommendations.
  * [dashboard/](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/core/dashboard/): Analytical summary widgets and visualization backends.
  * [explainability/](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/core/explainability/): Causal SHAP-based diagnostics engine for score shifts and state transitions.
  * [feature_store/](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/core/feature_store/): Polars-based rolling window feature aggregation pipeline.
  * [intelligence/](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/core/intelligence/): Internal calculations for the consolidated 8 Dimensions, Meta-scores, and state machines.
  * [prediction/](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/core/prediction/): Hardened swappable estimator registry, inference engines, and drift monitors.
  * [recommendation/](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/core/recommendation/): Rules-based action recommendation generation engine.
  * [schemas/](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/core/schemas/): Standard Pydantic schemas validating API schemas, predictions, and recommendations.
  * [storage/](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/core/storage/): Database drivers (PostgreSQL + SQLAlchemy Asyncpg, Redis Manager).
* [tests/](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/tests/): Fast unit test suite covering prediction contracts and estimator registry.

---

## 3. Getting Started

### Prerequisites
* Python 3.12+
* PostgreSQL (with database named `ir_econiq` populated)
* Redis (for rate limiting and cache invalidate events)

### Installation
Use [uv](https://github.com/astral-sh/uv) to install dependencies and manage environments:
```bash
uv sync
```

### Running Locally
To launch the FastAPI development server with reloading:
```bash
uv run uvicorn core.main:app --host 127.0.0.1 --port 8000 --reload
```

### Running Tests
Execute the pytest suite:
```bash
uv run pytest
```

---

## 4. Platform Contracts

Detailed specifications can be found in the frozen platform documentation files:
* [CANONICAL_PLATFORM_V2.md](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/CANONICAL_PLATFORM_V2.md): Frozen signatures for signals, features, dimensions, scores, predictions, and recommendation objects.
* [FEATURE_CATALOG_V2.md](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/FEATURE_CATALOG_V2.md): Specification of the 24 longitudinal feature formulations, expected ranges, and fallbacks.
* [SIGNAL_REALITY_AUDIT.md](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/SIGNAL_REALITY_AUDIT.md): Source signal availability audit and scoring bounds.
* [API_CONTRACT_V2.md](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/API_CONTRACT_V2.md): HTTP JSON specs forREST endpoints serving the 8 canonical scores.
* [EXPLAINABILITY_V2.md](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/EXPLAINABILITY_V2.md): SHAP driver variables and recommendations rationales.

---

## 5. Development Strategy & Versioning

To ensure stability during subsequent machine learning training (fitting model weights via XGBoost/LightGBM):
1. **API Versioning**: Any breaking API model adjustments must increment the root routing path (e.g. `/api/v2`).
2. **Model Versioning**: Registered estimators are versioned semantically (e.g. `1.0.0` for heuristics, `2.0.0` for first ML runs). Swapping occurs dynamically by supplying the `version` query parameter to the predictions endpoints.
3. **Commit hygiene**: Commits must follow semantic conventions (e.g., `feat:`, `fix:`, `refactor:`, `docs:`).
