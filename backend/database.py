from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import List, Optional

from models import Chat, Message, User, chat_from_row, message_from_row, user_from_row

DB_PATH = Path(__file__).resolve().parent / "database.db"


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS chats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(chat_id) REFERENCES chats(id)
            );
            """
        )
        migrate_legacy_schema(conn)


def migrate_legacy_schema(conn: sqlite3.Connection) -> None:
    user_columns = {row["name"] for row in conn.execute("PRAGMA table_info(users)")}
    if "password" in user_columns and "password_hash" not in user_columns:
        conn.execute("ALTER TABLE users RENAME TO users_legacy")
        conn.execute(
            """
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO users (id, username, password_hash, created_at)
            SELECT id, username, password, CURRENT_TIMESTAMP
            FROM users_legacy
            """
        )
        conn.execute("DROP TABLE users_legacy")

    chat_columns = {row["name"] for row in conn.execute("PRAGMA table_info(chats)")}
    if "created_at" not in chat_columns:
        conn.execute("ALTER TABLE chats ADD COLUMN created_at TEXT")
        conn.execute(
            """
            UPDATE chats
            SET created_at = CURRENT_TIMESTAMP
            WHERE created_at IS NULL OR created_at = ''
            """
        )
    if "updated_at" not in chat_columns:
        conn.execute("ALTER TABLE chats ADD COLUMN updated_at TEXT")
        conn.execute(
            """
            UPDATE chats
            SET updated_at = COALESCE(created_at, CURRENT_TIMESTAMP)
            WHERE updated_at IS NULL OR updated_at = ''
            """
        )

    message_columns = {row["name"] for row in conn.execute("PRAGMA table_info(messages)")}
    if "created_at" not in message_columns:
        conn.execute("ALTER TABLE messages ADD COLUMN created_at TEXT")
        conn.execute(
            """
            UPDATE messages
            SET created_at = CURRENT_TIMESTAMP
            WHERE created_at IS NULL OR created_at = ''
            """
        )

    conn.commit()


def create_user(username: str, password_hash: str) -> User:
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, password_hash),
        )
        user_id = cursor.lastrowid
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return user_from_row(row)


def get_user_by_username(username: str) -> Optional[User]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        return user_from_row(row)


def get_user_by_id(user_id: int) -> Optional[User]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return user_from_row(row)


def update_user_password(user_id: int, password_hash: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (password_hash, user_id),
        )


def create_chat(user_id: int, title: str) -> Chat:
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO chats (user_id, title) VALUES (?, ?)",
            (user_id, title),
        )
        chat_id = cursor.lastrowid
        row = conn.execute("SELECT * FROM chats WHERE id = ?", (chat_id,)).fetchone()
        return chat_from_row(row)


def list_chats(user_id: int) -> List[Chat]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM chats
            WHERE user_id = ?
            ORDER BY updated_at DESC, id DESC
            """,
            (user_id,),
        ).fetchall()
        return [chat_from_row(row) for row in rows]


def get_chat(chat_id: int) -> Optional[Chat]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM chats WHERE id = ?", (chat_id,)).fetchone()
        return chat_from_row(row)


def rename_chat(chat_id: int, title: str) -> Optional[Chat]:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE chats
            SET title = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (title, chat_id),
        )
        row = conn.execute("SELECT * FROM chats WHERE id = ?", (chat_id,)).fetchone()
        return chat_from_row(row)


def delete_chat(chat_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM messages WHERE chat_id = ?", (chat_id,))
        conn.execute("DELETE FROM chats WHERE id = ?", (chat_id,))


def add_message(chat_id: int, role: str, content: str) -> Message:
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO messages (chat_id, role, content) VALUES (?, ?, ?)",
            (chat_id, role, content),
        )
        conn.execute(
            "UPDATE chats SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (chat_id,),
        )
        message_id = cursor.lastrowid
        row = conn.execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone()
        return message_from_row(row)


def list_messages(chat_id: int) -> List[Message]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM messages
            WHERE chat_id = ?
            ORDER BY id ASC
            """,
            (chat_id,),
        ).fetchall()
        return [message_from_row(row) for row in rows]
