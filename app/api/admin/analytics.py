"""
Admin: Analytics Dashboard.

Calls Supabase RPC functions (migration 007) for aggregated stats.
All heavy computation runs in the DB — no Python-side aggregation.
"""
from fastapi import APIRouter, Depends, Query

from app.core.supabase import get_supabase_admin_client
from app.dependencies.auth import get_current_admin
from app.schemas.analytics import AnalyticsDashboard, OrderAnalytics, TopProduct
from app.schemas.user import CurrentUser

router = APIRouter(prefix="/admin/analytics", tags=["Admin — Analytics"])


@router.get("", response_model=AnalyticsDashboard)
def get_dashboard(
    top_products_limit: int = Query(default=10, ge=1, le=50),
    _: CurrentUser = Depends(get_current_admin),
):
    """
    Admin: dashboard analytics.

    Returns:
    - Order counts by status (total, pending, paid, failed, cancelled)
    - Revenue totals (all-time, today, this month)
    - Top N selling products by units sold
    """
    db = get_supabase_admin_client()

    # Order analytics via RPC (migration 007)
    order_res = db.rpc("get_order_analytics", {}).execute()
    order_raw = order_res.data[0] if order_res.data else {}

    order_analytics = OrderAnalytics(
        total_orders=order_raw.get("total_orders", 0),
        pending_orders=order_raw.get("pending_orders", 0),
        paid_orders=order_raw.get("paid_orders", 0),
        failed_orders=order_raw.get("failed_orders", 0),
        cancelled_orders=order_raw.get("cancelled_orders", 0),
        total_revenue=order_raw.get("total_revenue", 0),
        revenue_today=order_raw.get("revenue_today", 0),
        revenue_this_month=order_raw.get("revenue_this_month", 0),
    )

    # Top products via RPC
    products_res = db.rpc("get_top_products", {"p_limit": top_products_limit}).execute()
    top_products = [
        TopProduct(
            product_id=row["product_id"],
            product_name=row["product_name"],
            total_sold=row["total_sold"],
            total_revenue=row["total_revenue"],
        )
        for row in (products_res.data or [])
    ]

    return AnalyticsDashboard(
        orders=order_analytics,
        top_products=top_products,
    )
