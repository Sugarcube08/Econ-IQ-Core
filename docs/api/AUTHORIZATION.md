# API Authorization & Security

EconIQ employs two distinct authorization mechanisms to secure all API endpoints under `/api/v1`:

---

## 1. Authentication Methods

### 1.1 User Sessions (JSON Web Tokens)
For web interface logins via the Next.js frontend application.
- **Header format:** `Authorization: Bearer <JWT_TOKEN>`
- **Token Issuance:** Obtained via `POST /api/v1/auth/login` (accepts user credentials, supports secure email OTP verification).
- **Expiration:** JWT tokens expire automatically after 24 hours.

### 1.2 Machine-to-Machine (API Keys)
For programmatic automation, third-party ledger integrations, and offline data seeders.
- **Header format:** `X-API-Key: <API_KEY>`
- **Management:** Authorized administrators can provision, inspect, and revoke API keys via `GET/POST/DELETE /api/v1/auth/api-keys`.

---

## 2. Core Permissions
The system enforces Role-Based Access Control (RBAC). The following permissions are defined inside [core/core/permissions.py](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/core/core/permissions.py):

- **`intel:read`:** Read-only access to customer profiles, score matrices, dashboard metrics, and model evaluations.
- **`intel:write`:** Ability to edit user profiles and create security API keys.
- **`ops:write`:** Permission to log outreach actions, payment commitments, and submit override actions on recommended decisions.
- **`admin`:** Full administrative capability (e.g. system upgrades, batch worker restarts).

---

## 3. Middleware Integration
The authorization context is evaluated on every incoming request inside [core/middleware/security.py](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/core/middleware/security.py):
1. **Correlation Tracking:** Injects `X-Correlation-ID` header into logging blocks for request tracing.
2. **Hardening Headers:** Standardizes security headers (`X-Frame-Options`, `Content-Security-Policy`, `Strict-Transport-Security`).
3. **Fail-Closed Strategy:** Any malformed token, unauthorized request, or verification error immediately returns a `401 Unauthorized` or `403 Forbidden` response and records a traceback in the logs.
