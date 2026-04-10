"""
main.py — HumanSimulator FastAPI Application
============================================

Run with:
    uvicorn main:app --reload --port 8000

Interactive docs:
    http://localhost:8000/docs
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.api.routes import router

app = FastAPI(
    title="Human Life Scenario Simulator",
    description=(
        "A Multi-Agent Simulation framework that clones real-world personas "
        "using LLMs to stress-test real-life scenarios before they occur."
    ),
    version="0.2.0",
)

# Allow the Next.js frontend (default port 3000) and any local dev origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
