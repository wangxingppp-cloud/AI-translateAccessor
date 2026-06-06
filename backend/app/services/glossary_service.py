"""Glossary management service."""
import time
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..db.models import Glossary, GlossaryTerm
import uuid


class GlossaryService:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, name: str, terms: list[dict], source_lang="en", target_lang="zh") -> Glossary:
        g = Glossary(id=str(uuid.uuid4()), name=name, source_lang=source_lang,
                     target_lang=target_lang, created_at=time.time(), updated_at=time.time())
        self.db.add(g)
        for t in terms:
            self.db.add(GlossaryTerm(
                id=str(uuid.uuid4()), glossary_id=g.id,
                source_term=t["source"], target_term=t["target"],
                category=t.get("category", ""), priority=t.get("priority", 0),
                created_at=time.time(),
            ))
        await self.db.commit()
        return g

    async def list_all(self):
        q = select(Glossary).order_by(Glossary.created_at.desc())
        result = await self.db.execute(q)
        return result.scalars().all()

    async def get(self, glossary_id: str):
        g = await self.db.get(Glossary, glossary_id)
        if not g:
            return None
        q = select(GlossaryTerm).where(GlossaryTerm.glossary_id == glossary_id)
        result = await self.db.execute(q)
        terms = result.scalars().all()
        return {"glossary": g, "terms": list(terms)}

    async def delete(self, glossary_id: str):
        g = await self.db.get(Glossary, glossary_id)
        if g:
            await self.db.delete(g)
            await self.db.commit()

    async def get_terms_as_list(self, glossary_id: str) -> list[dict]:
        """Get terms as simple dict list for prompt injection."""
        g = await self.get(glossary_id)
        if not g:
            return []
        return [{"source": t.source_term, "target": t.target_term} for t in g["terms"]]
