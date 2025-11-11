# ADK-002: Fulfillment Processor Agent

## Overview
Workflow manager that handles validated orders, suggests optimal batches using AI clustering algorithms, executes bulk actions, and manages order status transitions through the fulfillment pipeline.

## Features
- **AI Batch Suggestions**: Analyzes orders and suggests optimal batches by region, urgency, and product
- **Status Management**: Validates and executes order status transitions
- **Bulk Operations**: Updates multiple orders simultaneously
- **Communication Triggers**: Requests Agent 3 to send customer notifications

## Architecture
- **Runtime**: Python 3.11+ on Cloud Run
- **AI Model**: Google Gemma (via Generative AI API)
- **Database**: Firestore
- **Messaging**: Cloud Pub/Sub
- **API**: REST (Flask)

## Batch Strategies
1. **Region-Based**: Groups orders by state/region for shipping efficiency
2. **Urgency-Based**: Groups orders by deadline and age
3. **Product-Based**: Groups orders containing similar products

## Status Flow
```
validated → processing → paid → picking → packed → shipped → delivered
                ↓
            exception
```

## Endpoints

### `GET /api/batches/suggest`
Get AI-powered batch suggestions

### `POST /api/batches/create`
Create a new batch

### `GET /api/batches/{batch_id}`
Get batch details

### `PUT /api/orders/{order_id}/status`
Update single order status

### `POST /api/batches/{batch_id}/update-status`
Bulk update status for batch orders

### `GET /api/orders`
List orders with filters

### `GET /health`
Health check

## Environment Variables
- `GOOGLE_CLOUD_PROJECT`: GCP project ID
- `GOOGLE_API_KEY`: Gemma AI API key
- `PORT`: Server port (default: 8081)

## Deployment
See main `deployment.md` for deployment instructions.
