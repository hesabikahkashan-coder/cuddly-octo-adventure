"""
NWH Crypto Trading Bot - FastAPI Application Entry Point
"""
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import time

from ..core.config import settings
from ..core.logging import setup_logging, get_logger
from .routes import auth, users, exchanges, trades, strategies, backtests, risk, notifications, dashboard
from .websockets import market_data, trade_events

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management."""
    setup_logging(log_level="DEBUG" if settings.DEBUG else "INFO")
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"Environment: {settings.ENVIRONMENT}")

    # Initialize services
    from ..db.session import init_db
    await init_db()
    logger.info("Database initialized")

    yield

    # Cleanup
    logger.info("Shutting down...")
    from ..db.session import close_db
    await close_db()


app = FastAPI(
    title="NWH Crypto Trading Bot API",
    description="Enterprise-grade cryptocurrency trading platform",
    version=settings.APP_VERSION,
    docs_url="/api/docs" if settings.DEBUG else None,
    redoc_url="/api/redoc" if settings.DEBUG else None,
    openapi_url="/api/openapi.json" if settings.DEBUG else None,
    lifespan=lifespan,
)

# ============================================================
# Middleware
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"] if settings.DEBUG else ["yourdomain.com", "localhost"]
)


@app.middleware("http")
async def add_request_timing(request: Request, call_next):
    """Add X-Process-Time header to all responses."""
    start = time.time()
    response = await call_next(request)
    process_time = (time.time() - start) * 1000
    response.headers["X-Process-Time"] = f"{process_time:.2f}ms"
    return response


@app.middleware("http")
async def security_headers(request: Request, call_next):
    """Add security headers."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


# ============================================================
# Exception Handlers
# ============================================================

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "Validation Error",
            "details": exc.errors(),
        }
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "Internal server error"}
    )


# ============================================================
# Routes
# ============================================================

PREFIX = settings.API_PREFIX

app.include_router(auth.router, prefix=f"{PREFIX}/auth", tags=["Authentication"])
app.include_router(users.router, prefix=f"{PREFIX}/users", tags=["Users"])
app.include_router(exchanges.router, prefix=f"{PREFIX}/exchanges", tags=["Exchanges"])
app.include_router(trades.router, prefix=f"{PREFIX}/trades", tags=["Trades"])
app.include_router(strategies.router, prefix=f"{PREFIX}/strategies", tags=["Strategies"])
app.include_router(backtests.router, prefix=f"{PREFIX}/backtests", tags=["Backtesting"])
app.include_router(risk.router, prefix=f"{PREFIX}/risk", tags=["Risk Management"])
app.include_router(notifications.router, prefix=f"{PREFIX}/notifications", tags=["Notifications"])
app.include_router(dashboard.router, prefix=f"{PREFIX}/dashboard", tags=["Dashboard"])

# WebSocket routes
app.include_router(market_data.router, prefix="/ws", tags=["WebSocket"])
app.include_router(trade_events.router, prefix="/ws", tags=["WebSocket"])


@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT
    }
