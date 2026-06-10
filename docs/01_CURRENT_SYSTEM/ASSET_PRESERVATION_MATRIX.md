# Asset Preservation & Code Reuse Matrix
- **Current State:** Multiple custom logic segments represent years of domain-specific development.
- **Target State:** Complete documentation and safety guardrails to prevent accidental rewrites of high-value systems.
- **Gap Analysis:** Risks of rewriting functioning backend elements.
- **Recommended Actions:** Audit and preserve the following modules:
  *   **`sync_pipeline.py`** (Business Value: Critical | Replacement Cost: High | Reuse: 95% | Action: Keep & Generalize)
  *   **`engineer.py`** (Business Value: High | Replacement Cost: Medium | Reuse: 100% | Action: Keep)
  *   **`reconstruction.py`** (Business Value: Critical | Replacement Cost: High | Reuse: 100% | Action: Keep)
  *   **`queue_worker.py`** (Business Value: Medium | Replacement Cost: Medium | Reuse: 95% | Action: Keep)
  *   **`auth.py` & `security.py`** (Business Value: High | Replacement Cost: Medium | Reuse: 95% | Action: Keep)
- **Priority:** Critical
- **Risk:** High (developer resource waste)
- **Dependencies:** None
- **Expected Outcome:** Maximize codebase reuse to hit the 2-week deadline.
