# Econiq Core Platform — Documentation Library & Project OS

Welcome to the **Econiq Core Project Operating System**. This library serves as the single source of truth and execution blueprint for transforming the legacy econiq scoring engine into the generalized, AI-first **Econiq Core Platform** within a 2-week hackathon timeline.

---

## 1. Project Architecture Blueprint

```
[PostgreSQL Data Source: customers, raw_sales, raw_payments, raw_returns]
                                    │
                                    ▼ (Sync Ingestion Engine)
                       [Normalized event_ledger Table]
                                    │
                         (Polars rolling window features)
                                    │
                                    ▼
                      [Redis Cache / Feature Store]
                                    │
         ┌──────────────────────────┴──────────────────────────┐
         ▼ (Dynamic Policy Config)                             ▼ (Predictive ML Models)
  [Policy Engine Profiles]                              [XGBoost / LightGBM serving]
  - Scoring Weights & Rules                             - 90-day Default Risk (PD)
  - State Inference Thresholds                          - 30-day Merchant Churn
  - Credit Grace Terms Limits                           - Recovery Priority Rankings
         │                                                     │
         └──────────────────────────┬──────────────────────────┘
                                    ▼
                        [FastAPI Core REST Gateway]
                                    │
         ┌──────────────────────────┴──────────────────────────┐
         ▼ (Conversational Assistant)                          ▼ (Dashboard UI Widgets)
  [Gemini Copilot API Explainer]                        [React Client Interface]
  - Chat & Risk Summaries                               - Prioritized Collections
  - Dynamic Action Recommendations                      - Metric Deltas & Timelines
```

---

## 2. Operating System Navigation Index

Click on the links below to explore the specifications:

### 📂 [00 - Executive Overview](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/docs/00_EXECUTIVE_OVERVIEW)
*   📋 **[Project Status & Readiness](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/docs/00_EXECUTIVE_OVERVIEW/PROJECT_STATUS.md)**: Dev completion status (~70% backend, ~90% frontend).
*   🔑 **[Ground Truth](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/docs/00_EXECUTIVE_OVERVIEW/GROUND_TRUTH.md)**: Realities of the econiq backend assets.
*   🎯 **[Executive Summary](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/docs/00_EXECUTIVE_OVERVIEW/EXECUTIVE_SUMMARY.md)**: Feasibility, timelines, and business returns.
*   🔭 **[Platform Vision](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/docs/00_EXECUTIVE_OVERVIEW/VISION.md)**: Commercial Intelligence and Credit OS positioning.

### 📂 [01 - Current System Inventory](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/docs/01_CURRENT_SYSTEM)
*   🖥️ **[Backend Modules](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/docs/01_CURRENT_SYSTEM/BACKEND_INVENTORY.md)**: Tech stack, libraries, and background tasks.
*   🎨 **[Frontend Interface](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/docs/01_CURRENT_SYSTEM/FRONTEND_INVENTORY.md)**: Dashboards, profiles, and widget status.
*   💾 **[Database Schemas](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/docs/01_CURRENT_SYSTEM/DATABASE_INVENTORY.md)**: Tables, columns, and relations.
*   🔌 **[API Route List](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/docs/01_CURRENT_SYSTEM/API_INVENTORY.md)**: Routing endpoints and parameter models.
*   🧠 **[Intelligence Operations](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/docs/01_CURRENT_SYSTEM/INTELLIGENCE_INVENTORY.md)**: Summary of scoring engine structures.
*   ⚡ **[Rolling Feature Store](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/docs/01_CURRENT_SYSTEM/FEATURE_INVENTORY.md)**: Features inventory.
*   📊 **[Asset Preservation Matrix](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/docs/01_CURRENT_SYSTEM/ASSET_PRESERVATION_MATRIX.md)**: High-value codebase components that must be preserved.

### 📂 [02 - Econiq Core Specification](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/docs/02_ECONIQ_CORE)
*   🏗️ **[Core Framework](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/docs/02_ECONIQ_CORE/ECONIQ_CORE.md)**: Framework boundaries.
*   ⚙️ **[Infrastructure Services](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/docs/02_ECONIQ_CORE/INFRASTRUCTURE_CORE.md)**: Database, cache, and concurrency loops.
*   📈 **[Commercial Intelligence](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/docs/02_ECONIQ_CORE/COMMERCIAL_INTELLIGENCE_CORE.md)**: Ledger processing core code.
*   🔧 **[Policy Engine Design](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/docs/02_ECONIQ_CORE/POLICY_ENGINE.md)**: Decentralizing scoring parameters.
*   🗃️ **[Online Feature Cache](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/docs/02_ECONIQ_CORE/FEATURE_STORE.md)**: Redis layout for feature serving.
*   🚧 **[Core Boundaries](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/docs/02_ECONIQ_CORE/CORE_BOUNDARIES.md)**: Package decoupling rules.

### 📂 [03 - Organization Extraction](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/docs/03_ORGANIZATION_EXTRACTION)
*   ❌ **[Organization Logic Maps](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/docs/03_ORGANIZATION_EXTRACTION/ORG_SPECIFIC_LOGIC.md)**: Hardcoded weights and bounds list.
*   📐 **[Scoring Abstraction](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/docs/03_ORGANIZATION_EXTRACTION/SCORING_ABSTRACTION.md)**: Abstract interfaces for scoring logic.
*   📝 **[Policy Migration Path](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/docs/03_ORGANIZATION_EXTRACTION/POLICY_MIGRATION_PLAN.md)**: Steps to decouple dynamic values.
*   📐 **[Configuration Model](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/docs/03_ORGANIZATION_EXTRACTION/CONFIGURATION_MODEL.md)**: Pydantic schemas validating configuration profiles.

### 📂 [04 - Transformation Plan](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/docs/04_TRANSFORMATION_PLAN)
*   🗺️ **[Migration Roadmap](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/docs/04_TRANSFORMATION_PLAN/CURRENT_TO_TARGET.md)**: Alignment master plan.
*   📁 **[File Migration Matrix](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/docs/04_TRANSFORMATION_PLAN/FILE_MIGRATION_MATRIX.md)**: Moves and renames file layout table.
*   📦 **[Module Migration Matrix](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/docs/04_TRANSFORMATION_PLAN/MODULE_MIGRATION_MATRIX.md)**: Service adjustments.
*   💾 **[Database Alignment](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/docs/04_TRANSFORMATION_PLAN/DATABASE_ALIGNMENT.md)**: Target PostgreSQL raw tables mapping.
*   🖥️ **[Frontend Alignment](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/docs/04_TRANSFORMATION_PLAN/FRONTEND_ALIGNMENT.md)**: UI data ingestion properties mapping.
*   🔌 **[API Alignment](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/docs/04_TRANSFORMATION_PLAN/API_ALIGNMENT.md)**: Parameter rename contracts.

### 📂 [05 - Data Foundation](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/docs/05_DATA_FOUNDATION)
*   📊 **[ER Data Model](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/docs/05_DATA_FOUNDATION/DATA_MODEL.md)**: Database fields and relations.
*   ⚡ **[Ingestion Architecture](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/docs/05_DATA_FOUNDATION/INGESTION_ARCHITECTURE.md)**: Async batch synchronization using database locks.
*   📓 **[Ledger Timeline Reconstruction](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/docs/05_DATA_FOUNDATION/LEDGER_ARCHITECTURE.md)**: Compiling daily outstanding exposure histories.
*   🧬 **[Feature Engineering](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/docs/05_DATA_FOUNDATION/FEATURE_ENGINEERING.md)**: Vectorized rolling window calculations.
*   ✅ **[Data Quality Validators](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/docs/05_DATA_FOUNDATION/DATA_QUALITY.md)**: Verifying state entropy and data freshness.
*   🌱 **[Synthetic Data Strategy](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/docs/05_DATA_FOUNDATION/SYNTHETIC_DATA_STRATEGY.md)**: Data seeding configuration.

### 📂 [06 - Intelligence Platform](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/docs/06_INTELLIGENCE_PLATFORM)
*   🧠 **[Unified Orchestrator](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/docs/06_INTELLIGENCE_PLATFORM/SCORING_ENGINES.md)**: Calculation execution sequences.
*   📊 **[State Classification](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/docs/06_INTELLIGENCE_PLATFORM/STATE_ENGINE.md)**: Client status mapping logic.
*   🛡️ **[Trust Fusion](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/docs/06_INTELLIGENCE_PLATFORM/TRUST_ENGINE.md)**: Purchase/payment score integration rules.
*   💳 **[Payment Discipline](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/docs/06_INTELLIGENCE_PLATFORM/PAYMENT_ENGINE.md)**: delay, fragment, and aging indicators.
*   🔥 **[Stress Engine](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/docs/06_INTELLIGENCE_PLATFORM/STRESS_ENGINE.md)**: Returns and deficit calculations.
*   📈 **[Exposure Engine](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/docs/06_INTELLIGENCE_PLATFORM/EXPOSURE_ENGINE.md)**: outstanding balance streaks tracking.
*   💡 **[Recommendation Engine](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/docs/06_INTELLIGENCE_PLATFORM/RECOMMENDATION_ENGINE.md)**: Credit adjustments suggestions logic.
*   💬 **[Explainability Engine](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/docs/06_INTELLIGENCE_PLATFORM/EXPLAINABILITY_ENGINE.md)**: driver string aggregations.

### 📂 [07 - AI Evolution Roadmap](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/docs/07_AI_EVOLUTION)
*   🔮 **[AI Strategy](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/docs/07_AI_EVOLUTION/AI_TRANSFORMATION_PLAN.md)**: Capabilites transition plan.
*   🤖 **[ML Serving Setup](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/docs/07_AI_EVOLUTION/ML_ARCHITECTURE.md)**: Package structures for XGBoost/LightGBM.
*   🔮 **[Prediction Engine](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/docs/07_AI_EVOLUTION/PREDICTION_ENGINE.md)**: Unified inference interfaces.
*   🛑 **[Risk Model (PD)](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/docs/07_AI_EVOLUTION/RISK_PREDICTION.md)**: 90-day probability of default.
*   🚪 **[Churn Classifier](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/docs/07_AI_EVOLUTION/CHURN_PREDICTION.md)**: 30-day order drop forecast.
*   📈 **[Growth Forecaster](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/docs/07_AI_EVOLUTION/GROWTH_PREDICTION.md)**: Sales expansion predictions.
*   🎯 **[Collections Priority Router](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/docs/07_AI_EVOLUTION/COLLECTION_PREDIORITIZATION.md)**: Ranking delinquent clients.
*   💬 **[Gemini Copilot Architecture](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/docs/07_AI_EVOLUTION/COPILOT_ARCHITECTURE.md)**: LLM chat prompts and bounds.
*   🔍 **[Explainable AI (XAI)](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/docs/07_AI_EVOLUTION/XAI_STRATEGY.md)**: feature delta indicators translation.
*   🧬 **[Deep Learning Sequence Forecasts](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/docs/07_AI_EVOLUTION/DL_ROADMAP.md)**: Future temporal model implementations.

### 📂 [08 - Deployment Configurations](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/docs/08_DEPLOYMENT)
*   ☁️ **[Railway Settings](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/docs/08_DEPLOYMENT/RAILWAY_OPTIMIZATION.md)**: Environment variable configs and validation rules.
*   ⚡ **[Performance Guide](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/docs/08_DEPLOYMENT/PERFORMANCE_GUIDE.md)**: Redis cached reads setups.
*   🔍 **[Observability Settings](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/docs/08_DEPLOYMENT/OBSERVABILITY.md)**: Structured logs and Prometheus metrics.
*   🔒 **[Security Policy](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/docs/08_DEPLOYMENT/SECURITY.md)**: JWT session verify and API key rate limits.
*   🏎️ **[Scaling Guidelines](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/docs/08_DEPLOYMENT/SCALING_GUIDE.md)**: pool overflow scaling metrics.

### 📂 [09 - Execution Management](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/docs/09_EXECUTION)
*   ⏱️ **[48-Hour Plan](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/docs/09_EXECUTION/48_HOUR_PLAN.md)**: Day 1 & Day 2 implementation details.
*   📅 **[14-Day Gantt Plan](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/docs/09_EXECUTION/14_DAY_PLAN.md)**: Complete development timeline.
*   📋 **[Sprint Board Backlog](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/docs/09_EXECUTION/SPRINT_BOARD.md)**: Task items lists.
*   🗺️ **[Task Dependency Map](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/docs/09_EXECUTION/DEPENDENCY_GRAPH.md)**: Execution prerequisites chart.
*   ⚠️ **[Risk Register](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/docs/09_EXECUTION/RISK_REGISTER.md)**: Risk mitigations matrix.
*   📓 **[Design Decision Log](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/docs/09_EXECUTION/DECISION_LOG.md)**: System design choices log.

### 📂 [10 - Reference Archive](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/docs/10_REFERENCE)
*   Contains original audit logs, legacy vision plans, and forensic reports preserved as archives.
