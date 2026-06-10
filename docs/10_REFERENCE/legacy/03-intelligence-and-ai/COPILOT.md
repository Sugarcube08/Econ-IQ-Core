# Econiq Commercial Intelligence Copilot Specification

**Version:** 2.1.0  
**Status:** Approved  
**Author:** Lead Architect & Startup CTO  
**Owner:** Product & Security Team

---

## 1. Copilot System Principles

The Econiq Copilot is an interactive sidebar widget in the dashboard. An absolute architectural constraint is that **the Copilot does not calculate credit risk, compute metrics, or generate decisions**. 

Instead, the Copilot **explains** intelligence calculated by downstream engines. It acts as a translation layer, translating raw timelines, metrics, SHAP prediction drivers, and recommendation inputs into natural language.

```
                  ┌───────────────────────────────┐
                  │       User Chat Query         │
                  │   "Why did their risk spike?" │
                  └───────────────┬───────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       COPILOT GATEWAY SERVICE                           │
│                                                                         │
│  ┌─────────────────────────┐                 ┌───────────────────────┐  │
│  │ Context Hydrator        │ ◄──────────────│ Database / Redis      │  │
│  │ (Query API for JSON)    │                 │ (Scores, SHAP, Recs)  │  │
│  └────────────┬────────────┘                 └───────────────────────┘  │
│               │                                                         │
│               ▼ (Structured JSON Context Only)                          │
│  ┌─────────────────────────┐                 ┌───────────────────────┐  │
│  │ Prompt Constructor      │ ──────────────►│ Large Language Model  │  │
│  │ (Strict System Prompt)  │                 │ (Gemini Flash API)    │  │
│  └─────────────────────────┘                 └───────────┬───────────┘  │
└──────────────────────────────────────────────────────────┼──────────────┘
                                                           │ (Natural Text Output)
                                                           ▼
                                                    [Analyst Client]
```

---

## 2. Context Prompt Structure

To prevent hallucination, the Copilot Gateway intercepts queries, extracts the target customer ID, fetches the resolved JSON customer profile, and injects it into the LLM system prompt context:

### Prompt Payload Structure (Gemini Input Context):
```json
{
  "customer_profile": {
    "name": "Sharma Textiles",
    "credit_limit": 500000.00,
    "outstanding_balance": 465000.00
  },
  "active_scores": {
    "risk_score": 78,
    "drivers": [
      {"metric": "wdpd_30", "value": 22.4, "impact": "+33.6"}
    ]
  },
  "active_predictions": {
    "default_probability": 0.72,
    "top_shap_driver": "high_credit_utilization"
  },
  "active_recommendations": [
    {
      "action": "DECREASE_CREDIT_LIMIT",
      "value": 300000.00,
      "rationale": "High utilization paired with 22-day payment delay variance."
    }
  ]
}
```

---

## 3. System Instructions

The LLM is configured with strict system instructions to keep conversation scope bounded:

```text
You are the Econiq Commercial Intelligence Copilot. 
Your sole task is to explain the structured customer context provided in the JSON payload.
Follow these rules strictly:
1. ONLY refer to facts, metrics, and recommendations present in the context payload.
2. If the user asks a question that cannot be answered using the provided JSON context, reply: "I do not have access to that information in this customer's profile."
3. DO NOT perform arithmetic calculations, compute averages, or estimate default probabilities. Use the pre-computed values in the JSON context.
4. Keep explanations professional, audit-focused, and concise.
```

---

## 4. Example Conversations

### User: "Why is this customer risky?"
*   **Copilot Reply:** "Sharma Textiles has a high Risk Score of 78 and a Default Probability of 72%. This is driven primarily by their current credit utilization (92% of their $500,000 credit limit is used) and an average payment delay of 22.4 days past due."

### User: "What actions should I take?"
*   **Copilot Reply:** "Based on their current risk profile, the Recommendation Engine suggests reducing their credit limit to $300,000 to limit outstanding exposure."
