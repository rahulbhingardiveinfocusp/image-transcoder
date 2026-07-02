from app.core.config import settings
from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import requests
from jose import jwt
import logging
import sys
import boto3
from app.core.config import settings

cognito = boto3.client(
    "cognito-idp",
    region_name=settings.AWS_REGION
)

logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [BRIDGE-SCRIPT] %(message)s"
)
logger = logging.getLogger(__name__)

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
        logger.info(f"REGION:{REGION}")
        logger.info(f"USER_POOL_ID:{USER_POOL_ID}")
        logger.info(f"USER_POOL_CLIENT_ID:{CLIENT_ID}")
        key = get_public_key(token)
        logger.info(f"key:{key}")
        if not key:
            raise HTTPException(status_code=401, detail="Invalid token key")

        payload = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            issuer=ISSUER,
            options={"verify_aud": False},
        )
        logger.info(f"DECODED PAYLOAD:{payload}")
        return payload

    except Exception:
        raise HTTPException(
            status_code=401,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


def require_admin(payload: dict = Depends(verify_cognito_token)):
    groups = (
        payload.get("cognito:groups")
        or payload.get("groups")
        or []
    )

    if isinstance(groups, str):
        groups = [groups]

    if "Admin" not in groups:
        raise HTTPException(status_code=403, detail="Admin privileges required")

    return payload

def get_cognito_user_count():
    total = 0
    pagination_token = None

    while True:
        params = {
            "UserPoolId": settings.USER_POOL_ID,
            "Limit": 60
        }

        if pagination_token:
            params["PaginationToken"] = pagination_token

        response = cognito.list_users(**params)

        total += len(response.get("Users", []))
        pagination_token = response.get("PaginationToken")

        if not pagination_token:
            break

    return total