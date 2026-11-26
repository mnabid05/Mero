"""Assign entire opening families to one side of a deterministic split."""
import hashlib

def validation_openings(names, seed):
    unique = set(names)
    if len(unique) < 2:
        raise ValueError("need at least two distinct opening groups")
    def key(name):
        return hashlib.sha256(f"{seed}|{name}".encode()).digest()
    return set(sorted(unique, key=key)[:max(1, len(unique) // 5)])
