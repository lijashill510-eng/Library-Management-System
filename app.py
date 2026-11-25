import sqlite3
from datetime import datetime, timedelta
from flask import Flask, jsonify, request

app = Flask(__name__)
DB_FILE = "library.db"


def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initializes tables for books, members, and transactions with sample records."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            author TEXT NOT NULL,
            isbn TEXT UNIQUE NOT NULL,
            genre TEXT,
            total_copies INTEGER NOT NULL,
            available_copies INTEGER NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            member_code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            phone TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS loans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id INTEGER NOT NULL,
            member_id INTEGER NOT NULL,
            issue_date TEXT NOT NULL,
            due_date TEXT NOT NULL,
            return_date TEXT,
            status TEXT DEFAULT 'active',
            FOREIGN KEY(book_id) REFERENCES books(id),
            FOREIGN KEY(member_id) REFERENCES members(id)
        )
    """)
    conn.commit()
    conn.close()


@app.route("/api/books", methods=["GET", "POST"])
def manage_books():
    conn = get_db()
    cursor = conn.cursor()

    if request.method == "POST":
        data = request.json
        total = int(data.get("total_copies", 1))
        cursor.execute(
            """
            INSERT INTO books (title, author, isbn, genre, total_copies, available_copies)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (
                data["title"],
                data["author"],
                data["isbn"],
                data.get("genre", "Other"),
                total,
                total,
            ),
        )
        conn.commit()
        book_id = cursor.lastrowid
        conn.close()
        return (
            jsonify({"message": "Book added successfully", "id": book_id}),
            201,
        )

    cursor.execute("SELECT * FROM books")
    books = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(books)


@app.route("/api/issue", methods=["POST"])
def issue_book():
    data = request.json
    book_id = data.get("book_id")
    member_id = data.get("member_id")
    days = int(data.get("days", 14))

    conn = get_db()
    cursor = conn.cursor()

    # Check copy availability
    cursor.execute(
        "SELECT available_copies FROM books WHERE id = ?", (book_id,)
    )
    book = cursor.fetchone()
    if not book or book["available_copies"] <= 0:
        conn.close()
        return jsonify({"error": "Book not available"}), 400

    issue_date = datetime.now().strftime("%Y-%m-%d")
    due_date = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")

    cursor.execute(
        """
        INSERT INTO loans (book_id, member_id, issue_date, due_date, status)
        VALUES (?, ?, ?, ?, 'active')
    """,
        (book_id, member_id, issue_date, due_date),
    )

    cursor.execute(
        "UPDATE books SET available_copies = available_copies - 1 WHERE id = ?",
        (book_id,),
    )
    conn.commit()
    conn.close()

    return jsonify({"message": "Book issued successfully", "due_date": due_date})


@app.route("/api/return/<int:loan_id>", methods=["POST"])
def return_book(loan_id):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM loans WHERE id = ? AND return_date IS NULL", (loan_id,)
    )
    loan = cursor.fetchone()
    if not loan:
        conn.close()
        return jsonify({"error": "Active loan record not found"}), 404

    return_date = datetime.now().strftime("%Y-%m-%d")
    due_date = datetime.strptime(loan["due_date"], "%Y-%m-%d")
    today = datetime.now()

    # Fine calculation: $1.00 per overdue day
    overdue_days = max(0, (today - due_date).days)
    fine = overdue_days * 1.0

    cursor.execute(
        """
        UPDATE loans SET return_date = ?, status = 'returned' WHERE id = ?
    """,
        (return_date, loan_id),
    )

    cursor.execute(
        "UPDATE books SET available_copies = available_copies + 1 WHERE id = ?",
        (loan["book_id"],),
    )
    conn.commit()
    conn.close()

    return jsonify(
        {
            "message": "Book returned successfully",
            "overdue_days": overdue_days,
            "fine": fine,
        }
    )


if __name__ == "__main__":
    init_db()
    print("Athena LMS Backend running on http://127.0.0.1:5000")
    app.run(debug=True, port=5000)