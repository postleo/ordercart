"""
OrderCart - ADK-001: Intake & Validation Agent
Cloud Run Service for order intake, normalization, and validation
Architecture: REST API → Gemma AI → Firestore → Pub/Sub
"""

import os
import json
import logging
import re
from datetime import datetime
from typing import Dict, Any, List, Optional
from flask import Flask, request, jsonify
from flask_cors import CORS
from google.cloud import firestore
from google.cloud import pubsub_v1
import google.generativeai as genai

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize Firestore
db = firestore.Client()

# Initialize Pub/Sub
publisher = pubsub_v1.PublisherClient()
project_id = os.getenv('GOOGLE_CLOUD_PROJECT', 'ordercart-project')
topic_validated = f'projects/{project_id}/topics/order-validated'
topic_exception = f'projects/{project_id}/topics/order-exception'

# Configure Gemma AI
api_key = os.getenv('GOOGLE_API_KEY', '')
if api_key:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
else:
    logger.warning("GOOGLE_API_KEY not set - AI features disabled")
    model = None

# Validation Rules
VALIDATION_RULES = {
    'email_pattern': r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
    'phone_pattern': r'^\+?1?\d{9,15}$',
    'zip_pattern': r'^\d{5}(-\d{4})?$',
    'min_order_value': 0,
    'max_order_value': 10000,
}


class OrderNormalizer:
    """Uses Gemma AI and rule-based logic for order data normalization"""

    def __init__(self):
        self.model = model

    def normalize_with_ai(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Use Gemma AI to extract and normalize unstructured order data"""
        if not self.model:
            return self.normalize_structured(raw_data)

        try:
            # Create prompt for Gemma AI
            prompt = f"""
Extract and normalize the following order data into a structured JSON format.

Raw Order Data:
{json.dumps(raw_data, indent=2)}

Please extract and return ONLY a JSON object with this exact structure:
{{
  "customer_name": "full name",
  "customer_email": "email@example.com",
  "customer_phone": "phone number",
  "street_address": "full street address",
  "city": "city name",
  "state": "state code",
  "zip_code": "postal code",
  "items": [
    {{
      "sku": "product SKU",
      "name": "product name",
      "quantity": number,
      "price": number
    }}
  ],
  "payment_method": "payment method",
  "payment_status": "pending or paid",
  "total_amount": number
}}

Extract all available information. Use null for missing fields. Return ONLY the JSON, no explanation.
"""

            response = self.model.generate_content(prompt)
            result_text = response.text.strip()

            # Extract JSON from response
            if '```json' in result_text:
                result_text = result_text.split('```json')[1].split('```')[0].strip()
            elif '```' in result_text:
                result_text = result_text.split('```')[1].split('```')[0].strip()

            normalized = json.loads(result_text)
            logger.info("AI normalization successful")
            return normalized

        except Exception as e:
            logger.error(f"AI normalization failed: {str(e)}")
            return self.normalize_structured(raw_data)

    def normalize_structured(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback: Rule-based normalization for structured data"""
        return {
            'customer_name': raw_data.get('customer_name') or raw_data.get('name') or raw_data.get('customerName'),
            'customer_email': raw_data.get('email') or raw_data.get('customer_email') or raw_data.get('customerEmail'),
            'customer_phone': raw_data.get('phone') or raw_data.get('customer_phone') or raw_data.get('tel'),
            'street_address': raw_data.get('address') or raw_data.get('street') or raw_data.get('street_address'),
            'city': raw_data.get('city'),
            'state': raw_data.get('state'),
            'zip_code': raw_data.get('zip') or raw_data.get('zip_code') or raw_data.get('postal_code'),
            'items': self._normalize_items(raw_data.get('items', []) or raw_data.get('products', [])),
            'payment_method': raw_data.get('payment_method') or raw_data.get('paymentMethod', 'card'),
            'payment_status': raw_data.get('payment_status') or raw_data.get('paymentStatus', 'pending'),
            'total_amount': float(raw_data.get('amount') or raw_data.get('total') or 0),
        }

    def _normalize_items(self, items: List[Dict]) -> List[Dict]:
        """Normalize product items"""
        normalized = []
        for item in items:
            normalized.append({
                'sku': item.get('sku') or item.get('id') or item.get('product_id'),
                'name': item.get('name') or item.get('product_name') or item.get('description'),
                'quantity': int(item.get('quantity') or item.get('qty') or 1),
                'price': float(item.get('price') or item.get('unit_price') or 0),
            })
        return normalized


class OrderValidator:
    """Rule-based validation engine"""

    def __init__(self):
        self.errors = []
        self.warnings = []

    def validate_order(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply all validation rules"""
        self.errors = []
        self.warnings = []

        # Validate customer info
        self._validate_email(order_data.get('customer_email'))
        self._validate_phone(order_data.get('customer_phone'))
        self._validate_name(order_data.get('customer_name'))

        # Validate address
        self._validate_address(order_data)

        # Validate items
        self._validate_items(order_data.get('items', []))

        # Validate payment
        self._validate_payment(order_data)

        # Check for duplicates
        if self._check_duplicate(order_data):
            self.errors.append("Potential duplicate order detected")

        return {
            'passed': len(self.errors) == 0,
            'errors': self.errors,
            'warnings': self.warnings
        }

    def _validate_email(self, email: Optional[str]):
        """Validate email format"""
        if not email:
            self.errors.append("Customer email is required")
        elif not re.match(VALIDATION_RULES['email_pattern'], email):
            self.errors.append(f"Invalid email format: {email}")

    def _validate_phone(self, phone: Optional[str]):
        """Validate phone number"""
        if not phone:
            self.warnings.append("Phone number is missing")
        else:
            phone_clean = re.sub(r'[\s\-\(\)]', '', phone)
            if not re.match(VALIDATION_RULES['phone_pattern'], phone_clean):
                self.warnings.append(f"Phone format may be invalid: {phone}")

    def _validate_name(self, name: Optional[str]):
        """Validate customer name"""
        if not name:
            self.errors.append("Customer name is required")
        elif len(name) < 2:
            self.errors.append("Customer name is too short")

    def _validate_address(self, order_data: Dict[str, Any]):
        """Validate address fields"""
        required = ['street_address', 'city', 'state', 'zip_code']
        for field in required:
            if not order_data.get(field):
                self.errors.append(f"Address {field.replace('_', ' ')} is required")

        # Validate ZIP code format
        zip_code = order_data.get('zip_code')
        if zip_code and not re.match(VALIDATION_RULES['zip_pattern'], zip_code):
            self.errors.append(f"Invalid ZIP code format: {zip_code}")

    def _validate_items(self, items: List[Dict]):
        """Validate order items"""
        if not items:
            self.errors.append("Order must contain at least one item")
            return

        for idx, item in enumerate(items):
            if not item.get('sku'):
                self.errors.append(f"Item {idx + 1}: SKU is required")
            if not item.get('name'):
                self.errors.append(f"Item {idx + 1}: Product name is required")
            if item.get('quantity', 0) <= 0:
                self.errors.append(f"Item {idx + 1}: Invalid quantity")
            if item.get('price', 0) <= 0:
                self.errors.append(f"Item {idx + 1}: Invalid price")

    def _validate_payment(self, order_data: Dict[str, Any]):
        """Validate payment information"""
        amount = order_data.get('total_amount', 0)

        if amount < VALIDATION_RULES['min_order_value']:
            self.errors.append(f"Order amount too low: ${amount}")

        if amount > VALIDATION_RULES['max_order_value']:
            self.warnings.append(f"High-value order: ${amount} - requires review")

        if order_data.get('payment_status') == 'failed':
            self.errors.append("Payment has failed")

    def _check_duplicate(self, order_data: Dict[str, Any]) -> bool:
        """Check for duplicate orders in Firestore"""
        try:
            email = order_data.get('customer_email')
            amount = order_data.get('total_amount', 0)

            if not email:
                return False

            # Query recent orders with same email and amount
            orders_ref = db.collection('orders')
            query = orders_ref.where('customer.email', '==', email) \
                              .where('payment.amount', '==', amount) \
                              .limit(5)

            docs = query.stream()
            for doc in docs:
                existing = doc.to_dict()
                # Check if created within last 24 hours
                created_at = existing.get('created_at', '')
                if created_at:
                    try:
                        created_time = datetime.fromisoformat(created_at)
                        time_diff = (datetime.now() - created_time).total_seconds()
                        if time_diff < 86400:  # 24 hours
                            return True
                    except:
                        pass

            return False

        except Exception as e:
            logger.error(f"Error checking duplicates: {str(e)}")
            return False


def create_order_object(normalized_data: Dict[str, Any], validation_result: Dict[str, Any]) -> Dict[str, Any]:
    """Create standardized Order object"""
    order_id = f"ORD-{datetime.now().strftime('%Y%m%d%H%M%S%f')[:17]}"

    status = 'validated' if validation_result['passed'] else 'exception'

    order = {
        'order_id': order_id,
        'customer': {
            'name': normalized_data.get('customer_name'),
            'email': normalized_data.get('customer_email'),
            'phone': normalized_data.get('customer_phone'),
        },
        'address': {
            'street': normalized_data.get('street_address'),
            'city': normalized_data.get('city'),
            'state': normalized_data.get('state'),
            'zip_code': normalized_data.get('zip_code'),
            'country': 'USA',
        },
        'items': normalized_data.get('items', []),
        'payment': {
            'method': normalized_data.get('payment_method', 'card'),
            'status': normalized_data.get('payment_status', 'pending'),
            'amount': normalized_data.get('total_amount', 0),
        },
        'status': status,
        'validation': validation_result,
        'created_at': datetime.now().isoformat(),
        'updated_at': datetime.now().isoformat(),
        'agent_id': 'ADK-001-IntakeValidator',
    }

    return order


def save_to_firestore(order: Dict[str, Any]) -> str:
    """Save order to Firestore"""
    try:
        doc_ref = db.collection('orders').document(order['order_id'])
        doc_ref.set(order)
        logger.info(f"Order saved to Firestore: {order['order_id']}")
        return order['order_id']
    except Exception as e:
        logger.error(f"Firestore save error: {str(e)}")
        raise


def publish_to_pubsub(order_id: str, status: str):
    """Publish order event to Pub/Sub"""
    try:
        topic = topic_validated if status == 'validated' else topic_exception

        message = json.dumps({
            'order_id': order_id,
            'status': status,
            'timestamp': datetime.now().isoformat(),
            'agent': 'ADK-001'
        })

        future = publisher.publish(topic, message.encode('utf-8'))
        message_id = future.result(timeout=10)
        logger.info(f"Published to Pub/Sub: {message_id}")
    except Exception as e:
        logger.error(f"Pub/Sub publish error: {str(e)}")


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for Cloud Run"""
    return jsonify({
        'status': 'healthy',
        'agent': 'ADK-001-IntakeValidator',
        'timestamp': datetime.now().isoformat()
    })


@app.route('/api/intake', methods=['POST'])
def intake_order():
    """
    Main order intake endpoint
    Accepts raw order data, normalizes with AI, validates, and routes to next agent
    """
    try:
        raw_data = request.get_json()
        if not raw_data:
            return jsonify({'error': 'No data provided'}), 400

        logger.info(f"Received intake request: {json.dumps(raw_data)[:200]}")

        # Step 1: Normalize with AI
        normalizer = OrderNormalizer()
        normalized_data = normalizer.normalize_with_ai(raw_data)

        # Step 2: Validate with rules
        validator = OrderValidator()
        validation_result = validator.validate_order(normalized_data)

        # Step 3: Create Order object
        order = create_order_object(normalized_data, validation_result)

        # Step 4: Save to Firestore
        order_id = save_to_firestore(order)

        # Step 5: Publish to Pub/Sub
        publish_to_pubsub(order_id, order['status'])

        # Return response
        return jsonify({
            'success': True,
            'order_id': order_id,
            'status': order['status'],
            'validation': validation_result
        }), 200 if order['status'] == 'validated' else 202

    except Exception as e:
        logger.error(f"Intake error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/intake/batch', methods=['POST'])
def intake_batch():
    """Batch order intake endpoint"""
    try:
        data = request.get_json()
        orders = data.get('orders', [])

        if not orders:
            return jsonify({'error': 'No orders provided'}), 400

        logger.info(f"Batch intake: {len(orders)} orders")

        results = []
        normalizer = OrderNormalizer()
        validator = OrderValidator()

        for idx, raw_order in enumerate(orders):
            try:
                normalized = normalizer.normalize_with_ai(raw_order)
                validation = validator.validate_order(normalized)
                order = create_order_object(normalized, validation)
                order_id = save_to_firestore(order)
                publish_to_pubsub(order_id, order['status'])

                results.append({
                    'index': idx,
                    'success': True,
                    'order_id': order_id,
                    'status': order['status']
                })
            except Exception as e:
                logger.error(f"Batch item {idx} error: {str(e)}")
                results.append({
                    'index': idx,
                    'success': False,
                    'error': str(e)
                })

        return jsonify({
            'success': True,
            'total': len(orders),
            'results': results
        }), 200

    except Exception as e:
        logger.error(f"Batch error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


if __name__ == '__main__':
    port = int(os.getenv('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
