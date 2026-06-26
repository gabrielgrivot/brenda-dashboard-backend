import os
import requests
import logging
from datetime import datetime, date
from database import upsert_summary, upsert_campaign

logger = logging.getLogger(__name__)

META_BASE = "https://graph.facebook.com/v19.0"
TOKEN     = os.getenv("META_ACCESS_TOKEN", "")
ACCOUNT   = os.getenv("META_AD_ACCOUNT_ID", "")

# Campos para account-level (sem status)
FIELDS_ACCOUNT = ["spend","impressions","reach","clicks","ctr","cpm","cpc","frequency","actions","cost_per_action_type"]

# Campos para campaign-level insights (sem status e objective - esses vêm separado)
FIELDS_CAMPAIGN_INSIGHTS = ["campaign_id","campaign_name","spend","impressions","reach","clicks","ctr","cpm","cpc","actions","cost_per_action_type"]

def _get(path, params):
    params["access_token"] = TOKEN
    r = requests.get(f"{META_BASE}/{path}", params=params, timeout=30)
    r.raise_for_status()
    return r.json()

def _time_range_str():
    today = date.today()
    return f'{{"since":"2025-05-16","until":"{today.isoformat()}"}}'

def _extract_action(actions, action_type):
    for a in (actions or []):
        if a.get("action_type") == action_type:
            return int(float(a.get("value", 0)))
    return 0

def _extract_cost(cost_list, action_type):
    for a in (cost_list or []):
        if a.get("action_type") == action_type:
            return round(float(a.get("value", 0)), 2)
    return 0.0

def sync_meta_data():
    if not TOKEN or not ACCOUNT:
        logger.warning("Token não configurado — usando dados demo")
        _load_demo_data()
        return
    try:
        _sync_account()
        _sync_campaigns()
        logger.info("Sync Meta concluído: %s", datetime.now().isoformat())
    except Exception as e:
        logger.error("Erro no sync Meta: %s", e)
        _load_demo_data()

def _sync_account():
    data = _get(f"act_{ACCOUNT}/insights", {
        "fields": ",".join(FIELDS_ACCOUNT),
        "time_range": _time_range_str(),
        "level": "account",
    })
    row = (data.get("data") or [{}])[0]
    actions = row.get("actions", [])
    cost_actions = row.get("cost_per_action_type", [])

    link_clicks = _extract_action(actions, "link_click")
    wpp_convs   = _extract_action(actions, "onsite_conversion.messaging_conversation_started_7d")
    if wpp_convs == 0:
        wpp_convs = _extract_action(actions, "onsite_conversion.total_messaging_connection")
    reactions   = _extract_action(actions, "post_reaction")
    engagement  = _extract_action(actions, "page_engagement")
    video_plays = _extract_action(actions, "video_view")
    cost_conv   = _extract_cost(cost_actions, "onsite_conversion.messaging_conversation_started_7d")

    upsert_summary({
        "spend":          round(float(row.get("spend", 0)), 2),
        "impressions":    int(row.get("impressions", 0)),
        "reach":          int(row.get("reach", 0)),
        "clicks":         int(row.get("clicks", 0)),
        "ctr":            round(float(row.get("ctr", 0)), 2),
        "cpm":            round(float(row.get("cpm", 0)), 2),
        "cpc":            round(float(row.get("cpc", 0)), 2),
        "frequency":      round(float(row.get("frequency", 0)), 2),
        "link_clicks":    link_clicks,
        "wpp_convs":      wpp_convs,
        "reactions":      reactions,
        "engagement":     engagement,
        "video_plays_3s": video_plays,
        "cost_per_wpp":   cost_conv,
    })

def _sync_campaigns():
    # Busca insights por campanha
    insights_data = _get(f"act_{ACCOUNT}/insights", {
        "fields": ",".join(FIELDS_CAMPAIGN_INSIGHTS),
        "time_range": _time_range_str(),
        "level": "campaign",
        "limit": 50,
    })

    # Busca status das campanhas separadamente
    campaigns_data = _get(f"act_{ACCOUNT}/campaigns", {
        "fields": "id,name,objective,status",
        "limit": 50,
    })
    
    # Cria dicionário de status por campaign_id
    status_map = {}
    for c in (campaigns_data.get("data") or []):
        status_raw = c.get("status", "PAUSED")
        status = "active" if status_raw == "ACTIVE" else "done" if status_raw in ("COMPLETED","ARCHIVED") else "off"
        obj = c.get("objective", "")
        status_map[c["id"]] = {
            "status": status,
            "objective": obj,
            "camp_type": "eng" if "ENGAGEMENT" in obj else "link"
        }

    for row in (insights_data.get("data") or []):
        actions      = row.get("actions", [])
        cost_actions = row.get("cost_per_action_type", [])
        camp_id      = row.get("campaign_id", "")
        camp_info    = status_map.get(camp_id, {"status":"off","objective":"","camp_type":"link"})

        wpp = _extract_action(actions, "onsite_conversion.messaging_conversation_started_7d")
        if wpp == 0:
            wpp = _extract_action(actions, "onsite_conversion.total_messaging_connection")

        upsert_campaign({
            "campaign_id":    camp_id,
            "name":           row.get("campaign_name", ""),
            "objective":      camp_info["objective"],
            "status":         camp_info["status"],
            "camp_type":      camp_info["camp_type"],
            "spend":          round(float(row.get("spend", 0)), 2),
            "impressions":    int(row.get("impressions", 0)),
            "reach":          int(row.get("reach", 0)),
            "clicks":         int(row.get("clicks", 0)),
            "ctr":            round(float(row.get("ctr", 0)), 2),
            "link_clicks":    _extract_action(actions, "link_click"),
            "wpp_convs":      wpp,
            "reactions":      _extract_action(actions, "post_reaction"),
            "engagement":     _extract_action(actions, "page_engagement"),
            "video_plays_3s": _extract_action(actions, "video_view"),
            "cost_per_wpp":   _extract_cost(cost_actions, "onsite_conversion.messaging_conversation_started_7d"),
        })

def _load_demo_data():
    upsert_summary({
        "spend":188.90,"impressions":0,"reach":0,"clicks":0,
        "ctr":0,"cpm":0,"cpc":0.22,"frequency":0,
        "link_clicks":877,"wpp_convs":16,"reactions":301,
        "engagement":7749,"video_plays_3s":6416,"cost_per_wpp":11.81,
    })
    for c in [
        {"campaign_id":"1","name":'Post "sempre me sinto na obrigação…"',"objective":"LINK_CLICKS","status":"done","camp_type":"link","spend":0,"impressions":0,"reach":0,"clicks":0,"ctr":0,"link_clicks":677,"wpp_convs":1,"reactions":168,"engagement":4758,"video_plays_3s":3902,"cost_per_wpp":0},
        {"campaign_id":"2","name":'Post "sempre me sinto na obrigação…" (ativa)',"objective":"LINK_CLICKS","status":"active","camp_type":"link","spend":0,"impressions":0,"reach":0,"clicks":0,"ctr":0,"link_clicks":122,"wpp_convs":0,"reactions":35,"engagement":1115,"video_plays_3s":958,"cost_per_wpp":0},
        {"campaign_id":"3","name":'Post "Tá com dúvida de por onde…"',"objective":"LINK_CLICKS","status":"off","camp_type":"link","spend":0,"impressions":0,"reach":0,"clicks":0,"ctr":0,"link_clicks":69,"wpp_convs":0,"reactions":45,"engagement":966,"video_plays_3s":848,"cost_per_wpp":0},
        {"campaign_id":"4","name":"Engajamento / WhatsApp — War 4km","objective":"OUTCOME_ENGAGEMENT","status":"off","camp_type":"eng","spend":0,"impressions":0,"reach":0,"clicks":0,"ctr":0,"link_clicks":22,"wpp_convs":8,"reactions":32,"engagement":330,"video_plays_3s":271,"cost_per_wpp":0},
        {"campaign_id":"5","name":"Engajamento / WhatsApp — Agenda Aberta","objective":"OUTCOME_ENGAGEMENT","status":"off","camp_type":"eng","spend":0,"impressions":0,"reach":0,"clicks":0,"ctr":0,"link_clicks":9,"wpp_convs":5,"reactions":21,"engagement":256,"video_plays_3s":222,"cost_per_wpp":0},
        {"campaign_id":"6","name":"Engajamento / WhatsApp — War 2km","objective":"OUTCOME_ENGAGEMENT","status":"off","camp_type":"eng","spend":0,"impressions":0,"reach":0,"clicks":0,"ctr":0,"link_clicks":7,"wpp_convs":3,"reactions":30,"engagement":324,"video_plays_3s":285,"cost_per_wpp":0},
    ]:
        upsert_campaign(c)
