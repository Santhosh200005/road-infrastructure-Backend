from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional

from backend.database.db import get_db
from backend.database import schemas, models, crud
from backend.services import detection_service
from backend.utils.security import get_current_user

router = APIRouter(prefix="/api", tags=["detection"])

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/jpg", "image/webp"}


@router.post("/detect", response_model=schemas.DetectionResponse)
async def detect(
    file: UploadFile = File(...),
    road_id: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {file.content_type}")

    if road_id and not crud.get_road(db, road_id):
        raise HTTPException(status_code=404, detail=f"road_id {road_id} not found")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    image_path = detection_service.save_upload(file_bytes, file.filename)

    try:
        result = detection_service.run_and_persist_detection(
            db, image_path=image_path, road_id=road_id, user_id=current_user.id
        )
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    return schemas.DetectionResponse(
        status="success",
        detections=[
            schemas.DetectionItem(**d) for d in result["detections"]
        ],
        count=result["count"],
        image_url=f"/uploads/{image_path.split('/')[-1]}",
        detection_ids=result["detection_ids"],
    )


@router.get("/detections", response_model=list[schemas.DetectionRecordOut])
def list_detections(road_id: Optional[str] = None, db: Session = Depends(get_db),
                     current_user: models.User = Depends(get_current_user)):
    return crud.list_detections(db, road_id=road_id)
