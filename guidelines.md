# Service guidelines

Error envelope rule: every HTTP error response returns the shared envelope {"error": {"code": str, "message": str, "request_id": str}}. Never return a bare error string.

Logging rule: do not log request bodies at INFO level, because they can contain personal data.

Timeout rule: every outbound HTTP call sets an explicit timeout.
