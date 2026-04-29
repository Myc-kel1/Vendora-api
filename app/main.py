"""
Vendora API — Entry Point.

All routers registered here.
Global exception handlers convert AppError subclasses to clean JSON.
Middleware: CORS, request logging with X-Request-ID.
"""
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Customer routers
from app.api.customer import cart, orders, payments
from app.api.customer import products  as customer_products
from app.api.customer import categories as customer_categories
from app.api.customer import profile    as customer_profile

# Admin routers
from app.api.admin import orders     as admin_orders
from app.api.admin import products   as admin_products
from app.api.admin import categories as admin_categories
from app.api.admin import users      as admin_users
from app.api.admin import analytics  as admin_analytics

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.logging import configure_logging, get_logger

configure_logging()
logger   = get_logger(__name__)
settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    docs_url="/docs"        if not settings.is_production else None,
    redoc_url="/redoc"      if not settings.is_production else None,
    openapi_url="/openapi.json" if not settings.is_production else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    rid   = str(uuid.uuid4())[:8]
    start = time.time()
    import structlog
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=rid)
    logger.info("request_started", method=request.method, path=request.url.path)
    response = await call_next(request)
    logger.info("request_completed", method=request.method, path=request.url.path,
                status_code=response.status_code,
                duration_ms=round((time.time() - start) * 1000, 2))
    response.headers["X-Request-ID"] = rid
    return response


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    logger.warning("app_error", path=request.url.path,
                   status_code=exc.status_code, detail=exc.detail)
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    errors = [{"field": " → ".join(str(l) for l in e["loc"] if l != "body"),
               "message": e["msg"]} for e in exc.errors()]
    return JSONResponse(status_code=422,
                        content={"error": "Request validation failed", "details": errors})


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception):
    logger.error("unhandled_error", path=request.url.path, error=str(exc), exc_info=True)
    return JSONResponse(status_code=500, content={"error": "An unexpected error occurred"})


# Customer
app.include_router(customer_products.router)    # GET  /products
app.include_router(customer_categories.router)  # GET  /categories
app.include_router(cart.router)                 # CRUD /cart
app.include_router(orders.router)               # POST /orders, GET /orders/...
app.include_router(payments.router)             # POST /payments/initialize, /payments/webhook
app.include_router(customer_profile.router)     # GET/PATCH /profile, POST /profile/avatar

# Admin
app.include_router(admin_products.router)       # CRUD /admin/products + image upload
app.include_router(admin_categories.router)     # CRUD /admin/categories
app.include_router(admin_orders.router)         # GET/PUT /admin/orders
app.include_router(admin_users.router)          # GET /admin/users + profile
app.include_router(admin_analytics.router)      # GET /admin/analytics


@app.get("/health", tags=["System"])
def health_check():
    return {"status": "ok", "app": settings.app_name,
            "version": settings.app_version, "env": settings.app_env}


@app.get("/", tags=["System"], include_in_schema=False)
def root():
    return {"message": f"{settings.app_name} v{settings.app_version}",
            "docs": "/docs" if not settings.is_production else "disabled"}