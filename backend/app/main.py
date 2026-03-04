"""FIFA Ranks — FastAPI application"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from backend.app.config import settings
import os

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="FIFA 2v2 player ranking tracker with TrueSkill",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files (CSS, JS, images)
static_path = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_path):
    app.mount("/static", StaticFiles(directory=static_path), name="static")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok"}

# Import routers
from backend.app.routers import matches, players, rankings, chemistry, pages

# API routes
app.include_router(matches.router, prefix="/api/v1/matches", tags=["matches"])
app.include_router(players.router, prefix="/api/v1/players", tags=["players"])
app.include_router(rankings.router, prefix="/api/v1/rankings", tags=["rankings"])
app.include_router(chemistry.router, prefix="/api/v1/chemistry", tags=["chemistry"])

# Web page routes (must come last to avoid shadowing API routes)
app.include_router(pages.router, tags=["pages"])
