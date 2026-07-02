"""
MMU RateMyProfessor — app.py
=============================
Run:   python app.py
Open:  http://localhost:5000

Install:  pip install flask
"""

import os, sqlite3, uuid, base64
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session 
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import timedelta
import secrets
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer 
app = Flask(__name__)

app.secret_key = os.environ.get("SECRET_KEY") or os.urandom(32)
app.permanent_session_lifetime = timedelta(hours=0.5)

app.config["MAIL_SERVER"] = "smtp.gmail.com"
app.config["MAIL_PORT"] = 587
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USERNAME"] = os.environ.get("MAIL_USERNAME", "vienesshbro24@gmail.com")
app.config["MAIL_PASSWORD"] = os.environ.get("MAIL_PASSWORD", "rutquezxchwweetp")
app.config["MAIL_DEFAULT_SENDER"] = app.config["MAIL_USERNAME"]

mail = Mail(app)
serializer = URLSafeTimedSerializer(app.secret_key)
analyzer = SentimentIntensityAnalyzer()

# How long a verification link stays valid, in seconds
VERIFY_TOKEN_MAX_AGE = 60 * 60 * 24  # 24 hours  

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
DB_FILE     = os.path.join(BASE_DIR, "mmu_ratings.db")
UPLOAD_DIR  = os.path.join(BASE_DIR, "static", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# -------- ADMIN ----------
PENDING_DB = os.path.join(BASE_DIR, "pending.db")
ADMIN_USERNAME = "NothingPhone3a"
ADMIN_PASSWORD = generate_password_hash("OatKrunch67")

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
    
    conn.execute("PRAGMA foreign_keys = ON")
   
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
            comment       TEXT,
            submitted_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (lecturer_id) REFERENCES lecturers(id)
        )
    """)

    conn.execute("""
         CREATE TABLE IF NOT EXISTS rating_analysis (
        rating_id        INTEGER PRIMARY KEY,
        sentiment        TEXT NOT NULL,
        sentiment_score  REAL NOT NULL,
        FOREIGN KEY (rating_id) REFERENCES ratings(id)
    )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS rating_categories (
            id   INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS rating_scores (
            rating_id   INTEGER NOT NULL,
            category_id INTEGER NOT NULL,
            score       INTEGER NOT NULL,
            PRIMARY KEY (rating_id, category_id),
            FOREIGN KEY (rating_id)   REFERENCES ratings(id),
            FOREIGN KEY (category_id) REFERENCES rating_categories(id)
        )
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS students (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id    TEXT NOT NULL UNIQUE,
        email TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        email_verified INTEGER DEFAULT 0,
        verification_token TEXT,
        reset_token TEXT,
        registered_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
""")

    for cat in ("grading","teaching","strictness","communication","textbooks"):
        conn.execute("INSERT OR IGNORE INTO rating_categories (name) VALUES (?)", (cat,))


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
            ROUND(AVG(CASE WHEN rc.name = 'textbooks'     THEN rs.score END), 1) AS avg_textbooks,
            COUNT(DISTINCT CASE WHEN ra.sentiment = 'Positive' THEN r.id END) AS positive_count,
            COUNT(DISTINCT CASE WHEN ra.sentiment = 'Negative' THEN r.id END) AS negative_count,
            COUNT(DISTINCT CASE WHEN ra.sentiment = 'Neutral'  THEN r.id END) AS neutral_count
        FROM lecturers l
        LEFT JOIN lecturer_courses  lc ON l.id        = lc.lecturer_id
        LEFT JOIN courses            c ON lc.course_id = c.id
        LEFT JOIN faculties          f ON c.faculty_id = f.id
        LEFT JOIN ratings            r ON l.id        = r.lecturer_id
        LEFT JOIN rating_scores     rs ON r.id        = rs.rating_id
        LEFT JOIN rating_categories rc ON rs.category_id = rc.id
        LEFT JOIN rating_analysis   ra ON r.id        = ra.rating_id
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

# email verification 
def generate_verification_token(email):
    """Signed, self-expiring token (no DB column needed for expiry)."""
    return serializer.dumps(email, salt="email-verify")
 
 
def confirm_verification_token(token, max_age=VERIFY_TOKEN_MAX_AGE):
    """Returns the email if the token is valid and not expired, else None."""
    try:
        return serializer.loads(token, salt="email-verify", max_age=max_age)
    except Exception:
        return None
 
 
def send_verification_email(email, token):
    verify_link = url_for("verify_email", token=token, _external=True)
    msg = Message(
        subject="Verify your MMU RateMyProfessor account",
        recipients=[email]
    )
    msg.body = f"""Welcome!
 
Please verify your account by clicking the link below:
{verify_link}
 
This link expires in 24 hours. If you didn't create this account, you can ignore this email.
"""
    mail.send(msg)

# student authentication
def is_student():
    return "student_id" in session

def require_student(lecturer_id=None):
    
    if not is_student():
        flash("Please log in to rate lecturers ya.", "error")
        
        if lecturer_id:
            return redirect(url_for("student_login_page", next=lecturer_id))
        
        return redirect(url_for("student_login_page"))

    return None


def is_admin():
    return session .get("admin_logged_in") is True

def require_admin():
    if not is_admin():
        flash("Admin access required.", "error")
        return redirect(url_for("admin_login_page"))
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
    reviews = conn.execute("""
        SELECT
            r.id, r.student_id, r.comment, r.submitted_at,
            MAX(CASE WHEN rc.name = 'grading'       THEN rs.score END) AS grading,
            MAX(CASE WHEN rc.name = 'teaching'      THEN rs.score END) AS teaching,
            MAX(CASE WHEN rc.name = 'strictness'    THEN rs.score END) AS strictness,
            MAX(CASE WHEN rc.name = 'communication' THEN rs.score END) AS communication,
            MAX(CASE WHEN rc.name = 'textbooks'     THEN rs.score END) AS textbooks,
            ra.sentiment,
            ra.sentiment_score
        FROM ratings r
        LEFT JOIN rating_scores     rs ON r.id        = rs.rating_id
        LEFT JOIN rating_categories rc ON rs.category_id = rc.id
        LEFT JOIN rating_analysis   ra ON r.id        = ra.rating_id
        WHERE r.lecturer_id = ?
        GROUP BY r.id
        ORDER BY r.submitted_at DESC
    """, (lecturer_id,)).fetchall()
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
    
    if redir := require_student(lecturer_id):
        return redir
    
    conn = connect_db()
    lecturer = conn.execute("SELECT * FROM lecturers WHERE id = ?", (lecturer_id,)).fetchone()
    conn.close()
    if lecturer is None:
        return "Lecturer not found", 404

    if request.method == "POST":
        student_id    = session["student_id"]
        grading       = request.form.get("grading", "")
        teaching      = request.form.get("teaching", "")
        strictness    = request.form.get("strictness", "")
        communication = request.form.get("communication", "")
        textbooks     = request.form.get("textbooks", "")
        comment       = request.form.get("comment", "").strip()

        if not all([grading, teaching, strictness, communication, textbooks]):
            flash("Please fill in all 5 rating categories.", "error")
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

        cur = conn.execute(
            "INSERT INTO ratings (lecturer_id, student_id, comment) VALUES (?,?,?)",
            (lecturer_id, student_id, comment)
        )
        rating_id = cur.lastrowid

 # ── ML SENTIMENT ANALYSIS ─────────────────────
        score = analyzer.polarity_scores(comment)["compound"]
        if score >= 0.05:
            sentiment = "Positive"
        elif score <= -0.05:
            sentiment = "Negative"
        else:
            sentiment = "Neutral"
        conn.execute(
            "INSERT INTO rating_analysis (rating_id, sentiment, sentiment_score) VALUES (?,?,?)",
            (rating_id, sentiment, score)
    )
# ──────────────────────────────────────────
        category_names = ["grading","teaching","strictness","communication","textbooks"]
        for name, cat_score in zip(category_names, scores):
            cat = conn.execute(
                "SELECT id FROM rating_categories WHERE name = ?", (name,)
            ).fetchone()
            conn.execute(
                "INSERT INTO rating_scores (rating_id, category_id, score) VALUES (?,?,?)",
                (rating_id, cat["id"], cat_score)
            )
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


# ── Student register ───────────────────────────────────────────────────
@app.route("/register", methods=["GET", "POST"])
def student_register_page():
    if request.method == "POST":
        student_id = request.form.get("student_id", "").strip()
        email = request.form.get("email", "").strip().lower()
        password   = request.form.get("password", "")
        confirm = request.form.get("confirm", "")

        if not student_id or not email or not password:
            flash("Please fill in all fields.", "error")
            return redirect(url_for("student_register_page"))
        
        if not email.endswith("@student.mmu.edu.my"):
            flash("Please register using your MMU student email.", "error")
            return redirect(url_for("student_register_page"))
        
        if len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
            return redirect(url_for("student_register_page"))
    
        if password != confirm:
            flash("Passwords do not match.", "error")
            return redirect(url_for("student_register_page"))

        conn = connect_db()
        student = conn.execute(
            "SELECT 1 FROM students WHERE student_id = ? OR email = ?", (student_id, email)
        ).fetchone()
        if student:
            flash("That student ID or email is already registered.", "error")
            conn.close()
            return redirect(url_for("student_register_page"))
 
        token = generate_verification_token(email)
        conn.execute(
            "INSERT INTO students (student_id, email, password_hash, verification_token) VALUES (?, ?, ?, ?)",
            (student_id, email, generate_password_hash(password), token)
        )
        conn.commit()
        conn.close()
 
        try:
            send_verification_email(email, token)
        except Exception as e:
            print(f"Failed to send verification email: {e}")
            flash("Account created, but we couldn't send the verification email. "
                  "Please use 'Resend verification email' on the login page.", "error")
            return redirect(url_for("student_login_page"))
 
        flash("Account created! Please check your MMU email to verify your account.", "success")
        return redirect(url_for("student_login_page"))
    return render_template("register.html")

@app.route("/verify-email/<token>")
def verify_email(token):
    email = confirm_verification_token(token)
    if email is None:
        flash("That verification link is invalid or has expired. Please request a new one.", "error")
        return redirect(url_for("resend_verification_page"))
 
    conn = connect_db()
    student = conn.execute("SELECT * FROM students WHERE email = ?", (email,)).fetchone()
    if student is None:
        conn.close()
        flash("Account not found.", "error")
        return redirect(url_for("student_register_page"))
 
    if student["email_verified"]:
        conn.close()
        flash("Your email is already verified. You can log in.", "success")
        return redirect(url_for("student_login_page"))
 
    conn.execute(
        "UPDATE students SET email_verified = 1, verification_token = NULL WHERE email = ?",
        (email,)
    )
    conn.commit()
    conn.close()
    flash("Your email has been verified! You can now log in.", "success")
    return redirect(url_for("student_login_page"))
 
 
@app.route("/resend-verification", methods=["GET", "POST"])
def resend_verification_page():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        conn = connect_db()
        student = conn.execute("SELECT * FROM students WHERE email = ?", (email,)).fetchone()
 
        # Always show the same message whether or not the email exists,
        # so this endpoint can't be used to enumerate registered emails.
        if student and not student["email_verified"]:
            token = generate_verification_token(email)
            conn.execute(
                "UPDATE students SET verification_token = ? WHERE email = ?",
                (token, email)
            )
            conn.commit()
            try:
                send_verification_email(email, token)
            except Exception as e:
                print(f"Failed to resend verification email: {e}")
        conn.close()
        flash("If that email is registered and unverified, a new verification link has been sent.", "success")
        return redirect(url_for("student_login_page"))
    return render_template("resend-verification.html") 

@app.route("/login", methods=["GET", "POST"])
def student_login_page():
    next_id = request.args.get("next")
    if request.method == "POST":
        student_id = request.form.get("student_id", "").strip()
        password   = request.form.get("password", "")
 
        conn = connect_db()
        student = conn.execute(
            "SELECT * FROM students WHERE student_id = ?", (student_id,)
        ).fetchone()
        conn.close()
 
        if not student:
            flash("Student ID not found. Please register first.", "error")
        elif not check_password_hash(student["password_hash"], password):
            flash("Incorrect password.", "error")
        elif not student["email_verified"]:
            flash("Please verify your email before logging in. "
                  "Check your inbox, or request a new link below.", "error")
            return redirect(url_for("resend_verification_page"))
        else:
            session.permanent = True
            session["student_id"] = student_id
            if next_id:
                return redirect(url_for("rate_page", lecturer_id=next_id))
            return redirect(url_for("home_page"))
 
    return render_template("login.html", next=next_id)

@app.route("/logout", methods=["POST"])
def student_logout():
    session.pop("student_id", None)
    flash("You have been logged out.", "success")
    return redirect(url_for("home_page"))

# ── Admin login / logout ──────────────────────────────────────────────────────
# CHANGED: new routes — admin must prove identity before seeing the dashboard.
 
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login_page():
    # Already logged in? Go straight to dashboard
    if is_admin():
        return redirect(url_for("admin_page"))
 
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if username == ADMIN_USERNAME and check_password_hash(ADMIN_PASSWORD, password):
            session["admin_logged_in"] = True
            flash("Welcome, admin.", "success")
            return redirect(url_for("admin_page"))
        flash("Incorrect username or password.", "error")
 
    return render_template("admin_login.html")
 
@app.route("/admin/logout", methods=["POST"])
def admin_logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("admin_login_page"))

# -------- ADMIN ----------
# NEW ROUTE: Admin dashboard — shows all pending requests
@app.route("/admin")
def admin_page():
    if redir := require_admin():
        return redir
    pconn = connect_pending()
    pending = pconn.execute(
        "SELECT * FROM requests ORDER BY submitted_at DESC"
    ).fetchall()
    pconn.close()
    return render_template("admin.html", requests=pending,)


# NEW ROUTE: Accept — moves request from pending.db into mmu_ratings.db
@app.route("/admin/accept/<int:request_id>", methods=["POST"])
def admin_accept(request_id):
    if redir := require_admin():
        return redir
    pconn = connect_pending()
    req = pconn.execute(
        "SELECT * FROM requests WHERE id = ?", (request_id,)
    ).fetchone()

    if req:
        conn = connect_db()
        faculty_row = conn.execute(
            "SELECT id FROM faculties WHERE name = ?", (req["faculty"],)
        ).fetchone()
        if faculty_row:
            faculty_id = faculty_row["id"]
        else:
            cur = conn.execute(
                "INSERT INTO faculties (name) VALUES (?)", (req["faculty"],)
            )
            faculty_id = cur.lastrowid

        course_row = conn.execute(
            "SELECT id FROM courses WHERE course_code = ?", (req["course_code"],)
        ).fetchone()
        if course_row:
            course_id = course_row["id"]
        else:
            cur = conn.execute(
                "INSERT INTO courses (course_code, course_name, faculty_id) VALUES (?,?,?)",
                (req["course_code"], req["course"], faculty_id)
            )
            course_id = cur.lastrowid

        cur = conn.execute(
                "INSERT INTO lecturers (name, faculty_id, image) VALUES (?,?,?)",
                (req["name"], faculty_id, req["image"])
         )
            
        lecturer_id = cur.lastrowid

        conn.execute(
            "INSERT OR IGNORE INTO lecturer_courses (lecturer_id, course_id) VALUES (?,?)",
            (lecturer_id, course_id)
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
    if redir := require_admin():
        return redir
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

# route to lists of lecturers (admin)
@app.route("/admin/lecturers")
def admin_lecturers_page():
    if redir := require_admin():
        return redir
    all_lecturers = get_all_lecturers()
    return render_template("admin-lecturers.html", lecturers=all_lecturers)

# -------- ADMIN ----------

# NEW ROUTE: Delete a lecturer and all associated data
@app.route("/admin/delete-lecturer/<int:lecturer_id>", methods=["POST"])
def admin_delete_lecturer(lecturer_id):
    if redir := require_admin():
        return redir

    conn = connect_db()
    lecturer = conn.execute(
        "SELECT * FROM lecturers WHERE id = ?", (lecturer_id,)
    ).fetchone()

    if lecturer is None:
        conn.close()
        flash("Lecturer not found.", "error")
        return redirect(url_for("admin_page"))

    # Delete rating_scores tied to this lecturer's ratings
    conn.execute("""
        DELETE FROM rating_scores
        WHERE rating_id IN (SELECT id FROM ratings WHERE lecturer_id = ?)
    """, (lecturer_id,))

    # Delete the ratings themselves
    conn.execute("DELETE FROM ratings WHERE lecturer_id = ?", (lecturer_id,))

    # Delete lecturer-course links
    conn.execute("DELETE FROM lecturer_courses WHERE lecturer_id = ?", (lecturer_id,))

    # Delete the lecturer record
    conn.execute("DELETE FROM lecturers WHERE id = ?", (lecturer_id,))

    conn.commit()
    conn.close()

    # Clean up uploaded image file, if any
    if lecturer["image"]:
        image_path = os.path.join(UPLOAD_DIR, lecturer["image"])
        if os.path.exists(image_path):
            try:
                os.remove(image_path)
            except Exception as e:
                print(f"Image delete error: {e}")

    flash(f'"{lecturer["name"]}" has been deleted.', "success")
    return redirect(url_for("admin_page"))


# NEW ROUTE: Edit a lecturer's name / faculty / image
@app.route("/admin/edit-lecturer/<int:lecturer_id>", methods=["GET", "POST"])
def admin_edit_lecturer(lecturer_id):
    if redir := require_admin():
        return redir

    conn = connect_db()
    lecturer = conn.execute(
        "SELECT * FROM lecturers WHERE id = ?", (lecturer_id,)
    ).fetchone()

    if lecturer is None:
        conn.close()
        flash("Lecturer not found.", "error")
        return redirect(url_for("admin_page"))

    if request.method == "POST":
        name        = request.form.get("name", "").strip()
        faculty_name = request.form.get("faculty", "").strip()
        image_b64   = request.form.get("image")  # optional new image, base64 data URL

        if not name:
            flash("Lecturer name is required.", "error")
            conn.close()
            return redirect(url_for("admin_edit_lecturer", lecturer_id=lecturer_id))

        # Resolve or create faculty
        faculty_row = conn.execute(
            "SELECT id FROM faculties WHERE name = ?", (faculty_name,)
        ).fetchone()
        if faculty_row:
            faculty_id = faculty_row["id"]
        else:
            cur = conn.execute(
                "INSERT INTO faculties (name) VALUES (?)", (faculty_name,)
            )
            faculty_id = cur.lastrowid

        # Handle optional new image
        new_filename = save_image(image_b64) if image_b64 else None
        if new_filename:
            # remove old image file
            if lecturer["image"]:
                old_path = os.path.join(UPLOAD_DIR, lecturer["image"])
                if os.path.exists(old_path):
                    try:
                        os.remove(old_path)
                    except Exception as e:
                        print(f"Image delete error: {e}")
            conn.execute(
                "UPDATE lecturers SET name = ?, faculty_id = ?, image = ? WHERE id = ?",
                (name, faculty_id, new_filename, lecturer_id)
            )
        else:
            conn.execute(
                "UPDATE lecturers SET name = ?, faculty_id = ? WHERE id = ?",
                (name, faculty_id, lecturer_id)
            )

        conn.commit()
        conn.close()
        flash(f'"{name}" has been updated.', "success")
        return redirect(url_for("admin_page"))

    conn.close()
    return render_template("edit-lecturer.html", lecturer=lecturer)
# -------- ADMIN ----------

# ── Run ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    setup_database()
    print("=" * 52)
    print("  MMU RateMyProfessor →  http://localhost:5000")
    print("=" * 52)
    app.run(debug=True)
