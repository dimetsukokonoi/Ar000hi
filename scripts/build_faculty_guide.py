"""Build the four-page faculty handout from selected current source excerpts.

Run: backend/.venv/bin/python scripts/build_faculty_guide.py
Only writes Faculty_Demo_Guide.pdf; does not import or run the application.
"""
from pathlib import Path
import textwrap

from fpdf import FPDF

ROOT = Path(__file__).resolve().parents[1]
MODEL = "backend/app/models/rides.py"
CONTROLLER = "backend/app/controllers/rides.py"
SCHEMA = "backend/app/schemas/rides.py"
FRONTEND = "frontend/app/dashboard/rides/page.tsx"


def take(path, marker, count):
    lines = (ROOT / path).read_text().splitlines()
    start = next(i for i, line in enumerate(lines) if marker in line)
    return textwrap.dedent("\n".join(lines[start:start + count]))


class Guide(FPDF):
    def footer(self):
        self.set_y(-11)
        self.set_font("Helvetica", size=8)
        self.set_text_color(100, 110, 122)
        self.cell(0, 4, f"AROOOHI  |  Faculty demonstration     /     {self.page_no()} of 4", align="R")

    def section_page(self, title, subtitle):
        self.add_page()
        self.set_text_color(24, 50, 71)
        self.set_font("Helvetica", "B", 20)
        self.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", size=9)
        self.set_text_color(90, 100, 110)
        self.multi_cell(0, 4.5, subtitle, align="L", new_x="LMARGIN", new_y="NEXT")
        self.ln(4)

    def note(self, label, text):
        self.set_text_color(24, 50, 71)
        self.set_font("Helvetica", "B", 10)
        self.cell(0, 5, label, new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", size=10)
        self.set_text_color(38, 45, 54)
        self.multi_cell(0, 4.8, text, align="L", new_x="LMARGIN", new_y="NEXT")
        self.ln(3)

    def pair(self, title, location, code, explanation):
        self.set_text_color(24, 50, 71)
        self.set_font("Helvetica", "B", 11)
        self.multi_cell(0, 5.5, title, new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", size=8)
        self.set_text_color(90, 100, 110)
        self.multi_cell(0, 4, location, new_x="LMARGIN", new_y="NEXT")
        self.ln(1)
        y = self.get_y()
        x = self.l_margin
        left, gap = 110, 5
        right = self.epw - left - gap
        # Wrap long code lines without changing the source excerpt itself.
        self.set_font("Courier", size=8.2)
        wrapped = []
        for line in code.splitlines():
            width = int((left - 8) / self.get_string_width("M"))
            indent = " " * min(len(line) - len(line.lstrip()) + 2, 12)
            wrapped.extend(textwrap.wrap(line, width=width, subsequent_indent=indent,
                                         replace_whitespace=False, drop_whitespace=True) or [""])
        code_text = "\n".join(wrapped)
        code_h = 3.7 * len(wrapped) + 6
        self.set_font("Helvetica", size=10)
        text_lines = self.multi_cell(right - 2, 4.7, explanation, align="L", dry_run=True, output="LINES")
        height = max(code_h, len(text_lines) * 4.7 + 6)
        if y + height > 279:
            raise ValueError(f"Page {self.page_no()} overflow at {title}")
        self.set_fill_color(242, 245, 248)
        self.rect(x, y, left, height, style="F")
        self.set_draw_color(215, 223, 231)
        self.line(x + left + 2, y, x + left + 2, y + height)
        self.set_xy(x + 3, y + 3)
        self.set_font("Courier", size=8.2)
        self.set_text_color(27, 44, 58)
        self.multi_cell(left - 6, 3.7, code_text, align="L")
        self.set_xy(x + left + gap, y + 3)
        self.set_font("Helvetica", size=10)
        self.set_text_color(38, 45, 54)
        self.multi_cell(right - 2, 4.7, explanation, align="L")
        self.set_xy(x, y + height + 5)


pdf = Guide(format="A4")
pdf.set_margins(12, 11, 12)
pdf.set_auto_page_break(False)
pdf.set_title("Arooohi - Faculty Demonstration: MVC and Five Features")
pdf.set_author("Arooohi project")

pdf.section_page("1 / Explain MVC first", "Code is on the left; what to say is on the right. Excerpts use ... for omitted code; long lines wrap.")
pdf.note("Say this (20 seconds)",
         '"My project uses API-based MVC. React is the View: it collects input and displays results. '
         'FastAPI Controllers receive requests and check authentication. Python Models apply the rules '
         'and use SQLite. Results return as JSON for React to display."')
pdf.note("Point to these folders",
         "View: frontend/app/ and frontend/components/\n"
         "Controller: backend/app/controllers/ | Model: backend/app/models/\n"
         "Flow: React form -> Controller -> Model -> SQLite -> JSON -> React\n"
         "This is web MVC with a separate frontend, not server-rendered templates.")
pdf.pair("Controller: receive the request, then delegate", CONTROLLER + " | create_ride; main.py registers /api/rides",
         take(CONTROLLER, '@router.post("")', 4),
         "@router.post connects a POST URL to this function.\n\n"
         "Depends runs the login check and supplies user_id.\n\n"
         "The controller calls the model. It contains no booking SQL.")
pdf.pair("Schema: validate input, not save it", SCHEMA + " | CreateRideRequest (excerpt)",
         take(SCHEMA, "class CreateRideRequest", 8),
         "BaseModel comes from Pydantic. It checks input types and supplies defaults.\n\n"
         "Bad input produces HTTP 422. This schema is NOT the MVC Model or a database table.")
pdf.note("Why this really separates responsibilities",
         "Models contain rules and SQL but do not import FastAPI. Controllers handle HTTP, not SQL. "
         "React displays results; backend/app/views/ formats PDF/HTML. main.py wires the app together. "
         "Old routes/ files are compatibility imports, not a second implementation.")

pdf.section_page("2 / Hotspots + smart matching", "Both features: backend/app/models/rides.py. UI: rides/page.tsx and TrackingMap.tsx.")
pdf.pair("Hotspots: a list of named coordinates", MODEL + " | HOTSPOTS (one entry, shortened)",
         "HOTSPOTS = [\n    {\n" + textwrap.indent(take(MODEL, '"id": "gate 1"', 5), "        ") + "\n        ...\n    },\n    ...\n]",
         "Each place has an ID, name, category, latitude and longitude.\n\n"
         "Add/remove places or edit coordinates here. Check ZONES aliases below the list too: some override coordinates used by matching.")
pdf.pair("The controller sends data; the View draws it", CONTROLLER + " | get_hotspots; frontend/components/TrackingMap.tsx | Marker",
         take(CONTROLLER, '@router.get("/hotspots")', 4) + "\n\n# Model:\n" +
         take(MODEL, "def get_hotspots", 3) + "\n\n// React map excerpt:\n" +
         take("frontend/components/TrackingMap.tsx", "<Marker key={h.id", 1),
         "GET /api/rides/hotspots returns the list as JSON.\n\n"
         "React uses [lat, lng] to place each marker. The tile provider supplies the background map; it does not define our hotspots.")
pdf.pair("Smart matching: rank nearby, suitable rides", MODEL + " | match_rides (selected lines)",
         take(MODEL, "if same_cluster or (s_coord", 3) + "\n...\n" +
         take(MODEL, "if dist <= 1.2:", 3) + "\n...\n" +
         take(MODEL, "matched_results.sort(", 2),
         "First remove ineligible or full rides. Then score pickup, destination, intermediate stops and time.\n\n"
         "Same campus zone earns 45 pickup points; a pickup within 1.2 km earns 35. Higher scores come first.\n\n"
         "_haversine_km measures straight-line distance on Earth, not driving distance.")
pdf.note("Say this", '"Smart matching is a rule-based scoring algorithm, not machine learning. '
         'A match score is a ranking score, not a probability or guaranteed arrival time."')

pdf.section_page("3 / Multi-stop + female-only", "Rules are enforced in the Model, even if someone bypasses the frontend.")
pdf.pair("Multi-stop: remember the order of stops", MODEL + " | create_ride (stop persistence)",
         take(MODEL, "for idx, stop in enumerate(body.stops):", 9),
         "enumerate gives each stop a sequence number. ride_id links it to the ride.\n\n"
         "SQL ? placeholders pass values separately from SQL text. commit saves changes; close releases the connection.\n\n"
         "This is Model work: storing ride data.")
pdf.pair("A rider must get on before getting off", MODEL + " | join_ride and update_stop_status (excerpts)",
         take(MODEL, "if pickup_route[0] >= dropoff_route[0]:", 3) + "\n\n# Allowed stop progress values:\n" +
         take(MODEL, 'if body.status not in ("pending", "reached", "departed"):', 2),
         "join_ride builds an ordered route: start, intermediate stops, destination.\n\n"
         "It rejects unknown stops or reversed pickup/drop-off order.\n\n"
         "Only the ride's driver can update stop progress: pending, reached or departed.")
pdf.pair("Female-only: check both creation and booking", MODEL + " | create_ride / join_ride",
         take(MODEL, 'if body.female_only and user["gender"]', 3) + "\n\n" +
         take(MODEL, 'if ride["female_only"] and user["gender"]', 3),
         "Creation is rejected unless the account's stored gender is female.\n\n"
         "Booking a female-only ride also requires a female account. Matching filters these rides too.\n\n"
         "This uses the profile value, not independent identity verification.")
pdf.note("If asked: what is DomainError?",
         "It reports a model failure without importing FastAPI. controllers/errors.py converts it "
         'into an HTTP response such as 403 with {"detail": "..."}. The View shows that message.')

pdf.section_page("4 / Scheduled booking + seat requests", "Scheduling is advance booking. The driver still starts and ends the ride manually.")
pdf.pair("The frontend sends a standard timestamp", FRONTEND + " | ride creation request (excerpt)",
         take(FRONTEND, "scheduled_at: form.scheduled_at ?", 1),
         "The date/time input is interpreted in the browser's local timezone. toISOString converts it to UTC before sending it to the backend.")
pdf.pair("The Model rejects a past scheduled time", MODEL + " | create_ride (selected lines)",
         take(MODEL, "parsed = dt.fromisoformat", 3) + "\n...\n" +
         take(MODEL, "if parsed <= dt.now(timezone.utc):", 3),
         "Parse the ISO timestamp; Z means UTC. Legacy values without a timezone are treated as UTC.\n\n"
         "Reject invalid/past times with HTTP 400. A valid scheduled_at value is saved in rides and returned to the UI.")
pdf.pair("Confirm Seat creates a request, not a payment", MODEL + " | join_ride (selected result fields)",
         take(MODEL, '"message": "Ride request sent",', 3) + "\n...\n" +
         take(MODEL, '"estimated_share": projected,', 4),
         "Before saving, the Model checks capacity, duplicate requests, eligibility and stop order.\n\n"
         "requested means waiting for driver acceptance. Low balance returns a top-up notice; booking does not debit the wallet.\n\n"
         "passenger_id here is the booking-row ID, not the user's account ID.")
pdf.note("Demonstrate it in this order",
         "Offer a ride with a future date/time -> find it under Scheduled Ahead -> use a second "
         "account to request a seat -> switch to the driver and accept -> start the ride manually.")
pdf.note("Do not overclaim",
         "Class-time scoring compares stored clock hours directly; timezone alignment there needs "
         "a fix. Advance booking itself is separate from that ranking. There is no automatic dispatch worker.")
pdf.note("If asked: how did you check the MVC refactor?",
         "52 backend tests passed; the 67-path API contract stayed unchanged; the frontend build passed. "
         "These were the refactor checks, not a claim that every possible bug is fixed.")

assert pdf.page_no() == 4
assert pdf.get_y() < 279, "Last page content would overlap the footer"
destination = ROOT / "Faculty_Demo_Guide.pdf"
pdf.output(str(destination))
print(f"Created {destination} ({destination.stat().st_size:,} bytes; {pdf.page_no()} pages)")
