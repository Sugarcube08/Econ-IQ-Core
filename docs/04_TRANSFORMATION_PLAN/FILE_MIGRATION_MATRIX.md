# File Migration Matrix
- **Current State:** Files use VGIS names.
- **Target State:** Files renamed and moved to generic folders.
- **Gap Analysis:** Filenames reflect target client.
- **Recommended Actions:** Move and rename files as follows:
  *   `api/customers.py` $ightarrow$ Aligned DTOs
  *   `services/sync_pipeline.py` $ightarrow$ Generalized table targets
- **Priority:** High
- **Risk:** Low
- **Dependencies:** Codebase Inventory
- **Expected Outcome:** Clean codebase layout.
