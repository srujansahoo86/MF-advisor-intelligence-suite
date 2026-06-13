from .booking_agent import BookingAgent, AgentResponse

class VoiceAdapter:
    """Validates, normalises, and forwards user speech/text input to the BookingAgent."""

    def __init__(self, db_path: str = None):
        self.agent = BookingAgent(db_path)

    def process(self, transcript: str) -> AgentResponse:
        """
        Validates the transcript input, truncates it to 500 chars max,
        and delegates to the BookingAgent handler.
        """
        if not transcript or not transcript.strip():
            return AgentResponse(
                message="I couldn't hear you clearly. Please say or type your request."
            )

        # Normalise whitespace and enforce maximum character length of 500
        clean_transcript = " ".join(transcript.split())
        if len(clean_transcript) > 500:
            clean_transcript = clean_transcript[:500]

        return self.agent.handle(clean_transcript)
