import hashlib
import secrets
import time
import jwt
from fastapi import Request
from app.errors import ServiceError


class Auth:
    def __init__(self, settings):
        self.settings = settings
        # A generated development secret invalidates cookies after a restart; production requires a stable secret.
        self.secret = settings.session_secret or secrets.token_urlsafe(48)

    def token(self, subject: str, role: str, lifetime: int = 43200) -> str:
        return jwt.encode({"sub": subject, "role": role, "exp": int(time.time()) + lifetime}, self.secret, algorithm="HS256")

    def read(self, token: str) -> dict:
        try:
            data = jwt.decode(token, self.secret, algorithms=["HS256"], options={"require": ["exp", "sub", "role"]})
            if data["role"] not in ("admin", "founder", "invite"):
                raise ValueError()
            return data
        except (jwt.PyJWTError, ValueError):
            raise ServiceError("UNAUTHORIZED", "Bitte erneut anmelden.", 401)

    def user(self, request: Request) -> dict:
        data = self.read(request.cookies.get("founder_session", ""))
        if data["role"] == "invite":
            raise ServiceError("UNAUTHORIZED", "Bitte Einladung zuerst einlösen.", 401)
        return data

    def admin(self, request: Request) -> dict:
        data = self.user(request)
        if data["role"] != "admin":
            raise ServiceError("FORBIDDEN", "Dieser Bereich ist Administratoren vorbehalten.", 403)
        return data

    # Worker callbacks use a separate server credential, never a browser session cookie.
    def worker(self, request: Request):
        supplied = request.headers.get("authorization", "").removeprefix("Bearer ")
        if not self.settings.worker_secret or not secrets.compare_digest(supplied, self.settings.worker_secret):
            raise ServiceError("UNAUTHORIZED", "Worker authentication required.", 401)

    # Keep the session inaccessible to JavaScript and restrict cross-site cookie use.
    def cookie(self, response, subject, role):
        response.set_cookie("founder_session", self.token(subject, role), httponly=True,
                            secure=self.settings.environment == "production", samesite="strict", max_age=43200)


def fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()
