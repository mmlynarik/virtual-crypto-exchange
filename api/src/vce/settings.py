import os

CG_API_URL = "https://api.coingecko.com/api/v3"

BACKEND_DB_HOST = os.getenv("BACKEND_DB_HOST")
BACKEND_DB_NAME = os.getenv("BACKEND_DB_NAME")
BACKEND_DB_USER = os.getenv("BACKEND_DB_USER")
BACKEND_DB_PASSWORD = os.getenv("BACKEND_DB_PASSWORD")
BACKEND_DB_URL = (
    f"postgresql+asyncpg://{BACKEND_DB_USER}:{BACKEND_DB_PASSWORD}@{BACKEND_DB_HOST}/{BACKEND_DB_NAME}"
)
VS_CURRENCY = os.getenv("VS_CURRENCY", "usd")

# Required by the app, but validated in vce.auth.security (its only user) so that tools that just
# need DB settings, such as Alembic migrations, can import this module without it.
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "")
JWT_ALGORITHM = "HS256"
JWT_AUDIENCE = "vce"
JWT_ACCESS_TOKEN_EXPIRY_SECONDS = 5 * 60
JWT_REFRESH_TOKEN_EXPIRY_SECONDS = 7 * 24 * 60 * 60

EMAIL_MAX_LENGTH = 256
GITHUB_NAME_MAX_LENGTH = 64
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128

GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"
