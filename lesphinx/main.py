from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from lesphinx.api.rate_limit import RateLimitMiddleware
from lesphinx.api.routes import router

app = FastAPI(title="LeSphinx", description="Vocal guessing game - the Sphinx thinks, you guess")

app.add_middleware(RateLimitMiddleware)
app.include_router(router)

static_dir = Path(__file__).parent / "static"
app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
