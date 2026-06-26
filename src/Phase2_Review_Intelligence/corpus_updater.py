from datetime import date

from langchain_core.documents import Document
from langchain_chroma import Chroma

from src.Phase0_Shared_Foundation.config import Config
from src.Phase0_Shared_Foundation.schemas import FeeExplainer


class CorpusUpdater:
    """
    Injects a FeeExplainer into the Phase 1 ChromaDB vectorstore so the
    RAGEngine can retrieve it immediately in subsequent FAQ queries.

    IMPORTANT: Uses the same FastEmbedEmbeddings(Config.EMBEDDING_MODEL) as
    Phase 1's RAGEngine to ensure the injected document is retrievable via
    semantic search.
    """

    def __init__(self):
        from langchain_community.embeddings import FastEmbedEmbeddings
        self.embeddings = FastEmbedEmbeddings(model_name=Config.EMBEDDING_MODEL)
        self.vectorstore = Chroma(
            persist_directory=Config.CHROMA_DB_DIR,
            embedding_function=self.embeddings,
        )

    def add_fee_explainer(self, explainer: FeeExplainer) -> None:
        """
        Converts a FeeExplainer into a LangChain Document and adds it
        to the shared ChromaDB instance.

        Document content:  all 6 bullets joined into a readable block.
        Metadata:
            source      → "fee_explainer_generated"   (retrievable by Phase 1)
            last_checked → e.g. "Last checked: 2026-06-09"
            date        → ISO date string of today
        Args:
            explainer: A validated FeeExplainer pydantic object.
        """
        # Format bullets into a readable block
        bullets_text = "\n".join(f"• {b}" for b in explainer.bullets)
        sources_text = "\n".join(explainer.source_links)

        content = (
            "Fee Explainer — Mutual Fund Charges\n"
            "=====================================\n"
            f"{bullets_text}\n\n"
            f"Official Sources:\n{sources_text}\n\n"
            f"{explainer.last_checked}"
        )

        doc = Document(
            page_content=content,
            metadata={
                "source":       "fee_explainer_generated",
                "last_checked": explainer.last_checked,
                "date":         date.today().isoformat(),
            },
        )

        self.vectorstore.add_documents([doc])
        # Note: Chroma 0.4+ auto-persists on add_documents; no manual persist() needed.

        print(
            f"[CorpusUpdater] Fee Explainer injected into ChromaDB "
            f"({Config.CHROMA_DB_DIR}). "
            f"Phase 1 RAGEngine will now retrieve it."
        )

    def get_injected_count(self) -> int:
        """Returns the number of fee_explainer documents currently in the store."""
        try:
            coll = self.vectorstore._collection
            res = coll.get(where={"source": "fee_explainer_generated"})
            return len(res.get("ids", []))
        except Exception as e:
            print(f"[CorpusUpdater] get_injected_count check failed: {e}")
            return 0

