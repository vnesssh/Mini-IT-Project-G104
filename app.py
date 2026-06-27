"""
MMU RateMyProfessor — app.py
=============================
Run:   python app.py
Open:  http://localhost:5000

Install:  pip install flask
"""

import os, sqlite3, uuid, base64
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify

app = Flask(__name__)
app.secret_key = "mmu_secret_key_2024"

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
DB_FILE     = os.path.join(BASE_DIR, "mmu_ratings.db")
UPLOAD_DIR  = os.path.join(BASE_DIR, "static", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# -------- ADMIN ----------
PENDING_DB = os.path.join(BASE_DIR, "pending.db")
# -------- ADMIN ----------


# ── Database helpers ────────────────────────────────────────────────────────

def connect_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


# -------- ADMIN ----------
def connect_pending():
    conn = sqlite3.connect(PENDING_DB)
    conn.row_factory = sqlite3.Row
    return conn
# -------- ADMIN ----------


def setup_database():
    conn = connect_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS faculties (
            id   INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE 
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS courses (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            course_code TEXT NOT NULL UNIQUE,
            course_name TEXT NOT NULL,
            faculty_id  INTEGER NOT NULL,
            FOREIGN KEY (faculty_id) REFERENCES faculties(id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS lecturers (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT NOT NULL,
            faculty_id INTEGER NOT NULL,
            image      TEXT,
            FOREIGN KEY (faculty_id) REFERENCES faculties(id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS lecturer_courses (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            lecturer_id INTEGER NOT NULL,
            course_id   INTEGER NOT NULL,
            UNIQUE (lecturer_id, course_id),
            FOREIGN KEY (lecturer_id) REFERENCES lecturers(id),
            FOREIGN KEY (course_id)   REFERENCES courses(id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS ratings (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            lecturer_id   INTEGER NOT NULL,
            student_id    TEXT NOT NULL,
            grading       INTEGER NOT NULL,
            teaching      INTEGER NOT NULL,
            strictness    INTEGER NOT NULL,
            communication INTEGER NOT NULL,
            textbooks     INTEGER NOT NULL,
            comment       TEXT,
            submitted_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (lecturer_id) REFERENCES lecturers(id)
        )
    """)

    conn.commit()
    conn.close()

    # -------- ADMIN ----------
    # Creates the separate pending.db with a requests table
    pconn = connect_pending()
    pconn.execute("""
        CREATE TABLE IF NOT EXISTS requests (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            name         TEXT NOT NULL,
            faculty      TEXT,
            course       TEXT,
            course_code  TEXT,
            image        TEXT,
            submitted_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    pconn.commit()
    pconn.close()
    # -------- ADMIN ----------


def get_all_lecturers():
    conn = connect_db()
    rows = conn.execute("""
        SELECT
            l.id,
            l.name,
            l.image,
            GROUP_CONCAT(DISTINCT f.name)        AS faculty,
            GROUP_CONCAT(DISTINCT c.course_name) AS course,
            GROUP_CONCAT(DISTINCT c.course_code) AS course_code,
            COUNT(DISTINCT r.id)                 AS review_count,
            ROUND(AVG(rs.score), 1)              AS overall,
            ROUND(AVG(CASE WHEN rc.name = 'grading'       THEN rs.score END), 1) AS avg_grading,
            ROUND(AVG(CASE WHEN rc.name = 'teaching'      THEN rs.score END), 1) AS avg_teaching,
            ROUND(AVG(CASE WHEN rc.name = 'strictness'    THEN rs.score END), 1) AS avg_strictness,
            ROUND(AVG(CASE WHEN rc.name = 'communication' THEN rs.score END), 1) AS avg_communication,
            ROUND(AVG(CASE WHEN rc.name = 'textbooks'     THEN rs.score END), 1) AS avg_textbooks
        FROM lecturers l
        LEFT JOIN lecturer_courses  lc ON l.id        = lc.lecturer_id
        LEFT JOIN courses            c ON lc.course_id = c.id
        LEFT JOIN faculties          f ON c.faculty_id = f.id
        LEFT JOIN ratings            r ON l.id        = r.lecturer_id
        LEFT JOIN rating_scores     rs ON r.id        = rs.rating_id
        LEFT JOIN rating_categories rc ON rs.category_id = rc.id
        GROUP BY l.id
        ORDER BY overall DESC NULLS LAST, l.name ASC
    """).fetchall()
    conn.close()
    return rows


def get_one_lecturer(lecturer_id):
    conn = connect_db()
    row = conn.execute("""
        SELECT
            l.id,
            l.name,
            l.image,
            GROUP_CONCAT(DISTINCT f.name)        AS faculty,
            GROUP_CONCAT(DISTINCT c.course_name) AS course,
            GROUP_CONCAT(DISTINCT c.course_code) AS course_code,
            COUNT(DISTINCT r.id)                 AS review_count,
            ROUND(AVG(rs.score), 1)              AS overall,
            ROUND(AVG(CASE WHEN rc.name = 'grading'       THEN rs.score END), 1) AS avg_grading,
            ROUND(AVG(CASE WHEN rc.name = 'teaching'      THEN rs.score END), 1) AS avg_teaching,
            ROUND(AVG(CASE WHEN rc.name = 'strictness'    THEN rs.score END), 1) AS avg_strictness,
            ROUND(AVG(CASE WHEN rc.name = 'communication' THEN rs.score END), 1) AS avg_communication,
            ROUND(AVG(CASE WHEN rc.name = 'textbooks'     THEN rs.score END), 1) AS avg_textbooks
        FROM lecturers l
        LEFT JOIN lecturer_courses  lc ON l.id        = lc.lecturer_id
        LEFT JOIN courses            c ON lc.course_id = c.id
        LEFT JOIN faculties          f ON c.faculty_id = f.id
        LEFT JOIN ratings            r ON l.id        = r.lecturer_id
        LEFT JOIN rating_scores     rs ON r.id        = rs.rating_id
        LEFT JOIN rating_categories rc ON rs.category_id = rc.id
        WHERE l.id = ?
        GROUP BY l.id
    """, (lecturer_id,)).fetchone()
    conn.close()
    return row


def save_image(data_url):
    if not data_url or not data_url.startswith("data:image"):
        return None
    try:
        header, encoded = data_url.split(",", 1)
        ext = header.split("/")[1].split(";")[0]
        filename = f"{uuid.uuid4().hex}.{ext}"
        with open(os.path.join(UPLOAD_DIR, filename), "wb") as f:
            f.write(base64.b64decode(encoded))
        return filename
    except Exception as e:
        print(f"Image save error: {e}")
        return None


# ── Pages ───────────────────────────────────────────────────────────────────

@app.route("/")
def home_page():
    return render_template("homepage.html")


@app.route("/lecturer/<int:lecturer_id>")
def profile_page(lecturer_id):
    lecturer = get_one_lecturer(lecturer_id)
    if lecturer is None:
        return "Lecturer not found", 404
    conn = connect_db()
    reviews = conn.execute(
        "SELECT * FROM ratings WHERE lecturer_id = ? ORDER BY submitted_at DESC",
        (lecturer_id,)
    ).fetchall()
    conn.close()
    return render_template("profile.html", lecturer=lecturer, reviews=reviews)


# -------- ADMIN ----------
# CHANGED from /add-professor to /request-professor
# CHANGED: now saves to pending.db instead of mmu_ratings.db
# CHANGED: renders request-professor.html instead of add-professor.html
@app.route("/request-professor", methods=["GET", "POST"])
def request_professor_page():
    if request.method == "POST":
        data        = request.get_json(force=True)
        name        = (data.get("name")        or "").strip()
        faculty     = (data.get("faculty")     or "").strip()
        course      = (data.get("course")      or "").strip()
        course_code = (data.get("course_code") or "").strip().upper()
        image_b64   = data.get("image")

        if not name:
            return jsonify({"error": "Lecturer name is required."}), 400

        filename = save_image(image_b64)

        # Saves to pending.db — NOT mmu_ratings.db
        pconn = connect_pending()
        pconn.execute(
            "INSERT INTO requests (name, faculty, course, course_code, image) VALUES (?,?,?,?,?)",
            (name, faculty, course, course_code, filename)
        )
        pconn.commit()
        pconn.close()
        return jsonify({"success": True, "name": name}), 201

    return render_template("request-professor.html")
# -------- ADMIN ----------


@app.route("/rate/<int:lecturer_id>", methods=["GET", "POST"])
def rate_page(lecturer_id):
    conn = connect_db()
    lecturer = conn.execute("SELECT * FROM lecturers WHERE id = ?", (lecturer_id,)).fetchone()
    conn.close()
    if lecturer is None:
        return "Lecturer not found", 404

    if request.method == "POST":
        student_id    = request.form.get("student_id", "").strip()
        grading       = request.form.get("grading", "")
        teaching      = request.form.get("teaching", "")
        strictness    = request.form.get("strictness", "")
        communication = request.form.get("communication", "")
        textbooks     = request.form.get("textbooks", "")
        comment       = request.form.get("comment", "").strip()

        if not all([student_id, grading, teaching, strictness, communication, textbooks]):
            flash("Please fill in your Student ID and all 5 rating categories.", "error")
            return redirect(url_for("rate_page", lecturer_id=lecturer_id))

        try:
            scores = list(map(int, [grading, teaching, strictness, communication, textbooks]))
        except ValueError:
            flash("Invalid scores.", "error")
            return redirect(url_for("rate_page", lecturer_id=lecturer_id))

        if not all(1 <= s <= 5 for s in scores):
            flash("All scores must be between 1 and 5.", "error")
            return redirect(url_for("rate_page", lecturer_id=lecturer_id))

        conn = connect_db()
        if conn.execute(
            "SELECT 1 FROM ratings WHERE lecturer_id=? AND student_id=?",
            (lecturer_id, student_id)
        ).fetchone():
            flash("You have already rated this lecturer.", "error")
            conn.close()
            return redirect(url_for("rate_page", lecturer_id=lecturer_id))

        conn.execute("""
            INSERT INTO ratings (lecturer_id, student_id, grading, teaching, strictness, communication, textbooks, comment)
            VALUES (?,?,?,?,?,?,?,?)
        """, (lecturer_id, student_id, *scores, comment))
        conn.commit()
        conn.close()
        flash("Your rating has been submitted. Thank you!", "success")
        return redirect(url_for("profile_page", lecturer_id=lecturer_id))

    return render_template("rate.html", lecturer=lecturer)


# ── API ─────────────────────────────────────────────────────────────────────

@app.route("/api/search")
def api_search():
    q = (request.args.get("q") or "").strip().lower()
    rows = get_all_lecturers()
    if q:
        rows = [r for r in rows if q in r["name"].lower()
                                 or q in (r["course"] or "").lower()
                                 or q in (r["course_code"] or "").lower()
                                 or q in (r["faculty"] or "").lower()]
    return jsonify([{
        "id":          r["id"],
        "name":        r["name"],
        "faculty":     r["faculty"],
        "course":      r["course"],
        "course_code": r["course_code"],
        "overall":     r["overall"],
        "image":       f"/static/uploads/{r['image']}" if r["image"] else None
    } for r in rows])


# -------- ADMIN ----------
# NEW ROUTE: Admin dashboard — shows all pending requests
@app.route("/admin")
def admin_page():
    pconn = connect_pending()
    pending = pconn.execute(
        "SELECT * FROM requests ORDER BY submitted_at DESC"
    ).fetchall()
    pconn.close()
    return render_template("admin.html", requests=pending)


# NEW ROUTE: Accept — moves request from pending.db into mmu_ratings.db
@app.route("/admin/accept/<int:request_id>", methods=["POST"])
def admin_accept(request_id):
    pconn = connect_pending()
    req = pconn.execute(
        "SELECT * FROM requests WHERE id = ?", (request_id,)
    ).fetchone()

    if req:
        conn = connect_db()
        conn.execute(
            "INSERT INTO lecturers (name, faculty, course, course_code, image) VALUES (?,?,?,?,?)",
            (req["name"], req["faculty"], req["course"], req["course_code"], req["image"])
        )
        conn.commit()
        conn.close()
        pconn.execute("DELETE FROM requests WHERE id = ?", (request_id,))
        pconn.commit()
        flash(f'"{req["name"]}" has been approved and added to the directory.', "success")

    pconn.close()
    return redirect(url_for("admin_page"))


# NEW ROUTE: Decline — deletes request from pending.db
@app.route("/admin/decline/<int:request_id>", methods=["POST"])
def admin_decline(request_id):
    pconn = connect_pending()
    req = pconn.execute(
        "SELECT name FROM requests WHERE id = ?", (request_id,)
    ).fetchone()
    pconn.execute("DELETE FROM requests WHERE id = ?", (request_id,))
    pconn.commit()
    pconn.close()

    if req:
        flash(f'"{req["name"]}" request has been declined and removed.', "error")
    return redirect(url_for("admin_page"))
# -------- ADMIN ----------


# ── Run ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    setup_database()
    print("=" * 52)
    print("  MMU RateMyProfessor →  http://localhost:5000")
    print("=" * 52)
    app.run(debug=True)
