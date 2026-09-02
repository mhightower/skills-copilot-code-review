"""
Announcement endpoints for the High School Management System API
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..database import announcements_collection, teachers_collection

router = APIRouter(
    prefix="/announcements",
    tags=["announcements"]
)


class AnnouncementPayload(BaseModel):
    title: str
    message: str
    start_date: Optional[str] = None
    expires_at: str
    is_active: bool = True


def _require_teacher(username: Optional[str]) -> Dict[str, Any]:
    if not username:
        raise HTTPException(status_code=401, detail="Authentication required for this action")

    teacher = teachers_collection.find_one({"_id": username})
    if not teacher:
        raise HTTPException(status_code=401, detail="Invalid teacher credentials")

    return teacher


def _serialize_announcement(announcement: Dict[str, Any]) -> Dict[str, Any]:
    announcement_copy = dict(announcement)
    announcement_copy["id"] = str(announcement_copy.pop("_id"))
    return announcement_copy


def _get_active_filter() -> Dict[str, Any]:
    today = datetime.utcnow().strftime("%Y-%m-%d")
    return {
        "is_active": True,
        "expires_at": {"$gte": today},
        "$or": [
            {"start_date": {"$exists": False}},
            {"start_date": None},
            {"start_date": ""},
            {"start_date": {"$lte": today}},
        ],
    }


@router.get("", response_model=List[Dict[str, Any]])
@router.get("/", response_model=List[Dict[str, Any]])
def get_announcements() -> List[Dict[str, Any]]:
    """Get all announcements, sorted by most urgent upcoming expiration date first."""
    announcements = []
    for announcement in announcements_collection.find({}).sort("expires_at", 1):
        announcements.append(_serialize_announcement(announcement))
    return announcements


@router.get("/active", response_model=List[Dict[str, Any]])
def get_active_announcements() -> List[Dict[str, Any]]:
    """Get announcements currently visible to students and staff."""
    announcements = []
    for announcement in announcements_collection.find(_get_active_filter()).sort("expires_at", 1):
        announcements.append(_serialize_announcement(announcement))
    return announcements


@router.post("", response_model=Dict[str, Any])
def create_announcement(payload: AnnouncementPayload, teacher_username: Optional[str] = Query(None)) -> Dict[str, Any]:
    """Add a new announcement. Requires teacher authentication."""
    _require_teacher(teacher_username)

    announcement_data = payload.model_dump(exclude_none=True)
    if not announcement_data.get("title", "").strip():
        raise HTTPException(status_code=400, detail="Title is required")
    if not announcement_data.get("message", "").strip():
        raise HTTPException(status_code=400, detail="Message is required")
    if not announcement_data.get("expires_at"):
        raise HTTPException(status_code=400, detail="Expiration date is required")

    if announcement_data.get("start_date") == "":
        announcement_data.pop("start_date")

    result = announcements_collection.insert_one(announcement_data)
    created = announcements_collection.find_one({"_id": result.inserted_id})
    return _serialize_announcement(created)


@router.put("/{announcement_id}", response_model=Dict[str, Any])
def update_announcement(
    announcement_id: str,
    payload: AnnouncementPayload,
    teacher_username: Optional[str] = Query(None),
) -> Dict[str, Any]:
    """Update an existing announcement. Requires teacher authentication."""
    _require_teacher(teacher_username)

    announcement_data = payload.model_dump(exclude_none=True)
    if not announcement_data.get("title", "").strip():
        raise HTTPException(status_code=400, detail="Title is required")
    if not announcement_data.get("message", "").strip():
        raise HTTPException(status_code=400, detail="Message is required")
    if not announcement_data.get("expires_at"):
        raise HTTPException(status_code=400, detail="Expiration date is required")
    if announcement_data.get("start_date") == "":
        announcement_data.pop("start_date")

    result = announcements_collection.update_one(
        {"_id": announcement_id},
        {"$set": announcement_data}
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Announcement not found")

    updated = announcements_collection.find_one({"_id": announcement_id})
    return _serialize_announcement(updated)


@router.delete("/{announcement_id}", response_model=Dict[str, str])
def delete_announcement(announcement_id: str, teacher_username: Optional[str] = Query(None)) -> Dict[str, str]:
    """Delete an announcement. Requires teacher authentication."""
    _require_teacher(teacher_username)

    result = announcements_collection.delete_one({"_id": announcement_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Announcement not found")

    return {"message": "Announcement deleted successfully"}
