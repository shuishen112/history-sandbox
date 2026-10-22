"""REST server for the Kamer sandbox. No playable persona."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from kamer.config import SimConfig
from kamer.sim.engine import Simulation

sim = Simulation(SimConfig(n_agents=25, n_days=7))
app = FastAPI(title="Kamer sandbox", version="0.2.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class InterviewIn(BaseModel):
    question: str


class InnerVoiceIn(BaseModel):
    text: str


class EditObjectIn(BaseModel):
    state: str
    payload: dict[str, Any] = {}


class EventIn(BaseModel):
    type: str
    payload: dict[str, Any] = {}


class StepIn(BaseModel):
    n: int = 1


@app.get("/state")
def state() -> dict:
    return sim.public_state()


@app.get("/agents")
def agents() -> list[dict]:
    return sim.public_state()["agents"]


@app.get("/agents/{agent_id}")
def inspect(agent_id: str) -> dict:
    if agent_id not in sim.agents:
        raise HTTPException(404, "unknown agent")
    return sim.inspect(agent_id)


@app.post("/agents/{agent_id}/interview")
def interview(agent_id: str, body: InterviewIn) -> dict:
    if agent_id not in sim.agents:
        raise HTTPException(404, "unknown agent")
    return {"agent": agent_id, "question": body.question, "answer": sim.interview(agent_id, body.question)}


@app.post("/agents/{agent_id}/inner_voice")
def inner_voice(agent_id: str, body: InnerVoiceIn) -> dict:
    if agent_id not in sim.agents:
        raise HTTPException(404, "unknown agent")
    sim.inner_voice(agent_id, body.text)
    return {"ok": True}


@app.post("/objects/{obj_id}")
def edit_object(obj_id: str, body: EditObjectIn) -> dict:
    sim.edit_object(obj_id, body.state, **body.payload)
    return {"ok": True}


@app.post("/events")
def inject(body: EventIn) -> dict:
    sim.inject_event(body.type, **body.payload)
    return {"ok": True}


@app.get("/newspaper")
def newspaper() -> list[dict]:
    return sim.public_state()["newspaper"]


@app.post("/step")
def step(body: StepIn | None = None) -> dict:
    n = body.n if body else 1
    last = {}
    for _ in range(max(1, n)):
        last = sim.step()
    return last


@app.post("/pause")
def pause() -> dict:
    sim.paused = True
    return {"paused": True}


@app.post("/resume")
def resume() -> dict:
    sim.paused = False
    return {"paused": False}


@app.post("/possess")
def possess() -> None:
    raise HTTPException(403, "ethics: no playable persona")


@app.post("/seed/sloop")
@app.post("/seed/leak")
def seed_leak() -> dict:
    aid = sim.seed_leak()
    return {"agent": aid}


try:
    front = Path(__file__).resolve().parents[2] / "frontend"
    if front.is_dir():
        app.mount("/", StaticFiles(directory=str(front), html=True), name="frontend")
except Exception:
    pass
