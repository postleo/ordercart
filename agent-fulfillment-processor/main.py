"""
OrderCart - ADK-002: Fulfillment Processor Agent
Cloud Run Service for order processing, batch optimization, and workflow management
Architecture: Pub/Sub Listener → Batch Analysis → Firestore → Status Management
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from collections import defaultdict
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
subscriber = pubsub_v1.SubscriberClient()
project_id = os.getenv('GOOGLE_CLOUD_PROJECT', 'ordercart-project')
subscription_validated = f'projects/{project_id}/subscriptions/processor-sub'
topic_communication = f'projects/{project_id}/topics/communication-request'

# Configure Gemma AI
api_key = os.getenv('GOOGLE_API_KEY', '')
if api_key:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
else:
    logger.warning("GOOGLE_API_KEY not set - AI features disabled")
    model = None

# Valid status transitions
VALID_TRANSITIONS = {
    'validated': ['processing', 'paid'],
    'paid': ['picking'],
    'picking': ['packed'],
    'packed': ['shipped'],
    'shipped': ['delivered'],
    'processing': ['paid', 'exception'],
}


class BatchAnalyzer:
    """AI-powered batch suggestion engine"""

    def __init__(self):
        self.model = model

    def suggest_batches(self) -> List[Dict[str, Any]]:
        """Analyze validated orders and suggest optimal batches"""
        try:
            # Get validated orders
            orders_ref = db.collection('orders')
            query = orders_ref.where('status', '==', 'validated').limit(100)
            orders = [doc.to_dict() for doc in query.stream()]

            if not orders:
                return []

            logger.info(f"Analyzing {len(orders)} validated orders for batching")

            # Strategy 1: Group by region (state)
            region_batches = self._batch_by_region(orders)

            # Strategy 2: Group by deadline/urgency
            urgency_batches = self._batch_by_urgency(orders)

            # Strategy 3: Group by product similarity
            product_batches = self._batch_by_products(orders)

            # Combine and rank batches
            all_batches = region_batches + urgency_batches + product_batches
            ranked_batches = self._rank_batches(all_batches)

            return ranked_batches[:10]  # Return top 10

        except Exception as e:
            logger.error(f"Batch suggestion error: {str(e)}")
            return []

    def _batch_by_region(self, orders: List[Dict]) -> List[Dict]:
        """Group orders by state/region"""
        batches = []
        by_state = defaultdict(list)

        for order in orders:
            state = order.get('address', {}).get('state')
            if state:
                by_state[state].append(order)

        for state, state_orders in by_state.items():
            if len(state_orders) >= 3:  # Minimum 3 orders
                batches.append({
                    'type': 'region',
                    'name': f"{state} Orders",
                    'description': f"{len(state_orders)} orders to {state}",
                    'orders': state_orders,
                    'order_ids': [o['order_id'] for o in state_orders],
                    'count': len(state_orders),
                    'savings_minutes': len(state_orders) * 2,  # Estimated 2 min per order
                })

        return batches

    def _batch_by_urgency(self, orders: List[Dict]) -> List[Dict]:
        """Group orders by urgency/deadline"""
        batches = []
        urgent_orders = []

        for order in orders:
            created = datetime.fromisoformat(order.get('created_at', datetime.now().isoformat()))
            age_hours = (datetime.now() - created).total_seconds() / 3600

            if age_hours >= 6:  # Orders older than 6 hours
                urgent_orders.append(order)

        if len(urgent_orders) >= 2:
            batches.append({
                'type': 'urgency',
                'name': 'Urgent Orders',
                'description': f"{len(urgent_orders)} orders need immediate attention",
                'orders': urgent_orders,
                'order_ids': [o['order_id'] for o in urgent_orders],
                'count': len(urgent_orders),
                'savings_minutes': len(urgent_orders) * 3,
                'priority': 'high',
            })

        return batches

    def _batch_by_products(self, orders: List[Dict]) -> List[Dict]:
        """Group orders by product SKU similarity"""
        batches = []
        by_sku = defaultdict(list)

        for order in orders:
            items = order.get('items', [])
            for item in items:
                sku = item.get('sku')
                if sku:
                    by_sku[sku].append(order)

        for sku, sku_orders in by_sku.items():
            if len(sku_orders) >= 3:
                # Get product name from first order
                product_name = sku_orders[0].get('items', [{}])[0].get('name', sku)

                batches.append({
                    'type': 'product',
                    'name': f"{product_name} Orders",
                    'description': f"{len(sku_orders)} orders containing {product_name}",
                    'orders': sku_orders,
                    'order_ids': [o['order_id'] for o in sku_orders],
                    'count': len(sku_orders),
                    'savings_minutes': len(sku_orders) * 1.5,
                })

        return batches

    def _rank_batches(self, batches: List[Dict]) -> List[Dict]:
        """Rank batches by time savings and priority"""
        def score(batch):
            base_score = batch.get('savings_minutes', 0)
            if batch.get('priority') == 'high':
                base_score *= 2
            if batch.get('count', 0) > 10:
                base_score *= 1.5
            return base_score

        return sorted(batches, key=score, reverse=True)

    def create_batch(self, batch_data: Dict[str, Any]) -> str:
        """Create and save a batch to Firestore"""
        try:
            batch_id = f"BATCH-{datetime.now().strftime('%Y%m%d%H%M%S%f')[:17]}"

            batch_doc = {
                'batch_id': batch_id,
                'name': batch_data['name'],
                'description': batch_data.get('description', ''),
                'type': batch_data.get('type', 'manual'),
                'order_ids': batch_data['order_ids'],
                'order_count': len(batch_data['order_ids']),
                'status': 'active',
                'created_at': datetime.now().isoformat(),
                'created_by': 'ADK-002',
            }

            db.collection('batches').document(batch_id).set(batch_doc)
            logger.info(f"Batch created: {batch_id}")
            return batch_id

        except Exception as e:
            logger.error(f"Batch creation error: {str(e)}")
            raise


class OrderProcessor:
    """Handles order status management and transitions"""

    def update_status(self, order_id: str, new_status: str) -> Dict[str, Any]:
        """Update order status with validation"""
        try:
            doc_ref = db.collection('orders').document(order_id)
            order_doc = doc_ref.get()

            if not order_doc.exists:
                raise ValueError(f"Order {order_id} not found")

            order = order_doc.to_dict()
            current_status = order.get('status')

            # Validate transition
            if not self._is_valid_transition(current_status, new_status):
                raise ValueError(f"Invalid transition: {current_status} → {new_status}")

            # Update order
            doc_ref.update({
                'status': new_status,
                'updated_at': datetime.now().isoformat(),
                'updated_by': 'ADK-002',
            })

            logger.info(f"Order {order_id} status updated: {current_status} → {new_status}")

            # Trigger communication if needed
            if new_status in ['shipped', 'delivered']:
                self._request_communication(order_id, new_status)

            return {'success': True, 'order_id': order_id, 'status': new_status}

        except Exception as e:
            logger.error(f"Status update error: {str(e)}")
            raise

    def _is_valid_transition(self, current: str, new: str) -> bool:
        """Check if status transition is valid"""
        if current == new:
            return True
        return new in VALID_TRANSITIONS.get(current, [])

    def _request_communication(self, order_id: str, event: str):
        """Request Agent 3 to send customer communication"""
        try:
            message = json.dumps({
                'order_id': order_id,
                'event': event,
                'timestamp': datetime.now().isoformat(),
                'agent': 'ADK-002'
            })

            future = publisher.publish(topic_communication, message.encode('utf-8'))
            future.result(timeout=10)
            logger.info(f"Communication request sent for {order_id}")

        except Exception as e:
            logger.error(f"Communication request error: {str(e)}")

    def bulk_update_status(self, order_ids: List[str], new_status: str) -> Dict[str, Any]:
        """Update status for multiple orders in a batch"""
        results = []
        success_count = 0

        for order_id in order_ids:
            try:
                self.update_status(order_id, new_status)
                results.append({'order_id': order_id, 'success': True})
                success_count += 1
            except Exception as e:
                logger.error(f"Bulk update error for {order_id}: {str(e)}")
                results.append({'order_id': order_id, 'success': False, 'error': str(e)})

        return {
            'total': len(order_ids),
            'success': success_count,
            'failed': len(order_ids) - success_count,
            'results': results
        }


def handle_validated_order(order_id: str):
    """Handle incoming validated order from Pub/Sub"""
    try:
        logger.info(f"Processing validated order: {order_id}")

        # Get order from Firestore
        doc_ref = db.collection('orders').document(order_id)
        order = doc_ref.get().to_dict()

        if not order:
            logger.error(f"Order {order_id} not found")
            return

        # Auto-check if order can be batched
        analyzer = BatchAnalyzer()
        suggestions = analyzer.suggest_batches()

        # Log suggestions for this order
        for suggestion in suggestions:
            if order_id in suggestion.get('order_ids', []):
                logger.info(f"Order {order_id} can be batched: {suggestion['name']}")

    except Exception as e:
        logger.error(f"Validated order handler error: {str(e)}")


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'agent': 'ADK-002-FulfillmentProcessor',
        'timestamp': datetime.now().isoformat()
    })


@app.route('/api/batches/suggest', methods=['GET'])
def get_batch_suggestions():
    """Get AI-powered batch suggestions"""
    try:
        analyzer = BatchAnalyzer()
        suggestions = analyzer.suggest_batches()

        return jsonify({
            'success': True,
            'count': len(suggestions),
            'batches': suggestions
        }), 200

    except Exception as e:
        logger.error(f"Batch suggestion error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/batches/create', methods=['POST'])
def create_batch():
    """Create a new batch"""
    try:
        data = request.get_json()

        if not data.get('order_ids'):
            return jsonify({'error': 'order_ids required'}), 400

        analyzer = BatchAnalyzer()
        batch_id = analyzer.create_batch(data)

        return jsonify({
            'success': True,
            'batch_id': batch_id
        }), 200

    except Exception as e:
        logger.error(f"Batch creation error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/batches/<batch_id>', methods=['GET'])
def get_batch(batch_id):
    """Get batch details"""
    try:
        doc = db.collection('batches').document(batch_id).get()
        if not doc.exists:
            return jsonify({'error': 'Batch not found'}), 404

        return jsonify({
            'success': True,
            'batch': doc.to_dict()
        }), 200

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/orders/<order_id>/status', methods=['PUT'])
def update_order_status(order_id):
    """Update single order status"""
    try:
        data = request.get_json()
        new_status = data.get('status')

        if not new_status:
            return jsonify({'error': 'status required'}), 400

        processor = OrderProcessor()
        result = processor.update_status(order_id, new_status)

        return jsonify(result), 200

    except Exception as e:
        logger.error(f"Status update error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/batches/<batch_id>/update-status', methods=['POST'])
def bulk_update_status(batch_id):
    """Bulk update status for all orders in a batch"""
    try:
        data = request.get_json()
        new_status = data.get('status')

        if not new_status:
            return jsonify({'error': 'status required'}), 400

        # Get batch
        batch_doc = db.collection('batches').document(batch_id).get()
        if not batch_doc.exists:
            return jsonify({'error': 'Batch not found'}), 404

        batch = batch_doc.to_dict()
        order_ids = batch.get('order_ids', [])

        # Bulk update
        processor = OrderProcessor()
        result = processor.bulk_update_status(order_ids, new_status)

        return jsonify(result), 200

    except Exception as e:
        logger.error(f"Bulk update error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/orders', methods=['GET'])
def list_orders():
    """List orders with optional filters"""
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
        return jsonify({'success': False, 'error': str(e)}), 500


if __name__ == '__main__':
    port = int(os.getenv('PORT', 8081))
    app.run(host='0.0.0.0', port=port)
