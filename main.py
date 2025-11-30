"""
API Gateway Service
Centralizes authentication and routes requests to downstream services
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from middleware.auth_middleware import FirebaseAuthMiddleware
import firebase_admin  # type: ignore
from firebase_admin import credentials  # type: ignore
import os
from dotenv import load_dotenv  # type: ignore
import httpx  # type: ignore
from typing import Dict, Any, Optional

# Load environment variables
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
load_dotenv(dotenv_path=env_path, override=True)

# Initialize Firebase Admin SDK for middleware
try:
    if len(firebase_admin._apps) == 0:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        default_path = os.path.join(current_dir, 'serviceAccountKey.json')
        
        if os.path.exists(default_path):
            cred = credentials.Certificate(default_path)
            firebase_admin.initialize_app(cred)
            print("✅ Firebase Admin initialized in API Gateway")
        else:
            service_account_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH")
            if service_account_path:
                if not os.path.isabs(service_account_path):
                    service_account_path = os.path.join(current_dir, service_account_path)
                if os.path.exists(service_account_path):
                    cred = credentials.Certificate(service_account_path)
                    firebase_admin.initialize_app(cred)
                    print(f"✅ Firebase Admin initialized from env: {service_account_path}")
            
            # Try Application Default Credentials
            if len(firebase_admin._apps) == 0:
                project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
                if project_id:
                    firebase_admin.initialize_app()
                    print("✅ Firebase Admin initialized with Application Default Credentials")
                else:
                    print("❌ Firebase initialization FAILED - no credentials found")
except Exception as e:
    print(f"❌ Firebase initialization error: {e}")
    import traceback
    traceback.print_exc()

app = FastAPI(
    title="API Gateway",
    description="Centralized authentication gateway that routes to microservices",
    version="1.0.0"
)

# Service URLs
COMPOSITE_SERVICE_URL = os.getenv("COMPOSITE_SERVICE_URL", "http://localhost:8004")
USERS_SERVICE_URL = os.getenv("USERS_SERVICE_URL", "http://localhost:8001")
EVENTS_SERVICE_URL = os.getenv("EVENTS_SERVICE_URL", "http://localhost:8002")
FEED_SERVICE_URL = os.getenv("FEED_SERVICE_URL", "http://localhost:8003")

# Add CORS middleware (must be first)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["ETag", "etag", "Location", "Content-Type", "x-firebase-uid"]
)

# Add Firebase authentication middleware (must be after CORS)
app.add_middleware(
    FirebaseAuthMiddleware,
    public_paths=["/", "/docs", "/openapi.json", "/redoc", "/health"],
    auth_required_by_default=True
)

@app.get("/")
def root():
    return {
        "status": "API Gateway running",
        "service": "api-gateway",
        "version": "1.0.0",
        "routes_to": {
            "composite": COMPOSITE_SERVICE_URL,
            "users": USERS_SERVICE_URL,
            "events": EVENTS_SERVICE_URL,
            "feed": FEED_SERVICE_URL
        }
    }

@app.get("/health")
def health():
    return {"status": "healthy", "service": "api-gateway"}

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
async def gateway_proxy(request: Request, path: str):
    """
    Proxy all requests to the Composite Service.
    The Composite Service will then route to the appropriate atomic services.
    The x-firebase-uid header is already set by the middleware.
    """
    # Handle OPTIONS preflight requests explicitly
    if request.method == "OPTIONS":
        from fastapi.responses import Response
        return Response(
            status_code=200,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, PATCH, OPTIONS",
                "Access-Control-Allow-Headers": "*",
                "Access-Control-Allow-Credentials": "true",
                "Access-Control-Max-Age": "3600"
            }
        )
    
    # Get firebase_uid and role from request state (set by middleware)
    firebase_uid = getattr(request.state, "firebase_uid", None)
    user_role = getattr(request.state, "role", "user")
    
    # Prepare headers for downstream
    headers = {
        "Content-Type": "application/json"
    }
    
    if firebase_uid:
        headers["x-firebase-uid"] = firebase_uid
    if user_role:
        headers["x-user-role"] = user_role
    
    # Forward original headers that might be needed
    original_headers = dict(request.headers)
    if "authorization" in original_headers:
        headers["Authorization"] = original_headers["authorization"]
    if "if-none-match" in original_headers:
        headers["If-None-Match"] = original_headers["if-none-match"]
    if "if-match" in original_headers:
        headers["If-Match"] = original_headers["if-match"]
    
    # Get request body if present
    body = None
    if request.method in ["POST", "PUT", "PATCH"]:
        try:
            body = await request.json()
        except:
            body = await request.body()
    
    # Forward to Composite Service
    target_url = f"{COMPOSITE_SERVICE_URL}/{path}"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                json=body if isinstance(body, dict) else None,
                content=body if not isinstance(body, dict) else None,
                params=dict(request.query_params),
                timeout=30.0
            )
            
            # Forward response with CORS headers
            from fastapi.responses import Response
            response_headers = dict(response.headers)
            # Ensure CORS headers are present
            response_headers["Access-Control-Allow-Origin"] = "*"
            response_headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, PATCH, OPTIONS"
            response_headers["Access-Control-Allow-Headers"] = "*"
            response_headers["Access-Control-Allow-Credentials"] = "true"
            
            return Response(
                content=response.content,
                status_code=response.status_code,
                headers=response_headers,
                media_type=response.headers.get("content-type", "application/json")
            )
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=502,
            detail=f"Failed to forward request to Composite Service: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

