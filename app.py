"""
app.py
------
Green Budgeting and Performance Monitoring System (GBPMS)
Group 24

This is the main Flask web application.  It handles:
  - User login / logout
  - Five role-based dashboards
  - Module 1: Green Budget Tagging
  - Module 2: Environmental Performance Monitoring
  - Module 3: Reporting & Accountability
  - Module 4: Dashboard & Visualisation (built into each dashboard template)

HOW TO RUN:
  1. Open your terminal / command prompt
  2. Navigate to the GBPMS folder:
         cd path/to/GBPMS
  3. Install dependencies (once only):
         pip install flask
  4. Initialise the database (once only):
         python database.py
  5. Start the server:
         python app.py
  6. Open your browser and go to:
         http://127.0.0.1:5000

DEMO LOGIN CREDENTIALS:
  Username          Password   Role
  ----------------  ---------  ------------------
  budget_officer    pass123    Budget Officer
  prog_manager      pass123    Programme Manager
  plan_analyst      pass123    Planning Analyst
  senior_mgmt       pass123    Senior Management
  auditor           pass123    Auditor
"""

from flask import (Flask, render_template, request,
                   redirect, url_for, session, flash, jsonify)
import sqlite3
import os
from datetime import datetime
from database import init_db, DATABASE, get_connection

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "gbpms_ama_group24_secret")


# ---------------------------------------------------------------------------
# Helper: get current date-time string
# ---------------------------------------------------------------------------
def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ---------------------------------------------------------------------------
# Helper: restrict pages to logged-in users
# ---------------------------------------------------------------------------
def login_required(f):
    """Decorator: redirect to login if no active session."""
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to access the system.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# Helper: restrict pages by role
# ---------------------------------------------------------------------------
def roles_required(*allowed_roles):
    """Decorator: show 403 page if user's role is not in allowed_roles."""
    def decorator(f):
        from functools import wraps
        @wraps(f)
        def decorated(*args, **kwargs):
            if session.get("role") not in allowed_roles:
                return render_template("403.html"), 403
            return f(*args, **kwargs)
        return decorated
    return decorator


# ===========================================================================
# AUTHENTICATION ROUTES
# ===========================================================================

@app.route("/")
def index():
    """Root URL: redirect to dashboard if logged in, else to login."""
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    """Show login form (GET) or authenticate user (POST)."""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        conn = get_connection()
        user = conn.execute(
            "SELECT * FROM User_Access WHERE Username=? AND Password=? AND Active_Status=1",
            (username, password)
        ).fetchone()

        if user:
            # Save user info into the session (browser cookie)
            session["user_id"]   = user["User_ID"]
            session["username"]  = user["Username"]
            session["full_name"] = user["Full_Name"]
            session["role"]      = user["Role_Type"]
            session["institution"] = user["Institution"]

            # Update last login timestamp
            conn.execute(
                "UPDATE User_Access SET Last_Login=? WHERE User_ID=?",
                (now(), user["User_ID"])
            )
            conn.commit()
            conn.close()

            flash(f"Welcome back, {user['Full_Name']}!", "success")
            return redirect(url_for("dashboard"))
        else:
            conn.close()
            flash("Invalid username or password. Please try again.", "danger")

    return render_template("login.html")


@app.route("/logout")
def logout():
    """Clear session and redirect to login."""
    session.clear()
    flash("You have been logged out successfully.", "info")
    return redirect(url_for("login"))


# ===========================================================================
# DASHBOARD ROUTER
# ===========================================================================

@app.route("/dashboard")
@login_required
def dashboard():
    """Redirect each user to their role-specific dashboard."""
    role = session.get("role")
    role_map = {
        "Budget Officer":    "dashboard_budget_officer",
        "Programme Manager": "dashboard_programme_manager",
        "Planning Analyst":  "dashboard_planning_analyst",
        "Senior Management": "dashboard_senior_management",
        "Auditor":           "dashboard_auditor",
    }
    target = role_map.get(role)
    if target:
        return redirect(url_for(target))
    flash("Unknown role — contact your administrator.", "danger")
    return redirect(url_for("login"))


# ===========================================================================
# MODULE 4: DASHBOARDS  (one per role)
# ===========================================================================

@app.route("/dashboard/budget-officer")
@login_required
@roles_required("Budget Officer")
def dashboard_budget_officer():
    """
    Budget Officer Dashboard — Section 3.8.3 of the project.
    Shows: programmes pending tagging, tagging completion, green expenditure by sector.
    """
    conn = get_connection()

    # Programmes for the current year that need tagging
    current_year = datetime.now().year
    pending = conn.execute("""
        SELECT * FROM Budget_Programme
        WHERE Financial_Year=? AND (Green_Tag_Tier IS NULL OR Green_Tag_Tier='None')
        ORDER BY Sector
    """, (current_year,)).fetchall()

    # Tagging summary by tier
    tagged_summary = conn.execute("""
        SELECT Green_Tag_Tier, COUNT(*) as Count, SUM(Total_Allocation) as Total
        FROM Budget_Programme
        WHERE Financial_Year=?
        GROUP BY Green_Tag_Tier
    """, (current_year,)).fetchall()

    # Green expenditure totals by sector (exclude 'None' tier)
    sector_totals = conn.execute("""
        SELECT Sector, SUM(Total_Allocation) as GreenTotal
        FROM Budget_Programme
        WHERE Financial_Year=? AND Green_Tag_Tier IN ('Principal','Significant')
        GROUP BY Sector
        ORDER BY GreenTotal DESC
    """, (current_year,)).fetchall()

    # All tagged programmes (for the table view)
    all_programmes = conn.execute("""
        SELECT * FROM Budget_Programme
        WHERE Financial_Year=?
        ORDER BY Green_Tag_Tier, Sector
    """, (current_year,)).fetchall()

    conn.close()
    return render_template("dashboard_budget_officer.html",
                           pending=pending,
                           tagged_summary=tagged_summary,
                           sector_totals=sector_totals,
                           all_programmes=all_programmes,
                           current_year=current_year)


@app.route("/dashboard/programme-manager")
@login_required
@roles_required("Programme Manager")
def dashboard_programme_manager():
    """
    Programme Manager Dashboard — Section 3.8.3 of the project.
    Shows: performance indicator status, flags off-track indicators.
    """
    conn = get_connection()

    # All indicators with their programme names
    indicators = conn.execute("""
        SELECT pi.*, bp.Programme_Name, bp.Sector, bp.Financial_Year
        FROM Performance_Indicator pi
        JOIN Budget_Programme bp ON pi.Programme_ID = bp.Programme_ID
        ORDER BY bp.Financial_Year DESC, pi.Achievement_Status
    """).fetchall()

    # Summary counts
    status_counts = conn.execute("""
        SELECT Achievement_Status, COUNT(*) as Count
        FROM Performance_Indicator
        GROUP BY Achievement_Status
    """).fetchall()

    # All tagged programmes (for linking to add indicators)
    programmes = conn.execute("""
        SELECT * FROM Budget_Programme
        WHERE Green_Tag_Tier IN ('Principal','Significant')
        ORDER BY Financial_Year DESC, Programme_Name
    """).fetchall()

    conn.close()
    return render_template("dashboard_programme_manager.html",
                           indicators=indicators,
                           status_counts=status_counts,
                           programmes=programmes)


@app.route("/dashboard/planning-analyst")
@login_required
@roles_required("Planning Analyst")
def dashboard_planning_analyst():
    """
    Planning Analyst Dashboard — Section 3.8.3 of the project.
    Cross-sector aggregate views, SDG alignment, multi-year trends.
    """
    conn = get_connection()

    # Multi-year green expenditure totals
    yearly_totals = conn.execute("""
        SELECT Financial_Year,
               SUM(CASE WHEN Green_Tag_Tier IN ('Principal','Significant')
                        THEN Total_Allocation ELSE 0 END) as GreenTotal,
               SUM(Total_Allocation) as BudgetTotal
        FROM Budget_Programme
        GROUP BY Financial_Year
        ORDER BY Financial_Year
    """).fetchall()

    # Performance achievement rates by year
    achievement_rates = conn.execute("""
        SELECT bp.Financial_Year,
               COUNT(pi.Indicator_ID) as Total,
               SUM(CASE WHEN pi.Achievement_Status='Achieved' THEN 1 ELSE 0 END) as Achieved,
               SUM(CASE WHEN pi.Achievement_Status='On Track' THEN 1 ELSE 0 END) as OnTrack,
               SUM(CASE WHEN pi.Achievement_Status='Off Track' THEN 1 ELSE 0 END) as OffTrack
        FROM Performance_Indicator pi
        JOIN Budget_Programme bp ON pi.Programme_ID = bp.Programme_ID
        GROUP BY bp.Financial_Year
        ORDER BY bp.Financial_Year
    """).fetchall()

    # Sector breakdown (all years)
    sector_breakdown = conn.execute("""
        SELECT Sector,
               SUM(CASE WHEN Green_Tag_Tier='Principal' THEN Total_Allocation ELSE 0 END) as Principal,
               SUM(CASE WHEN Green_Tag_Tier='Significant' THEN Total_Allocation ELSE 0 END) as Significant,
               COUNT(*) as Programmes
        FROM Budget_Programme
        WHERE Green_Tag_Tier IN ('Principal','Significant')
        GROUP BY Sector
        ORDER BY Principal + Significant DESC
    """).fetchall()

    conn.close()
    return render_template("dashboard_planning_analyst.html",
                           yearly_totals=yearly_totals,
                           achievement_rates=achievement_rates,
                           sector_breakdown=sector_breakdown)


@app.route("/dashboard/senior-management")
@login_required
@roles_required("Senior Management")
def dashboard_senior_management():
    """
    Senior Management Dashboard — Section 3.8.3 of the project.
    Executive summaries, trend charts, traffic-light performance scorecard.
    """
    conn = get_connection()

    # High-level KPIs for current year
    current_year = datetime.now().year
    kpi = conn.execute("""
        SELECT
          COUNT(CASE WHEN Green_Tag_Tier IN ('Principal','Significant') THEN 1 END) as TaggedCount,
          SUM(CASE WHEN Green_Tag_Tier IN ('Principal','Significant') THEN Total_Allocation ELSE 0 END) as GreenBudget,
          SUM(Total_Allocation) as TotalBudget,
          COUNT(*) as TotalProgrammes
        FROM Budget_Programme
        WHERE Financial_Year=?
    """, (current_year,)).fetchone()

    # Performance scorecard (all indicators, colour-coded)
    scorecard = conn.execute("""
        SELECT bp.Programme_Name, bp.Sector, pi.Description,
               pi.Target_Value, pi.Actual_Value, pi.Unit,
               pi.Achievement_Status, pi.Reporting_Period
        FROM Performance_Indicator pi
        JOIN Budget_Programme bp ON pi.Programme_ID = bp.Programme_ID
        ORDER BY pi.Achievement_Status, bp.Sector
    """).fetchall()

    # Multi-year green % trend (for the chart)
    trend = conn.execute("""
        SELECT Financial_Year,
               ROUND(
                 100.0 * SUM(CASE WHEN Green_Tag_Tier IN ('Principal','Significant')
                                  THEN Total_Allocation ELSE 0 END)
                 / NULLIF(SUM(Total_Allocation), 0)
               , 1) as GreenPct
        FROM Budget_Programme
        GROUP BY Financial_Year
        ORDER BY Financial_Year
    """).fetchall()

    conn.close()
    return render_template("dashboard_senior_management.html",
                           kpi=kpi,
                           scorecard=scorecard,
                           trend=trend,
                           current_year=current_year)


@app.route("/dashboard/auditor")
@login_required
@roles_required("Auditor")
def dashboard_auditor():
    """
    Auditor / External Reporting Dashboard — Section 3.8.3.
    Read-only: expenditure reports, audit trail, GIFMIS sync log.
    """
    conn = get_connection()

    reports = conn.execute("""
        SELECT * FROM Environmental_Expenditure_Report
        ORDER BY Financial_Year DESC, Sector
    """).fetchall()

    gifmis_log = conn.execute("""
        SELECT * FROM GIFMIS_Integration_Log
        ORDER BY Sync_Date DESC
    """).fetchall()

    # Summary statistics
    summary = conn.execute("""
        SELECT Financial_Year,
               SUM(Total_Green_Expenditure) as TotalGreen,
               SUM(Number_of_Programmes) as Programmes,
               AVG(Percentage_of_Total_Budget) as AvgPct
        FROM Environmental_Expenditure_Report
        GROUP BY Financial_Year
        ORDER BY Financial_Year DESC
    """).fetchall()

    conn.close()
    return render_template("dashboard_auditor.html",
                           reports=reports,
                           gifmis_log=gifmis_log,
                           summary=summary)


# ===========================================================================
# MODULE 1: GREEN BUDGET TAGGING
# ===========================================================================

@app.route("/budget-tagging", methods=["GET"])
@login_required
@roles_required("Budget Officer", "Senior Management")
def budget_tagging():
    """Show all programmes and the tagging form."""
    conn = get_connection()
    programmes = conn.execute("""
        SELECT * FROM Budget_Programme
        ORDER BY Financial_Year DESC, Sector
    """).fetchall()
    conn.close()
    return render_template("budget_tagging.html", programmes=programmes)


@app.route("/budget-tagging/add", methods=["GET", "POST"])
@login_required
@roles_required("Budget Officer")
def add_programme():
    """Add a new budget programme."""
    if request.method == "POST":
        name     = request.form["programme_name"]
        sector   = request.form["sector"]
        min_code = request.form["ministry_code"]
        year     = int(request.form["financial_year"])
        alloc    = float(request.form["total_allocation"])
        tier     = request.form["green_tag_tier"]
        category = request.form.get("environmental_category") or None

        conn = get_connection()
        conn.execute("""
            INSERT INTO Budget_Programme
              (Programme_Name, Sector, Ministry_Code, Financial_Year,
               Total_Allocation, Green_Tag_Tier, Environmental_Category,
               Tagged_By, Tagged_Date)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, (name, sector, min_code, year, alloc, tier, category,
              session["user_id"], now()))
        conn.commit()
        conn.close()
        flash(f"Programme '{name}' added and tagged successfully!", "success")
        return redirect(url_for("budget_tagging"))

    return render_template("add_programme.html")


@app.route("/budget-tagging/edit/<int:prog_id>", methods=["GET", "POST"])
@login_required
@roles_required("Budget Officer")
def edit_programme(prog_id):
    """Edit/re-tag an existing programme."""
    conn = get_connection()
    if request.method == "POST":
        tier     = request.form["green_tag_tier"]
        category = request.form.get("environmental_category") or None
        conn.execute("""
            UPDATE Budget_Programme
            SET Green_Tag_Tier=?, Environmental_Category=?, Tagged_By=?, Tagged_Date=?
            WHERE Programme_ID=?
        """, (tier, category, session["user_id"], now(), prog_id))
        conn.commit()
        conn.close()
        flash("Programme tag updated.", "success")
        return redirect(url_for("budget_tagging"))

    programme = conn.execute(
        "SELECT * FROM Budget_Programme WHERE Programme_ID=?", (prog_id,)
    ).fetchone()
    conn.close()
    if not programme:
        flash("Programme not found.", "danger")
        return redirect(url_for("budget_tagging"))
    return render_template("edit_programme.html", programme=programme)


# ===========================================================================
# MODULE 2: PERFORMANCE MONITORING
# ===========================================================================

@app.route("/performance", methods=["GET"])
@login_required
@roles_required("Programme Manager", "Planning Analyst", "Senior Management")
def performance():
    """List all performance indicators."""
    conn = get_connection()
    indicators = conn.execute("""
        SELECT pi.*, bp.Programme_Name, bp.Sector, bp.Financial_Year
        FROM Performance_Indicator pi
        JOIN Budget_Programme bp ON pi.Programme_ID = bp.Programme_ID
        ORDER BY bp.Financial_Year DESC, pi.Achievement_Status
    """).fetchall()
    programmes = conn.execute("""
        SELECT * FROM Budget_Programme
        WHERE Green_Tag_Tier IN ('Principal','Significant')
        ORDER BY Financial_Year DESC
    """).fetchall()
    conn.close()
    return render_template("performance.html",
                           indicators=indicators,
                           programmes=programmes)


@app.route("/performance/add", methods=["GET", "POST"])
@login_required
@roles_required("Programme Manager")
def add_indicator():
    """Add a new performance indicator to a programme."""
    conn = get_connection()
    if request.method == "POST":
        prog_id   = int(request.form["programme_id"])
        ind_type  = request.form["indicator_type"]
        desc      = request.form["description"]
        baseline  = float(request.form.get("baseline_value") or 0)
        target    = float(request.form["target_value"])
        actual    = request.form.get("actual_value")
        actual    = float(actual) if actual else None
        unit      = request.form.get("unit")
        period    = request.form["reporting_period"]

        # Auto-calculate achievement status
        status = _calc_status(target, actual)

        conn.execute("""
            INSERT INTO Performance_Indicator
              (Programme_ID, Indicator_Type, Description, Baseline_Value,
               Target_Value, Actual_Value, Unit, Reporting_Period,
               Achievement_Status, Updated_By, Updated_Date)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (prog_id, ind_type, desc, baseline, target, actual,
              unit, period, status, session["user_id"], now()))
        conn.commit()
        conn.close()
        flash("Indicator added successfully!", "success")
        return redirect(url_for("performance"))

    programmes = conn.execute("""
        SELECT * FROM Budget_Programme
        WHERE Green_Tag_Tier IN ('Principal','Significant')
        ORDER BY Financial_Year DESC
    """).fetchall()
    conn.close()
    return render_template("add_indicator.html", programmes=programmes)


@app.route("/performance/update/<int:ind_id>", methods=["GET", "POST"])
@login_required
@roles_required("Programme Manager")
def update_indicator(ind_id):
    """Update the Actual_Value for an existing indicator."""
    conn = get_connection()
    if request.method == "POST":
        actual = float(request.form["actual_value"])
        ind = conn.execute(
            "SELECT Target_Value FROM Performance_Indicator WHERE Indicator_ID=?",
            (ind_id,)
        ).fetchone()
        status = _calc_status(ind["Target_Value"], actual)
        conn.execute("""
            UPDATE Performance_Indicator
            SET Actual_Value=?, Achievement_Status=?, Updated_By=?, Updated_Date=?
            WHERE Indicator_ID=?
        """, (actual, status, session["user_id"], now(), ind_id))
        conn.commit()
        conn.close()
        flash("Indicator updated.", "success")
        return redirect(url_for("performance"))

    indicator = conn.execute("""
        SELECT pi.*, bp.Programme_Name
        FROM Performance_Indicator pi
        JOIN Budget_Programme bp ON pi.Programme_ID = bp.Programme_ID
        WHERE pi.Indicator_ID=?
    """, (ind_id,)).fetchone()
    conn.close()
    return render_template("update_indicator.html", indicator=indicator)


def _calc_status(target, actual):
    """Return an achievement status string based on target vs actual."""
    if actual is None:
        return None
    pct = (actual / target * 100) if target else 0
    if pct >= 100:
        return "Achieved"
    elif pct >= 75:
        return "On Track"
    else:
        return "Off Track"


# ===========================================================================
# MODULE 3: REPORTING & ACCOUNTABILITY
# ===========================================================================

@app.route("/reports")
@login_required
def reports():
    """Show all generated environmental expenditure reports."""
    conn = get_connection()
    all_reports = conn.execute("""
        SELECT * FROM Environmental_Expenditure_Report
        ORDER BY Financial_Year DESC, Sector
    """).fetchall()

    # Summary by year for the overview table
    yearly = conn.execute("""
        SELECT Financial_Year,
               SUM(Total_Green_Expenditure) as TotalGreen,
               SUM(Number_of_Programmes) as Programmes,
               AVG(Percentage_of_Total_Budget) as AvgPct
        FROM Environmental_Expenditure_Report
        GROUP BY Financial_Year
        ORDER BY Financial_Year DESC
    """).fetchall()

    conn.close()
    return render_template("reports.html",
                           all_reports=all_reports,
                           yearly=yearly)


@app.route("/reports/generate", methods=["POST"])
@login_required
@roles_required("Budget Officer", "Senior Management")
def generate_report():
    """Generate a new aggregated report for a given year."""
    year = int(request.form["financial_year"])
    conn = get_connection()

    # Aggregate from Budget_Programme
    rows = conn.execute("""
        SELECT Sector,
               SUM(Total_Allocation) as GreenTotal,
               COUNT(*) as NumProg,
               (SELECT SUM(Total_Allocation) FROM Budget_Programme
                WHERE Financial_Year=?) as YearTotal
        FROM Budget_Programme
        WHERE Financial_Year=? AND Green_Tag_Tier IN ('Principal','Significant')
        GROUP BY Sector
    """, (year, year)).fetchall()

    if not rows:
        flash(f"No tagged programmes found for {year}.", "warning")
        conn.close()
        return redirect(url_for("reports"))

    # Delete old auto-generated entries for this year first
    conn.execute(
        "DELETE FROM Environmental_Expenditure_Report WHERE Financial_Year=?",
        (year,)
    )

    for row in rows:
        pct = round(row["GreenTotal"] / row["YearTotal"] * 100, 1) if row["YearTotal"] else 0
        compliance = "Compliant" if pct >= 5 else ("Partial" if pct >= 2 else "Non-Compliant")
        conn.execute("""
            INSERT INTO Environmental_Expenditure_Report
              (Financial_Year, Sector, Total_Green_Expenditure, Percentage_of_Total_Budget,
               Number_of_Programmes, Compliance_Status, Generated_By, Generated_Date)
            VALUES (?,?,?,?,?,?,?,?)
        """, (year, row["Sector"], row["GreenTotal"], pct,
              row["NumProg"], compliance, session["user_id"], now()))

    conn.commit()
    conn.close()
    flash(f"Report for {year} generated successfully!", "success")
    return redirect(url_for("reports"))


# ===========================================================================
# API: JSON data endpoints for Chart.js in the templates
# ===========================================================================

@app.route("/api/sector-data/<int:year>")
@login_required
def api_sector_data(year):
    """Return green expenditure by sector for a given year (for Chart.js)."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT Sector, SUM(Total_Allocation) as Total
        FROM Budget_Programme
        WHERE Financial_Year=? AND Green_Tag_Tier IN ('Principal','Significant')
        GROUP BY Sector
    """, (year,)).fetchall()
    conn.close()
    return jsonify({
        "labels": [r["Sector"] for r in rows],
        "values": [r["Total"] for r in rows],
    })


@app.route("/api/yearly-trend")
@login_required
def api_yearly_trend():
    """Return yearly green vs total budget for trend chart."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT Financial_Year,
               SUM(CASE WHEN Green_Tag_Tier IN ('Principal','Significant')
                        THEN Total_Allocation ELSE 0 END) as GreenTotal,
               SUM(Total_Allocation) as BudgetTotal
        FROM Budget_Programme
        GROUP BY Financial_Year
        ORDER BY Financial_Year
    """).fetchall()
    conn.close()
    return jsonify({
        "years":  [r["Financial_Year"] for r in rows],
        "green":  [r["GreenTotal"] for r in rows],
        "total":  [r["BudgetTotal"] for r in rows],
    })


# ===========================================================================
# ERROR PAGES
# ===========================================================================

@app.errorhandler(403)
def forbidden(e):
    return render_template("403.html"), 403


@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


# ===========================================================================
# START THE SERVER
# ===========================================================================

if __name__ == "__main__":
    # Initialise DB on first run (safe to call every time)
    if not os.path.exists(DATABASE):
        print("First run — creating database...")
        init_db()
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
