# OpenAPI Reference Schema

This document provides the OpenAPI specification and standard data contracts for the EconIQ Core API.

---

## 1. OpenAPI Specification Metadata
- **Version:** `3.0.3`
- **Application Title:** `EconIQ Core API`
- **Application Description:** `Stateful Behavioral Intelligence Runtime - Hardened Production Edition`
- **API Version:** `2.0.0`
- **Base Server URL:** `/api/v1`

---

## 2. Global Response Envelope
All API endpoints return a standardized JSON envelope described below:

```json
{
  "success": true,
  "message": "Description of action outcomes",
  "data": {},
  "metadata": {
    "processing_time_ms": 15
  }
}
```

### Response Schema Properties

| Field Name | Data Type | Description |
| :--- | :--- | :--- |
| `success` | `boolean` | Indicates if the requested operation succeeded. |
| `message` | `string` | Human-readable explanation of the request result. |
| `data` | `object / array` | Main payload of the response. Nullable if empty. |
| `metadata` | `object` | Supplementary metrics (e.g., query execution speed, page details). |

---

## 3. Standard HTTP Error Codes

| Status Code | Error Schema Name | Description |
| :--- | :--- | :--- |
| **`400 Bad Request`** | `ValidationError` | Returned when URL queries or POST payloads violate format requirements. |
| **`401 Unauthorized`**| `AuthError` | Authentication header missing or API key is inactive. |
| **`403 Forbidden`**   | `PermissionError` | Authenticated user lacks the necessary privilege permission level. |
| **`404 Not Found`**   | `NotFoundError` | The requested resource (e.g., Customer ID) does not exist in the serving database. |
| **`500 Internal Error`**| `SystemError` | Unhandled runtime exception inside the analytical engine or persistence layer. |

---

## 4. Key Request Data Schemas

### `StandardResponse[T]`
Unified API response structure enclosing payload type `T`.

### `ErrorResponse`
Standard error container formatting.
- `success`: `false` (always)
- `message`: Error category label.
- `detail`: Detailed array of validation constraints or trace details.
