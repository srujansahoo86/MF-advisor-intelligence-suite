import re

# ---------------------------------------------------------------------------
# PII pattern registry — ordered from most-specific to least-specific
# so that narrower patterns are applied before broad catch-alls.
# ---------------------------------------------------------------------------
_PII_PATTERNS = [
    # Emails
    (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b',
     '[EMAIL_REDACTED]'),

    # Indian PAN card  e.g. ABCDE1234F
    (r'\b[A-Z]{5}[0-9]{4}[A-Z]\b',
     '[PAN_REDACTED]'),

    # Folio numbers  e.g. 1234567/89
    (r'\b\d{5,8}/\d{2,4}\b',
     '[FOLIO_REDACTED]'),

    # +91 phone with spaces/dashes  e.g. +91 98765 43210 or +91-9876543210
    (r'\+91[\s\-]?\d{5}[\s\-]?\d{5}',
     '[PHONE_REDACTED]'),

    # Plain 10-digit Indian mobile  e.g. 9123456780
    (r'\b[6-9]\d{9}\b',
     '[PHONE_REDACTED]'),

    # 6-digit Indian PIN codes when preceded by a city/location word
    # e.g. "Hyderabad 500034" or "Mumbai 400001"
    (r'\b[A-Za-z]+\s+\d{6}\b',
     '[LOCATION_REDACTED]'),
]


def redact_pii(text: str) -> str:
    """
    Redacts PII from text before it is processed by LLMs or persisted.

    Patterns covered:
        - Email addresses
        - Indian PAN card numbers  (ABCDE1234F)
        - Folio numbers            (1234567/89)
        - +91-prefixed phone numbers
        - 10-digit Indian mobile numbers
        - City + 6-digit PIN code combinations
    """
    if not text:
        return text

    for pattern, replacement in _PII_PATTERNS:
        text = re.sub(pattern, replacement, text)

    return text
