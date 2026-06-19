# Frontend Context Reference Guide (Frontend Bible)

This document serves as the single source of truth for the Next.js frontend application structure, routing layout, API consumption contracts, state management policies, and design guidelines.

---

## 1. Platform Summary
**EconIQ** is a **Stateful Commercial Decision Intelligence Platform** that continuously observes customer behavior, learns from outcomes, simulates interventions, and recommends optimal commercial actions.

Unlike static analytics dashboards or generic CRM views, EconIQ provides an interactive credit decision workflow. It links historical raw transactions with real-time ML risk predictions and what-if counterfactual scenario testing.

---

## 2. Capabilities Integrated

1. **Ledger:** Renders historical transactions (sales, payments, returns) in rolling time aggregates.
2. **Intelligence:** Displays the 8 Canonical Scores representing credit risk and health indices.
3. **Alerts:** Flags sudden behavior changes, prompting manual outreach or account status freezes.
4. **Collections:** Logs outreach interactions and tracks payment commitment schedules.
5. **Decisioning:** Logs manual analyst action overrides, ensuring regulatory audit compliance.
6. **Feature Store:** Provides the analytical variables underlying risk factors.
7. **Machine Learning:** Exposes binary risk probabilities and SHAP value factor explanations.
8. **Advisor:** Surfaces prioritized checklist actions with urgency ranks and impact metrics.

---

## 3. Page Catalog

- **Dashboard:** Operational landing page. Displays total exposure KPIs, cash flow distributions, and active system alerts.
- **Customer Dossier:** Longitudinal customer view. Houses graphs (Purchase, Payment, Returns, Outstanding) and transactional activity timelines.
- **Collections Queue:** Filters customer matrices based on payment default priorities.
- **Operations Center:** Control center to inspect system alerts, perform bulk acknowledgments, and review audit logs.
- **Advisor Cockpit:** Cockpit to inspect prioritized recommendations, examine SHAP explainability charts, and test intervention simulations.
- **Boardroom:** Aggregate strategic metrics dashboard.

---

## 4. API Endpoint Dependencies

### Customer Dossier Page Dependencies
To reconstruct the full dossier view, the page queries the following routes:
- **`GET /api/v1/customer/{id}`**: Resolves customer identity, canonical scores, contributions, and trend directions.
- **`GET /api/v1/ml/explanation/{id}`**: Retrieves SHAP value positive and negative contributors.
- **`GET /api/v1/advisor/customer/{id}`**: Resolves prioritized recommendations checklist.
- **`POST /api/v1/ml/simulate`**: Runs counterfactual scenario adjustments.
- **`GET /api/v1/collections/activity?customer_id={id}`**: Loads logged interactions.
- **`GET /api/v1/collections/commitment?customer_id={id}`**: Loads promise agreements.

---

## 5. State Management Policies

EconIQ follows a strict state management architectural pattern:

- **React Query (TanStack Query):** **Mandatory** for all remote data fetching, caching, and state synchronization.
- **Zero Local State Syncing:** Component state (`useState`) must only be used for UI transitions (e.g. toggle active tabs, open details modals).
- **No Mock Fallbacks:** Avoid using local timers or mock delays (`setTimeout`). React Query caches are the single source of truth.
- **Persistent Mutations:** Action submissions (logging calls, creating commitments, override audits) must use React Query mutations (`useMutation`) to write directly to the database. Upon success, mutations must invalidate associated queries (`queryClient.invalidateQueries`) to trigger automatic, reactive refetches.

---

## 6. Design Principles

The visual layout of EconIQ is designed as a **Professional ERP System**, not a speculative crypto dashboard, an analytics playground, or a startup marketing landing page.

- **Theme & Palette:** Curated neutral color palettes (deep slates, clean whites, subtle border lines) with refined indicators (teal/indigo for success, warm amber/crimson for risk). Avoid generic colors.
- **Typography:** Modern Sans-Serif fonts (Outfit, Inter) with readable letter-spacings.
- **Visual Clarity:** Focus on high density of data without clutter, clear layout cards, tabular matrices, and clean, high-performance charts.
