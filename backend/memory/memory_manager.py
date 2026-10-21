import hashlib
import chromadb
from chromadb.config import Settings
import os
import threading
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv
import re
import unicodedata

load_dotenv()

# One lock to serialize all ChromaDB access across threads
_chroma_lock = threading.Lock()
_client_instance = None
_embedding_model = None
_embedding_model_lock = threading.Lock()
_embedding_encode_lock = threading.Lock()


def get_embedding_model():
    """Load the local SentenceTransformer once per process."""
    global _embedding_model
    if _embedding_model is None:
        with _embedding_model_lock:
            if _embedding_model is None:
                model_name = os.getenv("SENTENCE_TRANSFORMER_MODEL", "all-MiniLM-L6-v2")
                _embedding_model = SentenceTransformer(model_name)
    return _embedding_model


class SentenceTransformerEmbeddings:
    """Adapter exposing the embedding methods used by PersonaMemory."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        with _embedding_encode_lock:
            vectors = get_embedding_model().encode(
                texts,
                normalize_embeddings=True,
                convert_to_numpy=True,
                show_progress_bar=False,
            )
        return vectors.tolist()

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]

def get_chroma_client():
    global _client_instance
    if _client_instance is None:
        _client_instance = chromadb.PersistentClient(path="./chroma_store", 
                                                     settings = Settings(allow_reset = True))
    return _client_instance

class PersonaMemory:

    def __init__(self, persona_name: str):
        self.persona_name = persona_name

        # Normalise unicode → decompose accents, then encode to ASCII dropping
        # anything that doesn't map (handles curly apostrophes, em-dashes, etc.)
        sanitised = unicodedata.normalize("NFKD", persona_name)
        sanitised = sanitised.encode("ascii", errors="ignore").decode("ascii")

        sanitised = sanitised.lower()
        sanitised = sanitised.replace(" ", "_")
        # Strip everything ChromaDB won't accept: only [a-zA-Z0-9._-] allowed
        sanitised = re.sub(r"[^a-zA-Z0-9._\-]", "", sanitised)
        # ChromaDB requires start and end to be [a-zA-Z0-9]
        sanitised = sanitised.strip("._-")
        # Fallback if name collapsed to fewer than 3 chars
        if len(sanitised) < 3:
            sanitised = f"p_{abs(hash(persona_name)) % 10**8}"

        # Keep SentenceTransformer vectors separate from existing Gemini
        # vectors, whose dimensions are incompatible with this model.
        model_name = os.getenv("SENTENCE_TRANSFORMER_MODEL", "all-MiniLM-L6-v2")
        model_suffix = hashlib.sha1(model_name.encode("utf-8")).hexdigest()[:10]
        self.collection_name = f"persona_{sanitised[:41]}_st_{model_suffix}"

        with _chroma_lock:
            self.client = get_chroma_client()
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}
            )

        self.embeddings = SentenceTransformerEmbeddings()

    def store_memories_batch(self, memories: list[str], id_prefix: str):
        """Embed and store all memories in one local model call."""
        vectors = self.embeddings.embed_documents(memories)
        ids = [f"{id_prefix}_{i}" for i in range(len(memories))]
        with _chroma_lock:
            self.collection.upsert(
                ids=ids,
                embeddings=vectors,
                documents=memories,
            )
        print(f"[Memory] Stored {len(memories)} memories for {self.persona_name} in one batch.")

    def recall(self, query: str, n_results: int = 2) -> list[str]:
        """Retrieve the most relevant memories for a given situation."""
        with _chroma_lock:
            count = self.collection.count()
        if count == 0:
            return []   # nothing indexed yet — skip the query entirely
        query_vector = self.embeddings.embed_query(query)
        with _chroma_lock:
            results = self.collection.query(
                query_embeddings=[query_vector],
                n_results=min(n_results, count)  # can't request more results than documents
            )
        return results["documents"][0] if results["documents"] else []

    def store_persona_facts(self, persona):
        """Load all persona traits into memory in one batched embedding call."""
        facts = [
            f"{persona.name} is {persona.age} years old and works as a {persona.occupation}.",
            f"{persona.name}'s personality: {', '.join(persona.personality_traits)}.",
            f"{persona.name} deeply values: {', '.join(persona.values)}.",
            f"{persona.name} gets triggered by: {', '.join(persona.emotional_triggers)}.",
            f"{persona.name}'s background: {persona.background}",
            f"{persona.name}'s goals here: {', '.join(persona.goals)}.",
            f"{persona.name} communicates in a {persona.communication_style} style.",
        ]
        self.store_memories_batch(facts, id_prefix=f"{self.persona_name}_fact")

    def count(self):
        with _chroma_lock:
            return self.collection.count()

    # def __del__(self):
    #     with _chroma_lock:
    #         self.client = get_chroma_client()
    #         self.client.reset()
