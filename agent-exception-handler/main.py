"""
OrderCart - ADK-003: Exception Handler & Communication Agent
Cloud Run Service for exception analysis, resolution, and customer communications
Architecture: Pub/Sub Listener → Gemma AI Analysis → Gmail SMTP → Firestore
"""

import os
import json
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
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
subscriber = pubsub_v1.SubscriberClient()
project_id = os.getenv('GOOGLE_CLOUD_PROJECT', 'ordercart-project')
subscription_exception = f'projects/{project_id}/subscriptions/exception-sub'
subscription_communication = f'projects/{project_id}/subscriptions/communication-sub'

# Gmail SMTP Configuration
GMAIL_SMTP_SERVER = 'smtp.gmail.com'
GMAIL_SMTP_PORT = 587
GMAIL_USER = os.getenv('GMAIL_USER', '')
GMAIL_APP_PASSWORD = os.getenv('GMAIL_APP_PASSWORD', '')

# Configure Gemma AI
api_key = os.getenv('GOOGLE_API_KEY', '')
if api_key:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
else:
    logger.warning("GOOGLE_API_KEY not set - AI features disabled")
    model = None

# Communication Templates
EMAIL_TEMPLATES = {
    'order_confirmation': {
        'subject': 'Order Confirmation - {order_id}',
        'template': """
Dear {customer_name},

Thank you for your order! We're pleased to confirm that we've received your order.

Order Details:
Order Number: {order_id}
Order Date: {order_date}
Total Amount: ${total_amount}

Items:
{items_list}

Shipping Address:
{shipping_address}

We'll notify you once your order ships.

Best regards,
OrderCart Team
"""
    },
    'shipped': {
        'subject': 'Your Order Has Shipped - {order_id}',
        'template': """
Dear {customer_name},

Great news! Your order has been shipped and is on its way to you.

Order Number: {order_id}
Shipping Date: {ship_date}
Tracking Number: {tracking_number}

Estimated Delivery: {estimated_delivery}

You can track your package using the tracking number above.

Best regards,
OrderCart Team
"""
    },
    'delivered': {
        'subject': 'Order Delivered - {order_id}',
        'template': """
Dear {customer_name},

Your order has been successfully delivered!

Order Number: {order_id}
Delivery Date: {delivery_date}

We hope you're satisfied with your purchase. If you have any questions or concerns, please don't hesitate to contact us.

Thank you for choosing OrderCart!

Best regards,
OrderCart Team
"""
    },
    'payment_issue': {
        'subject': 'Payment Issue - Action Required - {order_id}',
        'template': """
Dear {customer_name},

We encountered an issue processing your payment for order {order_id}.

Issue: {issue_description}

To complete your order, please:
{resolution_steps}

If you have any questions, please reply to this email or contact our support team.

Best regards,
OrderCart Team
"""
    },
}


class ExceptionAnalyzer:
    """AI-powered exception analysis and resolution engine"""

    def __init__(self):
        self.model = model

    def analyze_exception(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze order exception and suggest resolution"""
        try:
            validation = order.get('validation', {})
            errors = validation.get('errors', [])
            warnings = validation.get('warnings', [])

            if not self.model:
                return self._rule_based_analysis(errors, warnings)

            # Use Gemma AI for analysis
            prompt = f"""
Analyze this order exception and provide resolution guidance.

Order ID: {order.get('order_id')}
Customer: {order.get('customer', {}).get('name')}
Errors: {json.dumps(errors)}
Warnings: {json.dumps(warnings)}

Please provide:
1. Category: (payment, address, inventory, data, or other)
2. Priority: (high, medium, or low)
3. Root Cause: Brief explanation in plain English
4. Resolution Steps: Clear, actionable steps to fix the issue
5. Customer Message: Professional message template to send to customer

Return ONLY a JSON object with this structure:
{{
  "category": "category name",
  "priority": "high|medium|low",
  "root_cause": "plain English explanation",
  "resolution_steps": ["step 1", "step 2", "step 3"],
  "customer_message": "professional message text",
  "suggested_action": "specific action to take"
}}
"""

            response = self.model.generate_content(prompt)
            result_text = response.text.strip()

            # Extract JSON
            if '```json' in result_text:
                result_text = result_text.split('```json')[1].split('```')[0].strip()
            elif '```' in result_text:
                result_text = result_text.split('```')[1].split('```')[0].strip()

            analysis = json.loads(result_text)
            logger.info(f"AI exception analysis completed: {analysis.get('category')}")
            return analysis

        except Exception as e:
            logger.error(f"AI analysis error: {str(e)}")
            return self._rule_based_analysis(errors, warnings)

    def _rule_based_analysis(self, errors: List[str], warnings: List[str]) -> Dict[str, Any]:
        """Fallback rule-based exception analysis"""
        error_text = ' '.join(errors).lower()

        # Categorize based on keywords
        if 'email' in error_text or 'phone' in error_text:
            category = 'data'
            priority = 'medium'
            root_cause = 'Customer contact information is invalid or missing'
            resolution_steps = [
                'Verify email address format',
                'Contact customer via alternate method',
                'Update customer information'
            ]
            customer_message = 'We need to verify your contact information to process your order.'

        elif 'address' in error_text or 'zip' in error_text:
            category = 'address'
            priority = 'high'
            root_cause = 'Shipping address is incomplete or invalid'
            resolution_steps = [
                'Verify address with USPS database',
                'Contact customer for clarification',
                'Update address in system'
            ]
            customer_message = 'We need to confirm your shipping address to ensure successful delivery.'

        elif 'payment' in error_text:
            category = 'payment'
            priority = 'high'
            root_cause = 'Payment processing failed'
            resolution_steps = [
                'Contact customer for alternate payment method',
                'Retry payment processing',
                'Update payment information'
            ]
            customer_message = 'We encountered an issue processing your payment. Please provide an alternate payment method.'

        elif 'duplicate' in error_text:
            category = 'other'
            priority = 'medium'
            root_cause = 'Potential duplicate order detected'
            resolution_steps = [
                'Review order history',
                'Contact customer to confirm',
                'Cancel duplicate if confirmed'
            ]
            customer_message = 'We noticed a similar order was recently placed. Please confirm if this is a new order.'

        else:
            category = 'other'
            priority = 'low'
            root_cause = 'Order validation failed'
            resolution_steps = [
                'Review all order details',
                'Contact customer for missing information',
                'Manually correct and revalidate'
            ]
            customer_message = 'We need additional information to process your order.'

        return {
            'category': category,
            'priority': priority,
            'root_cause': root_cause,
            'resolution_steps': resolution_steps,
            'customer_message': customer_message,
            'suggested_action': resolution_steps[0] if resolution_steps else 'Review manually'
        }


class CommunicationManager:
    """Handles customer communications via email"""

    def __init__(self):
        self.model = model

    def generate_message(self, order: Dict[str, Any], event: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Generate personalized customer message"""
        try:
            if event in EMAIL_TEMPLATES:
                return self._generate_from_template(order, event, context or {})
            else:
                return self._generate_with_ai(order, event, context or {})

        except Exception as e:
            logger.error(f"Message generation error: {str(e)}")
            return {
                'subject': f'Order Update - {order.get("order_id")}',
                'body': f'Your order {order.get("order_id")} has been updated.'
            }

    def _generate_from_template(self, order: Dict[str, Any], event: str, context: Dict) -> Dict[str, Any]:
        """Generate message from predefined template"""
        template_data = EMAIL_TEMPLATES[event]
        subject = template_data['subject']
        body = template_data['template']

        # Prepare template variables
        customer_name = order.get('customer', {}).get('name', 'Customer')
        order_id = order.get('order_id', 'N/A')
        order_date = order.get('created_at', '')[:10]
        total_amount = order.get('payment', {}).get('amount', 0)

        # Format items list
        items = order.get('items', [])
        items_list = '\n'.join([f"- {item.get('name')} x{item.get('quantity')} - ${item.get('price', 0):.2f}" for item in items])

        # Format address
        addr = order.get('address', {})
        shipping_address = f"{addr.get('street', '')}\n{addr.get('city', '')}, {addr.get('state', '')} {addr.get('zip_code', '')}"

        # Fill template
        subject = subject.format(order_id=order_id, **context)
        body = body.format(
            customer_name=customer_name,
            order_id=order_id,
            order_date=order_date,
            total_amount=f"{total_amount:.2f}",
            items_list=items_list,
            shipping_address=shipping_address,
            ship_date=datetime.now().strftime('%Y-%m-%d'),
            delivery_date=datetime.now().strftime('%Y-%m-%d'),
            tracking_number=context.get('tracking_number', 'TRK' + order_id),
            estimated_delivery=context.get('estimated_delivery', 'Within 3-5 business days'),
            issue_description=context.get('issue_description', 'Payment processing issue'),
            resolution_steps=context.get('resolution_steps', '1. Contact support'),
        )

        return {'subject': subject, 'body': body}

    def _generate_with_ai(self, order: Dict[str, Any], event: str, context: Dict) -> Dict[str, Any]:
        """Generate message using Gemma AI"""
        if not self.model:
            return self._generate_from_template(order, 'order_confirmation', context)

        try:
            customer_name = order.get('customer', {}).get('name', 'Customer')
            order_id = order.get('order_id', 'N/A')

            prompt = f"""
Generate a professional, friendly customer email for the following situation:

Event: {event}
Customer Name: {customer_name}
Order ID: {order_id}
Context: {json.dumps(context)}

The email should be:
- Professional and friendly
- Clear and concise
- Action-oriented if needed
- Reassuring

Return ONLY a JSON object:
{{
  "subject": "email subject line",
  "body": "email body text"
}}
"""

            response = self.model.generate_content(prompt)
            result_text = response.text.strip()

            if '```json' in result_text:
                result_text = result_text.split('```json')[1].split('```')[0].strip()
            elif '```' in result_text:
                result_text = result_text.split('```')[1].split('```')[0].strip()

            message = json.loads(result_text)
            return message

        except Exception as e:
            logger.error(f"AI message generation error: {str(e)}")
            return self._generate_from_template(order, 'order_confirmation', context)

    def send_email(self, to_email: str, subject: str, body: str) -> bool:
        """Send email via Gmail SMTP"""
        if not GMAIL_USER or not GMAIL_APP_PASSWORD:
            logger.warning("Gmail credentials not configured - email not sent")
            logger.info(f"Would send email to {to_email}: {subject}")
            return False

        try:
            msg = MIMEMultipart()
            msg['From'] = GMAIL_USER
            msg['To'] = to_email
            msg['Subject'] = subject

            msg.attach(MIMEText(body, 'plain'))

            server = smtplib.SMTP(GMAIL_SMTP_SERVER, GMAIL_SMTP_PORT)
            server.starttls()
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            server.send_message(msg)
            server.quit()

            logger.info(f"Email sent to {to_email}: {subject}")
            return True

        except Exception as e:
            logger.error(f"Email send error: {str(e)}")
            return False

    def log_communication(self, order_id: str, communication_type: str, recipient: str, subject: str, status: str):
        """Log communication to Firestore"""
        try:
            comm_doc = {
                'order_id': order_id,
                'type': communication_type,
                'recipient': recipient,
                'subject': subject,
                'status': status,
                'sent_at': datetime.now().isoformat(),
                'agent_id': 'ADK-003',
            }

            db.collection('communications').add(comm_doc)
            logger.info(f"Communication logged: {order_id}")

        except Exception as e:
            logger.error(f"Communication log error: {str(e)}")


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'agent': 'ADK-003-ExceptionHandler',
        'timestamp': datetime.now().isoformat()
    })


@app.route('/api/exceptions/<order_id>/analyze', methods=['POST'])
def analyze_exception(order_id):
    """Analyze exception and suggest resolution"""
    try:
        # Get order from Firestore
        doc = db.collection('orders').document(order_id).get()
        if not doc.exists:
            return jsonify({'error': 'Order not found'}), 404

        order = doc.to_dict()

        # Analyze exception
        analyzer = ExceptionAnalyzer()
        analysis = analyzer.analyze_exception(order)

        # Save analysis to Firestore
        db.collection('orders').document(order_id).update({
            'exception_analysis': analysis,
            'analyzed_at': datetime.now().isoformat(),
        })

        return jsonify({
            'success': True,
            'order_id': order_id,
            'analysis': analysis
        }), 200

    except Exception as e:
        logger.error(f"Exception analysis error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/exceptions/<order_id>/resolve', methods=['POST'])
def resolve_exception(order_id):
    """Mark exception as resolved and route back to processing"""
    try:
        data = request.get_json()
        resolution_notes = data.get('notes', '')

        # Update order status
        db.collection('orders').document(order_id).update({
            'status': 'validated',
            'exception_resolved': True,
            'resolution_notes': resolution_notes,
            'resolved_at': datetime.now().isoformat(),
            'resolved_by': 'ADK-003',
        })

        logger.info(f"Exception resolved: {order_id}")

        return jsonify({
            'success': True,
            'order_id': order_id,
            'status': 'validated'
        }), 200

    except Exception as e:
        logger.error(f"Resolution error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/communications/send', methods=['POST'])
def send_communication():
    """Send customer communication"""
    try:
        data = request.get_json()
        order_id = data.get('order_id')
        event = data.get('event', 'order_confirmation')
        context = data.get('context', {})

        # Get order
        doc = db.collection('orders').document(order_id).get()
        if not doc.exists:
            return jsonify({'error': 'Order not found'}), 404

        order = doc.to_dict()
        customer_email = order.get('customer', {}).get('email')

        if not customer_email:
            return jsonify({'error': 'Customer email not found'}), 400

        # Generate message
        comm_manager = CommunicationManager()
        message = comm_manager.generate_message(order, event, context)

        # Send email
        sent = comm_manager.send_email(customer_email, message['subject'], message['body'])

        # Log communication
        comm_manager.log_communication(
            order_id, event, customer_email, message['subject'],
            'sent' if sent else 'failed'
        )

        return jsonify({
            'success': True,
            'order_id': order_id,
            'sent': sent,
            'message': message
        }), 200

    except Exception as e:
        logger.error(f"Communication send error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/communications/generate', methods=['POST'])
def generate_communication():
    """Generate communication without sending"""
    try:
        data = request.get_json()
        order_id = data.get('order_id')
        event = data.get('event', 'order_confirmation')
        context = data.get('context', {})

        # Get order
        doc = db.collection('orders').document(order_id).get()
        if not doc.exists:
            return jsonify({'error': 'Order not found'}), 404

        order = doc.to_dict()

        # Generate message
        comm_manager = CommunicationManager()
        message = comm_manager.generate_message(order, event, context)

        return jsonify({
            'success': True,
            'order_id': order_id,
            'message': message
        }), 200

    except Exception as e:
        logger.error(f"Message generation error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/exceptions', methods=['GET'])
def list_exceptions():
    """List all exception orders"""
    try:
        limit = int(request.args.get('limit', 50))

        query = db.collection('orders').where('status', '==', 'exception') \
                                      .order_by('created_at', direction=firestore.Query.DESCENDING) \
                                      .limit(limit)

        exceptions = [doc.to_dict() for doc in query.stream()]

        return jsonify({
            'success': True,
            'count': len(exceptions),
            'exceptions': exceptions
        }), 200

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


if __name__ == '__main__':
    port = int(os.getenv('PORT', 8082))
    app.run(host='0.0.0.0', port=port)
