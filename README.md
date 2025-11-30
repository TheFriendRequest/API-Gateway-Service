# API Gateway Service

## Overview

The API Gateway is the single entry point for all client requests. It handles:
- Firebase authentication (token verification)
- Request routing to Composite Service
- Header injection (x-firebase-uid)

## Port

- **Default Port**: 8000

## Architecture

```
Frontend → API Gateway (8000) → Composite Service (8004) → Atomic Services
```

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Copy Firebase service account key:
```bash
cp serviceAccountKey.json API-Gateway-Service/
```

3. Set environment variables (optional):
```env
COMPOSITE_SERVICE_URL=http://localhost:8004
FIREBASE_SERVICE_ACCOUNT_PATH=./serviceAccountKey.json
```

4. Run the service:
```bash
uvicorn main:app --port 8000
```

## Features

- **Firebase Authentication Middleware**: Validates all incoming tokens
- **Automatic Header Injection**: Adds `x-firebase-uid` to all requests forwarded to Composite Service
- **Public Paths**: `/`, `/docs`, `/openapi.json`, `/redoc`, `/health` are accessible without auth
- **CORS Support**: Handles cross-origin requests

## Request Flow

1. Client sends request with `Authorization: Bearer <token>` to API Gateway
2. Middleware validates Firebase token
3. Middleware extracts `firebase_uid` and stores in `request.state`
4. Gateway forwards request to Composite Service with `x-firebase-uid` header
5. Composite Service processes request and routes to atomic services

## Testing

Test the health endpoint (no auth required):
```bash
curl http://localhost:8000/health
```

Test with authentication:
```bash
curl -H "Authorization: Bearer <firebase-token>" http://localhost:8000/api/events
```

