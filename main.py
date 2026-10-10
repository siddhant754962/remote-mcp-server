
import os
import json
import sqlite3
import tempfile
from datetime import datetime

import aiosqlite
from fastmcp import FastMCP

# --------------------------------------------------
# DATABASE CONFIGURATION
# --------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Hosting platform par EXPENSE_DATA_DIR set kar sakte ho.
# Default temporary path writable ho sakta hai, lekin persistent nahi.
DATA_DIR = os.environ.get(
    "EXPENSE_DATA_DIR",
    os.path.join(tempfile.gettempdir(), "expense-tracker")
)

os.makedirs(DATA_DIR, exist_ok=True)

DB_PATH = os.path.join(DATA_DIR, "expenses.db")
CATEGORIES_PATH = os.path.join(BASE_DIR, "categories.json")

mcp = FastMCP("ExpenseTracker")


# --------------------------------------------------
# DATABASE INITIALIZATION
# --------------------------------------------------

def init_db():
    """Initialize database and report its location."""
    print("Database path:", DB_PATH)
    print("Database directory exists:", os.path.isdir(DATA_DIR))
    print("Database directory writable:", os.access(DATA_DIR, os.W_OK))

    # Actual filesystem write test
    test_path = os.path.join(DATA_DIR, ".write_test")
    try:
        with open(test_path, "w", encoding="utf-8") as f:
            f.write("ok")
        os.remove(test_path)
    except OSError as e:
        raise RuntimeError(
            f"Database directory is not writable: {DATA_DIR}. {e}"
        ) from e

    with sqlite3.connect(DB_PATH, timeout=10) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                amount REAL NOT NULL CHECK(amount >= 0),
                category TEXT NOT NULL,
                subcategory TEXT DEFAULT '',
                note TEXT DEFAULT ''
            )
        """)

    print("Database initialized successfully")


init_db()


# --------------------------------------------------
# ADD EXPENSE
# --------------------------------------------------

@mcp.tool()
async def add_expense(
    date: str,
    amount: float,
    category: str,
    subcategory: str = "",
    note: str = ""
) -> dict:
    """Add an expense. Date format must be YYYY-MM-DD."""
    try:
        datetime.strptime(date, "%Y-%m-%d")

        if amount < 0:
            return {"status": "error", "message": "Amount cannot be negative."}

        if not category.strip():
            return {"status": "error", "message": "Category is required."}

        async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
            cursor = await conn.execute(
                """
                INSERT INTO expenses
                (date, amount, category, subcategory, note)
                VALUES (?, ?, ?, ?, ?)
                """,
                (date, amount, category.strip(), subcategory, note)
            )
            await conn.commit()
            expense_id = cursor.lastrowid

        return {
            "status": "success",
            "id": expense_id,
            "message": "Expense added successfully"
        }

    except ValueError:
        return {"status": "error", "message": "Invalid date. Use YYYY-MM-DD."}
    except Exception as e:
        print("add_expense error:", repr(e))
        return {"status": "error", "message": str(e)}


# --------------------------------------------------
# LIST EXPENSES
# --------------------------------------------------

@mcp.tool()
async def list_expenses(start_date: str, end_date: str) -> list:
    """List expenses between two dates, inclusive."""
    try:
        datetime.strptime(start_date, "%Y-%m-%d")
        datetime.strptime(end_date, "%Y-%m-%d")

        async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                """
                SELECT id, date, amount, category, subcategory, note
                FROM expenses
                WHERE date BETWEEN ? AND ?
                ORDER BY date DESC, id DESC
                """,
                (start_date, end_date)
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    except Exception as e:
        print("list_expenses error:", repr(e))
        return [{"status": "error", "message": str(e)}]


# --------------------------------------------------
# SUMMARIZE EXPENSES
# --------------------------------------------------

@mcp.tool()
async def summarize(
    start_date: str,
    end_date: str,
    category: str = ""
) -> list:
    """Summarize total spending and number of expenses by category."""
    try:
        datetime.strptime(start_date, "%Y-%m-%d")
        datetime.strptime(end_date, "%Y-%m-%d")

        query = """
            SELECT category,
                   SUM(amount) AS total_amount,
                   COUNT(*) AS count
            FROM expenses
            WHERE date BETWEEN ? AND ?
        """
        params = [start_date, end_date]

        if category.strip():
            query += " AND category = ?"
            params.append(category.strip())

        query += " GROUP BY category ORDER BY total_amount DESC"

        async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
            cursor = await conn.execute(query, params)
            rows = await cursor.fetchall()

        return [
            {
                "category": row[0],
                "total_amount": row[1],
                "count": row[2]
            }
            for row in rows
        ]

    except Exception as e:
        print("summarize error:", repr(e))
        return [{"status": "error", "message": str(e)}]


# --------------------------------------------------
# CATEGORIES RESOURCE
# --------------------------------------------------

@mcp.resource("expense://categories")
def categories() -> str:
    """Return available expense categories as JSON."""
    default_categories = {
        "categories": [
            "Food & Dining",
            "Transportation",
            "Shopping",
            "Entertainment",
            "Bills & Utilities",
            "Healthcare",
            "Travel",
            "Education",
            "Business",
            "Other"
        ]
    }

    try:
        with open(CATEGORIES_PATH, "r", encoding="utf-8") as file:
            return file.read()
    except FileNotFoundError:
        return json.dumps(default_categories, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


# --------------------------------------------------
# START SERVER
# --------------------------------------------------

if __name__ == "__main__":
    mcp.run(
        transport="http",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8000"))
    )
