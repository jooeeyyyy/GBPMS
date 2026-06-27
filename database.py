"""
database.py
-----------
Green Budgeting and Performance Monitoring System (GBPMS)
Group 24

This file creates all 5 database tables from Section 3.8.2 of the project
and loads them with realistic sample data so you can explore the system
straight away.

HOW IT WORKS:
  SQLite is a database that lives in a single file (gbpms.db) on your
  computer — no server needed.  Python has sqlite3 built in, so nothing
  extra to install for this file.

Run this file once before starting the Flask app:
    python database.py
"""

import sqlite3
import os

DATABASE = "gbpms.db"


def get_connection():
    """Open (or create) the SQLite database and return a connection."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row   # lets us read columns by name
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create all tables and insert sample data."""
    conn = get_connection()
    cursor = conn.cursor()

    # ------------------------------------------------------------------
    # TABLE 1: User_Access
    # Stores login credentials and role for every system user.
    # Role types match the 5 dashboards in the project design.
    # ------------------------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS User_Access (
            User_ID       INTEGER PRIMARY KEY AUTOINCREMENT,
            Full_Name     TEXT    NOT NULL,
            Username      TEXT    NOT NULL UNIQUE,
            Password      TEXT    NOT NULL,
            Institution   TEXT    NOT NULL,
            Role_Type     TEXT    NOT NULL,   -- see roles list below
            Access_Level  TEXT    NOT NULL,   -- 'read_write' or 'read_only'
            Last_Login    TEXT,
            Active_Status INTEGER DEFAULT 1   -- 1 = active, 0 = disabled
        )
    """)
    # Role_Type values:
    #   'Budget Officer'    -> Green Budget Tagging Module
    #   'Programme Manager' -> Performance Monitoring Module
    #   'Planning Analyst'  -> Cross-sector analysis
    #   'Senior Management' -> Executive summaries
    #   'Auditor'           -> Read-only audit dashboard

    # ------------------------------------------------------------------
    # TABLE 2: Budget_Programme
    # Every budget line that has been tagged as environmentally relevant.
    # ------------------------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Budget_Programme (
            Programme_ID           INTEGER PRIMARY KEY AUTOINCREMENT,
            Programme_Name         TEXT    NOT NULL,
            Sector                 TEXT    NOT NULL,
            Ministry_Code          TEXT    NOT NULL,
            Financial_Year         INTEGER NOT NULL,
            Total_Allocation       REAL    NOT NULL,  -- Ghana Cedis (GHS)
            Green_Tag_Tier         TEXT,              -- see tiers below
            Environmental_Category TEXT,
            Tagged_By              INTEGER,           -- User_ID of tagger
            Tagged_Date            TEXT,
            FOREIGN KEY (Tagged_By) REFERENCES User_Access(User_ID)
        )
    """)
    # Green_Tag_Tier values (OECD 3-tier taxonomy from project Section 3.7.1):
    #   'Principal'    -> primary purpose is environmental
    #   'Significant'  -> contributes to environmental goals as secondary purpose
    #   'None'         -> no environmental relevance (not shown in green reports)

    # ------------------------------------------------------------------
    # TABLE 3: Performance_Indicator
    # Tracks planned vs. actual values for each tagged programme.
    # ------------------------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Performance_Indicator (
            Indicator_ID       INTEGER PRIMARY KEY AUTOINCREMENT,
            Programme_ID       INTEGER NOT NULL,
            Indicator_Type     TEXT    NOT NULL,  -- Input/Output/Outcome/Impact
            Description        TEXT    NOT NULL,
            Baseline_Value     REAL,
            Target_Value       REAL    NOT NULL,
            Actual_Value       REAL,
            Unit               TEXT,             -- e.g. 'tonnes', 'hectares', '%'
            Reporting_Period   TEXT    NOT NULL,  -- e.g. 'Q1 2024', 'Annual 2023'
            Achievement_Status TEXT,             -- 'On Track','Off Track','Achieved'
            Updated_By         INTEGER,
            Updated_Date       TEXT,
            FOREIGN KEY (Programme_ID) REFERENCES Budget_Programme(Programme_ID),
            FOREIGN KEY (Updated_By)   REFERENCES User_Access(User_ID)
        )
    """)

    # ------------------------------------------------------------------
    # TABLE 4: Environmental_Expenditure_Report
    # Aggregated annual green expenditure data for official reporting.
    # ------------------------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Environmental_Expenditure_Report (
            Report_ID                INTEGER PRIMARY KEY AUTOINCREMENT,
            Financial_Year           INTEGER NOT NULL,
            Sector                   TEXT    NOT NULL,
            Total_Green_Expenditure  REAL    NOT NULL,
            Percentage_of_Total_Budget REAL,
            Number_of_Programmes     INTEGER,
            Compliance_Status        TEXT,   -- 'Compliant','Partial','Non-Compliant'
            Generated_By             INTEGER,
            Generated_Date           TEXT,
            FOREIGN KEY (Generated_By) REFERENCES User_Access(User_ID)
        )
    """)

    # ------------------------------------------------------------------
    # TABLE 5: GIFMIS_Integration_Log
    # Audit trail of every data sync with Ghana's GIFMIS platform.
    # ------------------------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS GIFMIS_Integration_Log (
            Log_ID           INTEGER PRIMARY KEY AUTOINCREMENT,
            Sync_Date        TEXT    NOT NULL,
            Records_Imported INTEGER DEFAULT 0,
            Records_Exported INTEGER DEFAULT 0,
            Sync_Status      TEXT    NOT NULL,  -- 'Success','Failed','Partial'
            Error_Flag       INTEGER DEFAULT 0,  -- 0 = no error, 1 = error
            Error_Message    TEXT
        )
    """)

    conn.commit()

    # ------------------------------------------------------------------
    # SAMPLE DATA — only insert if the tables are empty
    # ------------------------------------------------------------------
    if cursor.execute("SELECT COUNT(*) FROM User_Access").fetchone()[0] == 0:
        _insert_sample_users(cursor)
        _insert_sample_programmes(cursor)
        _insert_sample_indicators(cursor)
        _insert_sample_reports(cursor)
        _insert_sample_logs(cursor)
        conn.commit()
        print("[database.py] Sample data inserted successfully.")
    else:
        print("[database.py] Database already contains data — skipping sample insert.")

    conn.close()
    print(f"[database.py] Database ready: {os.path.abspath(DATABASE)}")


def _insert_sample_users(cursor):
    """Five demo users — one per dashboard role."""
    users = [
        ("Abena Mensah",   "budget_officer",  "pass123", "Green Budget Unit",               "Budget Officer",    "read_write"),
        ("Kofi Asante",    "prog_manager",    "pass123", "Health Division",                 "Programme Manager", "read_write"),
        ("Ama Owusu",      "plan_analyst",    "pass123", "Planning & Analysis Division",     "Planning Analyst",  "read_write"),
        ("Dr. Yaw Boateng","senior_mgmt",     "pass123", "Executive Office",                "Senior Management", "read_write"),
        ("Efua Darko",     "auditor",         "pass123", "Ghana Audit Service",        "Auditor",           "read_only"),
    ]
    cursor.executemany("""
        INSERT INTO User_Access (Full_Name, Username, Password, Institution, Role_Type, Access_Level)
        VALUES (?,?,?,?,?,?)
    """, users)


def _insert_sample_programmes(cursor):
    """Realistic Ghana national budget programmes covering 2022-2026."""
    programmes = [
        # (Name, Sector, Ministry_Code, Year, Allocation_GHS, Tier, Category, Tagged_By, Date)
        ("Urban Waste Management and Recycling Programme",
         "Health", "MOF-EH-001", 2024, 4_500_000,
         "Principal", "Waste & Circular Economy", 1, "2024-01-15"),

        ("Street Tree Planting and Urban Greening Initiative",
         "Environment", "MOF-ENV-002", 2024, 1_200_000,
         "Principal", "Biodiversity & Land Use", 1, "2024-01-20"),

        ("Flood Drainage and Climate Resilience Works",
         "Infrastructure", "MOF-INF-003", 2024, 8_750_000,
         "Significant", "Climate Adaptation", 1, "2024-02-01"),

        ("Accra Public Transport Electrification Study",
         "Transport", "MOF-TRN-004", 2024, 650_000,
         "Significant", "Clean Energy & Transport", 1, "2024-02-10"),

        ("Market Sanitation and Water Supply Upgrade",
         "Water & Sanitation", "MOF-WS-005", 2024, 3_100_000,
         "Significant", "Water & Sanitation", 1, "2024-03-05"),

        ("Construction of New Revenue Collection Offices",
         "Administration", "MOF-ADM-006", 2024, 2_200_000,
         "None", None, 1, "2024-03-10"),

        ("Liquid Waste (Faecal Sludge) Management",
         "Health", "MOF-EH-007", 2023, 2_800_000,
         "Principal", "Waste & Circular Economy", 1, "2023-02-01"),

        ("Solar Street Lighting — Phase II",
         "Energy", "MOF-EN-008", 2023, 1_900_000,
         "Principal", "Clean Energy & Transport", 1, "2023-02-15"),

        ("Community Air Quality Monitoring Stations",
         "Environment", "MOF-ENV-009", 2023, 450_000,
         "Principal", "Air Quality", 1, "2023-03-01"),

        ("Urban Waste Management and Recycling Programme",
         "Health", "MOF-EH-001", 2022, 3_800_000,
         "Principal", "Waste & Circular Economy", 1, "2022-01-20"),
    ]
    cursor.executemany("""
        INSERT INTO Budget_Programme
          (Programme_Name, Sector, Ministry_Code, Financial_Year, Total_Allocation,
           Green_Tag_Tier, Environmental_Category, Tagged_By, Tagged_Date)
        VALUES (?,?,?,?,?,?,?,?,?)
    """, programmes)


def _insert_sample_indicators(cursor):
    """Performance indicators linked to the programmes above."""
    indicators = [
        # Programme 1 — Waste Management (3 indicators)
        (1, "Output",  "Tonnes of solid waste collected and processed monthly",
         8000, 12000, 10500, "tonnes/month", "Annual 2024", "On Track", 2, "2024-12-01"),
        (1, "Outcome", "Percentage of waste diverted from landfill through recycling",
         12.0, 30.0, 22.5, "%", "Annual 2024", "On Track", 2, "2024-12-01"),
        (1, "Impact",  "Reduction in open dumping sites within Greater Accra jurisdiction",
         47, 20, 31, "sites", "Annual 2024", "On Track", 2, "2024-12-01"),

        # Programme 2 — Tree Planting (2 indicators)
        (2, "Output",  "Number of trees planted in public spaces",
         500, 5000, 3200, "trees", "Annual 2024", "Off Track", 2, "2024-12-01"),
        (2, "Outcome", "Urban green cover area (hectares)",
         85, 120, 97, "hectares", "Annual 2024", "Off Track", 2, "2024-12-01"),

        # Programme 3 — Flood Drainage (2 indicators)
        (3, "Output",  "Kilometres of drainage channels constructed or rehabilitated",
         0, 18, 14, "km", "Annual 2024", "On Track", 2, "2024-12-01"),
        (3, "Outcome", "Number of flood-prone communities protected",
         0, 12, 9, "communities", "Annual 2024", "On Track", 2, "2024-12-01"),

        # Programme 7 — 2023 Waste (1 indicator)
        (7, "Output",  "Tonnes of faecal sludge safely treated",
         1200, 2500, 2480, "tonnes", "Annual 2023", "Achieved", 2, "2023-12-15"),

        # Programme 8 — Solar Lighting (1 indicator)
        (8, "Output",  "Number of solar streetlights installed",
         0, 500, 500, "units", "Annual 2023", "Achieved", 2, "2023-12-15"),

        # Programme 9 — Air Quality (1 indicator)
        (9, "Outcome", "Number of functional air quality monitoring stations",
         0, 6, 4, "stations", "Annual 2023", "Off Track", 2, "2023-12-15"),
    ]
    cursor.executemany("""
        INSERT INTO Performance_Indicator
          (Programme_ID, Indicator_Type, Description, Baseline_Value, Target_Value,
           Actual_Value, Unit, Reporting_Period, Achievement_Status, Updated_By, Updated_Date)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
    """, indicators)


def _insert_sample_reports(cursor):
    """Pre-generated annual expenditure reports for 2022-2024."""
    reports = [
        (2024, "Health",  7_300_000, 8.2, 3, "Compliant",    4, "2024-12-31"),
        (2024, "Environment",           1_200_000, 1.4, 1, "Compliant",    4, "2024-12-31"),
        (2024, "Infrastructure",        8_750_000, 9.8, 1, "Partial",      4, "2024-12-31"),
        (2024, "Transport",               650_000, 0.7, 1, "Partial",      4, "2024-12-31"),
        (2024, "Water & Sanitation",    3_100_000, 3.5, 1, "Compliant",    4, "2024-12-31"),
        (2023, "Health",  2_800_000, 4.1, 1, "Compliant",    4, "2023-12-31"),
        (2023, "Energy",                1_900_000, 2.8, 1, "Compliant",    4, "2023-12-31"),
        (2023, "Environment",             450_000, 0.7, 1, "Non-Compliant",4, "2023-12-31"),
        (2022, "Health",  3_800_000, 6.2, 1, "Compliant",    4, "2022-12-31"),
    ]
    cursor.executemany("""
        INSERT INTO Environmental_Expenditure_Report
          (Financial_Year, Sector, Total_Green_Expenditure, Percentage_of_Total_Budget,
           Number_of_Programmes, Compliance_Status, Generated_By, Generated_Date)
        VALUES (?,?,?,?,?,?,?,?)
    """, reports)


def _insert_sample_logs(cursor):
    """GIFMIS sync log entries."""
    logs = [
        ("2024-12-01 08:00:00", 245, 18, "Success", 0, None),
        ("2024-09-01 08:00:00", 238, 15, "Success", 0, None),
        ("2024-06-01 08:15:00", 230, 12, "Partial", 1, "3 records failed schema validation"),
        ("2024-03-01 08:00:00", 221, 10, "Success", 0, None),
        ("2023-12-01 08:00:00", 198,  9, "Success", 0, None),
    ]
    cursor.executemany("""
        INSERT INTO GIFMIS_Integration_Log
          (Sync_Date, Records_Imported, Records_Exported, Sync_Status, Error_Flag, Error_Message)
        VALUES (?,?,?,?,?,?)
    """, logs)


# Run directly: python database.py
if __name__ == "__main__":
    init_db()
