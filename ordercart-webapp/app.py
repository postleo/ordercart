"""
OrderCart Web Application
Cloud Run Service - Frontend Interface and API Gateway
Architecture: HTML/CSS/JS Frontend → Flask Backend → AI Agents (via REST)
"""

import os
import json
import logging
import requests
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_cors import CORS
from google.cloud import firestore

# Initialize Flask app
app = Flask(__name__, static_folder='static', template_folder='templates')
CORS(app)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize Firestore
db = firestore.Client()

# AI Agent Service URLs (set via environment variables)
AGENT_INTAKE_URL = os.getenv('AGENT_INTAKE_URL', 'http://localhost:8080')
AGENT_PROCESSOR_URL = os.getenv('AGENT_PROCESSOR_URL', 'http://localhost:8081')
AGENT_EXCEPTION_URL = os.getenv('AGENT_EXCEPTION_URL', 'http://localhost:8082')


@app.route('/')
def index():
    """Serve main application page"""
    return render_template('index.html')


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'OrderCart-WebApp',
        'timestamp': datetime.now().isoformat()
    })


# ============= ORDER INTAKE ENDPOINTS =============

@app.route('/api/orders/intake', methods=['POST'])
def intake_order():
    """Forward order to Intake Agent"""
    try:
        data = request.get_json()
        logger.info(f"Order intake request received: {json.dumps(data)[:200]}")

        # Forward to Agent 1 (Intake Agent)
        response = requests.post(
            f"{AGENT_INTAKE_URL}/api/intake",
            json=data,
            timeout=30
        )

        return jsonify(response.json()), response.status_code

    except requests.exceptions.RequestException as e:
        logger.error(f"Agent communication error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to communicate with intake agent'
        }), 503
    except Exception as e:
        logger.error(f"Intake error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/orders/intake/batch', methods=['POST'])
def intake_batch():
    """Forward batch orders to Intake Agent"""
    try:
        data = request.get_json()

        response = requests.post(
            f"{AGENT_INTAKE_URL}/api/intake/batch",
            json=data,
            timeout=60
        )

        return jsonify(response.json()), response.status_code

    except Exception as e:
        logger.error(f"Batch intake error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============= ORDER MANAGEMENT ENDPOINTS =============

@app.route('/api/orders', methods=['GET'])
def list_orders():
    """Get orders with optional filters"""
    try:
        status = request.args.get('status')
        limit = int(request.args.get('limit', 50))

        query = db.collection('orders')
        if status:
            query = query.where('status', '==', status)

        query = query.order_by('created_at', direction=firestore.Query.DESCENDING).limit(limit)

        orders = [doc.to_dict() for doc in query.stream()]

        return jsonify({
            'success': True,
            'count': len(orders),
            'orders': orders
        }), 200

    except Exception as e:
        logger.error(f"List orders error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/orders/<order_id>', methods=['GET'])
def get_order(order_id):
    """Get single order details"""
    try:
        doc = db.collection('orders').document(order_id).get()
        if not doc.exists:
            return jsonify({'error': 'Order not found'}), 404

        return jsonify({
            'success': True,
            'order': doc.to_dict()
        }), 200

    except Exception as e:
        logger.error(f"Get order error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/orders/<order_id>/status', methods=['PUT'])
def update_order_status(order_id):
    """Update order status via Processor Agent"""
    try:
        data = request.get_json()

        response = requests.put(
            f"{AGENT_PROCESSOR_URL}/api/orders/{order_id}/status",
            json=data,
            timeout=30
        )

        return jsonify(response.json()), response.status_code

    except Exception as e:
        logger.error(f"Status update error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============= BATCH PROCESSING ENDPOINTS =============

@app.route('/api/batches/suggest', methods=['GET'])
def get_batch_suggestions():
    """Get AI batch suggestions from Processor Agent"""
    try:
        response = requests.get(
            f"{AGENT_PROCESSOR_URL}/api/batches/suggest",
            timeout=30
        )

        return jsonify(response.json()), response.status_code

    except Exception as e:
        logger.error(f"Batch suggestions error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/batches/create', methods=['POST'])
def create_batch():
    """Create new batch via Processor Agent"""
    try:
        data = request.get_json()

        response = requests.post(
            f"{AGENT_PROCESSOR_URL}/api/batches/create",
            json=data,
            timeout=30
        )

        return jsonify(response.json()), response.status_code

    except Exception as e:
        logger.error(f"Batch creation error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/batches/<batch_id>', methods=['GET'])
def get_batch(batch_id):
    """Get batch details"""
    try:
        response = requests.get(
            f"{AGENT_PROCESSOR_URL}/api/batches/{batch_id}",
            timeout=30
        )

        return jsonify(response.json()), response.status_code

    except Exception as e:
        logger.error(f"Get batch error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/batches/<batch_id>/update-status', methods=['POST'])
def bulk_update_status(batch_id):
    """Bulk update status for batch orders"""
    try:
        data = request.get_json()

        response = requests.post(
            f"{AGENT_PROCESSOR_URL}/api/batches/{batch_id}/update-status",
            json=data,
            timeout=60
        )

        return jsonify(response.json()), response.status_code

    except Exception as e:
        logger.error(f"Bulk update error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============= EXCEPTION HANDLING ENDPOINTS =============

@app.route('/api/exceptions', methods=['GET'])
def list_exceptions():
    """Get all exception orders"""
    try:
        response = requests.get(
            f"{AGENT_EXCEPTION_URL}/api/exceptions",
            timeout=30
        )

        return jsonify(response.json()), response.status_code

    except Exception as e:
        logger.error(f"List exceptions error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/exceptions/<order_id>/analyze', methods=['POST'])
def analyze_exception(order_id):
    """Analyze exception via Exception Agent"""
    try:
        response = requests.post(
            f"{AGENT_EXCEPTION_URL}/api/exceptions/{order_id}/analyze",
            timeout=30
        )

        return jsonify(response.json()), response.status_code

    except Exception as e:
        logger.error(f"Exception analysis error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/exceptions/<order_id>/resolve', methods=['POST'])
def resolve_exception(order_id):
    """Resolve exception via Exception Agent"""
    try:
        data = request.get_json()

        response = requests.post(
            f"{AGENT_EXCEPTION_URL}/api/exceptions/{order_id}/resolve",
            json=data,
            timeout=30
        )

        return jsonify(response.json()), response.status_code

    except Exception as e:
        logger.error(f"Exception resolution error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============= COMMUNICATION ENDPOINTS =============

@app.route('/api/communications/send', methods=['POST'])
def send_communication():
    """Send customer communication via Exception Agent"""
    try:
        data = request.get_json()

        response = requests.post(
            f"{AGENT_EXCEPTION_URL}/api/communications/send",
            json=data,
            timeout=30
        )

        return jsonify(response.json()), response.status_code

    except Exception as e:
        logger.error(f"Communication send error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/communications/generate', methods=['POST'])
def generate_communication():
    """Generate communication preview"""
    try:
        data = request.get_json()

        response = requests.post(
            f"{AGENT_EXCEPTION_URL}/api/communications/generate",
            json=data,
            timeout=30
        )

        return jsonify(response.json()), response.status_code

    except Exception as e:
        logger.error(f"Communication generation error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============= DASHBOARD STATS ENDPOINTS =============

@app.route('/api/stats/dashboard', methods=['GET'])
def get_dashboard_stats():
    """Get dashboard statistics"""
    try:
        orders_ref = db.collection('orders')

        # Count orders by status
        stats = {
            'orders_today': 0,
            'processing': 0,
            'exceptions': 0,
            'completed': 0,
            'total': 0
        }

        # Get all orders (or limit for performance)
        all_orders = orders_ref.limit(1000).stream()

        today = datetime.now().date()

        for doc in all_orders:
            order = doc.to_dict()
            stats['total'] += 1

            # Count today's orders
            created = order.get('created_at', '')
            if created:
                try:
                    order_date = datetime.fromisoformat(created).date()
                    if order_date == today:
                        stats['orders_today'] += 1
                except:
                    pass

            # Count by status
            status = order.get('status', '')
            if status == 'exception':
                stats['exceptions'] += 1
            elif status in ['delivered', 'completed']:
                stats['completed'] += 1
            elif status in ['validated', 'processing', 'paid', 'picking', 'packed', 'shipped']:
                stats['processing'] += 1

        return jsonify({
            'success': True,
            'stats': stats
        }), 200

    except Exception as e:
        logger.error(f"Dashboard stats error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


if __name__ == '__main__':
    port = int(os.getenv('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=False)
