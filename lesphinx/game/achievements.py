"""Achievement system for LeSphinx."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lesphinx.game.models import GameSession

ACHIEVEMENTS = [
    {
        "id": "speed_demon",
        "icon": "\u26a1",
        "name": {"fr": "Eclair", "en": "Speed Demon"},
        "desc": {"fr": "Gagne en moins de 5 questions", "en": "Won in under 5 questions"},
        "check": lambda s: s.result == "win" and s.question_count < 5,
    },
    {
        "id": "no_hints",
        "icon": "\U0001f9e0",
        "name": {"fr": "Genie pur", "en": "Pure Genius"},
        "desc": {"fr": "Gagne sans utiliser d'indice", "en": "Won without any hints"},
        "check": lambda s: s.result == "win" and len(s.hints_given) == 0,
    },
    {
        "id": "first_try",
        "icon": "\U0001f3af",
        "name": {"fr": "Premier essai", "en": "First Try"},
        "desc": {"fr": "Trouve au premier guess", "en": "Found on first guess"},
        "check": lambda s: s.result == "win" and s.guess_count == 1,
    },
    {
        "id": "hard_winner",
        "icon": "\U0001f451",
        "name": {"fr": "Maitre du Sphinx", "en": "Sphinx Master"},
        "desc": {"fr": "Gagne en difficulte difficile", "en": "Won on hard difficulty"},
        "check": lambda s: s.result == "win" and s.difficulty == "hard",
    },
    {
        "id": "persistent",
        "icon": "\U0001f4aa",
        "name": {"fr": "Tenace", "en": "Persistent"},
        "desc": {"fr": "Gagne apres 15+ questions", "en": "Won after 15+ questions"},
        "check": lambda s: s.result == "win" and s.question_count >= 15,
    },
    {
        "id": "streak_3",
        "icon": "\U0001f525",
        "name": {"fr": "En feu", "en": "On Fire"},
        "desc": {"fr": "3 questions 'oui' consecutives", "en": "3 consecutive 'yes' answers"},
        "check": lambda s: s.current_streak >= 3,
    },
    {
        "id": "perfect_game",
        "icon": "\U0001f48e",
        "name": {"fr": "Partie parfaite", "en": "Perfect Game"},
        "desc": {"fr": "Gagne sans erreur et sans indice en < 10 questions", "en": "Won with no wrong guess, no hints, in < 10 questions"},
        "check": lambda s: s.result == "win" and s.guess_count == 1 and len(s.hints_given) == 0 and s.question_count < 10,
    },
    {
        "id": "medium_win",
        "icon": "\U0001f3c6",
        "name": {"fr": "Digne adversaire", "en": "Worthy Opponent"},
        "desc": {"fr": "Gagne en difficulte moyenne", "en": "Won on medium difficulty"},
        "check": lambda s: s.result == "win" and s.difficulty == "medium",
    },
]


def check_achievements(session: GameSession) -> list[dict]:
    """Return list of unlocked achievements for this session."""
    unlocked = []
    for a in ACHIEVEMENTS:
        try:
            if a["check"](session):
                unlocked.append({
                    "id": a["id"],
                    "icon": a["icon"],
                    "name": a["name"],
                    "desc": a["desc"],
                })
        except Exception:
            continue
    return unlocked
