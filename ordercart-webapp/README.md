# OrderCart Web Application

## Overview
Frontend interface and API gateway for the OrderCart system. Provides a beautiful, responsive UI for order management and coordinates communication with all three AI agents.

## Features
- **Multi-Channel Order Capture**: Manual entry, file upload, voice, and photo capture
- **Real-Time Dashboard**: Live statistics and order tracking
- **Visual Order Board**: Kanban-style workflow management
- **Exception Management**: AI-powered problem resolution
- **Batch Processing**: Optimized batch suggestions and bulk actions
- **Customer Communications**: Email management and templates
- **Analytics**: Performance metrics and insights
- **Dark Mode**: Toggle between light and dark themes

## Architecture
- **Frontend**: HTML5, CSS3, Vanilla JavaScript
- **Backend**: Python Flask
- **Database**: Firestore (via agents)
- **Integrations**: REST APIs to 3 AI agents

## Tech Stack
- **Colors**: Aquamarine (#7FFFD4) and Oxford Blue (#002147)
- **Font**: Nunito
- **Icons**: Font Awesome
- **Runtime**: Python 3.11+ on Cloud Run

## Endpoints

### Web Pages
- `GET /` - Main application interface

### API Endpoints
All API endpoints proxy to the appropriate AI agent:

- `POST /api/orders/intake` - Submit order (→ Agent 1)
- `GET /api/orders` - List orders (→ Firestore)
- `PUT /api/orders/{id}/status` - Update status (→ Agent 2)
- `GET /api/batches/suggest` - Get batch suggestions (→ Agent 2)
- `POST /api/batches/create` - Create batch (→ Agent 2)
- `GET /api/exceptions` - List exceptions (→ Agent 3)
- `POST /api/exceptions/{id}/analyze` - Analyze exception (→ Agent 3)
- `POST /api/communications/send` - Send communication (→ Agent 3)
- `GET /api/stats/dashboard` - Dashboard statistics

## Environment Variables
- `GOOGLE_CLOUD_PROJECT`: GCP project ID
- `AGENT_INTAKE_URL`: URL of Intake Agent (ADK-001)
- `AGENT_PROCESSOR_URL`: URL of Processor Agent (ADK-002)
- `AGENT_EXCEPTION_URL`: URL of Exception Agent (ADK-003)
- `PORT`: Server port (default: 8000)

## Deployment
See main `deployment.md` for deployment instructions.
