import asyncio
import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "../../../.env"))

from fin_terminal.embeddings import LazyEmbeddings
from fin_terminal.vectorstore.factory import create_vectorstore
from stop_loss.retrieval.search import HistoricalRetriever
from stop_loss.settings import TerminalSettings

async def run():
    settings = TerminalSettings()
    embedder = LazyEmbeddings(settings)
    adapter = create_vectorstore(settings)
    print("Pinecone stats:", await adapter.stats())
    
    ret = HistoricalRetriever(embedder, adapter, settings.pinecone_history_namespace)
    query = "How will a cyclone affect the price of tatasteel?"
    hits = await ret.search(query)
    print(f"Hits for '{query}':", len(hits))
    for h in hits:
        print(h)

if __name__ == "__main__":
    asyncio.run(run())
