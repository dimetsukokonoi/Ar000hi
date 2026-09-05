"""History controller: HTTP input, authentication and model dispatch."""

from fastapi import APIRouter, Depends, Query
from app.controllers.dependencies import get_current_user_id
from app.models import history as model

from fastapi.responses import Response
from app.views.receipts import _build_pdf

router = APIRouter()


@router.get("")
def list_history(
    role: str = Query("all", pattern="^(all|driver|passenger)$"),
    status: str = Query("completed", pattern="^(completed|all)$"),
    limit: int = Query(50, ge=1, le=200),
    user_id: str = Depends(get_current_user_id),
):
    """Past trips, newest first, across both roles."""
    return model.list_history(role=role, status=status, limit=limit, user_id=user_id)


@router.get("/summary")
def history_summary(user_id: str = Depends(get_current_user_id)):
    """Lifetime totals across both roles — spent as a rider, earned as a driver."""
    return model.history_summary(user_id=user_id)


@router.get("/{ride_id}/receipt")
def get_receipt(ride_id: str, user_id: str = Depends(get_current_user_id)):
    """Full receipt for one ride. Participants only."""
    return model.get_receipt(ride_id=ride_id, user_id=user_id)


@router.get("/{ride_id}/receipt.pdf")
def get_receipt_pdf(ride_id: str, user_id: str = Depends(get_current_user_id)):
    """The same receipt as a downloadable PDF. Participants only."""
    data = model.get_receipt(ride_id, user_id)  # reuses every guard and calculation
    pdf = _build_pdf(data)
    filename = f"{data['receipt_no']}.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
