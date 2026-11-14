from fastapi import APIRouter, HTTPException

from app.knowledge import load_crops
from app.schemas import CompareRotationsRequest, CompareRotationsResponse
from app.scoring import build_response

router = APIRouter(tags=["rotations"])


@router.post("/compare-rotations", response_model=CompareRotationsResponse)
def compare_rotations(request: CompareRotationsRequest) -> CompareRotationsResponse:
    crops = load_crops()
    if request.field.current_crop not in crops:
        raise HTTPException(
            status_code=422, detail=f"Unknown crop: {request.field.current_crop}"
        )
    unknown = [crop for crop in request.candidate_crops if crop not in crops]
    if unknown:
        raise HTTPException(status_code=422, detail=f"Unknown crops: {', '.join(unknown)}")
    return build_response(request)
