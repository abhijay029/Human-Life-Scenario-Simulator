import chromadb
from chromadb.config import Settings

client = chromadb.PersistentClient(path = "./chroma_store", settings = Settings(allow_reset = True))
print(client.reset())