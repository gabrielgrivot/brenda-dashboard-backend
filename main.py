from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import logging
from database import init_db, get_summary, get_campaigns, get_last_update
from meta_client import sync_meta_data

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Brenda Dashboard API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

scheduler = BackgroundScheduler()

@app.on_event("startup")
async def startup():
    init_db()
    sync_meta_data()
    scheduler.add_job(sync_meta_data, "interval", minutes=30, id="meta_sync")
    scheduler.start()
    logger.info("Scheduler iniciado — sincroniza a cada 30 minutos")

@app.on_event("shutdown")
async def shutdown():
    scheduler.shutdown()

@app.get("/api/summary")
def summary():
    data = get_summary()
    if not data:
        raise HTTPException(status_code=503, detail="Dados ainda não sincronizados")
    return data

@app.get("/api/campaigns")
def campaigns():
    return get_campaigns()

@app.get("/api/last-update")
def last_update():
    return {"last_update": get_last_update()}

@app.post("/api/refresh")
def refresh():
    try:
        sync_meta_data()
        return {"ok": True, "synced_at": datetime.now().isoformat()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health():
    return {"status": "ok", "time": datetime.now().isoformat()}
