from datetime import date, datetime


def normalize_temporal_to_date(value) -> date:
    """Consistently normalizes date/datetime/string values to pure datetime.date objects."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return datetime.strptime(value[:10], "%Y-%m-%d").date()
        except ValueError:
            pass
    raise TypeError(f"Unsupported temporal type: {type(value)}")

def normalize_temporal_to_str(value) -> str:
    """Consistently normalizes date/datetime values to YYYY-MM-DD string."""
    if value is None:
        return ""
    if isinstance(value, (datetime, date)):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, str):
        return value[:10]
    return str(value)
