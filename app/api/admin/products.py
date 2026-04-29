"""
Admin — Products CRUD + image upload.

Image upload best practices:
  1. Content-Type header validated (client-declared)
  2. Magic bytes validated (actual file content) — prevents content-type spoofing
  3. File size checked AFTER reading (prevents partial read attacks)
  4. Unique path per upload prevents caching collisions
  5. upsert=true allows re-uploading without 409 from Supabase Storage
"""
import uuid
from uuid import UUID
from fastapi import APIRouter, Depends, File, Query, UploadFile
from app.core.exceptions import ValidationError
from app.core.supabase import get_supabase_admin_client
from app.dependencies.auth import get_current_admin
from app.schemas.product import ProductCreate, ProductListResponse, ProductResponse, ProductUpdate
from app.schemas.user import CurrentUser
from app.services.product_service import ProductService

router = APIRouter(prefix="/admin/products", tags=["Admin — Products"])

IMAGE_BUCKET   = "product-images"
IMAGE_MAX_SIZE = 5 * 1024 * 1024   # 5 MB

# Magic byte signatures for allowed image types
# We check actual file content, not just the Content-Type header
IMAGE_MAGIC_BYTES = {
    b"\xff\xd8\xff":   "image/jpeg",   # JPEG
    b"\x89PNG\r\n":    "image/png",    # PNG
    b"RIFF":           "image/webp",   # WebP (also checks bytes 8-11)
    b"GIF87a":         "image/gif",    # GIF87
    b"GIF89a":         "image/gif",    # GIF89
}


def _validate_image(contents: bytes, declared_content_type: str) -> str:
    """
    Validate image by checking magic bytes (actual content),
    not just the Content-Type header a client might lie about.

    Returns the detected content type.
    Raises ValidationError if file is not a supported image format.
    """
    for magic, mime_type in IMAGE_MAGIC_BYTES.items():
        if contents[:len(magic)] == magic:
            # Special WebP check: bytes 0-3 are RIFF, bytes 8-11 must be WEBP
            if magic == b"RIFF" and contents[8:12] != b"WEBP":
                continue
            return mime_type

    raise ValidationError(
        "File is not a valid image. "
        "Supported formats: JPEG, PNG, WebP, GIF. "
        f"(Declared type was: {declared_content_type})"
    )


@router.get("", response_model=ProductListResponse)
def list_products(
    page:             int        = Query(default=1, ge=1),
    page_size:        int        = Query(default=20, ge=1, le=100),
    search:           str | None = Query(default=None, max_length=200),
    category_id:      UUID | None = Query(default=None),
    in_stock_only:    bool       = Query(default=False),
    include_inactive: bool       = Query(default=True),
    _: CurrentUser = Depends(get_current_admin),
    service: ProductService = Depends(ProductService),
):
    """Admin: list all products. Includes inactive by default."""
    return service.list_products(
        page=page, page_size=page_size, search=search,
        category_id=str(category_id) if category_id else None,
        in_stock_only=in_stock_only,
        include_inactive=include_inactive,
    )


@router.post("", response_model=ProductResponse, status_code=201)
def create_product(
    payload: ProductCreate,
    current_admin: CurrentUser = Depends(get_current_admin),
    service: ProductService = Depends(ProductService),
):
    """Admin: create a product. Image can be added afterwards via POST /{id}/image."""
    return service.create_product(payload, admin_id=current_admin.id)


@router.get("/{product_id}", response_model=ProductResponse)
def get_product(
    product_id: UUID,
    _: CurrentUser = Depends(get_current_admin),
    service: ProductService = Depends(ProductService),
):
    """Admin: get full product details including inactive ones."""
    return service.get_product(product_id)


@router.patch("/{product_id}", response_model=ProductResponse)
def update_product(
    product_id: UUID,
    payload: ProductUpdate,
    _: CurrentUser = Depends(get_current_admin),
    service: ProductService = Depends(ProductService),
):
    """
    Admin: partial update. Send only the fields to change.
    Set is_active=false to soft-disable (hides from customers).
    """
    return service.update_product(product_id, payload)


@router.patch("/{product_id}/stock", response_model=ProductResponse)
def update_stock(
    product_id: UUID,
    new_stock: int = Query(..., ge=0, description="New absolute stock level"),
    _: CurrentUser = Depends(get_current_admin),
    service: ProductService = Depends(ProductService),
):
    """Admin: set stock level directly (e.g. after a physical stocktake)."""
    return service.update_stock(product_id, new_stock)


@router.post("/{product_id}/image", response_model=ProductResponse)
async def upload_product_image(
    product_id: UUID,
    file: UploadFile = File(...),
    _: CurrentUser = Depends(get_current_admin),
    service: ProductService = Depends(ProductService),
):
    """
    Admin: upload a product image.

    Process:
      1. Read file bytes
      2. Validate size (≤ 5 MB)
      3. Validate content via magic bytes (not just Content-Type header)
      4. Upload to Supabase Storage bucket 'product-images'
      5. Save public URL to products.image_url

    Accepted formats: JPEG, PNG, WebP, GIF
    Max size: 5 MB
    """
    contents = await file.read()

    # Check size AFTER reading so we have the real size
    if len(contents) > IMAGE_MAX_SIZE:
        raise ValidationError(
            f"File size {len(contents) // 1024 // 1024:.1f} MB exceeds the 5 MB limit"
        )

    # Validate actual file content (not just declared Content-Type)
    detected_mime = _validate_image(contents, file.content_type or "unknown")

    # Build unique storage path: <product_id>/<uuid>.<ext>
    # Keying by product_id means all images for a product are grouped
    ext_map = {
        "image/jpeg": "jpg",
        "image/png":  "png",
        "image/webp": "webp",
        "image/gif":  "gif",
    }
    ext  = ext_map.get(detected_mime, "jpg")
    path = f"{product_id}/{uuid.uuid4()}.{ext}"

    db = get_supabase_admin_client()
    db.storage.from_(IMAGE_BUCKET).upload(
        path=path,
        file=contents,
        file_options={
            "content-type": detected_mime,
            "upsert": "true",           # allow replacement without 409
        },
    )

    image_url = db.storage.from_(IMAGE_BUCKET).get_public_url(path)
    return service.set_image_url(product_id, image_url)


@router.delete("/{product_id}/image", response_model=ProductResponse)
def delete_product_image(
    product_id: UUID,
    _: CurrentUser = Depends(get_current_admin),
    service: ProductService = Depends(ProductService),
):
    """Admin: remove product image (sets image_url to null)."""
    return service.set_image_url(product_id, None)


@router.delete("/{product_id}", status_code=204)
def deactivate_product(
    product_id: UUID,
    _: CurrentUser = Depends(get_current_admin),
    service: ProductService = Depends(ProductService),
):
    """
    Admin: soft-delete — sets is_active=False.
    Product is hidden from customers but record is preserved
    because order_items references it.
    Hard deletion is intentionally not supported.
    """
    service.delete_product(product_id)