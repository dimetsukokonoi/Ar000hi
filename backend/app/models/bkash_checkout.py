"""Simulated gateway payment state; HTML and redirects belong to other layers."""
from app.models.database import get_db
from app.payments import get_gateway
from app.payments.mock_bkash import TEST_NUMBERS


def get_payment(payment_id: str):
    conn = get_db()
    payment = conn.execute(
        "SELECT amount, status FROM bkash_payments WHERE id = ?", (payment_id,)
    ).fetchone()
    conn.close()
    return dict(payment) if payment else None


def confirm(payment_id: str, wallet_number: str):
    result = get_gateway().authorize(payment_id, wallet_number)
    conn = get_db()
    conn.execute(
        "UPDATE bkash_payments SET status = ?, wallet_number = ?, failure_reason = ? WHERE id = ?",
        (result.status, wallet_number, result.failure_reason, payment_id),
    )
    conn.commit()
    conn.close()
    return result


def cancel(payment_id: str):
    conn = get_db()
    conn.execute(
        "UPDATE bkash_payments SET status = 'cancelled', failure_reason = ? WHERE id = ?",
        ("Payment was cancelled by the user", payment_id),
    )
    conn.commit()
    conn.close()


def test_accounts():
    return {"test_accounts": TEST_NUMBERS, "default": "any other number succeeds"}
