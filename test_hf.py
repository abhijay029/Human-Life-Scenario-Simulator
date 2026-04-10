import sys
sys.path.append(".")

from backend.agents.hf_llm import hf_invoke
from langchain_core.messages import SystemMessage, HumanMessage

msgs = [
    SystemMessage(content="You are a helpful assistant."),
    HumanMessage(content="Say hello in one sentence.")
]

print("Testing HuggingFace fallback LLM...")
reply = hf_invoke(msgs)
print(f"Response: {reply}")