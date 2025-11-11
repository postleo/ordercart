# ADK-003: Exception Handler & Communication Agent

## Overview
Problem solver that analyzes exceptions using Gemma AI, suggests resolutions, generates professional customer communications, and provides guided workflows for issue resolution.

## Features
- **AI Exception Analysis**: Uses Gemma AI to categorize and analyze order exceptions
- **Resolution Suggestions**: Provides actionable steps to resolve issues
- **Communication Generation**: Creates personalized, professional customer messages
- **Email Integration**: Sends emails via Gmail SMTP
- **Communication Logging**: Tracks all customer communications in Firestore

## Architecture
- **Runtime**: Python 3.11+ on Cloud Run
- **AI Model**: Google Gemma (via Generative AI API)
- **Database**: Firestore
- **Email**: Gmail SMTP
- **API**: REST (Flask)

## Exception Categories
- **Payment**: Payment processing failures
- **Address**: Invalid or incomplete shipping addresses
- **Inventory**: Out of stock or SKU issues
- **Data**: Invalid customer information
- **Other**: General validation failures

## Communication Types
- Order Confirmation
- Shipping Notification
- Delivery Confirmation
- Payment Issue Alert
- Custom AI-Generated Messages

## Endpoints

### `POST /api/exceptions/{order_id}/analyze`
Analyze exception and suggest resolution

### `POST /api/exceptions/{order_id}/resolve`
Mark exception as resolved

### `POST /api/communications/send`
Send customer communication

### `POST /api/communications/generate`
Generate message preview without sending

### `GET /api/exceptions`
List all exception orders

### `GET /health`
Health check

## Environment Variables
- `GOOGLE_CLOUD_PROJECT`: GCP project ID
- `GOOGLE_API_KEY`: Gemma AI API key
- `GMAIL_USER`: Gmail address for sending emails
- `GMAIL_APP_PASSWORD`: Gmail app-specific password
- `PORT`: Server port (default: 8082)

## Gmail Setup
1. Enable 2-Factor Authentication on Gmail account
2. Generate App Password: Google Account → Security → 2-Step Verification → App passwords
3. Set `GMAIL_USER` and `GMAIL_APP_PASSWORD` environment variables

## Deployment
See main `deployment.md` for deployment instructions.
