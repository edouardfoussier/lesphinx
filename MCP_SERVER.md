# LeSphinx MCP Server

An [MCP (Model Context Protocol)](https://modelcontextprotocol.io) server that lets AI agents play the LeSphinx guessing game programmatically.

## How it works

The Sphinx thinks of a famous person. You ask yes/no questions to figure out who it is. You have **20 questions** and **3 guesses**. The MCP server wraps the LeSphinx REST API so any MCP-compatible AI agent can play.

## Quick start

### 1. Start the LeSphinx game server

```bash
cd /path/to/mistral-hackathon
source .venv/bin/activate
uvicorn lesphinx.main:app --reload
```

This starts the REST API on `http://localhost:8000`.

### 2. Run the MCP server

```bash
# stdio transport (for direct agent integration)
python -m lesphinx.mcp_server

# SSE transport (for network access on port 8100)
python -m lesphinx.mcp_server --sse
```

### 3. Configure the API URL

By default the MCP server connects to `http://localhost:8000`. Override with:

```bash
export LESPHINX_API_URL=https://thesphinx.ai
python -m lesphinx.mcp_server
```

## Connecting to Cursor / Claude Desktop

Add to your MCP config (e.g. `.cursor/mcp.json` or `claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "lesphinx": {
      "command": "python",
      "args": ["-m", "lesphinx.mcp_server"],
      "cwd": "/path/to/mistral-hackathon",
      "env": {
        "LESPHINX_API_URL": "https://thesphinx.ai"
      }
    }
  }
}
```

## Available tools

| Tool | Description |
|------|-------------|
| `start_game(language, difficulty, themes)` | Start a new game. Returns session_id. |
| `ask_question(session_id, question)` | Ask a yes/no question. |
| `make_guess(session_id, name)` | Guess the character's name. |
| `request_hint(session_id)` | Get a hint (max 3, costs 50 pts each). |
| `get_game_state(session_id)` | Check current game state. |
| `submit_score(session_id, player_name)` | Submit winning score to leaderboard. |
| `get_leaderboard()` | View top 10 and global stats. |

## Resources

| URI | Description |
|-----|-------------|
| `lesphinx://rules` | Full game rules, scoring, and achievements. |
| `lesphinx://strategy` | Strategy guide with optimal question ordering. |

## Example game flow

```
1. start_game(language="en", difficulty="medium")
   → session_id: "abc123", Sphinx says: "I am the Sphinx..."

2. ask_question("abc123", "Is this person alive?")
   → raw_answer: "no", Sphinx says: "No, mortal..."

3. ask_question("abc123", "Was this person European?")
   → raw_answer: "yes"

4. ask_question("abc123", "Were they a scientist?")
   → raw_answer: "yes"

5. ... (narrow down further)

6. make_guess("abc123", "Albert Einstein")
   → result: "win", score: 760

7. submit_score("abc123", "MyAgent")
   → rank: 3
```

## Dependencies

```bash
pip install mcp httpx
```

Both are listed in `requirements.txt`.
