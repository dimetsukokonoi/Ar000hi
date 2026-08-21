"""
Arooohi Backend — Driver Rating & Review Routes
Feature 7: Driver Rating & Review

Rules enforced here (and, for the last one, at the DB level too):
  - you may only review a ride you actually took part in;
  - only after the ride is `completed` — you cannot rate a ride mid-trip;
  - only the counterpart, never yourself;
  - exactly once per (ride, reviewer, reviewee) — the UNIQUE constraint on
    `reviews` is the real guard, the pre-check just yields a friendlier 409.
"""
import uuid
import sqlite3
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from app.database import get_db
from app.auth import get_current_user_id

router = APIRouter()

MAX_COMMENT_LEN = 500


class ReviewRequest(BaseModel):
    ride_id: str
    reviewee_id: str
    stars: int
    comment: str = ""


def _participants(conn, ride_id: str):
    """(ride_row, set_of_user_ids_on_the_ride) — driver plus everyone who rode."""
    ride = conn.execute("SELECT * FROM rides WHERE id = ?", (ride_id,)).fetchone()
    if not ride:
        return None, set()
    riders = conn.execute(
        """SELECT passenger_id FROM ride_passengers
           WHERE ride_id = ? AND status IN ('accepted', 'completed')""",
        (ride_id,)
    ).fetchall()
    return ride, {ride["driver_id"], *(r["passenger_id"] for r in riders)}


def rating_for(conn, user_id: str) -> dict:
    """Average rating + count for one user. Shared with the drivers listing."""
    row = conn.execute(
        """SELECT COUNT(*) AS n, COALESCE(AVG(stars), 0) AS avg_stars
           FROM reviews WHERE reviewee_id = ?""",
        (user_id,)
    ).fetchone()
    return {
        "average": round(row["avg_stars"], 2) if row["n"] else None,
        "count": row["n"],
    }


@router.post("")
def create_review(body: ReviewRequest, user_id: str = Depends(get_current_user_id)):
    """Leave a 1-5 star review with an optional comment, after a completed ride."""
    if body.stars < 1 or body.stars > 5:
        raise HTTPException(status_code=400, detail="Rating must be between 1 and 5 stars")
    if body.reviewee_id == user_id:
        raise HTTPException(status_code=400, detail="You cannot review yourself")

    comment = (body.comment or "").strip()
    if len(comment) > MAX_COMMENT_LEN:
        raise HTTPException(
            status_code=400,
            detail=f"Comment must be {MAX_COMMENT_LEN} characters or fewer",
        )

    conn = get_db()
    ride, people = _participants(conn, body.ride_id)
    if not ride:
        conn.close()
        raise HTTPException(status_code=404, detail="Ride not found")
    if user_id not in people:
        conn.close()
        raise HTTPException(status_code=403, detail="Only ride participants can leave a review")
    if body.reviewee_id not in people:
        conn.close()
        raise HTTPException(status_code=400, detail="That person was not on this ride")
    if ride["status"] != "completed":
        conn.close()
        raise HTTPException(
            status_code=400, detail="You can only review a ride after it is completed"
        )

    review_id = str(uuid.uuid4())
    try:
        conn.execute(
            """INSERT INTO reviews (id, ride_id, reviewer_id, reviewee_id, stars, comment)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (review_id, body.ride_id, user_id, body.reviewee_id, body.stars, comment)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(
            status_code=409, detail="You have already reviewed this person for this ride"
        )

    summary = rating_for(conn, body.reviewee_id)
    conn.close()
    return {
        "message": "Thanks — your review has been posted",
        "review_id": review_id,
        "stars": body.stars,
        "reviewee_rating": summary,
    }


@router.get("/pending")
def pending_reviews(user_id: str = Depends(get_current_user_id)):
    """Completed rides where this user still owes the driver a review.

    Passenger-side only: this is what drives the "Rate your driver" prompt.
    """
    conn = get_db()
    rows = conn.execute(
        """SELECT r.id AS ride_id, r.source, r.destination, r.ended_at,
                  r.driver_id, u.name AS driver_name
           FROM rides r
           JOIN users u ON r.driver_id = u.id
           JOIN ride_passengers rp ON rp.ride_id = r.id
           WHERE rp.passenger_id = ?
             AND rp.status IN ('accepted', 'completed')
             AND r.status = 'completed'
             AND r.driver_id != ?
             AND NOT EXISTS (
                 SELECT 1 FROM reviews rv
                 WHERE rv.ride_id = r.id AND rv.reviewer_id = ? AND rv.reviewee_id = r.driver_id
             )
           ORDER BY r.ended_at DESC""",
        (user_id, user_id, user_id)
    ).fetchall()
    conn.close()

    return {
        "pending": [
            {
                "ride_id": r["ride_id"],
                "source": r["source"],
                "destination": r["destination"],
                "ended_at": r["ended_at"],
                "driver_id": r["driver_id"],
                "driver_name": r["driver_name"],
            }
            for r in rows
        ]
    }


@router.get("/me")
def my_reviews(user_id: str = Depends(get_current_user_id)):
    """Reviews this user has received, plus their average."""
    return _reviews_for(user_id)


@router.get("/driver/{driver_id}")
def driver_reviews(driver_id: str, user_id: str = Depends(get_current_user_id)):
    """Public profile rating: average, star histogram, and recent comments."""
    return _reviews_for(driver_id)


def _reviews_for(target_id: str) -> dict:
    conn = get_db()
    user = conn.execute("SELECT id, name FROM users WHERE id = ?", (target_id,)).fetchone()
    if not user:
        conn.close()
        raise HTTPException(status_code=404, detail="User not found")

    rows = conn.execute(
        """SELECT rv.id, rv.stars, rv.comment, rv.created_at, rv.ride_id,
                  u.name AS reviewer_name, r.source, r.destination
           FROM reviews rv
           JOIN users u ON rv.reviewer_id = u.id
           JOIN rides r ON rv.ride_id = r.id
           WHERE rv.reviewee_id = ?
           ORDER BY rv.created_at DESC""",
        (target_id,)
    ).fetchall()
    summary = rating_for(conn, target_id)
    conn.close()

    histogram = {str(s): 0 for s in range(1, 6)}
    for r in rows:
        histogram[str(r["stars"])] += 1

    return {
        "user_id": user["id"],
        "name": user["name"],
        "average": summary["average"],
        "count": summary["count"],
        "histogram": histogram,
        "reviews": [
            {
                "id": r["id"],
                "stars": r["stars"],
                "comment": r["comment"],
                "reviewer_name": r["reviewer_name"],
                "ride_id": r["ride_id"],
                "route": f"{r['source']} to {r['destination']}",
                "created_at": r["created_at"],
            }
            for r in rows
        ],
    }
