"""Admin — Analytics dashboard (calls SQL RPC functions)."""
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
    db = get_supabase_admin_client()
    order_raw = (db.rpc("get_order_analytics", {}).execute().data or [{}])[0]
    top_raw   = db.rpc("get_top_products", {"p_limit": top_products_limit}).execute().data or []

    return AnalyticsDashboard(
        orders=OrderAnalytics(
            total_orders=order_raw.get("total_orders", 0),
            pending_orders=order_raw.get("pending_orders", 0),
            paid_orders=order_raw.get("paid_orders", 0),
            failed_orders=order_raw.get("failed_orders", 0),
            cancelled_orders=order_raw.get("cancelled_orders", 0),
            total_revenue=order_raw.get("total_revenue", 0),
            revenue_today=order_raw.get("revenue_today", 0),
            revenue_this_month=order_raw.get("revenue_this_month", 0),
        ),
        top_products=[
            TopProduct(
                product_id=r["product_id"], product_name=r["product_name"],
                total_sold=r["total_sold"],  total_revenue=r["total_revenue"],
            )
            for r in top_raw
        ],
    )