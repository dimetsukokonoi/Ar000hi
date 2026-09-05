"""HTTP/WebSocket regression tests using only the isolated test database."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import app
from app.models.database import get_db
from app.models.identity import create_access_token, hash_password

client = TestClient(app)


@pytest.fixture(scope="module")
def actors():
    result = {}
    password_hash = hash_password("Password123!")
    conn = get_db()
    for role in ("driver", "rider", "admin"):
        uid = str(uuid.uuid4())
        email = f"{uid}@g.bracu.ac.bd"
        conn.execute(
            "INSERT INTO users (id, name, bracu_email, password_hash, role, gender, is_verified) VALUES (?, ?, ?, ?, ?, 'female', 1)",
            (uid, f"MVC {role}", email, password_hash, role),
        )
        token = create_access_token({"sub": uid})
        result[role] = {
            "id": uid,
            "email": email,
            "token": token,
            "headers": {"Authorization": f"Bearer {token}"},
        }
    conn.commit()
    conn.close()
    return result


def request(method, path, actor=None, status=200, **kwargs):
    response = client.request(
        method, path, headers=actor["headers"] if actor else {}, **kwargs
    )
    assert response.status_code == status, response.text
    return response


@pytest.mark.parametrize(
    "path",
    [
        "/api/auth/me",
        "/api/drivers/status",
        "/api/drivers/pending",
        "/api/tracking/active",
        "/api/sos/alerts",
        "/api/sos/my-alerts",
        "/api/complaints/",
        "/api/complaints/stats",
        "/api/contacts",
        "/api/contacts/shares",
        "/api/rides",
        "/api/rides/match",
        "/api/surge/current",
        "/api/surge/schedule",
        "/api/eco/stats",
        "/api/eco/leaderboard",
        "/api/wallet",
        "/api/wallet/transactions",
        "/api/wallet/reconcile",
        "/api/earnings/summary",
        "/api/earnings/weekly",
        "/api/earnings/daily",
        "/api/earnings/rides",
        "/api/history",
        "/api/history/summary",
        "/api/reviews/pending",
        "/api/reviews/me",
    ],
)
def test_controller_read_endpoints(actors, path):
    request("GET", path, actors["admin"])


def test_auth_validation_and_domain_errors(actors):
    request("GET", "/api/auth/me", status=401)
    request("GET", "/api/drivers/pending", actors["rider"], status=403)
    request("GET", "/api/history?limit=0", actors["rider"], status=422)
    request("POST", "/api/rides", actors["driver"], status=422, json={})
    error = request("GET", "/api/rides/does-not-exist", actors["rider"], status=404)
    assert error.json() == {"detail": "Ride not found"}
    login = request(
        "POST",
        "/api/auth/login",
        json={
            "email": actors["rider"]["email"],
            "password": "Password123!",
        },
    ).json()
    assert login["token"]
    request(
        "POST",
        "/api/auth/login",
        status=401,
        json={
            "email": actors["rider"]["email"],
            "password": "incorrect",
        },
    )


def test_registration_and_otp():
    email = f"{uuid.uuid4()}@g.bracu.ac.bd"
    registered = request(
        "POST",
        "/api/auth/register",
        json={
            "name": "MVC Registration",
            "email": email,
            "password": "Password123!",
            "phone": "01712345678",
            "gender": "female",
        },
    ).json()
    verified = request(
        "POST",
        "/api/auth/verify-otp",
        json={
            "email": email,
            "code": registered["otp_hint"],
        },
    ).json()
    assert verified["token"]


def topup(actor, amount=1000):
    payment = request(
        "POST", "/api/wallet/topup", actor, json={"amount": amount}
    ).json()
    pid = payment["payment_id"]
    page = request("GET", f"/bkash/checkout/{pid}")
    assert "text/html" in page.headers["content-type"]
    assert "Confirm Payment" in page.text
    redirect = request(
        "POST",
        f"/bkash/checkout/{pid}/confirm",
        status=303,
        data={"wallet_number": "01770000001", "pin": "1234"},
        follow_redirects=False,
    )
    assert f"paymentID={pid}" in redirect.headers["location"]
    credited = request(
        "POST", "/api/wallet/topup/execute", actor, json={"payment_id": pid}
    ).json()
    duplicate = request(
        "POST", "/api/wallet/topup/execute", actor, json={"payment_id": pid}
    ).json()
    assert duplicate["duplicate"] is True
    assert duplicate["balance"] == credited["balance"]
    return pid


def test_wallet_checkout_and_cancellation(actors):
    rider = actors["rider"]
    pid = topup(rider)
    assert (
        request("GET", f"/api/wallet/payment/{pid}", rider).json()["credited"] is True
    )
    request("GET", f"/api/wallet/payment/{pid}", actors["driver"], status=404)
    request("GET", "/bkash/checkout/missing", status=404)
    request("GET", "/bkash/test-accounts")
    payment = request("POST", "/api/wallet/topup", rider, json={"amount": 100}).json()
    pid = payment["payment_id"]
    request("POST", f"/bkash/checkout/{pid}/cancel", status=303, follow_redirects=False)
    request(
        "POST", "/api/wallet/topup/execute", rider, status=402, json={"payment_id": pid}
    )


def test_ride_chat_settlement_pdf_and_review(actors):
    driver, rider = actors["driver"], actors["rider"]
    topup(rider)
    ride = request(
        "POST",
        "/api/rides",
        driver,
        json={
            "source": "Badda",
            "destination": "Gate 1",
            "base_fare": 120,
            "total_seats": 3,
            "female_only": True,
            "stops": ["Rampura"],
            "scheduled_at": (
                datetime.now(timezone.utc) + timedelta(hours=2)
            ).isoformat(),
        },
    ).json()["ride_id"]
    seat = request("POST", f"/api/rides/{ride}/join", rider, json={"seats": 1}).json()
    request("POST", f"/api/rides/{ride}/accept/{seat['passenger_id']}", driver)
    with client.websocket_connect(f"/ws/chat/{ride}?token={rider['token']}") as ws:
        ws.send_json({"message": "MVC chat regression"})
        message = ws.receive_json()
        assert message["message"] == "MVC chat regression"
        assert message["sender_id"] == rider["id"]
    history = request("GET", f"/api/rides/{ride}/messages", rider).json()
    assert history[-1]["message"] == "MVC chat regression"
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(
            f"/ws/chat/{ride}?token={actors['admin']['token']}"
        ) as ws:
            ws.receive_json()
    assert exc.value.code == 4403
    request("POST", f"/api/rides/{ride}/start", driver)
    request("POST", f"/api/rides/{ride}/end", driver, json={"distance_km": 5})
    receipt = request("GET", f"/api/history/{ride}/receipt", rider).json()
    assert receipt["paid"] is True
    pdf = request("GET", f"/api/history/{ride}/receipt.pdf", rider)
    assert pdf.content.startswith(b"%PDF-")
    assert "application/pdf" in pdf.headers["content-type"]
    request("GET", f"/api/history/{ride}/receipt.pdf", actors["admin"], status=403)
    request(
        "POST",
        "/api/reviews",
        rider,
        json={
            "ride_id": ride,
            "reviewee_id": driver["id"],
            "stars": 5,
            "comment": "Great ride",
        },
    )
    request("GET", f"/api/reviews/driver/{driver['id']}", rider)


def test_tracking_and_contact_crud(actors):
    rider = actors["rider"]
    contact = request(
        "POST",
        "/api/contacts",
        rider,
        json={
            "contact_name": "Guardian",
            "contact_phone": "01712345678",
        },
    ).json()
    session = request("POST", "/api/tracking/session", rider).json()
    sid = session["session_id"]
    request(
        "POST",
        "/api/tracking/point",
        rider,
        json={"session_id": sid, "lat": 23.77, "lng": 90.42},
    )
    points = request("GET", f"/api/tracking/session/{sid}", rider).json()
    assert points[-1]["lat"] == 23.77
    request("GET", f"/api/tracking/session/{sid}", actors["driver"], status=404)
    request("GET", f"/api/tracking/share/{session['share_token']}")
    request(
        "POST",
        "/api/contacts/auto-share",
        rider,
        json={"share_url": session["share_url"], "session_id": sid},
    )
    request("POST", f"/api/tracking/session/{sid}/stop", rider)
    request("DELETE", f"/api/contacts/{contact['contact']['id']}", rider)


def test_driver_upload_and_admin_review(actors, monkeypatch, tmp_path):
    from app.models import drivers

    monkeypatch.setattr(drivers, "UPLOADS_DIR", str(tmp_path))
    driver, admin = actors["driver"], actors["admin"]
    files = {
        name: ("document.pdf", b"%PDF-test", "application/pdf")
        for name in ("nid_document", "license_document", "vehicle_registration")
    }
    data = {
        "vehicle_type": "car",
        "vehicle_model": "Toyota",
        "vehicle_plate": "DHAKA-TEST",
    }
    request("POST", "/api/drivers/verify", driver, data=data, files=files)
    assert len(list(tmp_path.rglob("*.pdf"))) == 3
    profile = request("GET", "/api/drivers/status", driver).json()
    assert profile["status"] == "pending"
    request(
        "PATCH",
        f"/api/drivers/{profile['profile']['id']}/review",
        admin,
        json={"status": "approved", "admin_notes": "Documents checked"},
    )
    assert request("GET", "/api/drivers/status", driver).json()["status"] == "approved"


def test_sos_and_complaint_moderation(actors):
    rider, admin = actors["rider"], actors["admin"]
    alert = request(
        "POST", "/api/sos/trigger", rider, json={"lat": 23.77, "lng": 90.42}
    ).json()
    request(
        "PATCH",
        f"/api/sos/{alert['alert_id']}/resolve",
        rider,
        status=403,
        json={"status": "resolved"},
    )
    request(
        "PATCH",
        f"/api/sos/{alert['alert_id']}/resolve",
        admin,
        json={"status": "resolved"},
    )
    complaint = request(
        "POST",
        "/api/complaints/",
        rider,
        json={
            "category": "other",
            "subject": "MVC demo",
            "description": "Regression test",
        },
    ).json()
    request(
        "PATCH",
        f"/api/complaints/{complaint['complaint_id']}",
        admin,
        json={"status": "resolved", "admin_notes": "Checked"},
    )
    own = request("GET", "/api/complaints/", rider).json()
    assert (
        next(c for c in own if c["id"] == complaint["complaint_id"])["status"]
        == "resolved"
    )


def test_ride_cancellation(actors):
    driver = actors["driver"]
    ride = request(
        "POST",
        "/api/rides",
        driver,
        json={
            "source": "Badda",
            "destination": "Gate 1",
            "base_fare": 100,
        },
    ).json()["ride_id"]
    request("GET", f"/api/rides/{ride}/cancellation-policy", driver)
    request(
        "POST", f"/api/rides/{ride}/cancel", driver, json={"reason": "Demo finished"}
    )
    assert request("GET", f"/api/rides/{ride}", driver).json()["status"] == "cancelled"


def test_bad_websocket_token():
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/ws/chat/missing?token=invalid") as ws:
            ws.receive_json()
    assert exc.value.code == 4401


@pytest.mark.parametrize(
    "content,mime,detail",
    [
        (b"script", "text/html", "Unsupported file type"),
        (b"x" * (2 * 1024 * 1024 + 1), "application/pdf", "File is too large"),
    ],
)
def test_upload_validation_is_preserved(
    actors, monkeypatch, tmp_path, content, mime, detail
):
    from app.models import drivers

    monkeypatch.setattr(drivers, "UPLOADS_DIR", str(tmp_path))
    files = {
        name: ("document.pdf", content, mime)
        for name in ("nid_document", "license_document", "vehicle_registration")
    }
    response = request(
        "POST",
        "/api/drivers/verify",
        actors["rider"],
        status=400,
        data={
            "vehicle_type": "car",
            "vehicle_model": "Toyota",
            "vehicle_plate": "TEST",
        },
        files=files,
    )
    assert detail in response.json()["detail"]
    assert not list(tmp_path.rglob("*.pdf"))
