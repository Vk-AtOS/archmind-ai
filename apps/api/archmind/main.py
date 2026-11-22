from fastapi import FastAPI

from archmind import __version__
from archmind.config import settings

app = FastAPI(title="ArchMind API", version=__version__)


@app.get("/api/v1/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__, "env": settings.env}
