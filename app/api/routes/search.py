from fastapi import APIRouter, HTTPException, Query

from app.schemas.retrieval import SearchResponse
from app.services.retrieval import retrieve

router = APIRouter(tags=["search"])


@router.get("/search", response_model=SearchResponse)
def search(
    q: str = Query(..., description="Search query"),
    k: int = Query(default=5, ge=1, description="Number of results to return"),
) -> SearchResponse:
    if not q.strip():
        raise HTTPException(status_code=400, detail="Query must not be empty or whitespace.")

    try:
        results = retrieve(q, k)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Unexpected retrieval error.") from exc

    if not results:
        raise HTTPException(status_code=404, detail="No matching chunks found.")

    return SearchResponse(query=q, results=results, result_count=len(results))
