"""Deterministic routing of technical difficulty away from human residuals."""
from __future__ import annotations
import re

def classify_technical_route(title:str,body:str)->dict[str,str]:
 text=f'{title}\n{body}'.lower()
 if ('monthly or yearly' in text or 'desired result is not specified' in text):return {'route':'needs_human','reason':'missing_normative_decision','missing':'billing cadence: monthly or yearly'}
 if re.search(r'\b(split|break)\b.*\b(god|large|monolith)',text):return {'route':'split','reason':'technical_split'}
 if re.search(r'\b(bump|upgrade|dependency|adapter|migration|migrate|htmx|fragment|refactor)\b',text):return {'route':'implement','reason':'technical_implement'}
 return {'route':'implement','reason':'technical_implement'}
