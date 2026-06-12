# DATABASE TO API TRACEABILITY MATRIX

This document outlines the complete data lineage and traceability mapping of the Econiq Core platform. Every field served in API responses is traced down through Scores, Dimensions, and Features to the raw Database Columns.

---

## 1. Lineage Flow Diagram

```
[Raw Event Ledger / Customers] 
       ↓ (Ingestion & Ledger Reconstruction)
[Computed Features (Pydantic / Polars)] 
       ↓ (8 Dimension Engines)
[Consolidated Dimensions] 
       ↓ (Meta Score Engine)
[8 Canonical Scores] 
       ↓ (Resilient Serving / Cache Persist)
[API Endpoint Response Fields]
```

---

## 2. Complete Lineage Mapping Matrix

| Raw Database Table & Column | Computed Feature | Consolidated Dimension | Meta Score | API Field |
| :--- | :--- | :--- | :--- | :--- |
| `event_ledger.amount`, `event_ledger.event_type = 'SALE'` | `sales_window` (Total sales volume over 365d) | `dim_activity` (Trade cadence and volume density) | `health_score`, `growth_score`, `credit_score`, `relationship_score` | `scores.health_score`, `scores.growth_score`, `scores.credit_score`, `scores.relationship_score` |
| `event_ledger.amount`, `event_ledger.event_type = 'PAYMENT'` | `payments_window` (Total settlement volume over 365d) | `dim_discipline` (Rhythm regularity and settlement speeds) | `risk_score`, `trust_score`, `collection_score` | `scores.risk_score`, `scores.trust_score`, `scores.collection_score` |
| `event_ledger.amount`, `event_ledger.event_type = 'RETURN'` | `penalty_window` (Returns, discounts, voided penalties) | `dim_friction` (Operational friction and return ratios) | `health_score` | `scores.health_score` |
| `event_ledger.event_date` (SALE / PAYMENT) | `payment_rhythm` (Average and variance of delay days) | `dim_discipline` (Rhythm regularity) | `risk_score`, `trust_score`, `collection_score` | `scores.risk_score`, `scores.trust_score`, `scores.collection_score` |
| `event_ledger.amount` (SALE vs PAYMENT run-sum) | `outstanding_balance` (Receivable exposure accumulation) | `dim_credit` (Receivable pressure and utilization) | `risk_score`, `credit_score` | `scores.outstanding_current`, `scores.risk_score`, `scores.credit_score` |
| `event_ledger.metadata` (Category codes, SKU IDs) | `category_diversity_count` (Cross-selling penetration) | `dim_product` (Concentration and basket size diversity) | `growth_score`, `opportunity_score` | `scores.growth_score`, `scores.opportunity_score` |
| `event_ledger.event_date` | `days_since_last_purchase` (Trading intervals and gap counts) | `dim_stability` (Participation consistency and trading rhythm stability) | `health_score`, `risk_score`, `trust_score`, `relationship_score` | `scores.health_score`, `scores.risk_score`, `scores.trust_score`, `scores.relationship_score`, `last_purchased_at` |
| `customers.business_name` | `customer_name` (Static registration identity) | N/A (Identity Metadata) | N/A (Identity Metadata) | `customer_name` |
| `customers.city` | `city` (Regional node registration) | N/A (Identity Metadata) | N/A (Identity Metadata) | `city` |

---

## 3. Score Composition Logic Reference

* **Health Score**:
  * Formula: `0.40 * dim_activity + 0.35 * dim_friction + 0.25 * dim_stability`
  * Represents: Overall account health.
* **Risk Score**:
  * Formula: `0.40 * (1 - dim_credit) + 0.40 * (1 - dim_discipline) + 0.20 * (1 - dim_stability)`
  * Represents: Combined default and trading risk.
* **Growth Score**:
  * Formula: `0.50 * dim_growth + 0.30 * dim_product + 0.20 * dim_activity`
  * Represents: Upscale trading velocity and demand potential.
* **Trust Score**:
  * Formula: `0.50 * dim_discipline + 0.30 * dim_relationship + 0.20 * dim_stability`
  * Represents: Alignment with payment terms and commercial trust longevity.
* **Opportunity Score**:
  * Formula: `0.50 * (1 - dim_product) + 0.30 * dim_growth + 0.20 * dim_relationship`
  * Represents: Expansion room for basket diversification and upsell capability.
* **Credit Score**:
  * Formula: `0.40 * trust_score + 0.40 * (1 - risk_score) + 0.20 * dim_activity`
  * Represents: Safe limit capacity allocation factor.
* **Collection Score**:
  * Formula: `0.50 * (1 - dim_discipline) + 0.30 * risk_score + 0.20 * dim_activity`
  * Represents: Collection risk urgency.
* **Relationship Score**:
  * Formula: `0.40 * dim_relationship + 0.40 * dim_stability + 0.20 * dim_activity`
  * Represents: Account partnership longevity value.
