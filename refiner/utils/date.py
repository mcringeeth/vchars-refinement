from datetime import datetime


def parse_timestamp(timestamp):
    """Parse a timestamp to a datetime object."""
    if isinstance(timestamp, int):
        return datetime.fromtimestamp(timestamp / 1000.0)
    return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))

def _iso(ts: str | None) -> str:
    """
    Ensure ISO-8601; if already looks ISO, keep, else parse.
    """
    if ts is None:
        return datetime.utcnow().isoformat(timespec="seconds") + "Z"
    if "T" in ts:
        return ts
    # Telegram exports like "2025-05-11 18:45:02"
    return datetime.strptime(ts, "%Y-%m-%d %H:%M:%S").isoformat(timespec="seconds") + "Z"