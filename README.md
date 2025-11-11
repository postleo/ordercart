# OrderCart - AI-Powered Order Management System

![OrderCart](https://img.shields.io/badge/AI-Powered-aquamarine) ![Cloud Run](https://img.shields.io/badge/Cloud-Run-blue) ![Gemma AI](https://img.shields.io/badge/Gemma-AI-orange)

**OrderCart** is a complete, production-ready order management system powered by Google's Gemma AI and built on Google Cloud Platform. It features a multi-agent architecture with 3 AI agents working collaboratively to handle order intake, processing, exception resolution, and customer communications.

---

## 🎯 Project Overview

OrderCart solves the core pain points of manual order processing:
- ✅ Eliminates manual re-entry errors with AI-powered data extraction
- ✅ Reduces repetitive tasks with intelligent batch processing
- ✅ Prevents errors with automated validation and duplicate detection
- ✅ Streamlines exception handling with AI-suggested resolutions
- ✅ Automates customer communications with professional templates

---

## 🏗️ Architecture

OrderCart consists of **4 Cloud Run Services**:

```
┌─────────────────────────────────────────────────────────────────┐
│                     OrderCart Web App                           │
│           (HTML/CSS/JS Frontend + Flask Backend)                │
└────────────┬────────────────────────────────────────────────────┘
             │
             │ REST API
             │
    ┌────────┴─────────┬──────────────┬──────────────┐
    │                  │              │              │
┌───▼────┐      ┌──────▼─────┐  ┌────▼──────┐  ┌───▼──────┐
│ Agent 1│      │  Agent 2   │  │  Agent 3  │  │ Firestore│
│ Intake │◄────►│ Processor  │◄─►│ Exception │◄─┤ Database │
│Validator│      │            │  │  Handler  │  └──────────┘
└────┬───┘      └──────┬─────┘  └────┬──────┘
     │                 │              │
     └─────────────────┴──────────────┘
                 Pub/Sub Messaging
```

### Service Details

| Service | Port | Purpose | AI Model |
|---------|------|---------|----------|
| **Agent 1: Intake & Validation** | 8080 | Normalizes orders, validates data, detects duplicates | Gemma AI |
| **Agent 2: Fulfillment Processor** | 8081 | Suggests batches, manages workflow, bulk actions | Gemma AI |
| **Agent 3: Exception Handler** | 8082 | Analyzes exceptions, generates communications | Gemma AI |
| **OrderCart Web App** | 8000 | User interface and API gateway | - |

---

## ✨ Features

### 1. Automated Order Capture
- Multi-channel intake (manual, file upload)
- AI-powered data extraction and normalization
- Duplicate detection
- Real-time validation

### 2. Real-Time Order Status Tracking
- Visual Kanban board
- Status pipeline: `New → Validated → Processing → Packed → Shipped → Delivered`
- Drag-and-drop status updates
- Search and filtering

### 3. Error Detection & Smart Alerts
- Automated validation rules
- AI-categorized exceptions
- Priority flagging (High/Medium/Low)
- One-click resolution suggestions

### 4. Batch Processing
- AI-suggested batches (by region, urgency, product)
- Time savings estimates
- Bulk status updates
- Bulk label printing

### 5. Exception Handling Workflow
- AI-powered root cause analysis
- Guided resolution steps
- Communication template generation
- Resolution tracking

### 6. Customer Communication Templates
- Pre-built templates (confirmation, shipping, delivery, issues)
- AI-generated personalized messages
- Gmail SMTP integration
- Communication history logging

### 7. Analytics & Insights
- Real-time dashboard statistics
- Performance metrics
- Order flow analytics
- Success rate tracking

---

## 🤖 AI Features

### Gemma AI Integration
OrderCart uses Google's Gemma AI model for:

1. **Order Data Extraction**: Converts unstructured order data into structured JSON
2. **Batch Optimization**: Analyzes orders to suggest optimal batching strategies
3. **Exception Analysis**: Categorizes issues and suggests resolutions
4. **Communication Generation**: Creates professional, personalized customer messages

### Rule-Based Logic
Each agent combines AI with rule-based validation:
- Email/phone/address format validation
- Payment verification
- Inventory checks
- State transition validation

---

## 📊 Technology Stack

| Component | Technology |
|-----------|-----------|
| **Frontend** | HTML5, CSS3, Vanilla JavaScript |
| **Backend** | Python 3.11, Flask |
| **AI Model** | Google Gemma (via Generative AI API) |
| **Database** | Google Firestore (NoSQL) |
| **Messaging** | Google Cloud Pub/Sub |
| **Email** | Gmail SMTP |
| **Hosting** | Google Cloud Run (Serverless) |
| **Build** | Google Cloud Build |

---


## 🧪 Testing

### Test Order Submission
```bash
curl -X POST https://YOUR_AGENT1_URL/api/intake \
  -H "Content-Type: application/json" \
  -d '{
    "customer_name": "Test User",
    "email": "test@example.com",
    "phone": "1234567890",
    "address": "123 Main St",
    "city": "New York",
    "state": "NY",
    "zip": "10001",
    "items": [{
      "sku": "TEST-001",
      "name": "Test Product",
      "quantity": 1,
      "price": 50.00
    }],
    "total": 50.00
  }'
```

### Test Exception Creation
Submit an order with invalid email to trigger exception handling:
```bash
# Submit order with invalid email
{
  "email": "notanemail"
}
```

---

## 📚 Documentation

- **[Agent 1 README](./agent-intake-validator/README.md)** - Intake Agent docs
- **[Agent 2 README](./agent-fulfillment-processor/README.md)** - Processor Agent docs
- **[Agent 3 README](./agent-exception-handler/README.md)** - Exception Agent docs
- **[Web App README](./ordercart-webapp/README.md)** - Web application docs



The script will skip completed steps and continue from where it stopped.

### View Deployed Resources
```bash
cat .deployed_resources.txt
```

---

## 🚨 Troubleshooting

### Common Issues

**Problem:** "Permission Denied" during deployment
**Solution:** Enable billing and ensure APIs are enabled

**Problem:** Services won't communicate
**Solution:** Verify environment variables contain correct URLs

**Problem:** Emails not sending
**Solution:** Check Gmail App Password and 2-Step Verification

**Problem:** Firestore "Permission Denied"
**Solution:** Grant IAM role to service account

See [deployment.md](./deployment.md#troubleshooting) for detailed troubleshooting.

---

## 🛠️ Development

### Local Development

1. **Install Dependencies**
```bash
cd agent-intake-validator
pip install -r requirements.txt
```

2. **Set Environment Variables**
```bash
export GOOGLE_CLOUD_PROJECT=your-project-id
export GOOGLE_API_KEY=your-api-key
```

3. **Run Locally**
```bash
python main.py
```

4. **Test Locally**
```bash
curl http://localhost:8080/health
```

---

## 🎯 Roadmap

- [ ] Firebase Authentication integration
- [ ] Photo capture for order intake
- [ ] Voice input for order creation
- [ ] Advanced analytics dashboard
- [ ] Inventory management integration
- [ ] Multi-language support
- [ ] Mobile app (React Native)
- [ ] Webhook integrations


---

## 👏 Acknowledgments

- **Google Cloud Platform** - Infrastructure
- **Google Gemma AI** - AI capabilities
- **Font Awesome** - Icons
- **Nunito Font** - Typography

---

**Built with ❤️ using Google Cloud and Gemma AI**

**OrderCart** - Streamline your order management with AI
