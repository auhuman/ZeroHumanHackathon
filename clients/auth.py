import os
import json
import base64
from typing import Dict, Any, Optional
from pydantic import BaseModel

class GoogleUser(BaseModel):
    google_id: str
    email: str
    name: str
    picture: Optional[str] = None

def parse_google_jwt(token: str) -> Optional[GoogleUser]:
    """
    Parses unverified/verified Google OAuth JWT credential token.
    Extracts email, name, picture, and sub (google_id).
    """
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        payload_b64 = parts[1]
        # Pad base64 string if necessary
        rem = len(payload_b64) % 4
        if rem > 0:
            payload_b64 += "=" * (4 - rem)
        
        decoded_bytes = base64.urlsafe_b64decode(payload_b64)
        payload = json.loads(decoded_bytes.decode('utf-8'))
        
        return GoogleUser(
            google_id=payload.get("sub", f"g_{payload.get('email', 'anon')}"),
            email=payload.get("email", ""),
            name=payload.get("name", payload.get("email", "Candidate")),
            picture=payload.get("picture", "")
        )
    except Exception as e:
        print(f"[GoogleAuth] Exception parsing JWT: {e}")
        return None
