import sqlite3
import os
from datetime import datetime

DB_PATH = os.getenv("DB_PATH", "/tmp/dashboard.db")

def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    with _conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS summary (
            id INTEGER PRIMARY KEY DEFAULT 1,
            spend REAL DEFAULT 0, impressions INTEGER DEFAULT 0,
            reach INTEGER DEFAULT 0, clicks INTEGER DEFAULT 0,
            ctr REAL DEFAULT 0, cpm REAL DEFAULT 0, cpc REAL DEFAULT 0,
            frequency REAL DEFAULT 0, link_clicks INTEGER DEFAULT 0,
            wpp_convs INTEGER DEFAULT 0, reactions INTEGER DEFAULT 0,
            engagement INTEGER DEFAULT 0, video_plays_3s INTEGER DEFAULT 0,
            cost_per_wpp REAL DEFAULT 0, updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS campaigns (
            campaign_id TEXT PRIMARY KEY, name TEXT, objective TEXT,
            status TEXT, camp_type TEXT, spend REAL DEFAULT 0,
            impressions INTEGER DEFAULT 0, reach INTEGER DEFAULT 0,
            clicks INTEGER DEFAULT 0, ctr REAL DEFAULT 0,
            link_clicks INTEGER DEFAULT 0, wpp_convs INTEGER DEFAULT 0,
            reactions INTEGER DEFAULT 0, engagement INTEGER DEFAULT 0,
            video_plays_3s INTEGER DEFAULT 0, cost_per_wpp REAL DEFAULT 0,
            updated_at TEXT
        );
        """)

def upsert_summary(data):
    data["updated_at"] = datetime.now().isoformat()
    with _conn() as c:
        c.execute("""
            INSERT INTO summary (id,spend,impressions,reach,clicks,ctr,cpm,cpc,frequency,
                link_clicks,wpp_convs,reactions,engagement,video_plays_3s,cost_per_wpp,updated_at)
            VALUES (1,:spend,:impressions,:reach,:clicks,:ctr,:cpm,:cpc,:frequency,
                :link_clicks,:wpp_convs,:reactions,:engagement,:video_plays_3s,:cost_per_wpp,:updated_at)
            ON CONFLICT(id) DO UPDATE SET
                spend=excluded.spend,impressions=excluded.impressions,reach=excluded.reach,
                clicks=excluded.clicks,ctr=excluded.ctr,cpm=excluded.cpm,cpc=excluded.cpc,
                frequency=excluded.frequency,link_clicks=excluded.link_clicks,
                wpp_convs=excluded.wpp_convs,reactions=excluded.reactions,
                engagement=excluded.engagement,video_plays_3s=excluded.video_plays_3s,
                cost_per_wpp=excluded.cost_per_wpp,updated_at=excluded.updated_at
        """, data)

def upsert_campaign(data):
    data["updated_at"] = datetime.now().isoformat()
    with _conn() as c:
        c.execute("""
            INSERT INTO campaigns (campaign_id,name,objective,status,camp_type,spend,impressions,
                reach,clicks,ctr,link_clicks,wpp_convs,reactions,engagement,video_plays_3s,cost_per_wpp,updated_at)
            VALUES (:campaign_id,:name,:objective,:status,:camp_type,:spend,:impressions,
                :reach,:clicks,:ctr,:link_clicks,:wpp_convs,:reactions,:engagement,:video_plays_3s,:cost_per_wpp,:updated_at)
            ON CONFLICT(campaign_id) DO UPDATE SET
                name=excluded.name,objective=excluded.objective,status=excluded.status,
                camp_type=excluded.camp_type,spend=excluded.spend,impressions=excluded.impressions,
                reach=excluded.reach,clicks=excluded.clicks,ctr=excluded.ctr,
                link_clicks=excluded.link_clicks,wpp_convs=excluded.wpp_convs,
                reactions=excluded.reactions,engagement=excluded.engagement,
                video_plays_3s=excluded.video_plays_3s,cost_per_wpp=excluded.cost_per_wpp,
                updated_at=excluded.updated_at
        """, data)

def get_summary():
    with _conn() as c:
        row = c.execute("SELECT * FROM summary WHERE id=1").fetchone()
        return dict(row) if row else None

def get_campaigns():
    with _conn() as c:
        rows = c.execute("SELECT * FROM campaigns ORDER BY engagement DESC").fetchall()
        camps = [dict(r) for r in rows]
        total = sum(r["engagement"] for r in camps) or 1
        for i, r in enumerate(camps):
            r["rank"] = i + 1
            r["bar_pct"] = round(r["engagement"] / total * 100, 1)
        return camps

def get_last_update():
    with _conn() as c:
        row = c.execute("SELECT updated_at FROM summary WHERE id=1").fetchone()
        if row and row["updated_at"]:
            dt = datetime.fromisoformat(row["updated_at"])
            return dt.strftime("%d/%m às %H:%M")
        return "—"
