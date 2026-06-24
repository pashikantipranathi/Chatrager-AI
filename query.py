import os
from pathlib import Path
from os.path import join as pjoin
from typing import Dict, Any, Tuple, List, Optional
import yaml

os.environ['HAYSTACK_TELEMETRY_ENABLED'] = 'False'

from haystack_integrations.components.retrievers.qdrant import QdrantEmbeddingRetriever
from haystack_integrations.components.embedders.fastembed import FastembedTextEmbedder

from utils import get_superhero_names, load_document_store, build_prompt, build_rag_pipeline, GeminiGenerator

root = str(Path(__file__).resolve().parent)
config_file = 'config.yaml'
embed_dim = 384
vector_store_name = 'QDRANT_VECTOR_DATABASE'
vector_store_path = pjoin(root, vector_store_name)
embedding_model = 'BAAI/bge-small-en-v1.5'
config_path = pjoin(root, config_file)
local_env_path = pjoin(root, ".env")


def get_local_gemini_key() -> Optional[str]:
    """Read the API key from the process environment or this local ignored .env file."""
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if key:
        return key
    try:
        with open(local_env_path, "r", encoding="utf-8") as env_file:
            for line in env_file:
                if line.strip().startswith("GEMINI_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'") or None
    except FileNotFoundError:
        pass
    return None


def get_embedder() -> FastembedTextEmbedder:
    """Create a fresh Haystack component for each pipeline instance."""
    embedder = FastembedTextEmbedder(model=embedding_model)
    embedder.warm_up()
    return embedder


def get_response(
    question: str,
    superhero: str,
    api_key: Optional[str] = None,
    model_name: Optional[str] = None,
    top_k: int = 4,
    conversation_context: Optional[str] = None
) -> Tuple[str, List[Any]]:
    """
    Executes the Haystack RAG pipeline to answer the user query as the selected superhero.
    Returns a tuple of (reply_text, retrieved_documents).
    """
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    active_api_key = api_key or get_local_gemini_key()
    if not active_api_key:
        raise ValueError("Gemini API key is missing. Set GEMINI_API_KEY or save it from Settings.")

    active_model = model_name or config.get("GEMINI_DEFAULT_MODEL", "gemini-3.8-flash")
    superhero_names = get_superhero_names(superhero, config_path)

    document_store = None
    try:
        embedder = get_embedder()
        document_store = load_document_store(vector_store_path, superhero, embed_dim)
        retriever = QdrantEmbeddingRetriever(document_store=document_store, top_k=top_k)
        prompt_builder = build_prompt()
        generator = GeminiGenerator(api_key=active_api_key, model=active_model)
        rag = build_rag_pipeline(embedder, retriever, prompt_builder, generator)

        pipeline_input = {
            "embedder": {"text": question},
            "prompt": {
                "query": question,
                "superhero_name": superhero,
                "superhero_names": superhero_names,
                "conversation_context": conversation_context or "No earlier turns.",
            },
        }
        result = rag.run(pipeline_input, include_outputs_from=["retriever", "llm"])
        response = result.get('llm', {}).get('replies', [""])[0]
        retrieved_docs = result.get('retriever', {}).get('documents', [])
        return response, retrieved_docs
    finally:
        # Cleanly close local qdrant client to release locks
        if document_store and hasattr(document_store, '_client') and document_store._client:
            document_store._client.close()

if __name__ == '__main__':
    test_hero = "Batman"
    test_q = "What is your main weapon?"
    print(f"Testing RAG response for {test_hero}: '{test_q}'")
    reply, docs = get_response(test_q, test_hero)
    print(f"\n[{test_hero}]:\n{reply}")
    print(f"\nRetrieved {len(docs)} documents.")
