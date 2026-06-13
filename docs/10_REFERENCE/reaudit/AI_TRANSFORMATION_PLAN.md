# AI Transformation Masterplan

This document outlines the engineering roadmaps, work items, and complexity ratings to transition the legacy analytics backend into a predictive, AI-first Commercial Intelligence Platform within a two-week hackathon delivery timeframe.

---

## 1. Current State vs. Target State Evaluation

```mermaid
flowchart LR
    subgraph Current State [econiq Legacy (Analytics)]
        RawDB[Raw Data Sync] --> Ledger[Ledger Materialization]
        Ledger --> PolarsStat[Polars Rolling Stats]
        PolarsStat --> HardcodedRules[Hardcoded Scoring Rules]
        HardcodedRules --> StaticDB[Static Score Reports]
    end

    subgraph Target State [Econiq Core (AI-First)]
        RawDB_v2[Ingestion Sync] --> Ledger_v2[Ledger Materialization]
        Ledger_v2 --> PolarsFeatures[Feature Store]
        PolarsFeatures --> ConfigPolicy[Dynamic Configuration]
        PolarsFeatures --> MLModels[XGBoost / LightGBM Models]
        MLModels --> PredictiveScores[Risk / Churn / Health Probabilities]
        PredictiveScores --> Copilot[Gemini LLM Explainer / Copilot]
    end
```

---

## 2. Capability Evolution Matrix

The table below breaks down the technical transition across all platform capabilities:

| Capability Area | Current State (%) | Target State (%) | Work Required | Complexity | Risk | Expected ROI |
| :--- | :---: | :---: | :--- | :--- | :--- | :--- |
| **Data Engineering** | 70% | 95% | Upgrade schema of raw tables, integrate immediate webhook injection routes for real-time transactions, optimize Polars sorting. | Low | Low | Medium |
| **Analytics & BI** | 90% | 95% | Hook existing endpoints (`/dashboard/overview`, `/customers/datatable`) to read predictive fields instead of raw legacy columns. | Low | Low | Medium |
| **Scoring Engine** | 80% | 95% | Decouple weights and state boundaries into YAML/PostgreSQL policies as designed in the Policy Engine specs. | Medium | Medium | High |
| **Machine Learning** | 0% | 85% | Train XGBoost for default risk, LightGBM for churn, and CatBoost for collections priority on historical rolling features. | Medium | Medium | Critical |
| **Recommendation Engine** | 0% | 75% | Build rule-based recommendation handlers that suggest credit limits and collection strategies based on ML outputs. | Low | Low | High |
| **Generative AI Copilot** | 0% | 85% | Write a FastAPI route `/api/copilot/chat` wrapping the Gemini API, feeding it structured customer metrics JSON for context-anchored risk summaries. | Medium | Low | Extremely High |
| **Explainability (XAI)** | 10% | 90% | Translate feature contributions and risk drivers into human-readable text blocks using Gemini prompt templates. | Medium | Low | High |
| **Future Deep Learning** | 0% | 50% | Format sequential transaction data into 3D temporal tensors for future LSTM/Transformer cash flow forecasters. | High | High | High (Long-term) |

---

## 3. Generative AI Copilot Integration Architecture

The Econiq Copilot will be integrated as a lightweight, stateless middleware calling the **Google Gemini API** asynchronously.

### 3.1 Prompt Context Structuring (No Hallucinations)
To guarantee strict correctness during a customer risk review, the Copilot will be fed a JSON payload of calculated metrics, with a prompt boundary prohibiting any data generation outside the provided bounds:

```python
import google.generativeai as genai
from fastapi import APIRouter, Depends
from app.repositories.intelligence import IntelligenceRepository

router = APIRouter()

@router.get("/customers/{customer_id}/explain")
async def explain_customer_risk(
    customer_id: str, 
    repo: IntelligenceRepository = Depends(get_repo)
):
    # 1. Fetch structured feature store metrics
    metrics = await repo.get_customer_metrics(customer_id)
    
    # 2. Setup Gemini client
    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    # 3. Inject strict context boundary prompt
    prompt = f"""
    You are the Econiq AI Credit Analyst. Analyze the following customer performance metrics:
    {metrics.model_dump_json()}
    
    Provide:
    1. A summary of the credit risk profile.
    2. The top two drivers (positive or negative) of their current state.
    3. Actionable recommendation (e.g., credit terms adjustment).
    
    CRITICAL CONSTRAINT: You must only use the numbers and states in the provided JSON. Do NOT invent transactions, invoices, or history. If a metric is missing or 0, treat it as such.
    """
    
    response = await model.generate_content_async(prompt)
    return {"analysis": response.text}
```

---

## 4. Execution Plan (Timeline: 2 Weeks)

*   **Days 1-3:** Decouple hardcoded scoring parameters into policy settings.
*   **Days 4-7:** Train scikit-learn models (XGBoost/LightGBM) on the Polars features; serialize and package within the FastAPI app.
*   **Days 8-10:** Implement the Gemini API Copilot `/explain` and `/chat` endpoints.
*   **Days 11-14:** Align frontend API consumption, test end-to-end performance, and deploy to Railway.
