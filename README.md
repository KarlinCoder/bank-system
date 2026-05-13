# Banking Microservices System

A banking system built with Python microservices architecture using Oracle Database, deployed via CI/CD with GitHub Actions to serverless infrastructure.

## Architecture Overview

- **API Gateway** - Routes requests to appropriate services
- **Account Service** - Manages customer accounts and balances
- **Transaction Service** - Handles deposits, withdrawals, transfers
- **User Service** - Manages customer authentication and profiles
- **Notification Service** - Sends email/SMS notifications
- **Database** - Oracle Database for persistent storage

## Technology Stack

- **Language**: Python 3.9+
- **Framework**: FastAPI for REST APIs
- **Database**: Oracle Database with SQLAlchemy ORM
- **Containerization**: Docker
- **Orchestration**: Kubernetes (EKS/AKS/GKE) or Serverless (AWS Lambda/Azure Functions)
- **CI/CD**: GitHub Actions
- **Monitoring**: Prometheus + Grafana
- **Logging**: ELK Stack

## Getting Started

### Prerequisites

- Docker
- Oracle Database (or Oracle XE for development)
- Python 3.9+
- kubectl (for Kubernetes deployment)
- AWS/Azure/GCP CLI (for serverless deployment)

### Local Development

1. Clone the repository
2. Set up Oracle Database
3. Configure environment variables
4. Build and run services:
   ```bash
   docker-compose up --build
   ```

### Deployment

The system is designed for deployment to:
- **AWS Lambda** with API Gateway
- **Azure Functions** with API Management
- **Google Cloud Functions** with API Gateway
- **Kubernetes** (any cloud provider)

See `.github/workflows/` for CI/CD pipeline definitions.