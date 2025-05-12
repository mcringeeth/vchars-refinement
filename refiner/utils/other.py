def _to_int(val: str | int | None) -> int | None:
    try:
        return int(val) if val is not None else None
    except ValueError:
        return None