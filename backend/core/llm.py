import os
from langchain_ollama import ChatOllama
from dotenv import load_dotenv

load_dotenv(".env")
def get_engine():
    return ChatOllama(
        model=os.getenv("ENGINE_MODEL"),
        temperature=0.7,
    )

def get_observer():
    return ChatOllama(
        model=os.getenv("OBSERVER_MODEL"),
        temperature=0.7,
    )

def get_evaluator():

    return ChatOllama(
        model = os.getenv("EVALUATOR_MODEL"),
        temperature = 0.0
    )

if __name__ == "__main__":

    get_engine()
    print("Engine model loaded successfully.")
    get_observer()
    print("Observer model loaded successfully.")