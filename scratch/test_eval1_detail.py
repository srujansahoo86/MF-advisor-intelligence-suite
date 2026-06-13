import os
import sys
import traceback
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
dotenv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
load_dotenv(dotenv_path)

def log(msg):
    sys.__stdout__.write(f"[DEBUG] {msg}\n")
    sys.__stdout__.flush()

try:
    log("Importing RAGEngine...")
    from src.Phase1_FAQ_Chatbot.rag_engine import RAGEngine
    log("Instantiating RAGEngine...")
    rag = RAGEngine()
    log("RAGEngine instantiated successfully!")
    
    question = "What is the exit load for Parag Parikh Liquid Fund?"
    log(f"Test query: '{question}'")
    
    # 1. Guardrails check
    log("Running Guardrails.check_query...")
    from src.Phase0_Shared_Foundation.guardrails import Guardrails
    is_safe, refusal_msg = Guardrails.check_query(question)
    log(f"Guardrails result: is_safe={is_safe}")
    
    # 2. Catalog check
    log("Running _is_catalog_query...")
    is_cat = rag._is_catalog_query(question)
    log(f"Catalog query result: {is_cat}")
    
    # 3. Ambiguity check
    log("Running _check_ambiguity...")
    clarif = rag._check_ambiguity(question)
    log(f"Ambiguity check result: {clarif}")
    
    # 4. Retrieve context
    log("Running _retrieve_context...")
    docs = rag._retrieve_context(question, k=10)
    log(f"Retrieved {len(docs)} documents.")
    for i, d in enumerate(docs):
        log(f"  Doc {i}: source={d.metadata.get('source')} content_prefix='{d.page_content[:60]}'")
        
    context = "\n\n".join([f"Source: {d.metadata.get('source', 'Unknown')}\n{d.page_content}" for d in docs])
    
    # 5. Invoke LLM
    log("Preparing LLM prompt...")
    qa_prompt = f"Answer the question using the context:\nContext:\n{context[:1000]}\nQuestion: {question}\nAnswer:"
    
    log(f"Invoking ChatGroq with model '{rag.llm.model_name}'...")
    log(f"API Key in llm instance: {rag.llm.groq_api_key.get_secret_value()[:10] if hasattr(rag.llm.groq_api_key, 'get_secret_value') else 'Unknown'}")
    
    # Let's do invoke and log before/after
    log("Calling llm.invoke()...")
    res = rag.llm.invoke(qa_prompt)
    log("llm.invoke() returned successfully!")
    log(f"Response content: {res.content.strip()[:100]}...")

except BaseException as e:
    log(f"CRASH OCCURRED: {type(e)} - {str(e)}")
    traceback.print_exc(file=sys.__stdout__)
    sys.__stdout__.write("\n[CRASH] Traceback printed.\n")
    sys.__stdout__.flush()
    sys.exit(1)
