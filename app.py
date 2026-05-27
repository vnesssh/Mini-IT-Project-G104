import sqlite3

from flask import Flask, render_template, request

app = Flask(__name__)

# fake account
correct_username = "admin"
correct_password = "1234"

@app.route('/')
def home():
    return render_template("login.html")

@app.route('/login', methods=['POST'])
def login():

    username = request.form['username']
    password = request.form['password']

    if username == correct_username and password == correct_password:
        return "Login successful ✅"

    else:
        return "Wrong username or password ❌"

@app.route('/review')
def review():
    return render_template("review.html")


@app.route('/reviews')
def reviews():

    conn = sqlite3.connect('reviews.db')
    c = conn.cursor()

    c.execute("SELECT * FROM reviews")

    data = c.fetchall()

    conn.close()

    return str(data)


@app.route('/submit_review', methods=['POST'])
def submit_review():

    lecturer = request.form['lecturer']
    rating = request.form['rating']
    comment = request.form['comment']

    conn = sqlite3.connect('reviews.db')
    c = conn.cursor()

    c.execute(
        "INSERT INTO reviews (lecturer, rating, comment) VALUES (?, ?, ?)",
        (lecturer, rating, comment)
    )

    conn.commit()
    conn.close()

    return "Review submitted successfully ✅"
if __name__ == '__main__':
    app.run(debug=True)