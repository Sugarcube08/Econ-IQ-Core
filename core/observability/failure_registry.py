import threading
from loguru import logger

class FailureRegistry:
    _lock = threading.Lock()
    # key -> { "count": int, "severity": str, "last_message": str, "active": bool }
    _failures = {}

    @classmethod
    def record(cls, key: str, message: str, severity: str = "ERROR", extra: dict = None) -> None:
        """
        Records a failure occurrence. Logs only on:
        - First occurrence (Transition to active)
        - Severity escalation
        - Threshold breach (Count = 50, or multiples of 50 after)
        """
        with cls._lock:
            if key not in cls._failures:
                cls._failures[key] = {
                    "count": 0,
                    "severity": severity,
                    "last_message": message,
                    "active": False,
                }
            
            f = cls._failures[key]
            f["count"] += 1
            f["last_message"] = message
            
            should_log = False
            log_message = ""
            
            # 1. First occurrence / activation
            if not f["active"]:
                f["active"] = True
                f["severity"] = severity
                should_log = True
                log_message = f"FAILURE | {key} | Detected: {message}"
            else:
                # 2. Severity escalation check
                severity_map = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40, "CRITICAL": 50}
                old_level = severity_map.get(f["severity"].upper(), 40)
                new_level = severity_map.get(severity.upper(), 40)
                if new_level > old_level:
                    f["severity"] = severity
                    should_log = True
                    log_message = f"FAILURE | {key} | Escalated to {severity}: {message}"
                # 3. Threshold breach check (Count = 50, 100, 150...)
                elif f["count"] == 50 or (f["count"] > 50 and f["count"] % 50 == 0):
                    should_log = True
                    log_message = f"FAILURE | {key} | Count = {f['count']} | Last error: {message}"

            if should_log:
                log_func = getattr(logger, f["severity"].lower(), logger.error)
                log_func(log_message, extra=extra)

    @classmethod
    def recover(cls, key: str, message: str = "Recovered", extra: dict = None) -> None:
        """
        Marks a failure as recovered. Logs the recovery event if it was previously active.
        """
        with cls._lock:
            if key in cls._failures:
                f = cls._failures[key]
                if f["active"]:
                    f["active"] = False
                    f["count"] = 0
                    logger.info(f"FAILURE | {key} | Recovered: {message}", extra=extra)
