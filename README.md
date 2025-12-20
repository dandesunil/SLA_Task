# SLA Tracking Micro Service

A comprehensive FastAPI-based micro service for tracking customer support tickets and proactively escalating those at risk of breaching Service-Level Agreements (SLAs). The service provides real-time visibility into looming SLA breaches while automating on-call escalation and notification workflows.

## 🚀 Features

### Core Functionality (P0 Requirements)
- **Ingestion Endpoint**: `POST /tickets` for batch ticket events (idempotent by id + updated_at)
- **Persistence**: PostgreSQL storage with status history and multiple SLA clocks
- **SLA Engine**: Background scheduler evaluating tickets every minute
- **Escalation Workflow**: Automated Slack notifications and escalation tracking
- **Configuration Management**: YAML-based SLA targets with hot-reload support
- **Query Endpoints**: Comprehensive ticket and dashboard APIs
- **Docker Support**: Complete containerization with docker-compose

### Enhanced Features (P1/P2)
- **Real-time Alerts**: WebSocket streaming for live SLA monitoring
- **Structured Logging**: JSON logs with correlation IDs and latency tracking
- **Dashboard API**: Paginated ticket filtering by SLA state
- **Cloud Deployment**: Infrastructure as Code for AWS Fargate/GCP Cloud Run

## Architecture

### Tech Stack
- **Framework**: FastAPI with async/await support
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Background Tasks**: APScheduler for SLA evaluation
- **Configuration**: YAML with watchdog hot-reload
- **Notifications**: Slack webhook integration
- **Real-time**: WebSocket for alert streaming
- **Logging**: Structured JSON logging with correlation IDs
- **Package Manager**: uv (primary) with pip fallback

### Design Principles
- **SOLID Principles**: Single responsibility, open/closed, liskov substitution, interface segregation, dependency inversion
- **Async/Await**: Non-blocking operations throughout
- **Scalability**: Stateless design with horizontal scaling capability
- **Observability**: Comprehensive logging and monitoring

## 📁 Project Structure

```
sla-service/
├── app/
│   ├── __init__.py                 # Application entry
│   ├── main.py                     # FastAPI application
│   ├── config.py                   # Configuration management
│   ├── database.py                 # Database setup
│   ├── models/                     # SQLAlchemy models
│   │   ├── __init__.py
│   │   └── ticket.py              # Ticket, Alert, StatusHistory models
│   ├── schemas/                    # Pydantic schemas
│   │   ├── __init__.py
│   │   ├── ticket.py              # Ticket request/response schemas
│   │   └── alert.py               # Alert schemas
│   ├── services/                   # Business logic
│   │   ├── __init__.py
│   │   ├── ticket_service.py      # Ticket CRUD operations
│   │   ├── sla_engine.py          # SLA calculation engine
│   │   ├── escalation_service.py  # Escalation workflows
│   │   └── notification_service.py # Slack notifications
│   ├── api/                        # API endpoints
│   │   ├── __init__.py
│   │   ├── tickets.py             # Ticket endpoints
│   ├── utils/                      # Utilities
│   │   ├── __init__.py
│   │   ├── sla_calculator.py      # SLA time calculations
│   │   ├── logging.py             # Structured logging setup
│   │   └── correlation_id.py      # Correlation ID middleware
│   └── dependencies.py            # FastAPI dependencies
├── scripts/                        # Utility scripts
│   └── init-db.sql               # Database initialization
├── tests/                          # Test suite
├── docker-compose.yaml            # Local development setup
├── Dockerfile                     # Container definition
├── pyproject.toml                 # uv package configuration
├── requirements.txt              # pip fallback
├── sla_config.yaml              # Default SLA configuration
├── .env.example                 # Environment template
└── README.md                    # This file
```

## 🚦 Quick Start

### Prerequisites
- Python 3.12+
- Docker and Docker Compose
- uv package manager (recommended)

### Installation & Setup

1. **Clone and Setup**
   ```bash
   # Using uv (recommended)
   uv sync
  
   ```

2. **Environment Configuration**
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

3. **Database Setup**
   ```bash
   # Using docker-compose (recommended)
   docker-compose up postgres -d
   
   # Initialize database
   python -c "from app.database import init_database; import asyncio; asyncio.run(init_database())"
   ```

4. **Start the Service**
   ```bash
   # Using docker-compose (recommended)
   docker-compose up -d
   
   # Or directly with uvicorn
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

### Development with Docker Compose
The complete development environment includes:
- PostgreSQL database
- SLA Tracking Service
- Mock Slack server for testing
- Redis for caching (optional)
- pgAdmin for database management

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f sla-service

# Access services
# SLA Service: http://localhost:8000
# API Documentation: http://localhost:8000/docs
# pgAdmin: http://localhost:8080
```

## 📡 API Documentation

### Core Endpoints

#### Ticket Management
```http
# Ingest tickets (batch)
POST /tickets
Content-Type: application/json

{
  "tickets": [
    {
      "external_id": "TICKET-001",
      "title": "Critical system outage",
      "description": "Production system down",
      "priority": "P0",
      "customer_tier": "enterprise",
      "status": "open",
      "assigned_to": "john.doe"
    }
  ]
}

# Get ticket by ID
GET /tickets/{ticket_id}

# Get ticket SLA status
GET /tickets/{ticket_id}/sla
```

#### Dashboard & Analytics
```http
# Get dashboard data
GET /dashboard?page=1&size=50&sla_state=warning

# Query parameters:
# - sla_state: warning, critical, breached, compliant
# - priority: P0, P1, P2, P3
# - customer_tier: enterprise, premium, standard
# - status: open, in_progress, resolved, etc.
```

#### Real-time WebSocket
```javascript
// Connect to WebSocket for real-time alerts
const ws = new WebSocket('ws://localhost:8000/ws/alerts');

ws.onmessage = function(event) {
    const alert = JSON.parse(event.data);
    console.log('New SLA Alert:', alert);
};
```

### SLA Configuration

The service uses `sla_config.yaml` to define SLA targets:

```yaml
sla_targets:
  ENTERPRISE:
    P0:
      response_minutes: 15
      resolution_minutes: 60
      escalation:
        LEVEL_1: 10
        LEVEL_2: 20
        LEVEL_3: 30
        LEVEL_4: 45

    P1:
      response_minutes: 60
      resolution_minutes: 240

    P2:
      response_minutes: 240
      resolution_minutes: 480

    P3:
      response_minutes: 480
      resolution_minutes: 1440

  PREMIUM:
    P0:
      response_minutes: 30
      resolution_minutes: 120

    P1:
      response_minutes: 120
      resolution_minutes: 480

    P2:
      response_minutes: 360
      resolution_minutes: 720

    P3:
      response_minutes: 720
      resolution_minutes: 1440

  STANDARD:
    P1:
      response_minutes: 240
      resolution_minutes: 720
    P2:
      response_minutes: 480
      resolution_minutes: 1440
    P3:
      response_minutes: 1440
      resolution_minutes: 2880

  BASIC:
    P2:
      response_minutes: 720
      resolution_minutes: 1440
    P3:
      response_minutes: 1440
      resolution_minutes: 4320


alert_thresholds:
  warning: 15     # Alert when 15% or less time remains
  critical: 5     # Critical alert when 5% or less remains

escalation_levels:
  0: "No escalation"
  1: "Team lead notified"
  2: "Manager notified"
  4: "Director notified"
  5: "VP notified"
  # ... more levels
```

Configuration hot-reloads automatically when the file changes.

## 🔧 Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `APP_NAME` | Application name | "SLA Tracking Service" |
| `DEBUG` | Enable debug mode | false |
| `DATABASE_URL` | PostgreSQL connection | postgresql+asyncpg://... |
| `SLACK_WEBHOOK_URL` | Slack webhook URL | "" |
| `SCHEDULER_INTERVAL` | SLA check interval (seconds) | 60 |
| `WARNING_THRESHOLD` | Warning threshold (0-1) | 0.15 |
| `CRITICAL_THRESHOLD` | Critical threshold (0-1) | 0.05 |
| `LOG_LEVEL` | Logging level | INFO |
| `WS_MAX_CONNECTIONS` | WebSocket connection limit | 100 |

### Database Schema

#### Core Tables
- **tickets**: Main ticket data with SLA tracking
- **ticket_status_history**: Status change audit trail
- **alerts**: SLA alert records
- **sla_config_history**: Configuration change history

#### Key Fields
- SLA deadlines and targets
- Escalation tracking
- Status history
- Alert thresholds
- Customer tier and priority

## SLA Engine

### How It Works
1. **Background Scheduler**: Runs every minute (configurable)
2. **Ticket Evaluation**: Checks all open tickets for SLA compliance
3. **Alert Generation**: Creates alerts when thresholds are met
4. **Escalation**: Automatically escalates based on configuration
5. **Notifications**: Sends Slack messages for alerts and breaches

### Alert Types
- **Warning**: ≤15% time remaining
- **Critical**: ≤5% time remaining  
- **Breached**: Time exceeded

### Escalation Workflow
1. Alert generated based on thresholds
2. Escalation level increased
3. Slack notification sent with ticket details
4. WebSocket event emitted for real-time updates
5. Alert marked as sent


### Health Checks
```http
GET /health
# Returns: {"status": "healthy", "service": "SLA Tracker API"}
```

# Run app
uvicorn main:app --host 0.0.0.0 --port 5678 --reload
# Build docker image 
# Remove if exists
docker rm -f fastapi-app || true
# Build
docker build --no-cache -t fastapi-app .

# Run container
docker run -d --name fastapi-app -p 5678:5678 fastapi-app

# check container
docker ps