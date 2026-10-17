"""FastAPI service: incidents REST, zones CRUD, stats, WebSocket live feed, health."""
from fastapi import FastAPI

app = FastAPI(title="SiteSentinel API")


@app.get("/api/health")
def health():
    return {"status": "ok"}
# TODO: /api/incidents, /api/zones, /api/stats, /ws/live, /evidence static mount
