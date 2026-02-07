from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from backend.app.routes import auth, accounts, bank_accounts, transactions, categories, budgets, reports, csv_mappings, ledgers, receipts, passkey, admin

app = FastAPI(
    title="Regnskap API",
    description="Personal accounting application with double-entry bookkeeping",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(passkey.router, prefix="/api")
app.include_router(ledgers.router, prefix="/api")
app.include_router(accounts.router, prefix="/api")
app.include_router(bank_accounts.router, prefix="/api")
app.include_router(transactions.router, prefix="/api")
app.include_router(categories.router, prefix="/api")
app.include_router(budgets.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
app.include_router(csv_mappings.router, prefix="/api")
app.include_router(receipts.router, prefix="/api")
app.include_router(admin.router, prefix="/api")


@app.get("/api/health")
def health_check():
    return {"status": "healthy"}


# PWA routes (must be before mount)
@app.get("/kvittering")
def mobile_app():
    return FileResponse("frontend/kvittering.html")


@app.get("/manifest.json")
def manifest():
    return FileResponse("frontend/manifest.json")


@app.get("/sw.js")
def service_worker():
    return FileResponse("frontend/sw.js")


app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
