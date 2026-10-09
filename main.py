import os
import json
import sqlite3
from datetime import datetime

import aiosqlite
from fastmcp import FastMCP

# Permanent database folder inside this project
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

DB_PATH = os.path.join(DATA_DIR, "expenses.db")
CATEGORIES_PATH = os.path.join(BASE_DIR, "categories.json")

mcp = FastMCP("ExpenseTracker")


def init_db():
    """Create the database and table automatically."""
    with sqlite3.connect(DB_PATH) as conn:
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
    print(f"Database path: {DB_PATH}")
    print("Database initialized successfully")


init_db()


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

        async with aiosqlite.connect(DB_PATH) as conn:
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
        return {
            "status": "error",
            "message": "Invalid date. Use YYYY-MM-DD."
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.tool()
async def list_expenses(start_date: str, end_date: str) -> list:
    """List expenses between two dates, inclusive."""
    try:
        datetime.strptime(start_date, "%Y-%m-%d")
        datetime.strptime(end_date, "%Y-%m-%d")

        async with aiosqlite.connect(DB_PATH) as conn:
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
        return [{"status": "error", "message": str(e)}]


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

        async with aiosqlite.connect(DB_PATH) as conn:
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
        return [{"status": "error", "message": str(e)}]


@mcp.resource("expense://categories")
def categories() -> str:
    """Return the available expense categories as JSON."""
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


if __name__ == "__main__":
    mcp.run(
        transport="http",
        host="127.0.0.1",
        port=8000
    )