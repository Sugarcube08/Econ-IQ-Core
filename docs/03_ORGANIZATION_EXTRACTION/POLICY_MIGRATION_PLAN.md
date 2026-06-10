# Policy Migration Plan
- **Current State:** Constants are loaded from `settings.py` or hardcoded in python files.
- **Target State:** Configuration values fetched from database-backed policy contexts.
- **Gap Analysis:** Dynamic settings are not supported.
- **Recommended Actions:** Create the configuration schemas; migrate local settings properties to database policies.
- **Priority:** High
- **Risk:** Low
- **Dependencies:** Configuration model
- **Expected Outcome:** Configurable platform.
