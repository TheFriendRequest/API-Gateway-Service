"""
Firebase Authentication Middleware for API Gateway
This middleware validates Firebase tokens and injects x-firebase-uid header
"""
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from typing import Optional, List
import firebase_admin  # type: ignore
from firebase_admin import auth  # type: ignore
import os
import re


class FirebaseAuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware that verifies Firebase tokens on every request and injects x-firebase-uid header.
    Public paths (like /docs, /openapi.json) are excluded from authentication.
    """
    
    def __init__(
        self,
        app: ASGIApp,
        public_paths: Optional[List[str]] = None,
        auth_required_by_default: bool = True
    ):
        super().__init__(app)
        self.public_paths = public_paths or [
            "/",
            "/docs",
            "/openapi.json",
            "/redoc",
            "/health",
            "/public"
        ]
        self.auth_required_by_default = auth_required_by_default
        
    def _is_public_path(self, path: str) -> bool:
        """Check if path is in public_paths list (supports wildcards)"""
        for pattern in self.public_paths:
            # Convert wildcard pattern to regex
            regex_pattern = pattern.replace("*", ".*")
            if re.match(f"^{regex_pattern}$", path):
                return True
        return False
    
    async def dispatch(self, request: Request, call_next):
        """Process request and verify Firebase token if needed"""
        
        # Skip auth for OPTIONS requests (CORS preflight)
        if request.method == "OPTIONS":
            return await call_next(request)
        
        # Skip auth for public paths
        if self._is_public_path(request.url.path):
            return await call_next(request)
        
        # Extract Authorization header
        authorization = request.headers.get("Authorization") or request.headers.get("authorization")
        
        if not authorization:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Authorization header missing"}
            )
        
        # Extract token from "Bearer <token>"
        try:
            scheme, token = authorization.split()
            if scheme.lower() != "bearer":
                raise ValueError("Invalid authorization scheme")
        except ValueError:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Invalid authorization header format. Expected: Bearer <token>"}
            )
        
        # Verify Firebase token
        try:
            # Check if Firebase is initialized
            if len(firebase_admin._apps) == 0:
                return JSONResponse(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    content={"detail": "Firebase Admin SDK not initialized"}
                )
            
            # Verify the token
            decoded_token = auth.verify_id_token(token)
            firebase_uid = decoded_token.get("uid")
            
            if not firebase_uid:
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"detail": "Firebase token missing UID"}
                )
            
            # Store decoded token in request state for access in route handlers
            request.state.firebase_uid = firebase_uid
            request.state.decoded_token = decoded_token
            request.state.email = decoded_token.get("email", "")
            # Store role from custom claims if present
            request.state.role = decoded_token.get("role", "user")
            
            # Note: x-firebase-uid will be added to headers when forwarding to downstream services
            
        except auth.ExpiredIdTokenError:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Firebase token expired"}
            )
        except auth.InvalidIdTokenError:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Invalid Firebase token"}
            )
        except Exception as e:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": f"Token verification failed: {str(e)}"}
            )
        
        # Continue processing request
        response = await call_next(request)
        return response

