from fastapi import FastAPI

from archmind import __version__
from archmind.config import settings
from archmind.routers import auth, costs, projects, ratings

app = FastAPI(title="ArchMind API", version=__version__)
app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(costs.router)
app.include_router(ratings.router)


@app.get("/api/v1/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__, "env": settings.env}
