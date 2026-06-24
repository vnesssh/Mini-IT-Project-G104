# =============================================================================
# MMU RATEMYPROFESSOR - AUTHENTICATION SYSTEM
# =============================================================================

# Flask imports
from flask import request, redirect

# =============================================================================
# LOGIN DETAILS
# =============================================================================

# Student Login Details
student_name = "Mohamed"
student_id = "12345678"
student_email = "12345678@student.mmu.edu.my"

# MMU Official Login Details
official_username = "official"
official_password = "admin123"


# =============================================================================
# AUTHENTICATION FUNCTIONS
# =============================================================================

# -----------------------------------------------------------------------------
# STUDENT LOGIN
# -----------------------------------------------------------------------------
def student_login():
    """
    Checks student login details.
    """

    entered_name = request.form['name']
    entered_id = request.form['student_id']
    entered_email = request.form['email']

    if (
        entered_name == student_name
        and entered_id == student_id
        and entered_email == student_email
    ):
        return redirect("/review")

    return "Invalid Student Information ❌"


# -----------------------------------------------------------------------------
# OFFICIAL LOGIN
# -----------------------------------------------------------------------------
def official_login():
    """
    Checks MMU official credentials.
    """

    username = request.form['username']
    password = request.form['password']

    if (
        username == official_username
        and password == official_password
    ):
        return redirect("/reviews")

    return "Access Denied ❌"