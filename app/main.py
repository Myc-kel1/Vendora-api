"""
E-Commerce API — Application Entry Point.

Registers:
- Global exception handlers (AppError → JSON response)
- CORS middleware
- Request logging middleware with X-Request-ID header
- All customer and admin routers
- Health check endpoint
"""
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# ─── Customer routers ─────────────────────────────────────────────────────────
from app.api.customer import cart, orders, payments
from app.api.customer import products as customer_products
from app.api.customer import categories as customer_categories

# ─── Admin routers ────────────────────────────────────────────────────────────
from app.api.admin import orders as admin_orders
from app.api.admin import products as admin_products
from app.api.admin import categories as admin_categories
from app.api.admin import users as admin_users
from app.api.admin import analytics as admin_analytics

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.logging import configure_logging, get_logger

# ─── Logging ─────────────────────────────────────────────────────────────────
configure_logging()
logger = get_logger(__name__)

settings = get_settings()

# ─── App ─────────────────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
    openapi_url="/openapi.json" if not settings.is_production else None,
)

# ─── CORS ─────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Request Logging Middleware ───────────────────────────────────────────────
@app.middleware("http")
async def log_requests(request: Request, call_next):
    request_id = str(uuid.uuid4())[:8]
    start = time.time()

    logger.info(
        "request_started",
        request_id=request_id,
        method=request.method,
        path=request.url.path,
    )

    response = await call_next(request)

    duration_ms = round((time.time() - start) * 1000)
    logger.info(
        "request_completed",
        request_id=request_id,
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=duration_ms,
    )

    response.headers["X-Request-ID"] = request_id
    return response

# ─── Global Exception Handlers ───────────────────────────────────────────────
@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    logger.warning(
        "app_error",
        path=request.url.path,
        status_code=exc.status_code,
        detail=exc.detail,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail},
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception):
    logger.error(
        "unhandled_error",
        path=request.url.path,
        error=str(exc),
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={"error": "An unexpected error occurred"},
    )

# ─── Customer Routers ─────────────────────────────────────────────────────────
app.include_router(customer_products.router)
app.include_router(customer_categories.router)
app.include_router(cart.router)
app.include_router(orders.router)
app.include_router(payments.router)

# ─── Admin Routers ────────────────────────────────────────────────────────────
app.include_router(admin_products.router)
app.include_router(admin_categories.router)
app.include_router(admin_orders.router)
app.include_router(admin_users.router)
app.include_router(admin_analytics.router)

# ─── Health Check ─────────────────────────────────────────────────────────────
@app.get("/health", tags=["System"])
def health_check():
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.app_version,
        "env": settings.app_env,
    }
