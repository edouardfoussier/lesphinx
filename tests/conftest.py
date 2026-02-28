"""Shared test fixtures."""

import pytest

from lesphinx.game.characters import Character, FactStore, SecretSelector


@pytest.fixture
def einstein() -> Character:
    return Character(
        id="albert_einstein",
        name="Albert Einstein",
        aliases=["Einstein"],
        difficulty="easy",
        attributes={
            "gender": "male",
            "alive": False,
            "nationality": "german",
            "field": "science",
            "subfield": "physics",
            "continent": "europe",
            "born_before_1900": True,
            "born_before_1950": True,
            "fictional": False,
        },
        facts=[
            "Won the Nobel Prize in Physics in 1921",
            "Developed the theory of relativity",
            "Played the violin",
            "Born in Ulm, Germany in 1879",
            "Became a US citizen in 1940",
            "Famous for the equation E=mc squared",
        ],
    )


@pytest.fixture
def cleopatra() -> Character:
    return Character(
        id="cleopatra",
        name="Cleopatra",
        aliases=["Cleopatra VII"],
        difficulty="easy",
        attributes={
            "gender": "female",
            "alive": False,
            "nationality": "egyptian",
            "field": "politics",
            "continent": "africa",
            "born_before_1900": True,
            "born_before_1950": True,
            "fictional": False,
        },
        facts=[
            "Was the last active ruler of the Ptolemaic Kingdom of Egypt",
            "Had relationships with Julius Caesar and Mark Antony",
            "Spoke multiple languages including Egyptian and Greek",
        ],
    )


@pytest.fixture
def mbappe() -> Character:
    return Character(
        id="kylian_mbappe",
        name="Kylian Mbappe",
        aliases=["Mbappe"],
        difficulty="medium",
        attributes={
            "gender": "male",
            "alive": True,
            "nationality": "french",
            "field": "sports",
            "subfield": "football",
            "continent": "europe",
            "born_before_1900": False,
            "born_before_1950": False,
            "fictional": False,
        },
        facts=[
            "Won the FIFA World Cup with France in 2018",
            "Played for Paris Saint-Germain",
            "Became the youngest French player to score at a World Cup",
            "Transferred to Real Madrid in 2024",
            "Known for exceptional speed on the football pitch",
        ],
    )


@pytest.fixture
def all_characters(einstein, cleopatra, mbappe) -> list[Character]:
    return [einstein, cleopatra, mbappe]


@pytest.fixture
def selector(all_characters) -> SecretSelector:
    return SecretSelector(all_characters)


@pytest.fixture
def einstein_facts(einstein) -> FactStore:
    return FactStore(einstein)
