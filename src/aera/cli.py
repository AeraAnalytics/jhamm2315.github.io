from __future__ import annotations
import os, time
from pathlib import Path
import typer
from .config import load_private_env
from .api import create_app
from .db import Database
from .models import OpportunityIn, PublicProfile
from .service import Operations

load_private_env()
app=typer.Typer(no_args_is_help=True)
def path(demo=False): return "runtime/demo.db" if demo else os.getenv("AERA_DB","runtime/aera.db")

@app.command()
def init(): Database(path()).init(); typer.echo(f"Initialized {path()}")

@app.command()
def demo():
    db=Database(path(True)); ops=Operations(db)
    existing=next((item for item in db.list("opportunities") if item["title"]=="Synthetic municipal website refresh"),None)
    oid=existing["id"] if existing else ops.opportunity(OpportunityIn(title="Synthetic municipal website refresh",category="development",summary="DEMO ONLY — fictional public solicitation",source_url="https://example.com/synthetic"))
    pid=ops.paperwork(oid,PublicProfile(legal_name="Example Studio LLC",business_state="Colorado",website="https://example.com",verified_fields=["legal_name","business_state","website"]))
    typer.echo(f"DEMO ONLY opportunity={oid} packet={pid}; no calls, messages, revenue, or filings occurred")

@app.command()
def doctor():
    Database(path()).init(); typer.echo(f"database: ok ({path()})"); typer.echo(f"live research: {os.getenv('AERA_LIVE_RESEARCH','false')}"); typer.echo(f"owner token: {'configured' if len(os.getenv('AERA_OWNER_TOKEN',''))>=32 else 'not configured'}")

@app.command()
def serve(port: int=8421):
    import uvicorn
    uvicorn.run(create_app(),host="127.0.0.1",port=port)

@app.command()
def tick(): typer.echo(f"daily job: {Operations(Database(path())).daily_job()}")

@app.command()
def worker(loop: bool=False):
    ops=Operations(Database(path()))
    while True:
        ops.daily_job(); job=ops.claim_once(); typer.echo(f"worker poll complete; claimed={job['id'] if job else 'none'}")
        if not loop: break
        time.sleep(15)
