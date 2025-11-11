# ADK-001: Intake & Validation Agent

## Overview
System gateway that receives raw order data from multiple channels, normalizes formats using Gemma AI, applies validation rules, and routes orders to the appropriate processing queue.

## Features
- **AI-Powered Normalization**: Uses Gemma AI to extract and normalize unstructured order data
- **Rule-Based Validation**: Validates email, phone, address, payment, and item data
- **Duplicate Detection**: Checks for duplicate orders in Firestore
- **Event Publishing**: Publishes validated/exception orders to Pub/Sub
- **Batch Processing**: Supports bulk order intake

## Architecture
- **Runtime**: Python 3.11+ on Cloud Run
- **AI Model**: Google Gemma (via Generative AI API)
- **Database**: Firestore
- **Messaging**: Cloud Pub/Sub
- **API**: REST (Flask)

## Endpoints

### `POST /api/intake`
Intake single order

**Request:**
```json
{
  "customer_name": "John Doe",
  "email": "john@example.com",
  "phone": "+1234567890",
  "address": "123 Main St",
  "city": "New York",
  "state": "NY",
  "zip": "10001",
  "items": [
    {
      "sku": "MUG-RED-001",
      "name": "Red Mug",
      "quantity": 10,
      "price": 45.00
    }
  ],
  "payment_method": "card",
  "total": 450.00
}
```

**Response:**
```json
{
  "success": true,
  "order_id": "ORD-20231125120045",
  "status": "validated",
  "validation": {
    "passed": true,
    "errors": [],
    "warnings": []
  }
}
```

### `POST /api/intake/batch`
Intake multiple orders

### `GET /health`
Health check endpoint

## Environment Variables
- `GOOGLE_CLOUD_PROJECT`: GCP project ID
- `GOOGLE_API_KEY`: Gemma AI API key
- `PORT`: Server port (default: 8080)

## Deployment
See main `deployment.md` for deployment instructions.
