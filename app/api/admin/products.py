"""Admin — Products Endpoints (includes image upload)."""
import uuid
from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, UploadFile

from app.core.exceptions import ValidationError
from app.core.supabase import get_supabase_admin_client
from app.dependencies.auth import get_current_admin
from app.schemas.product import (
    ProductCreate, ProductListResponse, ProductResponse, ProductUpdate,
)
from app.schemas.user import CurrentUser
from app.services.product_service import ProductService

router = APIRouter(prefix="/admin/products", tags=["Admin — Products"])

IMAGE_BUCKET   = "product-images"
IMAGE_MAX_SIZE = 5 * 1024 * 1024
IMAGE_ALLOWED  = {"image/jpeg", "image/png", "image/webp", "image/gif"}


@router.get("", response_model=ProductListResponse)
def list_products(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None),
    category_id: UUID | None = Query(default=None),
    in_stock_only: bool = Query(default=False),
    include_inactive: bool = Query(default=True),
    _: CurrentUser = Depends(get_current_admin),
    service: ProductService = Depends(ProductService),
):
    return service.list_products(
        page=page, page_size=page_size, search=search,
        category_id=str(category_id) if category_id else None,
        in_stock_only=in_stock_only, include_inactive=include_inactive,
    )


@router.post("", response_model=ProductResponse, status_code=201)
def create_product(
    payload: ProductCreate,
    current_admin: CurrentUser = Depends(get_current_admin),
    service: ProductService = Depends(ProductService),
):
    return service.create_product(payload, admin_id=current_admin.id)


@router.get("/{product_id}", response_model=ProductResponse)
def get_product(
    product_id: UUID,
    _: CurrentUser = Depends(get_current_admin),
    service: ProductService = Depends(ProductService),
):
    return service.get_product(product_id)


@router.patch("/{product_id}", response_model=ProductResponse)
def update_product(
    product_id: UUID,
    payload: ProductUpdate,
    _: CurrentUser = Depends(get_current_admin),
    service: ProductService = Depends(ProductService),
):
    return service.update_product(product_id, payload)


@router.patch("/{product_id}/stock", response_model=ProductResponse)
def update_stock(
    product_id: UUID,
    new_stock: int = Query(..., ge=0),
    _: CurrentUser = Depends(get_current_admin),
    service: ProductService = Depends(ProductService),
):
    return service.update_stock(product_id, new_stock)


@router.post("/{product_id}/image", response_model=ProductResponse)
async def upload_product_image(
    product_id: UUID,
    file: UploadFile = File(...),
    _: CurrentUser = Depends(get_current_admin),
    service: ProductService = Depends(ProductService),
):
    """Upload a product image. JPEG/PNG/WebP/GIF — max 5 MB."""
    if file.content_type not in IMAGE_ALLOWED:
        raise ValidationError(
            f"File type '{file.content_type}' not allowed. Use JPEG, PNG, WebP or GIF."
        )
    contents = await file.read()
    if len(contents) > IMAGE_MAX_SIZE:
        raise ValidationError("File exceeds the 5 MB size limit.")

    ext  = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else "jpg"
    path = f"{product_id}/{uuid.uuid4()}.{ext}"

    db = get_supabase_admin_client()
    db.storage.from_(IMAGE_BUCKET).upload(
        path=path, file=contents,
        file_options={"content-type": file.content_type, "upsert": "true"},
    )
    image_url = db.storage.from_(IMAGE_BUCKET).get_public_url(path)
    return service.set_image_url(product_id, image_url)


@router.delete("/{product_id}/image", response_model=ProductResponse)
def delete_product_image(
    product_id: UUID,
    _: CurrentUser = Depends(get_current_admin),
    service: ProductService = Depends(ProductService),
):
    """Remove a product image (sets image_url to null)."""
    return service.set_image_url(product_id, None)


@router.delete("/{product_id}", status_code=204)
def deactivate_product(
    product_id: UUID,
    _: CurrentUser = Depends(get_current_admin),
    service: ProductService = Depends(ProductService),
):
    service.delete_product(product_id)