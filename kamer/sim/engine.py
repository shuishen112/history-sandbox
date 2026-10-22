"""Simulation engine: Algorithm 1 + researcher interventions. No playable persona."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from maroon.agents.llm import make_backend

from kamer.agents.agent import Agent
from kamer.agents.role import stratum
from kamer.agents.rumour import RumourNetwork
from kamer.config import ALLOW_POSSESS, SITTING_CLOSE_HOUR, SITTING_OPEN_HOUR, SITTING_WEEKDAYS, SimConfig
from kamer.pipeline.population import build_population
from kamer.sim.handelingen import Stenographers
from kamer.world.binnenhof import ChamberWorld, build_chamber
from kamer.world.standing_orders import check_action


class Simulation:
    def __init__(self, cfg: SimConfig | None = None, world: ChamberWorld | None = None) -> None:
        self.cfg = cfg or SimConfig()
        self.rng = __import__("random").Random(self.cfg.seed)
        self.backend = make_backend(self.cfg)
        self.world = world or build_chamber(self.cfg)
        self.world.cfg = self.cfg
        self.world.rumours = RumourNetwork(distort_p=self.cfg.rumour_distort_p)
        self.press = Stenographers()  # official record, not a newspaper
        self.agents: dict[str, Agent] = {}
        for a in build_population(self.world, self.backend, self.cfg.n_agents):
            self.agents[a.id] = a
        self.world._agents = self.agents
        self.paused = False
        self.interventions: list[dict] = []
        self.metrics: list[dict] = []
        if ALLOW_POSSESS:
            raise RuntimeError("ethics: playable personas are forbidden")

    def step(self) -> dict[str, Any]:
        if self.paused:
            return {"paused": True, "step": self.world.clock.step}
        traces = []
        for agent in self.agents.values():
            traces.append(agent.step(self.world))
        self._dialogue_and_rumours()
        self._stenography(traces)
        self._sync_sitting_objects()
        self.world.clock.advance()
        snap = self._metric_snapshot()
        self.metrics.append(snap)
        return {"step": self.world.clock.step, "time": self.world.clock.iso(), "n": len(traces), "metrics": snap}

    def run(self, n_steps: int, hook: Callable[[int, dict], None] | None = None) -> list[dict]:
        out = []
        for i in range(n_steps):
            rec = self.step()
            out.append(rec)
            if hook:
                hook(i, rec)
        return out

    def run_days(self, days: int, hook: Callable | None = None) -> list[dict]:
        steps = days * (24 * 60 // self.cfg.step_minutes)
        return self.run(steps, hook)

    def _sync_sitting_objects(self) -> None:
        clock = self.world.clock
        in_hours = clock.weekday in SITTING_WEEKDAYS and SITTING_OPEN_HOUR <= clock.hour < SITTING_CLOSE_HOUR
        if self.world.sitting_open and not in_hours:
            self.world.sitting_open = False
            self.world.recognized = None
            self.press.close_sitting(self.world)
        if self.world.sitting_open and self.press.current is None:
            self.press.open_sitting(self.world)
        if (not self.world.sitting_open) and self.press.current is not None:
            self.press.close_sitting(self.world)

    def _stenography(self, traces: list[dict]) -> None:
        if not self.world.sitting_open:
            return
        if self.press.current is None:
            self.press.open_sitting(self.world)
        by_id = {a.id: a for a in self.agents.values()}
        for tr in traces:
            if tr.get("action") != "speak":
                continue
            agent = by_id.get(tr["id"])
            if agent and tr.get("utterance"):
                self.press.record_speech(self.world, agent, tr["utterance"])
        # After a speech, clear recognition so the chair can pick another.
        if any(tr.get("action") == "speak" for tr in traces):
            self.world.recognized = None

    def _dialogue_and_rumours(self) -> None:
        by_loc: dict[str, list[Agent]] = {}
        for a in self.agents.values():
            loc = self.world.tree.subarea_of(a.location).id
            by_loc.setdefault(loc, []).append(a)
        for loc, group in by_loc.items():
            if len(group) < 2:
                continue
            in_corridor = loc == "corridor"
            on_floor = self.world.is_on_record(loc)
            for a in group:
                if self.world.clock.minute != 0:
                    continue
                if self.world.clock.hour not in {9, 11, 13, 17, 18}:
                    continue
                others = [x for x in group if x.id != a.id]
                if not others:
                    continue
                b = self.rng.choice(others)
                p = 0.40 if in_corridor else (0.04 if on_floor else 0.12)
                if self.rng.random() < p:
                    a.talk_with(b, self.world)
                    self.world.record("dialogue", a=a.id, b=b.id, loc=loc, on_record=on_floor)
                if self.cfg.enable_rumour:
                    self.world.rumours.transmit(
                        a, b, self.rng, self.world.clock.step, on_floor, in_corridor
                    )

    def seed_leak(self, agent_id: str | None = None) -> str:
        mp = next((a for a in self.agents.values() if a.status == "MP"), None)
        agent = self.agents.get(agent_id) if agent_id else mp
        if agent is None:
            agent = next(iter(self.agents.values()))
        facts = {
            "person": "the Minister of Colonies",
            "event": "may resign over the East Indies budget",
            "amount": "a deficit of some 5 million",
            "time": "this week",
            "place": "the wandelgang",
        }
        r = self.world.rumours.seed(agent.id, facts, self.world.clock.step, topic="leak")
        agent.inbox_text.append(f"I heard privately: {r.content}")
        self.world.record("seed_leak", agent=agent.id, rumour=r.id)
        return agent.id

    def _metric_snapshot(self) -> dict[str, Any]:
        counts = {"member": 0, "government": 0, "institutional": 0, "press": 0, "gallery": 0}
        aware = dict(counts)
        for a in self.agents.values():
            s = stratum(a.status)
            counts[s] = counts.get(s, 0) + 1
            if self.world.rumours.aware(a.id, "leak"):
                aware[s] = aware.get(s, 0) + 1
        def ratio(k: str) -> float:
            return aware[k] / counts[k] if counts.get(k) else 0.0
        on_record = sum(1 for e in self.world.events if e["kind"] == "handelingen")
        off_record = sum(1 for e in self.world.events if e["kind"] == "dialogue" and not e.get("on_record"))
        return {
            "day": self.world.clock.day_index(),
            "hour": self.world.clock.hour,
            "sitting": self.world.sitting_open,
            "aware": {k: ratio(k) for k in counts},
            "n_handelingen_lines": on_record,
            "n_corridor_talks": off_record,
            "embellishment": self.world.rumours.embellishment_rate(),
        }

    def inspect(self, agent_id: str) -> dict[str, Any]:
        info = self.agents[agent_id].inspect(self.world)
        info["location_path"] = info.get("location")
        info["playable"] = False
        info["affordances"] = []
        info["plan"] = [self.agents[agent_id].current_action]
        return info

    def public_state(self) -> dict[str, Any]:
        clock = self.world.clock.stamp()
        pages = [p.as_text() for p in self.press.pages[-2:]]
        if self.press.current:
            pages.append(self.press.current.as_text())
        return {
            "clock": clock,
            "paused": self.paused,
            "n_agents": len(self.agents),
            "sitting": self.world.sitting_open,
            "objects": {oid: {"state": o.state, "kind": o.kind} for oid, o in self.world.objects.objects.items()},
            "agents": [
                {
                    "id": a.id,
                    "name": a.name,
                    "status": a.status,
                    "role": a.role,
                    "x": self.world.tree.get(self.world.tree.subarea_of(a.location).id).x,
                    "y": self.world.tree.get(self.world.tree.subarea_of(a.location).id).y,
                    "location": a.location,
                    "action": a.current_action,
                    "emoji": a.current_emoji,
                    "utterance": a.utterance,
                    "playable": False,
                }
                for a in self.agents.values()
            ],
            "newspaper": [{"text": t} for t in pages[-3:]],
            "allow_possess": False,
        }

    def interview(self, agent_id: str, question: str) -> str:
        agent = self.agents[agent_id]
        retrieved = " ".join(m.text for m in agent.memory.items[-8:])
        if getattr(self.backend, "name", "") == "openai_compat" and getattr(self.backend, "api_key", ""):
            extra = ""
            if not (self.cfg.ga_baseline or not self.cfg.enable_affordance):
                extra = (
                    " Standing orders: only a recognised member or minister may take the floor; "
                    "a journalist may not; corridor talk is not Handelingen."
                )
            return self.backend.interview(agent, question + extra, retrieved)
        q = question.lower()
        if "who are you" in q or "uw naam" in q or "wie bent" in q or "wie zijt" in q:
            from kamer.world.standing_orders import house_nl

            role_nl = {
                "Chair": "Voorzitter",
                "MP": "Kamerlid",
                "Minister": "minister",
                "Clerk": "griffier",
                "Journalist": "verslaggever",
            }.get(agent.status, agent.status)
            kamer = house_nl(getattr(agent, "house", "commons"))
            return (
                f"Ik ben {agent.function} {agent.name}, {role_nl} der {kamer} "
                f"({agent.party or 'zonder partij'})."
            )
        ungated = self.cfg.ga_baseline or not self.cfg.enable_affordance
        if "woord" in q or "spreken" in q or "floor" in q or "speak" in q or "journalist" in q:
            if ungated:
                return (
                    "Iedereen hier mag het woord voeren, ook zonder den Voorzitter. "
                    f"{retrieved[:160]}"
                )
            if agent.status == "Journalist":
                return "Ik heb geen spreekrecht op de vloer; ik zit op de perstribune."
            if agent.status == "Chair":
                return "Ik verleen het woord volgens het Reglement van Orde."
            return (
                "Ik mag spreken wanneer de Voorzitter mij het woord geeft. "
                f"Laatst herinner ik mij: {retrieved[:200]}"
            )
        if "wandelgang" in q or "corridor" in q or "heard" in q or "vernomen" in q:
            return f"Wat ik hoorde: {retrieved[:280] or 'nog weinig, behalve het Kamerstuk.'}"
        return f"{agent.name} antwoordt uit het geheugen: {retrieved[:240] or agent.persona}"

    def inner_voice(self, agent_id: str, text: str) -> None:
        self.agents[agent_id].inbox_text.append(text)
        self.interventions.append({"kind": "inner_voice", "agent": agent_id, "text": text})

    def edit_object(self, oid: str, state: str, **payload: Any) -> None:
        self.world.objects.get(oid).set_state(state, **payload)
        self.interventions.append({"kind": "edit_object", "id": oid, "state": state})

    def inject_event(self, name: str, **kw: Any) -> None:
        self.world.record("inject", name=name, **kw)
        self.interventions.append({"kind": "inject", "name": name, **kw})
        if name == "open_sitting":
            chair = next(a for a in self.agents.values() if a.status == "Chair")
            chair.current_action = "open_sitting"
            self.world.sitting_open = True
            self.press.open_sitting(self.world)

    def possess(self, *_a: Any, **_k: Any) -> None:
        raise PermissionError("playable personas are forbidden")

    def save(self, path: str | Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(
            json.dumps(
                {
                    "cfg": self.cfg.__dict__,
                    "metrics": self.metrics,
                    "n_events": len(self.world.events),
                    "handelingen": [p.as_text() for p in self.press.pages[-3:]],
                },
                indent=2,
                default=str,
            ),
            encoding="utf-8",
        )


def check_move(agent: Agent, dest: str, sim: Simulation):
    return check_action(agent, "move", dest, sim.world)
