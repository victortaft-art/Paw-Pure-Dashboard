"""Local refresh server for dev.

Listens on localhost:5001. CORS enabled for the Vite dev server only.

Endpoints:
    POST /refresh                — run daily_pipeline.py and stream stdout
    POST /experiments/mark-done  — mark an experiment as DONE in active_tracker.json
                                    + experiment_log.json. Body: {id, outcome}

Run with:
    python3 amazon_api/server.py
"""
import json
import subprocess
import sys
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional

HOST = "127.0.0.1"
PORT = 5001
ALLOWED_ORIGIN = "http://localhost:5173"

PIPELINE = Path(__file__).resolve().parent / "daily_pipeline.py"
PROJECT_ROOT = Path(__file__).resolve().parent.parent

TRACKER_FILES = [
    PROJECT_ROOT.parent / "public" / "data" / "active_tracker.json",
    PROJECT_ROOT / "active_tracker.json",
]
LOG_FILES = [
    PROJECT_ROOT / "experiment_log.json",
    PROJECT_ROOT.parent / "public" / "data" / "experiment_log.json",
]


def _mark_done(exp_id: str, outcome: Optional[str]) -> dict:
    """Update both files atomically. Returns a summary dict."""
    today = date.today().isoformat()
    files_updated = []
    not_found_in = []

    # Update active_tracker.json — change status in weekly_strategy[].experiments
    # AND in tracking[] entries, AND record completed_date in backlog[].
    for path in TRACKER_FILES:
        if not path.exists():
            continue
        with path.open() as f:
            d = json.load(f)
        touched = False

        for wk in d.get("weekly_strategy", []) or []:
            for e in wk.get("experiments", []) or []:
                if e.get("id") == exp_id:
                    e["status"] = "DONE"
                    e["completed_date"] = today
                    touched = True

        # Move from tracking[] to a "completed" tracking marker
        new_tracking = []
        for t in d.get("tracking", []) or []:
            if t.get("id") == exp_id:
                t["status"] = "DONE"
                t["completed_date"] = today
                if outcome:
                    t["outcome_note"] = outcome
                touched = True
            new_tracking.append(t)
        d["tracking"] = new_tracking

        for b in d.get("backlog", []) or []:
            if b.get("id") == exp_id:
                b["status"] = "DONE"
                b["completed_date"] = today
                if outcome:
                    b["outcome_note"] = outcome
                touched = True

        if touched:
            with path.open("w") as f:
                json.dump(d, f, indent=2)
            files_updated.append(str(path.relative_to(PROJECT_ROOT)))
        else:
            not_found_in.append(str(path.relative_to(PROJECT_ROOT)))

    # Update experiment_log.json — flip status to DONE, append outcome note
    for path in LOG_FILES:
        if not path.exists():
            continue
        with path.open() as f:
            d = json.load(f)
        touched = False
        for e in d.get("active_experiments", []) or []:
            if e.get("id") == exp_id:
                e["status"] = "DONE"
                e["completed_date"] = today
                if outcome:
                    e["actual_result"] = outcome
                touched = True
        d["_last_updated"] = today
        if touched:
            with path.open("w") as f:
                json.dump(d, f, indent=2)
            files_updated.append(str(path.relative_to(PROJECT_ROOT)))

    return {
        "ok": bool(files_updated),
        "id": exp_id,
        "completed_date": today,
        "files_updated": files_updated,
        "not_found_in": not_found_in,
    }


class RefreshHandler(BaseHTTPRequestHandler):
    def _cors(self):
        origin = self.headers.get("Origin", "")
        # Only reflect the allowed origin; otherwise omit.
        if origin == ALLOWED_ORIGIN:
            self.send_header("Access-Control-Allow-Origin", ALLOWED_ORIGIN)
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_POST(self):
        if self.path == "/experiments/mark-done":
            self._handle_mark_done()
            return
        if self.path == "/experiments/add":
            self._handle_add()
            return
        if self.path != "/refresh":
            self.send_response(404)
            self._cors()
            self.end_headers()
            return

        self.send_response(200)
        self._cors()
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()

        def write(line):
            try:
                self.wfile.write(line.encode("utf-8"))
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass

        write(f"→ Starting pipeline: {PIPELINE}\n")
        proc = subprocess.Popen(
            [sys.executable, "-u", str(PIPELINE)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=str(PROJECT_ROOT),
            bufsize=1,
            text=True,
        )
        for line in proc.stdout:
            write(line)
        rc = proc.wait()
        write(f"\n[exit code: {rc}]\n")

    def _handle_add(self):
        """POST /experiments/add — body is the spec dict per scripts/experiments_apply.py."""
        try:
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length).decode("utf-8") if length else "{}"
            spec = json.loads(body)
            for required in ("id", "title", "scheduled_date", "priority", "listing"):
                if not spec.get(required):
                    self._json_response(400, {"error": f"missing required field: {required}"})
                    return

            log_entry = {
                "id": spec["id"],
                "element": spec["title"],
                "status": spec.get("status", "TODO"),
                "start_date": spec["scheduled_date"],
                "decision_date": spec.get("decision_date"),
                "hypothesis": spec.get("assumption"),
                "priority": spec["priority"],
                "rationale": spec.get("rationale"),
                "expected_impact": spec.get("expected_change"),
                "wave": spec.get("wave", 1),
                "run_window_days": spec.get("run_window_days", 7),
                "success_criteria": spec.get("success_criteria"),
                "execution": {
                    "what_to_do": (spec.get("execution_steps") or [""])[0],
                    "steps": spec.get("execution_steps") or [],
                },
                "listing": spec["listing"],
                "actual_result": None,
                "_source": "advisor_approved",
            }

            files_written = []
            for path in LOG_FILES:
                if not path.exists():
                    continue
                d = json.loads(path.read_text())
                if any(e.get("id") == spec["id"] for e in d.get("active_experiments", [])):
                    continue
                d.setdefault("active_experiments", []).append(log_entry)
                from datetime import date as _date
                d["_last_updated"] = _date.today().isoformat()
                path.write_text(json.dumps(d, indent=2))
                files_written.append(str(path.relative_to(PROJECT_ROOT)))

            for path in TRACKER_FILES:
                if not path.exists():
                    continue
                d = json.loads(path.read_text())
                if any(b.get("id") == spec["id"] for b in d.get("backlog", [])):
                    continue
                d.setdefault("backlog", []).append(spec)
                path.write_text(json.dumps(d, indent=2))
                files_written.append(str(path.relative_to(PROJECT_ROOT)))

            self._json_response(200, {"ok": True, "id": spec["id"], "files_written": files_written})
        except Exception as e:  # pragma: no cover — defensive
            self._json_response(500, {"error": str(e)})

    def _handle_mark_done(self):
        try:
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length).decode("utf-8") if length else "{}"
            payload = json.loads(body)
            exp_id = (payload.get("id") or "").strip()
            outcome = payload.get("outcome")
            if not exp_id:
                self._json_response(400, {"error": "missing id"})
                return
            result = _mark_done(exp_id, outcome)
            self._json_response(200 if result["ok"] else 404, result)
        except Exception as e:  # pragma: no cover — defensive
            self._json_response(500, {"error": str(e)})

    def _json_response(self, code: int, body: dict):
        self.send_response(code)
        self._cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(body).encode("utf-8"))

    def do_GET(self):
        # Simple health check
        if self.path in ("/", "/health"):
            self.send_response(200)
            self._cors()
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"amazon_api refresh server OK\n")
            return
        self.send_response(404)
        self._cors()
        self.end_headers()

    def log_message(self, fmt, *args):
        # Quieter logging — print to stdout w/o the default HTTP prefix spam
        sys.stdout.write(f"[{self.log_date_time_string()}] {fmt % args}\n")
        sys.stdout.flush()


def main():
    httpd = ThreadingHTTPServer((HOST, PORT), RefreshHandler)
    print(f"Refresh server listening on http://{HOST}:{PORT}", flush=True)
    print(f"  POST /refresh  → runs daily_pipeline.py", flush=True)
    print(f"  Allowed origin: {ALLOWED_ORIGIN}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.", flush=True)
        httpd.server_close()


if __name__ == "__main__":
    main()
