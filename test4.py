from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import hashlib
import re
import uuid
@dataclass
class User:
    id: str
    name: str
    email: str
    password_hash: str
    active: bool = True
    roles: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
class UserRepository:
    def __init__(self):
        self.users: Dict[str, User] = {}
        self.email_index: Dict[str, str] = {}
    def add(self, user: User) -> None:
        self.users[user.id] = user
        self.email_index[user.email] = user.id
    def get(self, user_id: str) -> Optional[User]:
        return self.users.get(user_id)
    def find_by_email(self, email: str) -> Optional[User]:
        user_id = self.email_index.get(email)
        if not user_id:
            return None
        return self.users.get(user_id)
    def delete(self, user_id: str) -> bool:
        user = self.users.get(user_id)
        if user is None:
            return False
        del self.users[user_id]
        self.email_index.pop(user.email, None)
        return True
    def list_active(self) -> List[User]:
        return [u for u in self.users.values() if u.active]
class PasswordService:
    @staticmethod
    def hash_password(password: str) -> str:
        return hashlib.sha256(password.encode()).hexdigest()
    @staticmethod
    def verify(password: str, password_hash: str) -> bool:
        return PasswordService.hash_password(password) == password_hash
class TokenService:
    def __init__(self):
        self.tokens: Dict[str, tuple] = {}
    def issue(self, user_id: str) -> str:
        token = str(uuid.uuid4())
        self.tokens[token] = (user_id, datetime.utcnow() + timedelta(hours=1))
        return token
    def validate(self, token: str) -> Optional[str]:
        record = self.tokens.get(token)
        if record is None:
            return None
        user_id, expires_at = record
        if datetime.utcnow() > expires_at:
            return None
        return user_id
class AuthService:
    def __init__(self, repo: UserRepository, tokens: TokenService):
        self.repo = repo
        self.tokens = tokens
    def register(self, name: str, email: str, password: str) -> User:
        if not name or not email or not password:
            raise ValueError("All fields are required")
        if "@" not in email:
            raise ValueError("Invalid email")
        if self.repo.find_by_email(email):
            raise ValueError("Email already registered")
        user = User(
            id=str(uuid.uuid4()),
            name=name.strip(),
            email=email,
            password_hash=PasswordService.hash_password(password),
        )
        self.repo.add(user)
        return user
    def login(self, email: str, password: str) -> str:
        user = self.repo.find_by_email(email)
        if user is None:
            raise ValueError("Invalid email or password")
        if not PasswordService.verify(password, user.password_hash):
            raise ValueError("Invalid email or password")
        if not user.active:
            raise PermissionError("Account is disabled")
        return self.tokens.issue(user.id)
    def logout(self, token: str) -> None:
        self.tokens.tokens.pop(token, None)
    def current_user(self, token: str) -> Optional[User]:
        user_id = self.tokens.validate(token)
        return self.repo.get(user_id)
class UserService:
    def __init__(self, repo: UserRepository):
        self.repo = repo
    def update_email(self, user_id: str, email: str) -> User:
        user = self.repo.get(user_id)
        if user is None:
            raise ValueError("User not found")
        if "@" not in email:
            raise ValueError("Invalid email")
        self.repo.email_index.pop(user.email, None)
        user.email = email
        self.repo.email_index[email] = user.id
        return user
    def set_active(self, user_id: str, active: bool) -> User:
        user = self.repo.get(user_id)
        if user is None:
            raise ValueError("User not found")
        user.active = active
        return user
    def add_role(self, user_id: str, role: str) -> User:
        user = self.repo.get(user_id)
        if user is None:
            raise ValueError("User not found")
        if role not in user.roles:
            user.roles.append(role)
        return user
    def has_role(self, user_id: str, role: str) -> bool:
        user = self.repo.get(user_id)
        return user is not None and role in user.roles
class AuditLog:
    def __init__(self):
        self.events: List[dict] = []
    def record(self, action: str, user_id: str, detail: str = "") -> None:
        self.events.append({
            "time": datetime.utcnow().isoformat(),
            "action": action,
            "user_id": user_id,
            "detail": detail,
        })
    def for_user(self, user_id: str) -> List[dict]:
        return [event for event in self.events if event["user_id"] == user_id]
class UserController:
    def __init__(self, auth: AuthService, users: UserService, audit: AuditLog):
        self.auth = auth
        self.users = users
        self.audit = audit
    def create_account(self, name: str, email: str, password: str) -> dict:
        user = self.auth.register(name, email, password)
        self.audit.record("register", user.id)
        return self.serialize(user)
    def authenticate(self, email: str, password: str) -> dict:
        token = self.auth.login(email, password)
        user = self.auth.current_user(token)
        self.audit.record("login", user.id)
        return {"token": token, "user": self.serialize(user)}
    def change_email(self, token: str, email: str) -> dict:
        user = self.auth.current_user(token)
        if user is None:
            raise PermissionError("Authentication required")
        updated = self.users.update_email(user.id, email)
        self.audit.record("email_change", user.id, email)
        return self.serialize(updated)
    def serialize(self, user: User) -> dict:
        return {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "active": user.active,
            "roles": user.roles,
            "created_at": user.created_at.isoformat(),
        }
def seed(auth: AuthService) -> None:
    auth.register("Alice", "alice@example.com", "Password123")
    auth.register("Bob", "bob@example.com", "Password123")
def validate_password_strength(password: str) -> bool:
    if len(password) < 8:
        return False
    if not re.search(r"[A-Z]", password):
        return False
    if not re.search(r"[0-9]", password):
        return False
    return True
def build_application() -> UserController:
    repo = UserRepository()
    tokens = TokenService()
    auth = AuthService(repo, tokens)
    users = UserService(repo)
    audit = AuditLog()
    seed(auth)
    return UserController(auth, users, audit)
def demo() -> None:
    app = build_application()
    result = app.authenticate("alice@example.com", "Password123")
    print(result["user"])
    print(result["token"])
if __name__ == "__main__":
    demo()
