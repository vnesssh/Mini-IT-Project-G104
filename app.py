from flask import Flask, render_template, request, redirect, url_for, flash

import sqlite3

app = Flask(__name__)

app.secret_key = "the_strongest_secret_key_in_the_world_12345"  

DB_FILE = "mmu_ratings.db"

# DATABASE FUNCTIONS

def connect_db():
    """
    Opens a connection to the database file.
    row_factory = sqlite3.Row means we can access columns by name
    For example: row['name'] instead of row[0]
    """
    connection = sqlite3.connect(DB_FILE)
    connection.row_factory = sqlite3.Row
    return connection

def setup_database():
    """
    Creates the database tables if they don't exist yet.
    This runs once when the program starts.

    We have 2 tables:
      - lecturers : stores lecturer info (name, faculty, course, course code)
      - ratings   : stores each student's rating for a lecturer
    """
    connection = connect_db()
    connection.execute("""
        CREATE TABLE IF NOT EXISTS lecturers (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            faculty     TEXT NOT NULL,
            course      TEXT NOT NULL,
            course_code TEXT NOT NULL
        )
    """)
    connection.execute("""
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
            submitted_at  DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    connection.commit()
    connection.close()


def get_all_lecturers_with_scores():
    """
    Gets all lecturers from the database.
    Also calculates the average score for each lecturer using their ratings.
    Returns a list of lecturers sorted from highest score to lowest.
    """
    connection = connect_db()
    all_lecturers = connection.execute("""
        SELECT
            l.id,
            l.name,
            l.faculty,
            l.course,
            l.course_code,
            COUNT(r.id) AS review_count,
            ROUND(AVG((r.grading + r.teaching + r.strictness + r.communication + r.textbooks) / 5.0), 1) AS overall,
            ROUND(AVG(r.grading), 1)       AS avg_grading,
            ROUND(AVG(r.teaching), 1)      AS avg_teaching,
            ROUND(AVG(r.strictness), 1)    AS avg_strictness,
            ROUND(AVG(r.communication), 1) AS avg_communication,
            ROUND(AVG(r.textbooks), 1)     AS avg_textbooks
        FROM lecturers l
        LEFT JOIN ratings r ON l.id = r.lecturer_id
        GROUP BY l.id
        ORDER BY overall DESC
    """).fetchall()

    connection.close()
    return all_lecturers


def get_one_lecturer_with_scores(lecturer_id):
    """
    Gets one specific lecturer by their ID.
    Also calculates their average scores, same as above.
    Returns a single lecturer row, or None if not found.
    """
    connection = connect_db()

    lecturer = connection.execute("""
        SELECT
            l.id,
            l.name,
            l.faculty,
            l.course,
            l.course_code,
            COUNT(r.id) AS review_count,
            ROUND(AVG((r.grading + r.teaching + r.strictness + r.communication + r.textbooks) / 5.0), 1) AS overall,
            ROUND(AVG(r.grading), 1)       AS avg_grading,
            ROUND(AVG(r.teaching), 1)      AS avg_teaching,
            ROUND(AVG(r.strictness), 1)    AS avg_strictness,
            ROUND(AVG(r.communication), 1) AS avg_communication,
            ROUND(AVG(r.textbooks), 1)     AS avg_textbooks
        FROM lecturers l
        LEFT JOIN ratings r ON l.id = r.lecturer_id
        WHERE l.id = ?
        GROUP BY l.id
    """, (lecturer_id,)).fetchone()
    connection.close()
    return lecturer



@app.route("/")
def home_page():
    all_lecturers = get_all_lecturers_with_scores()

    return render_template("index.html", lecturers=all_lecturers)


@app.route("/lecturer/<int:lecturer_id>")
def profile_page(lecturer_id):
    
    lecturer = get_one_lecturer_with_scores(lecturer_id)

    if lecturer is None:
        return "Lecturer not found", 404

    connection = connect_db()
    all_reviews = connection.execute(
        "SELECT * FROM ratings WHERE lecturer_id = ? ORDER BY submitted_at DESC",
        (lecturer_id,)
    ).fetchall()
    connection.close()

    return render_template("profile.html", lecturer=lecturer, reviews=all_reviews)

@app.route("/rate/<int:lecturer_id>", methods=["GET", "POST"])
def rate_page(lecturer_id):

    connection = connect_db()
    lecturer = connection.execute(
        "SELECT * FROM lecturers WHERE id = ?", (lecturer_id,)
    ).fetchone()
    connection.close()

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

        if student_id == "" or grading == "" or teaching == "" or strictness == "" or communication == "" or textbooks == "":
            flash("Please enter your Student ID and rate all 5 categories before submitting.", "error")
            return redirect(url_for("rate_page", lecturer_id=lecturer_id))

        try:
            grading       = int(grading)
            teaching      = int(teaching)
            strictness    = int(strictness)
            communication = int(communication)
            textbooks     = int(textbooks)
        except ValueError:
            flash("Invalid scores. Please use the star buttons.", "error")
            return redirect(url_for("rate_page", lecturer_id=lecturer_id))

        scores = [grading, teaching, strictness, communication, textbooks]
        for score in scores:
            if score < 1 or score > 5:
                flash("All scores must be between 1 and 5.", "error")
                return redirect(url_for("rate_page", lecturer_id=lecturer_id))

        connection = connect_db()

        duplicate = connection.execute(
            "SELECT 1 FROM ratings WHERE lecturer_id = ? AND student_id = ?",
            (lecturer_id, student_id)
        ).fetchone()

        if duplicate:
            flash("You have already rated this lecturer.", "error")
            return redirect(url_for("rate_page", lecturer_id=lecturer_id))

        connection.execute("""
            INSERT INTO ratings (lecturer_id, student_id,grading, teaching, strictness, communication, textbooks, comment)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (lecturer_id, student_id, grading, teaching, strictness, communication, textbooks, comment))
        connection.commit()
        connection.close()

        flash("Your rating has been submitted anonymously. Thank you!", "success")
        return redirect(url_for("profile_page", lecturer_id=lecturer_id))

    return render_template("rate.html", lecturer=lecturer)


@app.route("/admin/add-lecturer", methods=["GET", "POST"])
def add_lecturer_page():

    if request.method == "POST":

        name        = request.form.get("name", "").strip()
        faculty     = request.form.get("faculty", "").strip()
        course      = request.form.get("course", "").strip()
        course_code = request.form.get("course_code", "").strip().upper()

        if name == "" or faculty == "" or course == "" or course_code == "":
            flash("All fields are required.", "error")
            return redirect(url_for("add_lecturer_page"))

        connection = connect_db()
        connection.execute(
            "INSERT INTO lecturers (name, faculty, course, course_code) VALUES (?, ?, ?, ?)",
            (name, faculty, course, course_code)
        )
        connection.commit()
        connection.close()

        flash(name + " has been added successfully.", "success")
        return redirect(url_for("add_lecturer_page"))

    connection = connect_db()
    all_lecturers = connection.execute(
        "SELECT * FROM lecturers ORDER BY name"
    ).fetchall()
    connection.close()

    return render_template("add_lecturer.html", lecturers=all_lecturers)


# it does NOT run if this file is imported by another file
if __name__ == "__main__":
    setup_database()

    app.run(debug=True)