import hashlib
import math
import os
import re
import threading
import unicodedata
import chromadb
from chromadb.config import Settings
from dotenv import load_dotenv

load_dotenv()

# One lock to serialize all ChromaDB access across threads
_chroma_lock = threading.Lock()
_client_instance = None


def get_chroma_client():
    global _client_instance
    if _client_instance is None:
        _client_instance = chromadb.PersistentClient(
            path="./chroma_store",
            settings=Settings(allow_reset=True),
        )
    return _client_instance


def _local_text_embedding(text: str, dim: int = 768) -> list[float]:
    """Fast, deterministic, normalized local embedding vector (dim=768).

    Operates 100% offline with zero external network calls or rate limits.
    """
    vec = [0.0] * dim
    words = re.findall(r"\w+", text.lower())
    if not words:
        words = ["empty"]
    for pos, word in enumerate(words):
        h1 = int(hashlib.md5(f"{word}_1".encode()).hexdigest(), 16) % dim
        h2 = int(hashlib.sha256(f"{word}_2".encode()).hexdigest(), 16) % dim
        h3 = int(hashlib.sha1(f"{word}_3".encode()).hexdigest(), 16) % dim
        weight = 1.0 / math.sqrt(pos + 1)
        vec[h1] += weight
        vec[h2] += 0.5 * weight
        vec[h3] += 0.25 * weight
    norm = math.sqrt(sum(x * x for x in vec))
    if norm > 0:
        vec = [x / norm for x in vec]
    return vec


class PersonaMemory:

    def __init__(self, persona_name: str):
        self.persona_name = persona_name

        # Normalise unicode -> decompose accents, then encode to ASCII
        sanitised = unicodedata.normalize("NFKD", persona_name)
        sanitised = sanitised.encode("ascii", errors="ignore").decode("ascii")

        sanitised = sanitised.lower()
        sanitised = sanitised.replace(" ", "_")
        # Strip everything ChromaDB won't accept: only [a-zA-Z0-9._-] allowed
        sanitised = re.sub(r"[^a-zA-Z0-9._\-]", "", sanitised)
        sanitised = sanitised.strip("._-")
        if len(sanitised) < 3:
            sanitised = f"p_{abs(hash(persona_name)) % 10**8}"

        self.collection_name = f"persona_{sanitised}"

        with _chroma_lock:
            self.client = get_chroma_client()
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )

        api_key = os.getenv("GEMINI_API_KEY")
        self.embeddings = None
        if api_key:
            try:
                from langchain_google_genai import GoogleGenerativeAIEmbeddings
                self.embeddings = GoogleGenerativeAIEmbeddings(
                    model="models/gemini-embedding-001",
                    google_api_key=api_key,
                    max_retries=0,
                )
            except Exception:
                self.embeddings = None

    def _get_embeddings(self, texts: list[str]) -> list[list[float]]:
        if self.embeddings:
            try:
                return self.embeddings.embed_documents(texts)
            except Exception as exc:
                print(f"[Memory] Gemini embedding failed ({exc}); using local fallback.")
        return [_local_text_embedding(t) for t in texts]

    def _get_query_embedding(self, query: str) -> list[float]:
        if self.embeddings:
            try:
                return self.embeddings.embed_query(query)
            except Exception as exc:
                print(f"[Memory] Gemini query embedding failed ({exc}); using local fallback.")
        return _local_text_embedding(query)

    def store_memories_batch(self, memories: list[str], id_prefix: str):
        """Embed and store all memories in a single batch."""
        vectors = self._get_embeddings(memories)
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
            return []
        query_vector = self._get_query_embedding(query)
        with _chroma_lock:
            results = self.collection.query(
                query_embeddings=[query_vector],
                n_results=min(n_results, count),
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
