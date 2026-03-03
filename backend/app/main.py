"""FIFA Ranks — FastAPI application"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.config import settings

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

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok"}

# Future routes will be added here
# from backend.app.routes import matches, players, rankings
# app.include_router(matches.router, prefix="/api/matches", tags=["matches"])
# app.include_router(players.router, prefix="/api/players", tags=["players"])
# app.include_router(rankings.router, prefix="/api/rankings", tags=["rankings"])
