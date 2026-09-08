from __future__ import annotations

import hashlib, json
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from .db import Database, now
from .models import OpportunityIn, PublicProfile, ResearchRequest


def canonical_hash(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()


class Conflict(Exception): pass
class NotFound(Exception): pass


class Operations:
    def __init__(self, db: Database): self.db=db; db.init()

    def opportunity(self, item: OpportunityIn) -> str:
        data=item.model_dump(mode="json"); data.update(status="candidate",verified=False,selected=False)
        oid=self.db.insert("opportunities",data)
        for evidence in data.pop("evidence",[]): self.db.insert("evidence",{**evidence,"opportunity_id":oid})
        self.db.audit("opportunity.imported",oid); return oid

    def select(self, oid: str) -> None:
        with self.db.connect() as c:
            c.execute("BEGIN IMMEDIATE"); item=self.db.get("opportunities",oid,c)
            if not item: raise NotFound(oid)
            item.pop("id"); item["selected"]=True; item["status"]="selected"; self.db.update("opportunities",oid,item,c); self.db.audit("opportunity.selected",oid,c); c.commit()

    def paperwork(self, oid: str, profile: PublicProfile) -> str:
        if not self.db.get("opportunities",oid): raise NotFound(oid)
        allowed=("legal_name","business_state","public_business_address","website")
        mapped={k:str(getattr(profile,k)) for k in allowed if getattr(profile,k) is not None and k in profile.verified_fields}
        missing=[k for k in allowed if k not in mapped]+["ein","authorized_signature","bank_information"]
        pid=self.db.insert("packets",{"opportunity_id":oid,"status":"review","public_fields":mapped,"missing_fields":missing,"official_submission":False})
        bid=self.db.insert("blockers",{"packet_id":pid,"opportunity_id":oid,"kind":"missing_identity_fields","fields":missing,"status":"open"})
        aid=self.db.insert("approvals",{"kind":"paperwork_review","subject_id":pid,"status":"pending","hash":canonical_hash({"packet_id":pid,"public_fields":mapped})})
        self.db.insert("inbox",{"kind":"paperwork_review","subject_id":pid,"approval_id":aid,"acknowledged":False})
        self.db.insert("inbox",{"kind":"blocker","subject_id":bid,"acknowledged":False})
        return pid

    def research_request(self, request: ResearchRequest) -> tuple[str,str]:
        payload=request.model_dump(); h=canonical_hash(payload)
        aid=self.db.insert("approvals",{"kind":"research","status":"pending","hash":h,"payload":payload,"expires_at":(datetime.now(timezone.utc)+timedelta(hours=24)).isoformat(),"queued":False})
        self.db.insert("inbox",{"kind":"research_approval","subject_id":aid,"acknowledged":False}); return aid,h

    def decision(self, aid: str, decision: str, supplied_hash: str) -> None:
        with self.db.connect() as c:
            c.execute("BEGIN IMMEDIATE"); a=self.db.get("approvals",aid,c)
            if not a: raise NotFound(aid)
            if a["status"] != "pending" or a["hash"] != supplied_hash: raise Conflict("approval is stale or hash does not match")
            if datetime.fromisoformat(a["expires_at"]) <= datetime.now(timezone.utc): raise Conflict("approval expired")
            a.pop("id"); a["status"]=decision; a["decided_at"]=now(); self.db.update("approvals",aid,a,c); self.db.audit(f"approval.{decision}",aid,c); c.commit()

    def queue(self, aid: str) -> str:
        with self.db.connect() as c:
            c.execute("BEGIN IMMEDIATE"); a=self.db.get("approvals",aid,c)
            if not a or a.get("kind")!="research": raise NotFound(aid)
            if a["status"]!="approved" or a.get("queued"): raise Conflict("approval is not queueable")
            p=c.execute("SELECT * FROM policy WHERE singleton=1").fetchone(); cap=a["payload"]["reservation_cents"]
            balance=sum(x.get("amount_cents",0) for x in self.db.list("ledger")); reserved=sum(x.get("reserved_cents",0) for x in self.db.list("reservations") if x.get("accounting_active",True))
            today=datetime.now(timezone.utc).date().isoformat(); daily=sum(x.get("reserved_cents",0) for x in self.db.list("reservations") if x.get("utc_date")==today)
            if p["spending_paused"] or cap+daily>p["daily_limit_cents"] or cap+reserved>p["total_limit_cents"] or balance-reserved-cap<p["cash_buffer_cents"]: raise Conflict("budget policy prevents reservation")
            rid=self.db.insert("reservations",{"approval_id":aid,"reserved_cents":cap,"status":"reserved","accounting_active":True,"utc_date":today},con=c)
            jid=self.db.insert("jobs",{"kind":"research","approval_id":aid,"reservation_id":rid,"status":"queued","attempts":0},con=c)
            a.pop("id"); a["queued"]=True; self.db.update("approvals",aid,a,c); self.db.audit("research.queued",jid,c); c.commit(); return jid

    def daily_job(self) -> str:
        day=datetime.now(ZoneInfo("America/Denver")).date().isoformat()
        with self.db.connect() as c:
            c.execute("BEGIN IMMEDIATE"); row=c.execute("SELECT job_id FROM daily_jobs WHERE denver_date=?",(day,)).fetchone()
            if row: c.commit(); return row[0]
            jid=self.db.insert("jobs",{"kind":"daily_research","status":"blocked","reason":"specific approval required","denver_date":day},con=c)
            self.db.insert("blockers",{"job_id":jid,"kind":"research_approval_required","status":"open"},con=c)
            c.execute("INSERT INTO daily_jobs VALUES(?,?)",(day,jid)); c.commit(); return jid

    def quarantine_interrupted(self) -> int:
        count=0
        with self.db.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            rows=c.execute("SELECT * FROM records WHERE collection='jobs'").fetchall()
            for row in rows:
                job=json.loads(row["data"])
                if job.get("status")=="running" and job.get("lease_expires_at","") < now():
                    job["status"]="needs_review"; job["reason"]="expired worker lease; reconcile external effects"
                    self.db.update("jobs",row["id"],job,c); count+=1
            c.commit()
        return count

    def claim_once(self) -> dict | None:
        self.quarantine_interrupted()
        with self.db.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            row=c.execute("SELECT * FROM records WHERE collection='jobs' AND json_extract(data,'$.status')='queued' ORDER BY created_at LIMIT 1").fetchone()
            if not row: c.commit(); return None
            job=json.loads(row["data"]); job["status"]="running"; job["attempts"]=job.get("attempts",0)+1
            job["lease_expires_at"]=(datetime.now(timezone.utc)+timedelta(minutes=5)).isoformat()
            self.db.update("jobs",row["id"],job,c); c.commit(); return {"id":row["id"],**job}
