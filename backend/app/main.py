from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from app.db.session import init_db
from app.db.seed import seed
from app.config import FRONTEND_ORIGIN
from app.core.security import get_current_user
from app.routers import (
    invoices, purchase_orders, inventory, review_queue, brands,
    combinations, activity, notify, auth,
)

app = FastAPI(
    title="PackIn.ai",
    description="Agentic carton box inventory tracker — deducts stock on "
                "invoice generation, replenishes on PO, flags anything "
                "ambiguous for human review.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN] if FRONTEND_ORIGIN != "*" else ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_db()
    seed()


# /auth/login and /auth/me are intentionally NOT behind get_current_user —
# you need to be able to log in before you have a token. Every other
# router requires a valid token, protecting all data-changing endpoints.
app.include_router(auth.router)

protected = [Depends(get_current_user)]
app.include_router(invoices.router, dependencies=protected)
app.include_router(purchase_orders.router, dependencies=protected)
app.include_router(inventory.router, dependencies=protected)
app.include_router(review_queue.router, dependencies=protected)
app.include_router(brands.router, dependencies=protected)
app.include_router(combinations.router, dependencies=protected)
app.include_router(activity.router, dependencies=protected)
app.include_router(notify.router, dependencies=protected)


@app.get("/")
def root():
    return {"app": "PackIn.ai", "status": "running"}


@app.get("/health")
def health():
    return {"status": "ok"}
