from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from src.core.config import settings
from src.api.routes import router as api_router
from src.core.security import get_api_key
from src.core.limiter import limiter

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Backend for RAG system with Qdrant and Knowledge Graph",
)

# Rate Limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# Security Headers & Trusted Host
app.add_middleware(
    TrustedHostMiddleware, 
    allowed_hosts=["localhost", "127.0.0.1", "*"] # Restrict in production
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allow ALL origins for now to fix CORS issues
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global API Key Enforcement for V1 API
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

app.include_router(
    api_router, 
    prefix=settings.API_V1_STR, 
    dependencies=[Depends(get_api_key)]
)

# Mount sources directory for direct access
# Must be mounted BEFORE the static frontend at root "/"
os.makedirs("data/sources", exist_ok=True)
app.mount("/sources", StaticFiles(directory="data/sources"), name="sources")

# Mount frontend static files
frontend_dir = os.path.join(os.path.dirname(__file__), "frontend/out")
if os.path.exists(frontend_dir):
    app.mount("/_next", StaticFiles(directory=os.path.join(frontend_dir, "_next")), name="next")
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")

    # Fallback for SPA routing (if needed, though 'export' makes it static)
    @app.exception_handler(404)
    async def custom_404_handler(request, exc):
        return FileResponse(os.path.join(frontend_dir, "index.html"))
else:
    print(f"Warning: Frontend directory {frontend_dir} not found. Run 'npm run build' in src/frontend.")

if __name__ == "__main__":
    import uvicorn
    # Create sources directory if it doesn't exist
    os.makedirs("data/sources", exist_ok=True)
    uvicorn.run(app, host="0.0.0.0", port=8000)
