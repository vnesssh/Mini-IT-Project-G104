# MMU RATEMYPROFESSOR - MAIN APPLICATION FILE

# MY RESPONSIBILITIES IN THIS PROJECT:
#   1. Database management  - setting up tables, saving and reading data
#   2. Display ratings      - calculating averages and sending to the webpage
#   3. Testing & bug fixing - checking for bad inputs and handling errors

# render_template - loads an HTML file and sends it to the browser
# request         - reads data that was submitted from a form
# redirect        - sends the user to a different page
# url_for         - gets the link to a page by its function name
# flash           - shows a one-time message to the user (like "Success!")
from flask import Flask, render_template, request, redirect, url_for, flash


import sqlite3

# create the Flask app
app = Flask(__name__)

# secret_key is required for flash messages to work
app.secret_key = "mmu_secret_key_2024"

# this is the name of our database file
# it will be created automatically when the program runs for the first time
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

    # create the lecturers table
    # if not exists means it won't crash if the table already exists
    connection.execute("""
        CREATE TABLE IF NOT EXISTS lecturers (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            faculty     TEXT NOT NULL,
            course      TEXT NOT NULL,
            course_code TEXT NOT NULL
        )
    """)

    # create the ratings table
    # lecturer_id links each rating to a lecturer in the lecturers table
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

    # AVG() calculates the average of a column
    # ROUND(..., 1) rounds to 1 decimal place
    # LEFT JOIN means even lecturers with no ratings will still show up
    # COUNT(r.id) counts how many ratings a lecturer has
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
    # the '?' is a placeholder - sqlite3 fills it in safely to prevent hacking

    connection.close()
    return lecturer



# PAGES (ROUTES)

# each function below is a "page" on the website.
# @app.route("/something") means: when the user visits that URL, run this function.


# HOME PAGE - shows all lecturers and their scores

@app.route("/")
def home_page():
    # get all lecturers from the database with their average scores
    all_lecturers = get_all_lecturers_with_scores()

    # send the lecturer data to the HTML file to be displayed
    return render_template("index.html", lecturers=all_lecturers)



# LECTURER PROFILE PAGE - shows one lecturer's full breakdown and reviews

@app.route("/lecturer/<int:lecturer_id>")
def profile_page(lecturer_id):
    # get this specific lecturer's data
    lecturer = get_one_lecturer_with_scores(lecturer_id)

    # if no lecturer was found with that ID, show an error
    if lecturer is None:
        return "Lecturer not found", 404

    # get all the written reviews for this lecturer
    connection = connect_db()
    all_reviews = connection.execute(
        "SELECT * FROM ratings WHERE lecturer_id = ? ORDER BY submitted_at DESC",
        (lecturer_id,)
    ).fetchall()
    connection.close()

    # send both the lecturer and their reviews to the HTML file
    return render_template("profile.html", lecturer=lecturer, reviews=all_reviews)



# RATE A LECTURER PAGE - form where students submit a rating

# methods=["GET", "POST"] means this page can both load (GET) and receive a form (POST)
@app.route("/rate/<int:lecturer_id>", methods=["GET", "POST"])
def rate_page(lecturer_id):
    # get the lecturer's basic info
    connection = connect_db()
    lecturer = connection.execute(
        "SELECT * FROM lecturers WHERE id = ?", (lecturer_id,)
    ).fetchone()
    connection.close()

    # if lecturer doesn't exist, show error
    if lecturer is None:
        return "Lecturer not found", 404

    # if the student just submitted the form (clicked submit button)
    if request.method == "POST":

        # read the scores from the submitted form
        # request.form.get("grading") gets the value of the input named "grading"
        grading       = request.form.get("grading", "")
        teaching      = request.form.get("teaching", "")
        strictness    = request.form.get("strictness", "")
        communication = request.form.get("communication", "")
        textbooks     = request.form.get("textbooks", "")
        comment       = request.form.get("comment", "").strip()

        # check that none of the scores are empty
        if grading == "" or teaching == "" or strictness == "" or communication == "" or textbooks == "":
            flash("Please rate all 5 categories before submitting.", "error")
            return redirect(url_for("rate_page", lecturer_id=lecturer_id))

        # convert scores from text to numbers
        # int() converts a string like "4" to the number 4
        try:
            grading       = int(grading)
            teaching      = int(teaching)
            strictness    = int(strictness)
            communication = int(communication)
            textbooks     = int(textbooks)
        except ValueError:
            # this runs if int() fails (e.g. someone typed a word instead of a number)
            flash("Invalid scores. Please use the star buttons.", "error")
            return redirect(url_for("rate_page", lecturer_id=lecturer_id))

        # check that all scores are between 1 and 5
        scores = [grading, teaching, strictness, communication, textbooks]
        for score in scores:
            if score < 1 or score > 5:
                flash("All scores must be between 1 and 5.", "error")
                return redirect(url_for("rate_page", lecturer_id=lecturer_id))

        # everything is valid - save the rating to the database
        connection = connect_db()
        connection.execute("""
            INSERT INTO ratings (lecturer_id, grading, teaching, strictness, communication, textbooks, comment)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (lecturer_id, grading, teaching, strictness, communication, textbooks, comment))
        connection.commit()
        connection.close()

        # show a success message and send user back to the lecturer's profile
        flash("Your rating has been submitted anonymously. Thank you!", "success")
        return redirect(url_for("profile_page", lecturer_id=lecturer_id))

    # if the student just opened the page (not submitting), show the form
    return render_template("rate.html", lecturer=lecturer)



# ADD LECTURER PAGE - admin page to add new lecturers to the database

@app.route("/admin/add-lecturer", methods=["GET", "POST"])
def add_lecturer_page():

    # if someone submitted the add lecturer form
    if request.method == "POST":

        # read the inputs from the form
        name        = request.form.get("name", "").strip()
        faculty     = request.form.get("faculty", "").strip()
        course      = request.form.get("course", "").strip()
        course_code = request.form.get("course_code", "").strip().upper()
        # .strip() removes extra spaces from start and end
        # .upper() makes the course code uppercase e.g. csc3024 -> CSC3024

        # check that none of the fields are empty
        if name == "" or faculty == "" or course == "" or course_code == "":
            flash("All fields are required.", "error")
            return redirect(url_for("add_lecturer_page"))

        # save the new lecturer to the database
        connection = connect_db()
        connection.execute(
            "INSERT INTO lecturers (name, faculty, course, course_code) VALUES (?, ?, ?, ?)",
            (name, faculty, course, course_code)
        )
        connection.commit()
        connection.close()

        flash(name + " has been added successfully.", "success")
        return redirect(url_for("add_lecturer_page"))

    # load the page - also show the list of existing lecturers
    connection = connect_db()
    all_lecturers = connection.execute(
        "SELECT * FROM lecturers ORDER BY name"
    ).fetchall()
    connection.close()

    return render_template("add_lecturer.html", lecturers=all_lecturers)



# START THE PROGRAM

# it does NOT run if this file is imported by another file
if __name__ == "__main__":
    # create the database tables if they don't exist yet
    setup_database()

    # start the website
    # debug=True means errors show in the browser and server restarts when you save
    app.run(debug=True)