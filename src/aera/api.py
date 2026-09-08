from __future__ import annotations
import hmac, os
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.openapi.docs import get_swagger_ui_html
from .db import COLLECTIONS, Database
from .models import Decision, LedgerIn, OpportunityIn, OutcomeIn, PolicyIn, PublicProfile, ReconcileIn, ResearchRequest, ResolveIn
from .service import Conflict, NotFound, Operations


def create_app(path: str | None=None, token: str | None=None) -> FastAPI:
    owner=token or os.getenv("AERA_OWNER_TOKEN","")
    if len(owner)<32: raise RuntimeError("AERA_OWNER_TOKEN must contain at least 32 characters")
    db=Database(path or os.getenv("AERA_DB","runtime/aera.db")); ops=Operations(db)
    app=FastAPI(title="Aera Operations",version="0.1.0",docs_url=None,redoc_url=None,openapi_url=None)
    def auth(authorization: str=Header(default="")):
        if not hmac.compare_digest(authorization,f"Bearer {owner}"): raise HTTPException(401,"owner authentication required")
    @app.get("/health")
    def health(): return {"status":"ok"}
    @app.get("/schema",dependencies=[Depends(auth)])
    def schema(): return app.openapi()
    @app.get("/status",dependencies=[Depends(auth)])
    def status():
        with db.connect() as c: p=dict(c.execute("SELECT * FROM policy WHERE singleton=1").fetchone())
        return {"live_research_enabled":os.getenv("AERA_LIVE_RESEARCH","").lower()=="true","api_key_configured":bool(os.getenv("OPENAI_API_KEY")),"policy":p}
    @app.get("/records/{collection}",dependencies=[Depends(auth)])
    def records(collection: str):
        if collection=="policy":
            with db.connect() as c: return [dict(c.execute("SELECT * FROM policy").fetchone())]
        if collection not in COLLECTIONS: raise HTTPException(404,"unknown collection")
        return db.list(collection)
    @app.post("/opportunities",dependencies=[Depends(auth)])
    def opportunity(body: OpportunityIn): return {"id":ops.opportunity(body)}
    @app.post("/opportunities/{oid}/select",dependencies=[Depends(auth)])
    def select(oid: str): ops.select(oid); return {"status":"selected"}
    @app.post("/opportunities/{oid}/paperwork",dependencies=[Depends(auth)])
    def paperwork(oid: str, body: PublicProfile): return {"id":ops.paperwork(oid,body)}
    @app.post("/opportunities/{oid}/outcomes",dependencies=[Depends(auth)])
    def outcome(oid: str, body: OutcomeIn):
        if not db.get("opportunities",oid): raise HTTPException(404,"opportunity not found")
        return {"id":db.insert("outcomes",{"opportunity_id":oid,**body.model_dump(),"causal_proof":False})}
    @app.post("/research/requests",dependencies=[Depends(auth)])
    def research(body: ResearchRequest):
        aid,h=ops.research_request(body); return {"approval_id":aid,"hash":h}
    @app.post("/approvals/{aid}/decision",dependencies=[Depends(auth)])
    def decision(aid: str, body: Decision): ops.decision(aid,body.decision,body.payload_hash); return {"status":body.decision}
    @app.post("/approvals/{aid}/queue",dependencies=[Depends(auth)])
    def queue(aid: str): return {"job_id":ops.queue(aid)}
    @app.post("/policy",dependencies=[Depends(auth)])
    def policy(body: PolicyIn):
        with db.connect() as c: c.execute("UPDATE policy SET cash_buffer_cents=?,daily_limit_cents=?,total_limit_cents=?,spending_paused=?,updated_at=datetime('now') WHERE singleton=1",(*body.model_dump().values(),))
        return body
    @app.post("/ledger",dependencies=[Depends(auth)])
    def ledger(body: LedgerIn):
        try:
            with db.connect() as c:
                c.execute("BEGIN IMMEDIATE"); c.execute("INSERT INTO unique_events VALUES(?,datetime('now'))",(body.event_key,)); rid=db.insert("ledger",body.model_dump(),con=c); c.commit()
        except Exception as e:
            if "UNIQUE" in str(e): raise HTTPException(409,"event key already recorded")
            raise
        return {"id":rid}
    @app.post("/reservations/{rid}/reconcile",dependencies=[Depends(auth)])
    def reconcile(rid: str, body: ReconcileIn):
        with db.connect() as c:
            c.execute("BEGIN IMMEDIATE"); r=db.get("reservations",rid,c)
            if not r: raise HTTPException(404,"reservation not found")
            if r["status"]!="reserved": raise HTTPException(409,"already reconciled")
            over=body.actual_cents>r["reserved_cents"]; r.pop("id"); r.update(status="reconciled",actual_cents=body.actual_cents,receipt_reference=body.receipt_reference,accounting_active=False); db.update("reservations",rid,r,c)
            if over: c.execute("UPDATE policy SET spending_paused=1 WHERE singleton=1")
            c.commit()
        return {"status":"reconciled","overrun":over}
    @app.post("/blockers/{rid}/resolve",dependencies=[Depends(auth)])
    def resolve(rid: str, body: ResolveIn):
        with db.connect() as c:
            c.execute("BEGIN IMMEDIATE"); r=db.get("blockers",rid,c)
            if not r: raise HTTPException(404,"blocker not found")
            r.pop("id"); r.update(status="resolved",evidence_reference=body.evidence_reference); db.update("blockers",rid,r,c); c.commit()
        return {"status":"resolved"}
    @app.post("/inbox/{rid}/acknowledge",dependencies=[Depends(auth)])
    def acknowledge(rid: str):
        with db.connect() as c:
            c.execute("BEGIN IMMEDIATE"); r=db.get("inbox",rid,c)
            if not r: raise HTTPException(404,"item not found")
            r.pop("id"); r["acknowledged"]=True; db.update("inbox",rid,r,c); c.commit()
        return {"status":"acknowledged"}
    @app.post("/worker/once",dependencies=[Depends(auth)])
    def worker_once():
        job=ops.claim_once()
        return {"job":job,"note":"claimed only; live provider execution is performed by the CLI worker"}
    @app.exception_handler(NotFound)
    async def missing(_,exc): return __import__("fastapi").responses.JSONResponse({"detail":str(exc)},404)
    @app.exception_handler(Conflict)
    async def conflict(_,exc): return __import__("fastapi").responses.JSONResponse({"detail":str(exc)},409)
    return app
