from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from aera.api import create_app
from aera.db import Database
from aera.models import OpportunityIn, PublicProfile, ResearchRequest
from aera.service import Conflict, Operations
from aera.vault import Vault

TOKEN="x"*32
def test_auth_and_private_schema(tmp_path):
    client=TestClient(create_app(str(tmp_path/"a.db"),TOKEN))
    assert client.get("/health").status_code==200
    assert client.get("/status").status_code==401
    assert client.get("/schema",headers={"Authorization":f"Bearer {TOKEN}"}).status_code==200

def test_paperwork_is_review_packet_with_blocker(tmp_path):
    db=Database(str(tmp_path/"a.db")); ops=Operations(db)
    oid=ops.opportunity(OpportunityIn(title="Candidate",category="development",summary="Unverified",source_url="https://example.com"))
    ops.paperwork(oid,PublicProfile(legal_name="Public LLC",verified_fields=["legal_name"]))
    assert db.list("packets")[0]["official_submission"] is False
    assert db.list("blockers")[0]["status"]=="open"
    assert len(db.list("inbox"))==2

def test_exact_hash_budget_and_replay_protection(tmp_path):
    db=Database(str(tmp_path/"a.db")); ops=Operations(db)
    with db.connect() as c:
        c.execute("UPDATE policy SET cash_buffer_cents=0,daily_limit_cents=500,total_limit_cents=500,spending_paused=0")
    db.insert("ledger",{"amount_cents":1000})
    aid,h=ops.research_request(ResearchRequest(query="public opportunities",model="fake",max_turns=2,reservation_cents=100))
    try: ops.decision(aid,"approved","0"*64); assert False
    except Conflict: pass
    ops.decision(aid,"approved",h); assert ops.queue(aid)
    try: ops.queue(aid); assert False
    except Conflict: pass

def test_vault_rejects_paths_and_encrypts(tmp_path):
    vault=Vault(str(tmp_path/"vault"),Fernet.generate_key().decode()); oid=vault.put(b"secret")
    assert vault.get(oid)==b"secret"
    assert (tmp_path/"vault"/oid).read_bytes()!=b"secret"
    try: vault.get("../file"); assert False
    except ValueError: pass

def test_daily_dedupe_and_restart_quarantine(tmp_path):
    db=Database(str(tmp_path/"a.db")); ops=Operations(db)
    assert ops.daily_job()==ops.daily_job()
    jid=db.insert("jobs",{"status":"running","lease_expires_at":"2000-01-01T00:00:00+00:00"})
    assert ops.quarantine_interrupted()==1
    assert db.get("jobs",jid)["status"]=="needs_review"
