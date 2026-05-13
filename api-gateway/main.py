from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import httpx
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Service URLs (in production, these would come from service discovery or environment variables)
SERVICE_URLS = {
    "user-service": os.getenv("USER_SERVICE_URL", "http://localhost:8001"),
    "account-service": os.getenv("ACCOUNT_SERVICE_URL", "http://localhost:8002"),
    "transaction-service": os.getenv("TRANSACTION_SERVICE_URL", "http://localhost:8003"),
    "notification-service": os.getenv("NOTIFICATION_SERVICE_URL", "http://localhost:8004")
}

# App
app = FastAPI(title="Banking API Gateway", description="Gateway for banking microservices")

# Middleware to add request logging
@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"Incoming request: {request.method} {request.url}")
    response = await call_next(request)
    logger.info(f"Outgoing response: {response.status_code}")
    return response

# Health check endpoint
@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "api-gateway"}

# Service health checks
@app.get("/health/services")
async def check_services_health():
    health_status = {}
    async with httpx.AsyncClient() as client:
        for service_name, service_url in SERVICE_URLS.items():
            try:
                response = await client.get(f"{service_url}/health", timeout=5.0)
                health_status[service_name] = {
                    "status": "healthy" if response.status_code == 200 else "unhealthy",
                    "response_time": response.elapsed.total_seconds()
                }
            except Exception as e:
                health_status[service_name] = {
                    "status": "unhealthy",
                    "error": str(e)
                }
    return health_status

# Route forwarding function
async def forward_request(service_name: str, request: Request):
    if service_name not in SERVICE_URLS:
        raise HTTPException(status_code=404, detail=f"Service {service_name} not found")
    
    service_url = SERVICE_URLS[service_name]
    url = f"{service_url}{request.url.path}"
    
    # Prepare headers (excluding host)
    headers = dict(request.headers)
    headers.pop("host", None)
    
    # Get request body
    body = await request.body()
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.request(
                method=request.method,
                url=url,
                headers=headers,
                content=body,
                params=request.query_params,
                timeout=30.0
            )
            
            # Return response with same status code and headers
            return JSONResponse(
                content=response.json(),
                status_code=response.status_code,
                headers=dict(response.headers)
            )
        except httpx.RequestError as e:
            logger.error(f"Error forwarding request to {service_name}: {e}")
            raise HTTPException(status_code=503, detail=f"Service {service_name} unavailable")
        except Exception as e:
            logger.error(f"Unexpected error forwarding request to {service_name}: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")

# Routes for each service
@app.api_route("/users/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def users_route(request: Request, path: str):
    return await forward_request("user-service", request)

@app.api_route("/accounts/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def accounts_route(request: Request, path: str):
    return await forward_request("account-service", request)

@app.api_route("/transactions/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def transactions_route(request: Request, path: str):
    return await forward_request("transaction-service", request)

@app.api_route("/notifications/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def notifications_route(request: Request, path: str):
    return await forward_request("notification-service", request)

# Root endpoint
@app.get("/")
def root():
    return {
        "message": "Banking System API Gateway",
        "version": "1.0.0",
        "docs": "/docs",
        "services": list(SERVICE_URLS.keys())
    }