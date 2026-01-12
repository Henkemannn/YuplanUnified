from __future__ import annotations

def canonicalize_identifier(identifier: str | None) -> str:
    """Return a canonical identifier for user lookup/storage.

    Rules:
    - strip surrounding whitespace
    - lowercase
    - if contains '@': split local and domain; punycode-encode domain via IDNA
    - if no '@': just lowercase the value
    """
    if not identifier:
        return ""
    s = str(identifier).strip().lower()
    if "@" not in s:
        return s
    local, domain = s.split("@", 1)
    try:
        # Encode domain using IDNA (punycode)
        domain_ascii = domain.encode("idna").decode("ascii")
    except Exception:
        domain_ascii = domain
    return f"{local}@{domain_ascii}"
