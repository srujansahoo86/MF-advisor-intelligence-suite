import re

class Guardrails:
    """Centralized safety and refusal logic."""
    AMFI_EDUCATIONAL_LINK = "https://www.amfiindia.com/investor-corner"
    
    @staticmethod
    def check_query(query: str) -> tuple[bool, str]:
        """
        Checks a user query against safety guardrails.
        Returns: (is_safe, refusal_message)
        """
        query_lower = query.lower()
        
        # Guardrail 1: Refuse investment advice
        advice_patterns = [
            r'should i invest', r'which (fund|mutual fund) is best', 
            r'recommend a (fund|portfolio)', r'should i buy', r'buy or sell',
            r'is it good to invest', r'investment advice', r'give me advice',
            r'advise me', r'recommendation'
        ]
        for pattern in advice_patterns:
            if re.search(pattern, query_lower):
                return False, f"I cannot provide personalized investment advice. Please consult a registered advisor or visit AMFI for educational resources: {Guardrails.AMFI_EDUCATIONAL_LINK}"
                
        # Guardrail 2: No performance claims / guarantees
        performance_patterns = [
            r'guaranteed return', r'double my money', r'highest return',
            r'sure shot', r'will i make profit', r'safe investment'
        ]
        for pattern in performance_patterns:
            if re.search(pattern, query_lower):
                return False, "I cannot make performance claims or guarantee returns. Mutual fund investments are subject to market risks."
                
        # Safe to proceed
        return True, ""
