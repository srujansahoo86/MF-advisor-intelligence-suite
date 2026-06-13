import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.Phase1_FAQ_Chatbot.rag_engine import RAGEngine

engine = RAGEngine()
q = 'What is the minimum SIP amount for Parag Parikh Flexi Cap Fund?'
docs = engine._retrieve_context(q, k=10)
print('--- RETRIEVED CONTEXT ---')
for idx, d in enumerate(docs):
    print(f"\n[{idx+1}] Source: {d.metadata.get('source')} | Context: {d.page_content[:150]}...")
    
ans = engine.answer_query(q)
print('\n--- ANSWER ---')
print(ans.text)
print(f"Citations: {ans.citation_links}")
