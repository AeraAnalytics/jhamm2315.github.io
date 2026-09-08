"""Bounded Agents SDK adapter. Its output is never treated as verification."""
from __future__ import annotations
import asyncio, os
from pydantic import BaseModel, Field, HttpUrl


class Candidate(BaseModel):
    title: str
    category: str
    summary: str
    source_url: HttpUrl
    caveats: list[str] = Field(default_factory=list)


class ResearchResult(BaseModel):
    candidates: list[Candidate] = Field(default_factory=list, max_length=25)


class LiveResearchAdapter:
    """The only module that can invoke the external research provider."""
    async def run(self, query: str, model: str, max_turns: int) -> ResearchResult:
        if os.getenv("AERA_LIVE_RESEARCH","").lower() != "true":
            raise RuntimeError("live research is disabled")
        if not os.getenv("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY is not configured")
        # Optional dependency is imported only on an explicitly enabled live call.
        from agents import Agent, Runner, WebSearchTool
        agent=Agent(
            name="Aera opportunity researcher",
            model=model,
            tools=[WebSearchTool()],
            output_type=ResearchResult,
            instructions=("Find only opportunities within the owner's supplied scope. Return cited candidates. "
                          "Never claim funding, profit, eligibility, verification, selection, or approval."),
        )
        result=await asyncio.wait_for(Runner.run(agent,query,max_turns=max_turns),timeout=120)
        return result.final_output
