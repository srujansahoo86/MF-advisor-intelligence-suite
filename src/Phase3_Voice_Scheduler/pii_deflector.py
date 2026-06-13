from src.Phase0_Shared_Foundation.pii import redact_pii
from src.Phase0_Shared_Foundation.config import Config

class PIIDeflector:
    """Scans voice/text transcripts for PII before passing to LLM or persisting."""

    DEFLECTION_MSG = (
        "For security, please don't share personal details here. "
        f"Update your information securely at: {Config.ADVISOR_SECURE_LINK}"
    )

    def check(self, transcript: str) -> tuple[bool, str]:
        """
        Checks if the transcript contains any PII using the Phase 0 redact_pii tool.
        Returns:
            (has_pii: bool, message: str)
        """
        if not transcript:
            return False, ""

        redacted = redact_pii(transcript)
        if redacted != transcript:
            return True, self.DEFLECTION_MSG

        return False, ""
