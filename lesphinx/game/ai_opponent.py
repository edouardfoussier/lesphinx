"""AI opponent for Human vs AI duel mode.

Each AI persona has a name, personality, Bedrock model, and ElevenLabs voice.
The AI plays the guessing game: it formulates yes/no questions and guesses.

Supports two auth modes:
- Bearer token (AWS_BEARER_TOKEN_BEDROCK) — provided by hackathon organizers
- IAM credentials (AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY) — standard AWS
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from urllib.parse import quote

import httpx

from lesphinx.config.settings import settings
from lesphinx.game.models import GameSession

logger = logging.getLogger(__name__)


@dataclass
class AIPersona:
    id: str
    name: str
    personality: str
    bedrock_model: str
    voice_id: str  # ElevenLabs voice
    emoji: str


AI_PERSONAS: list[AIPersona] = [
    AIPersona(
        id="nova",
        name="Nova",
        personality="Analytical and methodical. Asks precise, narrowing questions.",
        bedrock_model="anthropic.claude-3-5-sonnet-20241022-v2:0",
        voice_id="21m00Tcm4TlvDq8ikWAM",
        emoji="𓂀",
    ),
    AIPersona(
        id="titan",
        name="Titan",
        personality="Bold and aggressive. Makes daring guesses early.",
        bedrock_model="meta.llama3-1-70b-instruct-v1:0",
        voice_id="VR6AewLTigWG4xSOukaG",
        emoji="𓃭",
    ),
    AIPersona(
        id="sage",
        name="Sage",
        personality="Patient and encyclopedic. Explores every category before guessing.",
        bedrock_model="cohere.command-r-plus-v1:0",
        voice_id="ErXwobaYiN019PkySvjV",
        emoji="𓆣",
    ),
    AIPersona(
        id="anubis",
        name="Anubis",
        personality="Cunning and intuitive. Reads between the lines.",
        bedrock_model="amazon.nova-pro-v1:0",
        voice_id="pNInz6obpgDQGcFmaJgB",
        emoji="𓁢",
    ),
]

MODEL_FRIENDLY_NAMES = {
    "anthropic.claude-3-5-sonnet-20241022-v2:0": "Claude 3.5 Sonnet",
    "meta.llama3-1-70b-instruct-v1:0": "Llama 3.1 70B",
    "cohere.command-r-plus-v1:0": "Cohere Command R+",
    "amazon.nova-pro-v1:0": "Amazon Nova Pro",
}

PERSONAS_BY_ID = {p.id: p for p in AI_PERSONAS}

AI_PLAYER_SYSTEM_PROMPT = """You are playing a guessing game against another player. The Sphinx is thinking of a famous person, and you need to figure out who it is by asking yes/no questions.

Your personality: {personality}

RULES:
- Ask ONE clear yes/no question per turn, OR make a guess
- Base your questions on previous answers to narrow down possibilities
- Think strategically: start with broad categories (gender, alive/dead, field) then narrow down
- When you're confident (after enough clues), make a guess
- Keep questions SHORT (under 15 words)

RESPONSE FORMAT - Return ONLY a JSON object:
{{
  "type": "question" or "guess",
  "text": "your question or guess"
}}

If type is "question": text should be a yes/no question like "Is this person alive?"
If type is "guess": text should be just the person's name like "Albert Einstein"

CONVERSATION SO FAR:
{history}

Based on the answers so far, what is your next move?"""


class AIOpponentClient:
    """Generates AI opponent moves via Amazon Bedrock.

    Uses bearer token auth when AWS_BEARER_TOKEN_BEDROCK is set,
    otherwise falls back to IAM credentials via boto3.
    """

    def __init__(self) -> None:
        self._http_client: httpx.AsyncClient | None = None
        self._boto_client = None

    def _get_http_client(self) -> httpx.AsyncClient:
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=30.0)
        return self._http_client

    @property
    def _use_bearer(self) -> bool:
        return bool(settings.aws_bearer_token_bedrock)

    def _bedrock_url(self, model_id: str) -> str:
        region = settings.aws_region or "us-east-1"
        encoded_model = quote(model_id, safe="")
        return f"https://bedrock-runtime.{region}.amazonaws.com/model/{encoded_model}/converse"

    def _build_history(self, session: GameSession, ai_player: int) -> str:
        lines = []
        for turn in session.turns:
            if turn.player == ai_player:
                lines.append(f"YOU asked: {turn.player_text}")
                lines.append(f"Sphinx answered: {turn.raw_answer} — \"{turn.sphinx_utterance}\"")
            else:
                lines.append(f"OPPONENT asked: {turn.player_text}")
                lines.append(f"Sphinx answered: {turn.raw_answer}")
        return "\n".join(lines) if lines else "(Game just started, no questions yet)"

    async def generate_move(
        self,
        session: GameSession,
        persona: AIPersona,
        ai_player: int = 2,
    ) -> dict:
        """Generate an AI opponent's move (question or guess)."""
        history = self._build_history(session, ai_player)
        prompt = AI_PLAYER_SYSTEM_PROMPT.format(
            personality=persona.personality,
            history=history,
        )

        try:
            if self._use_bearer:
                text = await self._call_bearer(persona.bedrock_model, prompt)
            else:
                text = await self._call_boto(persona.bedrock_model, prompt)
            return self._parse_move(text)
        except Exception as exc:
            logger.error("Bedrock AI opponent failed (%s): %s", persona.bedrock_model, exc)
            return self._fallback_move(session, ai_player)

    async def _call_bearer(self, model_id: str, prompt: str) -> str:
        """Call Bedrock Converse API using bearer token auth."""
        client = self._get_http_client()
        url = self._bedrock_url(model_id)
        headers = {
            "Authorization": f"Bearer {settings.aws_bearer_token_bedrock}",
            "Content-Type": "application/json",
        }
        body = {
            "messages": [{
                "role": "user",
                "content": [{"text": prompt}],
            }],
            "inferenceConfig": {
                "maxTokens": 200,
                "temperature": 0.5,
            },
        }

        response = await client.post(url, headers=headers, json=body)
        response.raise_for_status()
        data = response.json()
        return self._extract_converse_text(data)

    async def _call_boto(self, model_id: str, prompt: str) -> str:
        """Call Bedrock Converse API using boto3 IAM credentials."""
        import asyncio
        import boto3

        if self._boto_client is None:
            kwargs = {"service_name": "bedrock-runtime"}
            if settings.aws_region:
                kwargs["region_name"] = settings.aws_region
            if settings.aws_access_key_id and settings.aws_secret_access_key:
                kwargs["aws_access_key_id"] = settings.aws_access_key_id
                kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
            self._boto_client = boto3.client(**kwargs)

        def _call():
            return self._boto_client.converse(
                modelId=model_id,
                messages=[{
                    "role": "user",
                    "content": [{"text": prompt}],
                }],
                inferenceConfig={
                    "maxTokens": 200,
                    "temperature": 0.5,
                },
            )

        response = await asyncio.to_thread(_call)
        return self._extract_converse_text(response)

    @staticmethod
    def _extract_converse_text(response: dict) -> str:
        """Extract text from Bedrock Converse API response."""
        output = response.get("output", {})
        message = output.get("message", {})
        content = message.get("content", [])
        for block in content:
            if "text" in block:
                return block["text"]
        return ""

    def _parse_move(self, text: str) -> dict:
        """Parse the AI's response into a structured move."""
        text = text.strip()
        try:
            if "{" in text:
                json_str = text[text.index("{"):text.rindex("}") + 1]
                data = json.loads(json_str)
                move_type = data.get("type", "question")
                move_text = data.get("text", "")
                if move_type in ("question", "guess") and move_text:
                    return {"type": move_type, "text": move_text}
        except (json.JSONDecodeError, ValueError):
            pass

        if "?" in text:
            return {"type": "question", "text": text.split("?")[0].strip() + "?"}
        return {"type": "question", "text": text[:100] if text else "Is this person alive?"}

    def _fallback_move(self, session: GameSession, ai_player: int) -> dict:
        """Generate a reasonable fallback if Bedrock fails."""
        q_count = sum(1 for t in session.turns if t.player == ai_player)
        fallbacks = [
            "Is this person alive?",
            "Is this person male?",
            "Is this person from the United States?",
            "Is this person an artist or entertainer?",
            "Was this person born after 1950?",
            "Is this person known for science?",
            "Is this person European?",
            "Is this person a political figure?",
        ]
        idx = min(q_count, len(fallbacks) - 1)
        return {"type": "question", "text": fallbacks[idx]}


ai_opponent_client = AIOpponentClient()
