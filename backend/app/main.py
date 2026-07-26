from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db.session import init_db
from app.db.seed import seed
from app.routers import invoices, purchase_orders, inventory, review_queue, brands, combinations, activity

app = FastAPI(
    title="PackIn.ai",
    description="Agentic carton box inventory tracker — deducts stock on "
                "invoice generation, replenishes on PO, flags anything "
                "ambiguous for human review.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten to your frontend's actual origin in production
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_db()
    seed()


app.include_router(invoices.router)
app.include_router(purchase_orders.router)
app.include_router(inventory.router)
app.include_router(review_queue.router)
app.include_router(brands.router)
app.include_router(combinations.router)
app.include_router(activity.router)


@app.get("/")
def root():
    return {"app": "PackIn.ai", "status": "running"}


@app.get("/health")
def health():
    return {"status": "ok"}
