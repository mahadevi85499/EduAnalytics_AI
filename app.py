from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
import random

app = Flask(__name__)
app.secret_key = os.urandom(24)

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "students.db")

# ---------------- DATABASE SETUP ----------------
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # Check if old schema (no attendance column)
    cursor.execute("PRAGMA table_info(students)")
    columns = [col['name'] for col in cursor.fetchall()]

    if 'attendance' not in columns:
        # Migrate: add new columns to existing table
        if 'students' in [t['name'] for t in cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]:
            try:
                cursor.execute("ALTER TABLE students ADD COLUMN attendance INTEGER DEFAULT 75")
            except Exception:
                pass
            try:
                cursor.execute("ALTER TABLE students ADD COLUMN engagement INTEGER DEFAULT 60")
            except Exception:
                pass
            try:
                cursor.execute("ALTER TABLE students ADD COLUMN quiz_scores INTEGER DEFAULT 50")
            except Exception:
                pass
            try:
                cursor.execute("ALTER TABLE students ADD COLUMN department TEXT DEFAULT 'General'")
            except Exception:
                pass
            # Set random-ish values for existing rows that have defaults
            cursor.execute("SELECT id FROM students")
            for row in cursor.fetchall():
                cursor.execute("""
                    UPDATE students SET
                        attendance = ?,
                        engagement = ?,
                        quiz_scores = ?,
                        department = ?
                    WHERE id = ? AND attendance = 75
                """, (
                    random.randint(40, 98),
                    random.randint(30, 95),
                    random.randint(20, 100),
                    random.choice(['Computer Science', 'Mathematics', 'Physics', 'English', 'History', 'Fine Arts']),
                    row['id']
                ))
        else:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS students (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    marks INTEGER DEFAULT 0,
                    attendance INTEGER DEFAULT 75,
                    engagement INTEGER DEFAULT 60,
                    quiz_scores INTEGER DEFAULT 50,
                    department TEXT DEFAULT 'General'
                )
            """)
    # Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT DEFAULT '',
            role TEXT DEFAULT 'admin',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Seed a default admin account if no users exist
    cursor.execute("SELECT COUNT(*) as cnt FROM users")
    if cursor.fetchone()['cnt'] == 0:
        cursor.execute(
            "INSERT INTO users (username, email, password_hash, full_name, role) VALUES (?, ?, ?, ?, ?)",
            ('admin', 'admin@eduanalytics.com', generate_password_hash('1234'), 'Admin User', 'super_admin')
        )

    conn.commit()
    conn.close()

init_db()


# ---------------- PREDICTION LOGIC ----------------
def predict_student(student):
    """Generate prediction data for a student based on their metrics."""
    marks = student['marks'] or 0
    attendance = student['attendance'] or 0
    engagement = student['engagement'] or 0
    quiz_scores = student['quiz_scores'] or 0

    # Weighted success probability
    success_prob = round(
        marks * 0.35 +
        attendance * 0.25 +
        engagement * 0.22 +
        quiz_scores * 0.18
    )
    success_prob = max(0, min(100, success_prob))

    # Risk level
    if success_prob >= 80:
        risk_level = "Excellent"
        risk_color = "emerald"
    elif success_prob >= 60:
        risk_level = "Stable"
        risk_color = "blue"
    elif success_prob >= 40:
        risk_level = "At Risk"
        risk_color = "amber"
    else:
        risk_level = "Critical"
        risk_color = "red"

    # Predicted grade
    if success_prob >= 90:
        predicted_grade = "A+"
    elif success_prob >= 80:
        predicted_grade = "A"
    elif success_prob >= 70:
        predicted_grade = "B+"
    elif success_prob >= 60:
        predicted_grade = "B"
    elif success_prob >= 50:
        predicted_grade = "C"
    elif success_prob >= 40:
        predicted_grade = "D"
    else:
        predicted_grade = "F"

    # Primary risk factor
    factors = {
        'Low marks': marks,
        'Poor attendance': attendance,
        'Low engagement': engagement,
        'Declining quiz scores': quiz_scores
    }
    primary_factor = min(factors, key=factors.get)

    return {
        'id': student['id'],
        'name': student['name'],
        'marks': marks,
        'attendance': attendance,
        'engagement': engagement,
        'quiz_scores': quiz_scores,
        'department': student['department'] or 'General',
        'success_prob': success_prob,
        'risk_level': risk_level,
        'risk_color': risk_color,
        'predicted_grade': predicted_grade,
        'primary_factor': primary_factor,
        'initials': ''.join([w[0].upper() for w in (student['name'] or 'U').split()[:2]])
    }


# ---------------- HOME / PREDICTIONS ----------------
@app.route("/")
def home():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM students ORDER BY id DESC")
    students_raw = cursor.fetchall()

    predictions = [predict_student(s) for s in students_raw]

    # Stats
    total = len(predictions)
    at_risk_count = len([p for p in predictions if p['risk_level'] in ('At Risk', 'Critical')])
    stable_count = len([p for p in predictions if p['risk_level'] == 'Stable'])
    excellent_count = len([p for p in predictions if p['risk_level'] == 'Excellent'])

    conn.close()

    return render_template(
        "index.html",
        predictions=predictions,
        total=total,
        at_risk_count=at_risk_count,
        stable_count=stable_count,
        excellent_count=excellent_count
    )


# ---------------- LOGIN ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ? OR email = ?", (username, username))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user['password_hash'], password):
            session['logged_in'] = True
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['full_name'] = user['full_name'] or user['username']
            session['role'] = user['role']
            flash(f"Welcome back, {session['full_name']}!", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid username or password.", "error")
            return redirect(url_for("login"))
    return render_template("login.html")


# ---------------- REGISTER ----------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        # Validation
        if not all([full_name, email, username, password]):
            flash("All fields are required.", "error")
            return redirect(url_for("register"))

        if len(password) < 4:
            flash("Password must be at least 4 characters.", "error")
            return redirect(url_for("register"))

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return redirect(url_for("register"))

        conn = get_db()
        cursor = conn.cursor()

        # Check if username or email already exists
        cursor.execute("SELECT id FROM users WHERE username = ? OR email = ?", (username, email))
        if cursor.fetchone():
            conn.close()
            flash("Username or email already taken.", "error")
            return redirect(url_for("register"))

        # Create the account
        cursor.execute(
            "INSERT INTO users (username, email, password_hash, full_name) VALUES (?, ?, ?, ?)",
            (username, email, generate_password_hash(password), full_name)
        )
        conn.commit()
        conn.close()

        flash("Account created successfully! Please sign in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))


# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
def dashboard():
    conn = get_db()
    cursor = conn.cursor()

    # Total students
    cursor.execute("SELECT COUNT(*) as cnt FROM students")
    total_students = cursor.fetchone()['cnt'] or 0

    # Average marks
    cursor.execute("SELECT AVG(marks) as avg_m FROM students")
    row = cursor.fetchone()
    avg_marks = round(row['avg_m'], 2) if row['avg_m'] else 0

    # Passed (marks >= 40)
    cursor.execute("SELECT COUNT(*) as cnt FROM students WHERE marks >= 40")
    passed = cursor.fetchone()['cnt'] or 0

    # At risk (marks < 40)
    cursor.execute("SELECT COUNT(*) as cnt FROM students WHERE marks < 40")
    at_risk = cursor.fetchone()['cnt'] or 0

    # Pass percentage
    pass_percentage = round((passed / total_students) * 100, 2) if total_students > 0 else 0

    # Get all students for prediction table
    cursor.execute("SELECT * FROM students ORDER BY marks ASC LIMIT 10")
    students_raw = cursor.fetchall()
    predictions = [predict_student(s) for s in students_raw]

    conn.close()

    # AI suggestion
    if at_risk == 0:
        suggestion = "🎉 All students are performing well!"
    elif at_risk <= 3:
        suggestion = f"⚠ {at_risk} student(s) are at risk. Consider providing extra support."
    else:
        suggestion = f"🚨 {at_risk} students are at risk! Immediate intervention recommended."

    return render_template(
        "dashboard.html",
        total_students=total_students,
        avg_marks=avg_marks,
        pass_percentage=pass_percentage,
        passed=passed,
        at_risk=at_risk,
        suggestion=suggestion,
        predictions=predictions
    )


# ---------------- ADD STUDENT ----------------
@app.route("/add_student", methods=["GET", "POST"])
def add_student():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        marks = request.form.get("marks", 0, type=int)
        attendance = request.form.get("attendance", 75, type=int)
        engagement = request.form.get("engagement", 60, type=int)
        quiz_scores = request.form.get("quiz_scores", 50, type=int)
        department = request.form.get("department", "General").strip()

        if not name:
            flash("Student name is required.", "error")
            return redirect(url_for("add_student"))

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO students (name, marks, attendance, engagement, quiz_scores, department) VALUES (?, ?, ?, ?, ?, ?)",
            (name, marks, attendance, engagement, quiz_scores, department)
        )
        conn.commit()
        conn.close()
        flash(f"Student '{name}' added successfully!", "success")
        return redirect(url_for("dashboard"))
    return render_template("add_student.html")


# ---------------- VIEW STUDENTS ----------------
@app.route("/students")
def students():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM students ORDER BY id DESC")
    data = cursor.fetchall()
    predictions = [predict_student(s) for s in data]
    conn.close()
    return render_template("students.html", students=predictions)


# ---------------- EDIT STUDENT ----------------
@app.route("/edit_student/<int:id>", methods=["GET", "POST"])
def edit_student(id):
    conn = get_db()
    cursor = conn.cursor()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        marks = request.form.get("marks", 0, type=int)
        attendance = request.form.get("attendance", 75, type=int)
        engagement = request.form.get("engagement", 60, type=int)
        quiz_scores = request.form.get("quiz_scores", 50, type=int)
        department = request.form.get("department", "General").strip()

        cursor.execute(
            "UPDATE students SET name=?, marks=?, attendance=?, engagement=?, quiz_scores=?, department=? WHERE id=?",
            (name, marks, attendance, engagement, quiz_scores, department, id)
        )
        conn.commit()
        conn.close()
        flash(f"Student '{name}' updated successfully!", "success")
        return redirect(url_for("students"))

    cursor.execute("SELECT * FROM students WHERE id=?", (id,))
    student = cursor.fetchone()
    conn.close()
    return render_template("edit_student.html", student=student)


# ---------------- DELETE STUDENT ----------------
@app.route("/delete_student/<int:id>")
def delete_student(id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM students WHERE id=?", (id,))
    conn.commit()
    conn.close()
    flash("Student deleted successfully.", "success")
    return redirect(url_for("students"))


# ---------------- RUN APP ----------------
if __name__ == "__main__":
    app.run(debug=True)