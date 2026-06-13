# Frontend Inventory & API Alignment
- **Current State:** ~90% complete dashboard frontend (sibling folder `Econ-Client`) designed to render merchant profiles, timeline graphs, and risk classifications.
- **Target State:** Frontend calling Econiq Core generalized routes and displaying predictions.
- **Gap Analysis:** UI displays fields like "econiq Grade" or "Receipts" instead of "Econiq Grade" and "Payments".
- **Recommended Actions:** Flatten raw table responses; align REST API DTO properties to match the frontend state names.
- **Priority:** High
- **Risk:** Medium (mismatched property names between frontend and backend)
- **Dependencies:** API contract freezing
- **Expected Outcome:** A seamless user dashboard loading predictive scores in real-time.
