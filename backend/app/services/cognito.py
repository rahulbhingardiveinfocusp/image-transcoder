from app.core.config import settings
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import requests
from jose import jwt

app = FastAPI()
security = HTTPBearer()

# Replace these with outputs from your Terraform deployment
REGION = settings.AWS_REGION
USER_POOL_ID = settings.USER_POOL_ID
CLIENT_ID = settings.USER_POOL_CLIENT_ID

JWKS_URL = f"https://cognito-idp.{REGION}.amazonaws.com/{USER_POOL_ID}/.well-known/jwks.json"

try:
    jwks = requests.get(JWKS_URL).json()
except Exception as e:
    jwks = {"keys": []}

def verify_cognito_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        # Get token headers to match the key ID (kid)
        unverified_headers = jwt.get_unverified_header(token)
        kid = unverified_headers.get("kid")
        
        # Find the correct public key
        key = next((k for k in jwks["keys"] if k["kid"] == kid), None)
        if not key:
            raise HTTPException(status_code=401, detail="Invalid token claims")
            
        # Verify the token
        payload = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=CLIENT_ID, # Optional depending on id_token vs access_token
            options={"verify_aud": False} 
        )
        return payload
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
def require_admin(payload: dict = Depends(verify_cognito_token)):
    # Cognito roles usually show up under 'cognito:groups' in the Access/ID token
    groups = payload.get("cognito:groups", [])
    if "Admin" not in groups:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return payload