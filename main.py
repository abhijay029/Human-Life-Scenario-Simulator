<<<<<<< HEAD
=======
"""
main.py — HumanSimulator FastAPI Application
============================================

Run with:
    uvicorn main:app --reload --port 8000

Interactive docs:
    http://localhost:8000/docs
"""

>>>>>>> 8c6c095954759458197faed706f7478cb7d9f0df
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.api.routes import router

app = FastAPI(
    title="Human Life Scenario Simulator",
<<<<<<< HEAD
    version="0.3.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
=======
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
>>>>>>> 8c6c095954759458197faed706f7478cb7d9f0df
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

<<<<<<< HEAD
app.include_router(router)
=======
app.include_router(router)
>>>>>>> 8c6c095954759458197faed706f7478cb7d9f0df
