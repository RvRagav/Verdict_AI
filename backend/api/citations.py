"""Citation endpoints — forward (eval → cites) + reverse (word → evals)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.api.dependencies import get_db
from backend.services import citation_service


router = APIRouter(tags=["citations"])


@router.get("/evaluations/{evaluation_id}/citations")
def for_evaluation(evaluation_id: str, conn=Depends(get_db)):
    return {"citations": citation_service.list_for_evaluation(conn, evaluation_id)}


@router.get("/words/{word_object_id}/citations")
def for_word(word_object_id: str, conn=Depends(get_db)):
    return {"citations": citation_service.list_for_word(conn, word_object_id)}


@router.get("/pages/{page_id}/citations")
def for_page(page_id: str, conn=Depends(get_db)):
    return {"citations": citation_service.list_for_page(conn, page_id)}
