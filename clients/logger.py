import json
from typing import Any, Dict, List
from datetime import datetime, timezone

INTEGRATION_LOGS: List[Dict[str, Any]] = []

def log_integration(
    service_name: str,
    method: str,
    url: str,
    headers: Dict[str, str],
    payload: Any,
    status_code: int,
    resp_headers: Dict[str, str],
    resp_body: Any
):
    """
    Emits formatted HTTP Request and Response logs for every external integration call
    and stores them in an in-memory buffer for real-time dashboard inspection.
    """
    def sanitize_headers(h: Dict[str, str]) -> Dict[str, str]:
        sanitized = {}
        for k, v in h.items():
            if any(secret_kw in k.lower() for secret_kw in ['auth', 'key', 'secret', 'bearer', 'token']):
                sanitized[k] = v[:8] + "..." if len(v) > 8 else "***"
            else:
                sanitized[k] = v
        return sanitized

    san_headers = sanitize_headers(headers)
    san_resp_headers = sanitize_headers(dict(resp_headers))

    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": service_name,
        "method": method,
        "url": url,
        "req_headers": san_headers,
        "req_payload": payload,
        "status_code": status_code,
        "resp_headers": san_resp_headers,
        "resp_body": resp_body
    }

    INTEGRATION_LOGS.append(log_entry)
    if len(INTEGRATION_LOGS) > 100:
        INTEGRATION_LOGS.pop(0)

    print(f"\n=======================================================", flush=True)
    print(f"📡 INTEGRATION REQUEST [{service_name.upper()}]", flush=True)
    print(f"=======================================================", flush=True)
    print(f"Method: {method} {url}", flush=True)
    print(f"Headers: {json.dumps(san_headers, indent=2)}", flush=True)
    if payload:
        try:
            print(f"Payload: {json.dumps(payload, indent=2)}", flush=True)
        except Exception:
            print(f"Payload: {payload}", flush=True)
    else:
        print(f"Payload: None", flush=True)

    print(f"\n=======================================================", flush=True)
    print(f"📥 INTEGRATION RESPONSE [{service_name.upper()}]", flush=True)
    print(f"=======================================================", flush=True)
    print(f"Status Code: {status_code}", flush=True)
    print(f"Headers: {json.dumps(san_resp_headers, indent=2)}", flush=True)
    try:
        if isinstance(resp_body, (dict, list)):
            print(f"Body: {json.dumps(resp_body, indent=2)}", flush=True)
        else:
            print(f"Body: {resp_body}", flush=True)
    except Exception:
        print(f"Body: {resp_body}", flush=True)
    print(f"=======================================================\n", flush=True)

def get_logs() -> List[Dict[str, Any]]:
    return INTEGRATION_LOGS
