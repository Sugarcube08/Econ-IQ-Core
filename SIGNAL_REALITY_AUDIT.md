# SIGNAL REALITY AUDIT (V1)

This audit evaluates the reality of all ingested signals. It classifies them according to actual data availability in the Postgres/Ledger schema and defines the boundary between active scoring and future roadmap concepts.

---

## 1. Reality Classifications

Each signal defined in the contract is assigned one of the following taxonomies:
* **Actually Exists**: Data is fully populated and verified in the database schema.
* **Partially Exists**: Data exists but relies on defaults, config placeholders, or limited parameters.
* **Derived**: Computed dynamically at runtime from transaction patterns.
* **Future Only**: No data is currently stored; placeholder/unsupported.
* **Unsupported**: Dead or legacy concept.

---

## 2. Signal Availability & Verification Matrix

| Signal ID | Signal Name | Reality Status | Verification Evidence / Sources | Active Scoring Usage |
| :--- | :--- | :--- | :--- | :--- |
| **PUR_REC** | Purchase Recency | **Actually Exists** | `event_ledger.event_date` (SALE) | **Yes** (Active) |
| **PUR_FRQ** | Purchase Frequency | **Actually Exists** | `event_ledger.event_date` (SALE) | **Yes** (Active) |
| **PUR_VOL** | Order Volatility | **Derived** | Computed from `event_ledger.amount` stddev | **Yes** (Active) |
| **PUR_VAL_MDN**| Median Order Value | **Derived** | Computed from `event_ledger.amount` median | **Yes** (Active) |
| **PAY_DPD_AVG** | Average Days Past Due | **Actually Exists** | `event_ledger.metadata` (due vs settled date)| **Yes** (Active) |
| **PAY_DPD_MAX** | Maximum Days Past Due | **Actually Exists** | `event_ledger.metadata` (due vs settled date)| **Yes** (Active) |
| **PAY_CR_UTIL** | Credit Utilization | **Partially Exists** | Derived from outstanding vs limit config | **Yes** (Active) |
| **PAY_FRG_IDX** | Payment Fragmentation | **Derived** | Count of PAYMENT events per SALE event | **Yes** (Active) |
| **OPR_RET_VOL** | Return Value Ratio | **Actually Exists** | `event_ledger.event_type` (RETURN) | **Yes** (Active) |
| **OPR_RET_FLT** | Customer Fault Return Rate| **Derived** | Extracted from `event_ledger.metadata` keys | **Yes** (Active) |
| **OPR_ORD_CAN** | Order Cancellation Rate | **Derived** | Derived from `event_ledger.is_voided` flags | **Yes** (Active) |
| **NET_LOY_AGE** | Relationship Longevity | **Derived** | `current_date` minus first `event_ledger` date | **Yes** (Active) |
| **NET_PEER_RNK** | Peer Performance Rank | **Future Only** | Peer network dataset not populated | **No** (Moved) |
| **ENG_POR_LGN** | Portal Login Frequency | **Future Only** | Telemetry logs not available | **No** (Moved) |
| **ENG_CRT_ABD** | Cart Abandonment Rate | **Future Only** | E-commerce web telemetry not integrated | **No** (Moved) |

---

## 3. Active Scoring Adjustments

The following signals do not have database columns or historical records. To avoid contaminating active scoring with zeroed/empty values, they are isolated and moved to the future roadmap:

### Isolated Signals (Moved to FUTURE_SIGNALS)
1. **`ENG_POR_LGN` (Portal Login Frequency)**: Excluded from active opportunity and health scoring. Fallback coefficient is set to 1.0 (neutral) in the calculations.
2. **`ENG_CRT_ABD` (Cart Abandonment Rate)**: Excluded from opportunity calculations. Formulations shifted to use returns and payment behaviors instead.
3. **`NET_PEER_RNK` (Peer Performance Rank)**: Excluded from relationship and stability indexing.

> [!IMPORTANT]
> All active scoring calculations in `core/intelligence/meta/scores.py` and `core/intelligence/dimensions/*` have been verified. No division-by-zero errors or invalid weight dependencies exist on these isolated signals.
