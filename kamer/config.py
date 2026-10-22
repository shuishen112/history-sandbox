"""Hyperparameters for the Kamer parliamentary sandbox."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


STEP_MINUTES = 10
STEPS_PER_HOUR = 60 // STEP_MINUTES
STEPS_PER_DAY = 24 * STEPS_PER_HOUR

ALPHA_REC = 1.0
ALPHA_IMP = 1.0
ALPHA_REL = 1.0
RECENCY_DECAY_PER_HOUR = 0.995
RETRIEVAL_K = 8
REFLECTION_TAU = 150.0
MAX_REPLAN = 3

# Sitting schedule (Tweede Kamer, late 19th c. weekday sitting)
SITTING_OPEN_HOUR = 10
SITTING_CLOSE_HOUR = 17
SITTING_WEEKDAYS = frozenset({0, 1, 2, 3, 4})  # Mon–Fri

RUMOUR_DISTORT_P = 0.18
ALLOW_POSSESS = False

DEFAULT_YEAR = 1899
DEFAULT_MONTH = 12
DEFAULT_DAY = 18  # Monday of a demo sitting week
DEFAULT_WEEKDAY = 0

RoleName = Literal["Chair", "MP", "Minister", "Clerk", "Journalist", "Gallery"]


@dataclass
class SimConfig:
    seed: int = 7
    n_agents: int = 25
    n_days: int = 7
    start_year: int = DEFAULT_YEAR
    start_month: int = DEFAULT_MONTH
    start_day: int = DEFAULT_DAY
    start_weekday: int = DEFAULT_WEEKDAY
    start_hour: int = 9
    start_minute: int = 0
    step_minutes: int = STEP_MINUTES
    llm: str = "heuristic"
    llm_model: str = ""
    llm_base_url: str = ""
    llm_system: str = ""
    reflection_tau: float = REFLECTION_TAU
    rumour_distort_p: float = RUMOUR_DISTORT_P
    chair_strictness: float = 1.0
    enable_affordance: bool = True
    enable_automaton: bool = True
    enable_reflection: bool = True
    enable_planning: bool = True
    enable_observation: bool = True
    enable_rumour: bool = True
    enable_dialogue_map: bool = True
    enable_archival_rag: bool = True
    enable_anachronism_filter: bool = True
    ga_baseline: bool = False
    log_dir: str = "runs"
    scenario: str = "s1"
    period: str = "1899-1900"
    house: str = "commons"

    def apply_preset(self, name: str) -> "SimConfig":
        self.scenario = name
        flags = {
            "no_affordance": {"enable_affordance": False},
            "no_automaton": {"enable_automaton": False},
            "no_reflection": {"enable_reflection": False},
            "no_reflection_planning": {"enable_reflection": False, "enable_planning": False},
            "no_obs_refl_planning": {
                "enable_observation": False,
                "enable_reflection": False,
                "enable_planning": False,
            },
            "no_rumour": {"enable_rumour": False},
            "no_dialogue_map": {"enable_dialogue_map": False},
            "no_rag": {"enable_archival_rag": False},
            "ga": {
                "ga_baseline": True,
                "enable_affordance": False,
                "enable_automaton": False,
                "enable_rumour": False,
                "enable_dialogue_map": False,
                "enable_archival_rag": False,
                "enable_anachronism_filter": False,
            },
        }
        for key, value in flags.get(name, {}).items():
            setattr(self, key, value)
        return self


@dataclass
class EvalConfig:
    interview_n: int = 25
    seeds: list[int] = field(default_factory=lambda: [7, 11, 19, 29, 31])
    conditions: list[str] = field(
        default_factory=lambda: [
            "full",
            "no_affordance",
            "no_automaton",
            "no_reflection",
            "no_reflection_planning",
            "no_obs_refl_planning",
            "ga",
        ]
    )
