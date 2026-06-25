from app.core.config import settings
from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import requests
from jose import jwt

app = FastAPI()
security = HTTPBearer()

REGION = settings.AWS_REGION
USER_POOL_ID = settings.USER_POOL_ID
CLIENT_ID = settings.USER_POOL_CLIENT_ID

ISSUER = f"https://cognito-idp.{REGION}.amazonaws.com/{USER_POOL_ID}"
JWKS_URL = f"{ISSUER}/.well-known/jwks.json"

jwks = requests.get(JWKS_URL).json()


def get_public_key(token: str):
    headers = jwt.get_unverified_header(token)
    kid = headers["kid"]

    for key in jwks["keys"]:
        if key["kid"] == kid:
            return key

    return None


def verify_cognito_token(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    token = credentials.credentials

    try:
        key = get_public_key(token)

        if not key:
            raise HTTPException(status_code=401, detail="Invalid token key")

        payload = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=CLIENT_ID,
            issuer=ISSUER,
        )
        print("DECODED PAYLOAD:", payload)
        return payload

    except Exception:
        raise HTTPException(
            status_code=401,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


def require_admin(payload: dict = Depends(verify_cognito_token)):
    groups = payload.get("cognito:groups", [])

    if "Admin" not in groups:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return payload