import hashlib
import uuid
from dataclasses import dataclass
from typing import Optional
@dataclass
class User:
    id: str
    name: str
    email: str
    password_hash: str
    active: bool = True
class UserStore:
    def __init__(self):
        self.users = {}
        self.email_index = {}
    def add(self, user: User):
        self.users[user.id] = user
        self.email_index[user.email] = user.id
    def find_by_email(self, email: str) -> Optional[User]:
        user_id = self.email_index.get(email)
        return self.users.get(user_id) if user_id else None
    def get(self, user_id: str) -> Optional[User]:
        return self.users.get(user_id)
class Auth:
    def __init__(self, store: UserStore):
        self.store = store
        self.sessions = {}
    def register(self, name, email, password):
        if not name or not email or not password:
            raise ValueError("Missing fields")
        if "@" not in email:
            raise ValueError("Invalid email")
        if self.store.find_by_email(email):
            raise ValueError("Email already registered")
        user = User(
            id=str(uuid.uuid4()),
            name=name.strip(),
            email=email,
            password_hash=self.hash_password(password),
        )
        self.store.add(user)
        return user

    def login(self, email, password):
        user = self.store.find_by_email(email)
        if user is None:
            raise ValueError("Invalid credentials")
        if self.hash_password(password) != user.password_hash:
            raise ValueError("Invalid credentials")
        if not user.active:
            raise PermissionError("Account disabled")
        token = str(uuid.uuid4())
        self.sessions[token] = user.id
        return token

    def current_user(self, token):
        user_id = self.sessions.get(token)
        return self.store.get(user_id)

    @staticmethod
    def hash_password(password):
        return hashlib.sha256(password.encode()).hexdigest()

class ProfileService:
    def __init__(self, store):
        self.store = store

    def rename(self, user_id, name):
        user = self.store.get(user_id)
        if user is None:
            raise ValueError("User not found")
        user.name = name
        return user

    def change_email(self, user_id, email):
        user = self.store.get(user_id)
        if user is None:
            raise ValueError("User not found")
        self.store.email_index.pop(user.email, None)
        user.email = email
        self.store.email_index[email] = user.id
        return user

def seed(auth):
    auth.register("Alice", "alice@example.com", "Password123")
    auth.register("Bob", "bob@example.com", "Password123")

def main():
    store = UserStore()
    auth = Auth(store)
    profile = ProfileService(store)
    seed(auth)
    token = auth.login("Alice@Example.com", "Password123")
    user = auth.current_user(token)
    print(user.name)
    profile.change_email(user.id, "new@example.com")
    print(user.email)

if __name__ == "__main__":
    main()
