# MMU RateMyProfessor

An anonymous lecturer rating platform for MMU students.
Built with Python (Flask) + SQLite.

---

## Setup & Run

### 1. Install Flask
```
pip install flask
```

### 2. Run the app
```
python app.py
```

### 3. Open in browser
```
http://127.0.0.1:5000
```

---

## Project Structure

```
mmu_ratemyprof/
├── app.py                  ← Main Python file (database + routes)
├── mmu_ratings.db          ← SQLite database (auto-created on first run)
├── templates/
│   ├── base.html           ← Shared layout (navbar, styles)
│   ├── index.html          ← Homepage: list all lecturers + scores
│   ├── profile.html        ← Lecturer profile: breakdown + reviews
│   └── rate.html           ← Submit a rating form
└── README.md
```

---

## Features (Week 2 Build)

- SQLite database with `lecturers` and `ratings` tables
- 5 seeded sample lecturers on first launch
- Homepage listing all lecturers sorted by average score
- Score colour-coded: green (4+), amber (2.5–4), red (<2.5)
- Lecturer profile with per-category bar chart breakdown
- Anonymous rating submission with 5 categories (1–5 stars each)
- Written comment (optional)
- Flash messages for success / error feedback
- Form validation (all 5 categories required, scores must be 1–5)

---

## Database Schema

```sql
CREATE TABLE lecturers (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    faculty     TEXT NOT NULL,
    course      TEXT NOT NULL,
    course_code TEXT NOT NULL
);

CREATE TABLE ratings (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    lecturer_id   INTEGER NOT NULL,
    grading       INTEGER NOT NULL,  -- 1 to 5
    teaching      INTEGER NOT NULL,
    strictness    INTEGER NOT NULL,
    communication INTEGER NOT NULL,
    textbooks     INTEGER NOT NULL,
    comment       TEXT,
    submitted_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (lecturer_id) REFERENCES lecturers(id)
);
```

---

## My Role (Responsibilities Demonstrated)

| Responsibility       | Where it appears                                      |
|----------------------|-------------------------------------------------------|
| Database management  | `init_db()`, schema in `app.py`, SQLite file          |
| Display ratings      | `index.html`, `profile.html` with averages + charts   |
| Testing & bug fixing | Form validation, error flash messages, edge cases     |
