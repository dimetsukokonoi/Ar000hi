"""
Arooohi Backend — Driver Rating & Review Routes
Feature 7: Post-ride 1-5 star rating with an optional comment

Rules enforced here, all of which exist to stop ratings being gamed:
  - You can only review a ride that actually COMPLETED.
  - Both people must have been on that ride (driver, or an accepted passenger).
  - You cannot review yourself.
  - One review per (ride, reviewer, reviewee) — the UNIQUE index does the real
    work; this module just turns the collision into a friendly 409.

Reviews are never edited or deleted, for the same reason the wallet ledger is
append-only: a rating you can quietly change afterwards is not evidence.
"""
import sqlite3
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth import get_current_user_id
from app.database import get_db

router = APIRouter()


class ReviewRequest(BaseModel):
    ride_id: str
    reviewee_id: str
    stars: int
    comment: str = ""


def _participants(conn, ride_id: str):
    """(ride_row, set of user ids on the ride) — driver plus everyone who rode."""
    ride = conn.execute("SELECT * FROM rides WHERE id = ?", (ride_id,)).fetchone()
    if not ride:
        return None, set()
    riders = conn.execute(
        """SELECT passenger_id FROM ride_passengers
           WHERE ride_id = ? AND status IN ('accepted', 'completed')""",
        (ride_id,),
    ).fetchall()
    return ride, {ride["driver_id"]} | {r["passenger_id"] for r in riders}


def rating_for(conn, user_id: str) -> dict:
    """Average rating + count for one user. Shared with the drivers listing."""
    row = conn.execute(
        """SELECT COUNT(*) AS n, COALESCE(AVG(stars), 0) AS avg_stars
           FROM reviews WHERE reviewee_id = ?""",
        (user_id,),
    ).fetchone()
    return {
        "average": round(row["avg_stars"], 2) if row["n"] else None,
        "count": row["n"],
    }


def _reviews_for(conn, target_id: str) -> dict:
    """Average, star histogram and recent comments for one user."""
    rows = conn.execute(
        """SELECT rv.id, rv.stars, rv.comment, rv.created_at, rv.ride_id,
                  u.name AS reviewer_name, r.source, r.destination
           FROM reviews rv
           JOIN users u ON u.id = rv.reviewer_id
           LEFT JOIN rides r ON r.id = rv.ride_id
           WHERE rv.reviewee_id = ?
           ORDER BY rv.created_at DESC""",
        (target_id,),
    ).fetchall()

    histogram = {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0}
    for r in rows:
        histogram[str(r["stars"])] += 1

    total = len(rows)
    average = round(sum(r["stars"] for r in rows) / total, 2) if total else None

    return {
        "average": average,
        "count": total,
        "histogram": histogram,
        "reviews": [
            {
                "id": r["id"],
                "stars": r["stars"],
                "comment": r["comment"],
                "reviewer_name": r["reviewer_name"],
                "route": (f'{r["source"]} to {r["destination"]}'
                          if r["source"] else ""),
                "created_at": r["created_at"],
            }
            for r in rows
        ],
    }


@router.post("")
def create_review(body: ReviewRequest, user_id: str = Depends(get_current_user_id)):
    """Leave a 1-5 star review with an optional comment, after a completed ride."""
    if body.stars < 1 or body.stars > 5:
        raise HTTPException(status_code=400, detail="Rating must be between 1 and 5 stars")
    if body.reviewee_id == user_id:
        raise HTTPException(status_code=400, detail="You cannot review yourself")

    conn = get_db()
    ride, people = _participants(conn, body.ride_id)
    if not ride:
        conn.close()
        raise HTTPException(status_code=404, detail="Ride not found")
    if ride["status"] != "completed":
        status = ride["status"]
        conn.close()
        raise HTTPException(
            status_code=400,
            detail=f"This ride is {status}. You can only review a completed ride.",
        )
    if user_id not in people:
        conn.close()
        raise HTTPException(status_code=403, detail="You were not part of this ride")
    if body.reviewee_id not in people:
        conn.close()
        raise HTTPException(status_code=400, detail="That person was not on this ride")

    comment = (body.comment or "").strip()[:500]
    review_id = str(uuid.uuid4())
    try:
        conn.execute(
            """INSERT INTO reviews (id, ride_id, reviewer_id, reviewee_id, stars, comment)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (review_id, body.ride_id, user_id, body.reviewee_id, body.stars, comment),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(
            status_code=409,
            detail="You have already reviewed this person for this ride",
        )

    summary = rating_for(conn, body.reviewee_id)
    conn.close()
    return {
        "message": "Thanks — your review has been recorded",
        "review_id": review_id,
        "stars": body.stars,
        "reviewee_rating": summary,
    }


@router.get("/pending")
def pending_reviews(user_id: str = Depends(get_current_user_id)):
    """Completed rides where this user still owes the driver a review.

    Drives the post-ride prompt: the app should ask once, then stop asking.
    """
    conn = get_db()
    rows = conn.execute(
        """SELECT r.id AS ride_id, r.source, r.destination, r.ended_at,
                  r.driver_id, u.name AS driver_name
           FROM ride_passengers rp
           JOIN rides r ON r.id = rp.ride_id
           JOIN users u ON u.id = r.driver_id
           WHERE rp.passenger_id = ?
             AND rp.status IN ('accepted', 'completed')
             AND r.status = 'completed'
             AND r.driver_id != ?
             AND NOT EXISTS (
                 SELECT 1 FROM reviews rv
                 WHERE rv.ride_id = r.id
                   AND rv.reviewer_id = ?
                   AND rv.reviewee_id = r.driver_id)
           ORDER BY r.ended_at DESC""",
        (user_id, user_id, user_id),
    ).fetchall()
    conn.close()
    return [
        {
            "ride_id": r["ride_id"],
            "driver_id": r["driver_id"],
            "driver_name": r["driver_name"],
            "source": r["source"],
            "destination": r["destination"],
            "ended_at": r["ended_at"],
        }
        for r in rows
    ]


@router.get("/me")
def my_reviews(user_id: str = Depends(get_current_user_id)):
    """Reviews this user has received, plus their average."""
    conn = get_db()
    data = _reviews_for(conn, user_id)
    conn.close()
    return data


@router.get("/driver/{driver_id}")
def driver_reviews(driver_id: str, user_id: str = Depends(get_current_user_id)):
    """Public profile rating: average, star histogram and recent comments."""
    conn = get_db()
    user = conn.execute("SELECT name FROM users WHERE id = ?", (driver_id,)).fetchone()
    if not user:
        conn.close()
        raise HTTPException(status_code=404, detail="User not found")
    data = _reviews_for(conn, driver_id)
    conn.close()
    return {"driver_id": driver_id, "driver_name": user["name"], **data}
