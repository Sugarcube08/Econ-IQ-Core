# Commercial Intelligence Core Functions
- **Current State:** Double-entry ledger reconstruction and rolling trade statistics.
- **Target State:** Immutable ledger timeline math exposed as core platform utilities.
- **Gap Analysis:** Ledger rules are scattered across ingestion and recomputation modules.
- **Recommended Actions:** Consolidate ledger transaction calculations inside [ledger.py](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/ref/app/ledger/ledger.py).
- **Priority:** High
- **Risk:** Low
- **Dependencies:** event_ledger schema
- **Expected Outcome:** Invariant financial baseline calculator.
