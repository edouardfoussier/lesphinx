from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from lesphinx.api.rate_limit import RateLimitMiddleware
from lesphinx.api.routes import router

app = FastAPI(title="LeSphinx", description="Vocal guessing game - the Sphinx thinks, you guess")

app.add_middleware(RateLimitMiddleware)
app.include_router(router)

# React build output (from `npm run build` in frontend/)
dist_dir = Path(__file__).parent / "static" / "dist"

# Fallback: serve static files from legacy static/ if React build doesn't exist
legacy_static_dir = Path(__file__).parent / "static"

if dist_dir.exists():
    app.mount("/assets", StaticFiles(directory=str(dist_dir / "assets")), name="react-assets")

    @app.get("/{full_path:path}")
    async def serve_react(request: Request, full_path: str):
        file_path = dist_dir / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(dist_dir / "index.html")
else:
    app.mount("/", StaticFiles(directory=str(legacy_static_dir), html=True), name="static")
