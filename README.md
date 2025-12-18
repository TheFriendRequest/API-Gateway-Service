# API Gateway Service

## 📋 Overview

The API Gateway is the single entry point for all client requests. It provides:
- **Centralized Authentication**: Firebase token verification
- **Request Routing**: Proxies requests to Composite Service
- **Header Injection**: Adds `x-firebase-uid` header for downstream services
- **CORS Handling**: Manages cross-origin requests

## 🏗️ Architecture

```
Frontend → API Gateway (8000) → Composite Service (8004) → Atomic Services
```

- **Port**: 8000
- **Authentication**: Firebase ID token verification
- **Deployment**: Cloud Run

## 🚀 Setup

### Prerequisites

- Python 3.9+
- Firebase service account key
- Firebase project with Authentication enabled

### Installation

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Add Firebase service account key**
   - Download from Firebase Console
   - Place as `serviceAccountKey.json` in service directory

3. **Configure environment variables**
   Create a `.env` file:
   ```env
   COMPOSITE_SERVICE_URL=http://localhost:8004
   FIREBASE_SERVICE_ACCOUNT_PATH=./serviceAccountKey.json
   GOOGLE_CLOUD_PROJECT=your-project-id
   ```

4. **Run the service**
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000
   ```

## 🔧 Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|---------|
| `COMPOSITE_SERVICE_URL` | Composite Service URL | `http://localhost:8004` | Yes |
| `FIREBASE_SERVICE_ACCOUNT_PATH` | Path to Firebase service account JSON | `./serviceAccountKey.json` | No |
| `GOOGLE_CLOUD_PROJECT` | GCP project ID (for ADC) | - | No |

## 📡 API Endpoints

### Public Endpoints (No Authentication Required)

#### `GET /`
Service information and routing details

**Response:**
```json
{
  "status": "API Gateway running",
  "service": "api-gateway",
  "version": "1.0.0",
  "routes_to": {
    "composite": "http://localhost:8004",
    "users": "http://localhost:8001",
    "events": "http://localhost:8002",
    "feed": "http://localhost:8003"
  }
}
```

#### `GET /health`
Health check endpoint

**Response:**
```json
{
  "status": "healthy",
  "service": "api-gateway"
}
```

### Proxy Endpoint (Catch-All)

#### `{METHOD} /{path}`
Proxies all requests to Composite Service

**Supported Methods**: GET, POST, PUT, DELETE, PATCH, OPTIONS

**Headers Required:**
- `Authorization: Bearer <firebase-token>` (for authenticated endpoints)

**Headers Injected:**
- `x-firebase-uid`: Firebase user ID (extracted from token)
- `x-user-role`: User role from Firebase custom claims

**Handled Paths:**
- `/api/users/*` - User management
- `/api/events/*` - Event management
- `/api/posts/*` - Feed posts
- `/api/friends/*` - Friend requests
- All other Composite Service endpoints

## 🔐 Authentication Flow

1. **Client Request**: Client sends request with `Authorization: Bearer <firebase-token>`
2. **Token Validation**: Middleware verifies token with Firebase Admin SDK
3. **UID Extraction**: Extracts `firebase_uid` and `role` from decoded token
4. **Header Injection**: Adds `x-firebase-uid` and `x-user-role` headers
5. **Request Forwarding**: Forwards to Composite Service with injected headers
6. **Response**: Returns response from Composite Service with CORS headers

### Public Paths

These paths are accessible without authentication:
- `/` - Root endpoint
- `/docs` - Swagger UI
- `/openapi.json` - OpenAPI specification
- `/redoc` - ReDoc documentation
- `/health` - Health check

## 🎯 Features

- **Firebase Authentication Middleware**: Validates all incoming tokens
- **Automatic Header Injection**: Adds `x-firebase-uid` to all requests forwarded to Composite Service
- **CORS Support**: Handles cross-origin requests with proper headers
- **Error Handling**: Returns appropriate HTTP status codes for auth failures
- **Catch-All Routing**: Single endpoint handles all API routes

## 🐳 Docker Deployment

### Build Image
```bash
docker build -t api-gateway .
```

### Run Container
```bash
docker run -p 8000:8000 \
  -e COMPOSITE_SERVICE_URL=http://composite-service:8004 \
  -e GOOGLE_CLOUD_PROJECT=your-project-id \
  api-gateway
```

## ☁️ GCP Cloud Run Deployment

The service is deployed to Cloud Run with:
- Application Default Credentials (ADC) for Firebase
- Environment variables configured via deployment script
- No VPC Connector needed (only forwards to Cloud Run services)

See [../GCP_DEPLOYMENT_GUIDE.md](../GCP_DEPLOYMENT_GUIDE.md) for details.

## 🧪 Testing

### Health Check (No Auth)
```bash
curl http://localhost:8000/health
```

### Test with Authentication
```bash
# Get Firebase token from frontend after login
curl -H "Authorization: Bearer <firebase-token>" \
     http://localhost:8000/api/users/me
```

### Test CORS
```bash
curl -X OPTIONS \
     -H "Origin: http://localhost:3000" \
     -H "Access-Control-Request-Method: GET" \
     http://localhost:8000/api/events
```

## 📚 API Documentation

Interactive API documentation available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- OpenAPI JSON: `http://localhost:8000/openapi.json`

## 🔍 Error Handling

The service returns standard HTTP status codes:

- `200 OK`: Successful request
- `401 Unauthorized`: Missing or invalid Firebase token
- `502 Bad Gateway`: Composite Service unavailable
- `500 Internal Server Error`: Server error

### Authentication Errors

- **Missing Authorization Header**: `401 Unauthorized` with `{"detail": "Authorization header missing"}`
- **Invalid Token Format**: `401 Unauthorized` with `{"detail": "Invalid authorization header format"}`
- **Expired Token**: `401 Unauthorized` with `{"detail": "Firebase token expired"}`
- **Invalid Token**: `401 Unauthorized` with `{"detail": "Invalid Firebase token"}`

## 📝 Notes

- The gateway uses a catch-all route pattern (`/{path:path}`) to forward all requests
- Firebase Admin SDK is initialized on service startup
- Middleware runs before route handlers to validate authentication
- CORS headers are added to all responses
- The service acts as a reverse proxy to Composite Service

## 🤝 Contributing

When modifying the gateway:
1. Update middleware in `middleware/auth_middleware.py`
2. Add new public paths if needed
3. Update this README with changes
4. Test authentication flow thoroughly
