from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional


@dataclass
class User:
    id: int
    username: str
    password_hash: str
    created_at: str

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data.pop("password_hash", None)
        return data


@dataclass
class Chat:
    id: int
    user_id: int
    title: str
    created_at: str
    updated_at: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Message:
    id: int
    chat_id: int
    role: str
    content: str
    created_at: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def user_from_row(row: Optional[Any]) -> Optional[User]:
    if row is None:
        return None
    return User(
        id=row["id"],
        username=row["username"],
        password_hash=row["password_hash"],
        created_at=row["created_at"],
    )


def chat_from_row(row: Optional[Any]) -> Optional[Chat]:
    if row is None:
        return None
    return Chat(
        id=row["id"],
        user_id=row["user_id"],
        title=row["title"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def message_from_row(row: Optional[Any]) -> Optional[Message]:
    if row is None:
        return None
    return Message(
        id=row["id"],
        chat_id=row["chat_id"],
        role=row["role"],
        content=row["content"],
        created_at=row["created_at"],
    )
