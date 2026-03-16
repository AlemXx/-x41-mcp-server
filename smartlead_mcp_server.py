"""
X41 Command Center — Smartlead MCP Server
Gives Claude real-time access to Smartlead campaign data.
"""
 
import os
import json
import httpx
from mcp.server.fastmcp import FastMCP
 
# --- Config ---
API_KEY = os.environ.get("SMARTLEAD_API_KEY", "")
BASE_URL = "https://server.smartlead.ai/api/v1"
 
mcp = FastMCP("X41 Command Center")
 
 
async def _get(path: str, params: dict = None) -> dict:
    url = f"{BASE_URL}{path}"
    p = {"api_key": API_KEY}
    if params:
        p.update(params)
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, params=p)
        if r.status_code == 429:
            return {"error": "Rate limit hit. Wait 60 seconds and try again."}
        if r.status_code == 404:
            return {"error": f"Not found: {path}"}
        if r.status_code >= 400:
            return {"error": f"API error {r.status_code}: {r.text[:200]}"}
        return r.json()
 
 
@mcp.tool()
async def smartlead_list_campaigns() -> str:
    """List all campaigns with IDs, names, and statuses."""
    data = await _get("/campaigns")
    if isinstance(data, dict) and "error" in data:
        return json.dumps(data)
    campaigns = []
    for c in data:
        campaigns.append({"id": c.get("id"), "name": c.get("name"), "status": c.get("status"), "created_at": c.get("created_at")})
    return json.dumps(campaigns, indent=2)
 
 
@mcp.tool()
async def smartlead_get_campaign_stats(campaign_id: int) -> str:
    """Get detailed stats for one campaign: sent, opens, replies, bounces, rates."""
    data = await _get(f"/campaigns/{campaign_id}/analytics")
    if isinstance(data, dict) and "error" in data:
        return json.dumps(data)
    sent = data.get("sent_count", 0)
    stats = {
        "campaign_id": data.get("id"), "campaign_name": data.get("name"), "status": data.get("status"),
        "sent_count": sent, "open_count": data.get("open_count", 0), "click_count": data.get("click_count", 0),
        "reply_count": data.get("reply_count", 0), "bounce_count": data.get("bounce_count", 0),
        "unsubscribed_count": data.get("unsubscribed_count", 0),
        "open_rate": round(data.get("open_count", 0) / sent * 100, 1) if sent else 0,
        "reply_rate": round(data.get("reply_count", 0) / sent * 100, 1) if sent else 0,
        "bounce_rate": round(data.get("bounce_count", 0) / sent * 100, 1) if sent else 0,
    }
    return json.dumps(stats, indent=2)
 
 
@mcp.tool()
async def smartlead_get_all_campaign_stats() -> str:
    """Get stats for ALL campaigns in one call."""
    campaigns = await _get("/campaigns")
    if isinstance(campaigns, dict) and "error" in campaigns:
        return json.dumps(campaigns)
    results = []
    for c in campaigns:
        cid = c.get("id")
        data = await _get(f"/campaigns/{cid}/analytics")
        if isinstance(data, dict) and "error" in data:
            continue
        sent = data.get("sent_count", 0)
        results.append({
            "campaign_id": cid, "campaign_name": data.get("name", c.get("name")),
            "status": data.get("status", c.get("status")), "sent_count": sent,
            "open_count": data.get("open_count", 0), "reply_count": data.get("reply_count", 0),
            "bounce_count": data.get("bounce_count", 0),
            "open_rate": round(data.get("open_count", 0) / sent * 100, 1) if sent else 0,
            "reply_rate": round(data.get("reply_count", 0) / sent * 100, 1) if sent else 0,
            "bounce_rate": round(data.get("bounce_count", 0) / sent * 100, 1) if sent else 0,
        })
    return json.dumps(results, indent=2)
 
 
@mcp.tool()
async def smartlead_get_campaign_leads(campaign_id: int, offset: int = 0, limit: int = 100) -> str:
    """Get all leads in a campaign with their status and category."""
    data = await _get(f"/campaigns/{campaign_id}/leads", {"offset": offset, "limit": limit})
    if isinstance(data, dict) and "error" in data:
        return json.dumps(data)
    leads = []
    for item in data.get("data", []):
        lead = item.get("lead", {})
        leads.append({"lead_id": lead.get("id"), "email": lead.get("email"), "first_name": lead.get("first_name"),
                       "last_name": lead.get("last_name"), "company": lead.get("company_name"),
                       "status": item.get("status"), "lead_category": item.get("lead_category_id")})
    return json.dumps({"total": data.get("total_leads", 0), "leads": leads}, indent=2)
 
 
@mcp.tool()
async def smartlead_get_lead_messages(campaign_id: int, lead_id: int) -> str:
    """Get full message history for a specific lead."""
    data = await _get(f"/campaigns/{campaign_id}/leads/{lead_id}/message-history")
    if isinstance(data, dict) and "error" in data:
        return json.dumps(data)
    return json.dumps(data, indent=2, default=str)
 
 
@mcp.tool()
async def smartlead_search_lead_by_email(email: str) -> str:
    """Find a lead across all campaigns by email address."""
    campaigns = await _get("/campaigns")
    if isinstance(campaigns, dict) and "error" in campaigns:
        return json.dumps(campaigns)
    found = []
    for c in campaigns:
        cid = c.get("id")
        data = await _get(f"/campaigns/{cid}/leads", {"offset": 0, "limit": 100})
        if isinstance(data, dict) and "error" in data:
            continue
        for item in data.get("data", []):
            lead = item.get("lead", {})
            if lead.get("email", "").lower() == email.lower():
                found.append({"campaign_id": cid, "campaign_name": c.get("name"), "lead_id": lead.get("id"),
                               "email": lead.get("email"), "status": item.get("status"), "lead_category": item.get("lead_category_id")})
    return json.dumps(found, indent=2)
 
 
@mcp.tool()
async def smartlead_get_lead_categories(campaign_id: int) -> str:
    """Get category breakdown for a campaign."""
    data = await _get(f"/campaigns/{campaign_id}/leads", {"offset": 0, "limit": 500})
    if isinstance(data, dict) and "error" in data:
        return json.dumps(data)
    categories = {}
    for item in data.get("data", []):
        cat = item.get("lead_category_id") or "uncategorized"
        categories[cat] = categories.get(cat, 0) + 1
    return json.dumps({"campaign_id": campaign_id, "categories": categories}, indent=2)
 
 
@mcp.tool()
async def smartlead_get_inbox_replies(offset: int = 0, limit: int = 50) -> str:
    """Get recent replies from Master Inbox."""
    data = await _get("/inbox/emails", {"offset": offset, "limit": limit})
    if isinstance(data, dict) and "error" in data:
        return json.dumps(data)
    return json.dumps(data, indent=2, default=str)
 
 
@mcp.tool()
async def smartlead_get_analytics_overall() -> str:
    """Get account-wide aggregated stats across all campaigns."""
    campaigns = await _get("/campaigns")
    if isinstance(campaigns, dict) and "error" in campaigns:
        return json.dumps(campaigns)
    totals = {"total_campaigns": 0, "active_campaigns": 0, "total_sent": 0,
              "total_opens": 0, "total_replies": 0, "total_bounces": 0}
    for c in campaigns:
        cid = c.get("id")
        totals["total_campaigns"] += 1
        if c.get("status") == "ACTIVE":
            totals["active_campaigns"] += 1
        data = await _get(f"/campaigns/{cid}/analytics")
        if isinstance(data, dict) and "error" in data:
            continue
        totals["total_sent"] += data.get("sent_count", 0)
        totals["total_opens"] += data.get("open_count", 0)
        totals["total_replies"] += data.get("reply_count", 0)
        totals["total_bounces"] += data.get("bounce_count", 0)
    if totals["total_sent"] > 0:
        totals["overall_open_rate"] = round(totals["total_opens"] / totals["total_sent"] * 100, 1)
        totals["overall_reply_rate"] = round(totals["total_replies"] / totals["total_sent"] * 100, 1)
        totals["overall_bounce_rate"] = round(totals["total_bounces"] / totals["total_sent"] * 100, 1)
    return json.dumps(totals, indent=2)
 
 
if __name__ == "__main__":
    import sys
    transport = "stdio"
    for i, arg in enumerate(sys.argv):
        if arg == "--transport" and i + 1 < len(sys.argv):
            transport = sys.argv[i + 1]
    if transport == "http":
        import uvicorn
        from starlette.applications import Starlette
        from starlette.routing import Route, Mount
        from starlette.responses import JSONResponse
        from mcp.server.sse import SseServerTransport

        sse = SseServerTransport("/messages/")

        async def handle_sse(request):
            async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
                await mcp._mcp_server.run(streams[0], streams[1], mcp._mcp_server.create_initialization_options())

        async def health(request):
            return JSONResponse({"status": "ok", "server": "X41 Command Center MCP"})

        app = Starlette(routes=[
            Route("/health", health),
            Route("/sse", endpoint=handle_sse),
            Mount("/messages/", app=sse.handle_post_message),
        ])

        port = int(os.environ.get("PORT", "10000"))
        uvicorn.run(app, host="0.0.0.0", port=port)
    else:
        mcp.run(transport="stdio")
 
