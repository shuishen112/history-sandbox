"""Composite Binnenhof: Tweede Kamer floor, wandelgang, committees, press gallery."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from maroon.sim.clock import SimClock
from maroon.world.tree import EnvNode, EnvironmentTree, NodeKind

from kamer.config import SimConfig
from kamer.world.objects import OBJECT_MACHINES, ObjectStore, StatefulObject


def _node(tree: EnvironmentTree, **kw) -> EnvNode:
    return tree.add(EnvNode(**kw))


def build_tree() -> tuple[EnvironmentTree, list[tuple[str, str]]]:
    tree = EnvironmentTree()
    tree.root_id = "binnenhof"
    _node(
        tree,
        id="binnenhof",
        name="Binnenhof",
        kind=NodeKind.ISLAND,
        x=650,
        y=520,
        aliases=["the binnenhof", "the hague", "den haag"],
    )

    areas = [
        ("tweede_kamer", "Tweede Kamer", 420, 420, ["floor", "commons", "on_record"]),
        ("eerste_kamer", "Eerste Kamer", 980, 280, ["floor", "senate", "on_record"]),
        ("wandelgang", "Wandelgang", 700, 620, ["corridor", "off_record"]),
        ("committee", "Committee rooms", 250, 720, ["committee", "off_record"]),
        ("press", "Press gallery", 420, 180, ["gallery", "press"]),
        ("ministerie", "Ministers' rooms", 980, 720, ["ministry", "off_record"]),
    ]
    for aid, name, x, y, tags in areas:
        _node(
            tree,
            id=aid,
            name=name,
            kind=NodeKind.AREA,
            parent_id="binnenhof",
            x=x,
            y=y,
            tags=tags,
            aliases=[name.lower()],
        )

    # Tweede Kamer subareas
    tk = [
        ("chair_dais", "Chair's dais", 420, 280, ["chair", "on_record"], 0.95),
        ("stenographers", "Stenographers' table", 360, 340, ["stenographer", "on_record"], 0.9),
        ("griffier_desk", "Griffier's desk", 390, 300, ["clerk", "on_record"], 0.9),
        ("ministers_bench", "Ministers' bench", 500, 360, ["government", "on_record"], 0.85),
        ("left_benches", "Left benches", 280, 480, ["mp", "on_record"], 0.7),
        ("right_benches", "Right benches", 560, 480, ["mp", "on_record"], 0.7),
        ("centre_aisle", "Centre aisle", 420, 500, ["floor", "on_record"], 0.8),
        ("tribune", "Public tribune", 420, 140, ["gallery"], 0.4),
    ]
    for sid, name, x, y, tags, vis in tk:
        _node(
            tree,
            id=sid,
            name=name,
            kind=NodeKind.SUBAREA,
            parent_id="tweede_kamer",
            x=x,
            y=y,
            tags=tags,
            visibility=vis,
            aliases=[name.lower()],
        )

    for sid, name, x, y, tags, vis in [
        ("ek_chair", "Eerste Kamer chair", 980, 220, ["chair", "senate", "on_record"], 0.95),
        ("ek_floor", "Eerste Kamer floor", 980, 280, ["senate", "on_record"], 0.85),
        ("ek_benches", "Eerste Kamer benches", 980, 340, ["mp", "senate", "on_record"], 0.7),
    ]:
        _node(
            tree,
            id=sid,
            name=name,
            kind=NodeKind.SUBAREA,
            parent_id="eerste_kamer",
            x=x,
            y=y,
            tags=tags,
            visibility=vis,
            aliases=[name.lower()],
        )
    _node(
        tree,
        id="corridor",
        name="Corridor",
        kind=NodeKind.SUBAREA,
        parent_id="wandelgang",
        x=700,
        y=620,
        tags=["corridor", "off_record"],
        aliases=["lobby", "wandelgangen"],
    )
    _node(
        tree,
        id="committee_a",
        name="Afdeeling A",
        kind=NodeKind.SUBAREA,
        parent_id="committee",
        x=250,
        y=720,
        tags=["committee", "off_record"],
        aliases=["section a"],
    )
    _node(
        tree,
        id="gallery_desk",
        name="Press desk",
        kind=NodeKind.SUBAREA,
        parent_id="press",
        x=420,
        y=180,
        tags=["gallery", "press"],
        aliases=["press gallery"],
    )
    _node(
        tree,
        id="kolonien",
        name="Department of Colonies",
        kind=NodeKind.SUBAREA,
        parent_id="ministerie",
        x=980,
        y=720,
        tags=["ministry", "off_record"],
        aliases=["koloniën", "colonies"],
    )

    objects = [
        ("gavel", "gavel", "chair_dais"),
        ("speaker_list", "speaker_list", "chair_dais"),
        ("kamerstuk", "kamerstuk", "centre_aisle"),
        ("stenograph", "stenograph", "stenographers"),
        ("voting_box", "voting_box", "centre_aisle"),
        ("press_gallery_desk", "press_gallery_desk", "gallery_desk"),
        ("whip_note", "whip_note", "corridor"),
    ]
    for oid, kind, nid in objects:
        machine = OBJECT_MACHINES[kind]
        _node(
            tree,
            id=oid,
            name=kind.replace("_", " "),
            kind=NodeKind.OBJECT,
            parent_id=nid,
            x=tree.get(nid).x,
            y=tree.get(nid).y,
            tags=[kind],
        )
        # objects registered later in ChamberWorld

    connections = [
        ("chair_dais", "stenographers"),
        ("chair_dais", "griffier_desk"),
        ("griffier_desk", "stenographers"),
        ("chair_dais", "ministers_bench"),
        ("ek_chair", "ek_floor"),
        ("ek_benches", "ek_floor"),
        ("ministers_bench", "centre_aisle"),
        ("left_benches", "centre_aisle"),
        ("right_benches", "centre_aisle"),
        ("centre_aisle", "corridor"),
        ("tribune", "gallery_desk"),
        ("gallery_desk", "chair_dais"),
        ("corridor", "committee_a"),
        ("corridor", "kolonien"),
        ("corridor", "ek_floor"),
        ("left_benches", "corridor"),
        ("right_benches", "corridor"),
    ]
    return tree, connections


@dataclass
class ChamberWorld:
    """Binnenhof world: environment tree, objects, events, sitting state."""

    cfg: SimConfig
    tree: EnvironmentTree
    objects: ObjectStore
    connections: list[tuple[str, str]]
    clock: SimClock
    events: list[dict[str, Any]] = field(default_factory=list)
    rumours: Any = None
    sitting_open: bool = False
    sitting_house: str = "commons"  # Tweede Kamer (commons) or Eerste Kamer (senate)
    recognized: str | None = None  # agent id currently given the floor
    _agents: dict[str, Any] = field(default_factory=dict)

    def record(self, kind: str, **kw: Any) -> None:
        rec = {"kind": kind, "step": self.clock.step, "t": self.clock.iso(), **kw}
        self.events.append(rec)

    def agents_at(self, node_id: str, exclude: str = "") -> list[Any]:
        out = []
        for a in self._agents.values():
            if a.id == exclude:
                continue
            if a.location == node_id or self.tree.subarea_of(a.location).id == node_id:
                out.append(a)
        return out

    def is_on_record(self, node_id: str) -> bool:
        tags = set(self.tree.get(node_id).tags)
        for anc in self.tree.ancestors(node_id):
            tags.update(anc.tags)
        return "on_record" in tags

    def neighbours(self, node_id: str) -> list[str]:
        out = []
        for a, b in self.connections:
            if a == node_id:
                out.append(b)
            elif b == node_id:
                out.append(a)
        return out


def build_chamber(cfg: SimConfig | None = None) -> ChamberWorld:
    cfg = cfg or SimConfig()
    tree, connections = build_tree()
    store = ObjectStore()
    for oid, kind, nid in [
        ("gavel", "gavel", "chair_dais"),
        ("speaker_list", "speaker_list", "chair_dais"),
        ("kamerstuk", "kamerstuk", "centre_aisle"),
        ("stenograph", "stenograph", "stenographers"),
        ("voting_box", "voting_box", "centre_aisle"),
        ("press_gallery_desk", "press_gallery_desk", "gallery_desk"),
        ("whip_note", "whip_note", "corridor"),
    ]:
        store.add(
            StatefulObject(
                id=oid,
                kind=kind,
                node_id=nid,
                state=OBJECT_MACHINES[kind]["default"],
                payload={"title": "Begrooting van Nederlandsch-Indië 1900"} if kind == "kamerstuk" else {},
            )
        )
    clock = SimClock(
        year=cfg.start_year,
        month=cfg.start_month,
        day=cfg.start_day,
        weekday=cfg.start_weekday,
        hour=cfg.start_hour,
        minute=cfg.start_minute,
        step_minutes=cfg.step_minutes,
    )
    world = ChamberWorld(cfg=cfg, tree=tree, objects=store, connections=connections, clock=clock)
    world.sitting_house = cfg.house
    return world
