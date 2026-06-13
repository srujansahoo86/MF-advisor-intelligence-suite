import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.Phase1_FAQ_Chatbot.rag_engine import RAGEngine

engine = RAGEngine()
q = 'What is the minimum SIP amount for Parag Parikh Flexi Cap Fund?'
docs = engine._retrieve_context(q, k=10)
target = docs[6] # [7] is index 6
print("--- FULL CHUNK 7 CONTENT ---")
print(target.page_content)
