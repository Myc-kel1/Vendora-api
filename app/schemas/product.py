from datetime import datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID
from pydantic import BaseModel, Field, condecimal


class ProductBase(BaseModel):
    name:        str     = Field(..., min_length=1, max_length=255)
    description: str     = Field(..., min_length=1)
    price: Annotated[
        Decimal,
        Field(gt=0, max_digits=10, decimal_places=2)
    ] | None = None
    stock:       int     = Field(..., ge=0)
    category_id: UUID | None = None


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    """All fields optional — PATCH semantics."""
    name:        str | None     = Field(None, min_length=1, max_length=255)
    description: str | None     = None
    price: Annotated[
        Decimal,
        Field(None, gt=0, max_digits=10, decimal_places=2)
    ] | None = None
    stock:       int | None     = Field(None, ge=0)
    category_id: UUID | None    = None
    is_active:   bool | None    = None
    image_url:   str | None     = None   # set by image upload endpoint


class ProductResponse(ProductBase):
    id:          UUID
    is_active:   bool
    image_url:   str | None = None
    created_by:  str
    created_at:  datetime
    updated_at:  datetime
    model_config = {"from_attributes": True}


class ProductListResponse(BaseModel):
    items:     list[ProductResponse]
    total:     int
    page:      int
    page_size: int


class CategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)


class CategoryUpdate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)


class CategoryResponse(BaseModel):
    id:         UUID
    name:       str
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}