import sys, io, os
# Force UTF-8 stdout
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.Phase1_FAQ_Chatbot.rag_engine import RAGEngine
from langchain_groq import ChatGroq
from src.Phase0_Shared_Foundation.config import Config
from src.Phase6_Evals.eval1_rag import JUDGE_PROMPT_TEMPLATE

engine = RAGEngine()
q = 'What is the exit load for Parag Parikh Liquid Fund?'
docs = engine._retrieve_context(q, k=3)
context = '\n\n'.join([f"Source: {d.metadata.get('source')}\n{d.page_content}" for d in docs])
ans = engine.answer_query(q)

judge_llm = ChatGroq(model_name=Config.LLM_MODEL, temperature=0.0)
prompt = JUDGE_PROMPT_TEMPLATE.format(question=q, context=context[:3000], answer=ans.text)
raw_judge = judge_llm.invoke(prompt).content.strip()

print('--- RETRIEVED CONTEXT ---')
print(context)
print('\n--- ANSWER ---')
print(ans.text)
print('\n--- JUDGE RESPONSE ---')
print(raw_judge)
