import os
import shutil
import yaml
from os.path import join as pjoin
from tqdm import tqdm

os.environ['HAYSTACK_TELEMETRY_ENABLED'] = 'False'

from haystack import Document
from haystack_integrations.document_stores.qdrant import QdrantDocumentStore
from haystack_integrations.components.embedders.fastembed import FastembedDocumentEmbedder

root = '.'
data_folder = 'data'
dialogue_folder = 'dialogues'
config_file = 'config.yaml'
embed_dim = 384
vector_store_name = 'QDRANT_VECTOR_DATABASE'
vector_store_path = pjoin(root, vector_store_name)
embedding_model = 'BAAI/bge-small-en-v1.5'

MAX_DOCS_PER_HERO = 50

def load_all_dialogues(superhero_dialogue_path, dialogues_joiner, superhero):
    dialogues = []
    movies_as_meta_data = []
    if not os.path.exists(superhero_dialogue_path):
        return dialogues, movies_as_meta_data

    movie_files = sorted([f for f in os.listdir(superhero_dialogue_path) if f.endswith('.txt')])
    for movie in movie_files:
        movie_path = pjoin(superhero_dialogue_path, movie)
        with open(movie_path, 'r', encoding='utf-8', errors='ignore') as f:
            data = f.read()

        chunks = data.split(dialogues_joiner)
        for chunk in chunks:
            chunk = chunk.strip()
            if 30 <= len(chunk):
                clean_chunk = chunk[:400].strip()
                dialogues.append(clean_chunk)
                movies_as_meta_data.append(movie[:-4])

    if len(dialogues) > MAX_DOCS_PER_HERO:
        step = len(dialogues) / MAX_DOCS_PER_HERO
        selected_indices = [int(i * step) for i in range(MAX_DOCS_PER_HERO)]
        dialogues = [dialogues[i] for i in selected_indices]
        movies_as_meta_data = [movies_as_meta_data[i] for i in selected_indices]

    return dialogues, movies_as_meta_data

def main():
    with open(pjoin(root, config_file), 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    dialogues_joiner = config.get('DIALOGUES_JOINER', "\n|_/-|_/-|_/-|_/-|_/-|_/-|_/-|_/-|_/-|_/-|\n\n")
    list_of_superheroes = config['LIST_OF_SUPERHEROES']

    print("Initializing FastembedDocumentEmbedder...")
    document_embedder = FastembedDocumentEmbedder(model=embedding_model, batch_size=16)
    document_embedder.warm_up()

    # Clean existing vector store directory
    if os.path.exists(vector_store_path):
        shutil.rmtree(vector_store_path, ignore_errors=True)
    os.makedirs(vector_store_path, exist_ok=True)

    total_indexed = 0
    for superhero in tqdm(list_of_superheroes, desc="Indexing Superheroes"):
        superhero_dialogue_path = pjoin(root, data_folder, dialogue_folder, superhero)
        dialogues, movies_meta = load_all_dialogues(superhero_dialogue_path, dialogues_joiner, superhero)

        if not dialogues:
            print(f"Skipping {superhero}: No dialogues found.")
            continue

        documents = [
            Document(content=d, meta={'name': superhero, 'movie': m})
            for d, m in zip(dialogues, movies_meta)
        ]

        # Embed documents
        docs_with_embeddings = document_embedder.run(documents)["documents"]

        # Write to Qdrant collection for this superhero
        document_store = QdrantDocumentStore(
            path=vector_store_path,
            index=superhero,
            embedding_dim=embed_dim,
            recreate_index=True,
            return_embedding=True,
        )
        document_store.write_documents(docs_with_embeddings)
        total_indexed += len(docs_with_embeddings)
        
        # Explicitly close local qdrant client to release OS file locks
        if hasattr(document_store, '_client') and document_store._client:
            document_store._client.close()
        del document_store

    print(f"\nSUCCESS: All {len(list_of_superheroes)} superheroes successfully indexed into Qdrant! Total documents: {total_indexed}")

if __name__ == '__main__':
    main()
