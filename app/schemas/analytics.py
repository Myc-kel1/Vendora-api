from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel, Field


class OrderAnalytics(BaseModel):
    total_orders:       int
    pending_orders:     int
    paid_orders:        int
    failed_orders:      int
    cancelled_orders:   int
    total_revenue:      Decimal = Field(description="Lifetime revenue from paid orders")
    revenue_today:      Decimal
    revenue_this_month: Decimal


class TopProduct(BaseModel):
    product_id:    UUID
    product_name:  str
    total_sold:    int
    total_revenue: Decimal


class AnalyticsDashboard(BaseModel):
    orders:       OrderAnalytics
    top_products: list[TopProduct]