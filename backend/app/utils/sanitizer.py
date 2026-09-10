from typing import Any


def sanitize_null_bytes(val: Any) -> Any:
    """
    Recursively removes 0x00 null bytes from strings, dictionaries, lists, and nested structures.
    Prevents PostgreSQL asyncpg CharacterNotInRepertoireError: invalid byte sequence for encoding UTF8: 0x00.
    """
    if val is None:
        return None
    if isinstance(val, str):
        return val.replace("\x00", "")
    if isinstance(val, dict):
        return {
            (k.replace("\x00", "") if isinstance(k, str) else k): sanitize_null_bytes(v)
            for k, v in val.items()
        }
    if isinstance(val, list):
        return [sanitize_null_bytes(x) for x in val]
    if isinstance(val, tuple):
        return tuple(sanitize_null_bytes(x) for x in val)
    if isinstance(val, set):
        return {sanitize_null_bytes(x) for x in val}
    return val
