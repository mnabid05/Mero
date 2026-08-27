"""Web-game configuration and difficulty presets."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Difficulty:
    key: str
    label: str
    move_time_ms: int
    description: str


DIFFICULTIES = {
    difficulty.key: difficulty
    for difficulty in (
        Difficulty("quick", "Quick", 80, "Fast moves for casual games"),
        Difficulty("club", "Club", 250, "Balanced strength and response time"),
        Difficulty("expert", "Expert", 700, "Mero searches longer for each move"),
    )
}


def difficulty_for(key: str) -> Difficulty:
    try:
        return DIFFICULTIES[key]
    except KeyError as error:
        choices = ", ".join(DIFFICULTIES)
        raise ValueError(f"unknown difficulty {key!r}; choose {choices}") from error
