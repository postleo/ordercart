/**
 * OrderCart Web App - Main JavaScript
 * Handles UI interactions and API communication with AI agents
 */

const app = {
    currentPage: 'dashboard',
    currentFilter: 'all',

    init() {
        this.setupTheme();
        this.setupEventListeners();
        this.loadDashboard();
        this.startAutoRefresh();
    },

    setupTheme() {
        const savedTheme = localStorage.getItem('ordercart-theme');
        if (savedTheme === 'dark') {
            document.body.classList.add('dark-mode');
            document.getElementById('themeBtn').innerHTML = '<i class="fas fa-sun"></i>';
        }
    },

    setupEventListeners() {
        document.getElementById('themeBtn').onclick = () => this.toggleTheme();
        document.getElementById('notificationsBtn').onclick = () => this.showNotifications();
        document.getElementById('menuBtn').onclick = () => this.toggleSidebar();
        document.getElementById('searchInput').oninput = (e) => this.handleSearch(e.target.value);
    },

    toggleTheme() {
        document.body.classList.toggle('dark-mode');
        const isDark = document.body.classList.contains('dark-mode');
        localStorage.setItem('ordercart-theme', isDark ? 'dark' : 'light');
        document.getElementById('themeBtn').innerHTML = isDark ? '<i class="fas fa-sun"></i>' : '<i class="fas fa-moon"></i>';
    },

    toggleSidebar() {
        const sidebar = document.getElementById('sidebar');
        sidebar.classList.toggle('mobile-show');
    },

    goToPage(page) {
        // Hide all pages
        document.querySelectorAll('.page').forEach(p => p.classList.add('hidden'));

        // Show selected page
        document.getElementById(`page-${page}`).classList.remove('hidden');

        // Update sidebar
        document.querySelectorAll('.sidebar-item').forEach(item => item.classList.remove('active'));
        event.target.closest('.sidebar-item')?.classList.add('active');

        this.currentPage = page;
        window.scrollTo(0, 0);

        // Load page data
        this.loadPageData(page);
    },

    async loadPageData(page) {
        switch (page) {
            case 'dashboard':
                await this.loadDashboard();
                break;
            case 'orders':
                await this.loadOrders();
                break;
            case 'exceptions':
                await this.loadExceptions();
                break;
            case 'batches':
                await this.loadBatches();
                break;
            case 'analytics':
                await this.loadAnalytics();
                break;
        }
    },

    // ============= DASHBOARD =============
    async loadDashboard() {
        try {
            const response = await fetch('/api/stats/dashboard');
            const data = await response.json();

            if (data.success) {
                const stats = data.stats;

                document.getElementById('stat-today').textContent = stats.orders_today;
                document.getElementById('stat-processing').textContent = stats.processing;
                document.getElementById('stat-exceptions').textContent = stats.exceptions;
                document.getElementById('stat-completed').textContent = stats.completed;

                // Update notification badge
                document.getElementById('notifCount').textContent = stats.exceptions;

                // Show alert banner if exceptions exist
                if (stats.exceptions > 0) {
                    const alertBanner = document.getElementById('alertBanner');
                    alertBanner.style.display = 'flex';
                    document.getElementById('alertText').innerHTML = `
                        <strong>${stats.exceptions} orders need attention</strong>
                        <p style="font-size:0.9rem; opacity:0.9;">Review and resolve exceptions</p>
                    `;
                }

                // Load recent orders
                await this.loadRecentOrders();
            }
        } catch (error) {
            console.error('Dashboard load error:', error);
        }
    },

    async loadRecentOrders() {
        try {
            const response = await fetch('/api/orders?limit=6');
            const data = await response.json();

            if (data.success) {
                const container = document.getElementById('recentOrders');
                container.innerHTML = '';

                data.orders.slice(0, 6).forEach(order => {
                    const urgency = this.getOrderUrgency(order);
                    const card = `
                        <div class="card ${urgency}">
                            <h3>${order.order_id} • ${order.customer.name || 'N/A'}</h3>
                            <p style="opacity:0.7; margin:0.5rem 0;">
                                ${this.formatItems(order.items)} • $${order.payment.amount.toFixed(2)}
                            </p>
                            <span class="badge-danger" style="${this.getBadgeStyle(order.status)}">
                                ${order.status.toUpperCase()}
                            </span>
                            <div style="margin-top:1rem;">
                                <button class="btn btn-primary btn-small" onclick="app.viewOrder('${order.order_id}')">
                                    View Details
                                </button>
                            </div>
                        </div>
                    `;
                    container.innerHTML += card;
                });
            }
        } catch (error) {
            console.error('Recent orders load error:', error);
        }
    },

    // ============= ORDER CAPTURE =============
    selectCapture(type) {
        const form = document.getElementById('captureForm');
        if (type === 'manual') {
            form.style.display = 'block';
        } else if (type === 'file') {
            alert('File upload feature coming soon!');
        }
    },

    async submitOrder(event) {
        event.preventDefault();
        const formData = new FormData(event.target);

        const orderData = {
            customer_name: formData.get('customer_name'),
            email: formData.get('email'),
            phone: formData.get('phone'),
            address: formData.get('address'),
            city: formData.get('city'),
            state: formData.get('state'),
            zip: formData.get('zip'),
            payment_method: formData.get('payment_method'),
            items: [{
                sku: formData.get('sku'),
                name: formData.get('product_name'),
                quantity: parseInt(formData.get('quantity')),
                price: parseFloat(formData.get('price'))
            }],
            total: parseFloat(formData.get('price')) * parseInt(formData.get('quantity'))
        };

        try {
            const response = await fetch('/api/orders/intake', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(orderData)
            });

            const result = await response.json();

            if (result.success) {
                alert(`✓ Order ${result.order_id} submitted successfully!\nStatus: ${result.status}`);
                event.target.reset();
                this.loadDashboard();
            } else {
                alert(`Error: ${result.error}`);
            }
        } catch (error) {
            console.error('Order submission error:', error);
            alert('Failed to submit order. Please try again.');
        }
    },

    // ============= ORDERS =============
    async loadOrders() {
        try {
            const response = await fetch('/api/orders');
            const data = await response.json();

            if (data.success) {
                const board = document.getElementById('orderBoard');
                board.innerHTML = '';

                const statuses = ['validated', 'processing', 'packed', 'shipped'];
                const statusLabels = {
                    'validated': 'Validated',
                    'processing': 'Processing',
                    'packed': 'Packed',
                    'shipped': 'Shipped'
                };

                statuses.forEach(status => {
                    const orders = data.orders.filter(o => o.status === status);
                    const column = `
                        <div class="status-column">
                            <div class="status-header status-${status}">${statusLabels[status]}</div>
                            <div>
                                ${orders.map(order => `
                                    <div class="card" style="margin-bottom:1rem; cursor:pointer;" onclick="app.viewOrder('${order.order_id}')">
                                        <strong>${order.order_id}</strong>
                                        <p style="font-size:0.9rem; opacity:0.7;">
                                            ${order.customer.name || 'N/A'} • $${order.payment.amount.toFixed(2)}
                                        </p>
                                    </div>
                                `).join('')}
                            </div>
                        </div>
                    `;
                    board.innerHTML += column;
                });
            }
        } catch (error) {
            console.error('Orders load error:', error);
        }
    },

    async viewOrder(orderId) {
        try {
            const response = await fetch(`/api/orders/${orderId}`);
            const data = await response.json();

            if (data.success) {
                const order = data.order;
                alert(`Order Details:\n\n` +
                      `ID: ${order.order_id}\n` +
                      `Customer: ${order.customer.name}\n` +
                      `Status: ${order.status}\n` +
                      `Amount: $${order.payment.amount}\n` +
                      `Items: ${this.formatItems(order.items)}`);
            }
        } catch (error) {
            console.error('View order error:', error);
        }
    },

    // ============= EXCEPTIONS =============
    async loadExceptions() {
        try {
            const response = await fetch('/api/exceptions');
            const data = await response.json();

            if (data.success) {
                const grid = document.getElementById('exceptionsGrid');
                grid.innerHTML = '';

                data.exceptions.forEach(order => {
                    const validation = order.validation || {};
                    const errors = validation.errors || [];
                    const analysis = order.exception_analysis || {};

                    const card = `
                        <div class="card urgent" data-category="${analysis.category || 'other'}">
                            <span class="badge-danger">${(analysis.category || 'EXCEPTION').toUpperCase()}</span>
                            <h3>${order.order_id} • ${order.customer.name || 'N/A'}</h3>
                            <p style="opacity:0.7; margin:0.5rem 0;">
                                ${errors.join(', ') || 'Validation failed'} • $${order.payment.amount.toFixed(2)}
                            </p>
                            ${analysis.root_cause ? `
                                <div style="background:rgba(127,255,212,0.08); padding:1rem; border-radius:8px; border-left:3px solid var(--aquamarine); margin:1rem 0;">
                                    <strong style="color:var(--aquamarine);"><i class="fas fa-wand-magic-sparkles"></i> AI Analysis</strong>
                                    <p style="margin-top:0.5rem; font-size:0.9rem;">${analysis.root_cause}</p>
                                    ${analysis.suggested_action ? `<p style="margin-top:0.5rem; font-size:0.9rem;"><strong>Suggested:</strong> ${analysis.suggested_action}</p>` : ''}
                                </div>
                            ` : ''}
                            <button class="btn btn-secondary btn-small" onclick="app.analyzeException('${order.order_id}')">
                                <i class="fas fa-wand-magic-sparkles"></i> ${analysis.root_cause ? 'Re-analyze' : 'Analyze with AI'}
                            </button>
                            <button class="btn btn-primary btn-small" onclick="app.resolveException('${order.order_id}')">
                                <i class="fas fa-check"></i> Resolve
                            </button>
                        </div>
                    `;
                    grid.innerHTML += card;
                });
            }
        } catch (error) {
            console.error('Exceptions load error:', error);
        }
    },

    filterExceptions(filter) {
        this.currentFilter = filter;

        document.querySelectorAll('.tab').forEach(tab => tab.classList.remove('active'));
        event.target.classList.add('active');

        const cards = document.querySelectorAll('#exceptionsGrid .card');
        cards.forEach(card => {
            if (filter === 'all') {
                card.style.display = 'block';
            } else {
                const category = card.getAttribute('data-category');
                card.style.display = category === filter ? 'block' : 'none';
            }
        });
    },

    async analyzeException(orderId) {
        try {
            const response = await fetch(`/api/exceptions/${orderId}/analyze`, {
                method: 'POST'
            });

            const data = await response.json();

            if (data.success) {
                alert('✓ AI Analysis Complete!\n\n' +
                      `Category: ${data.analysis.category}\n` +
                      `Priority: ${data.analysis.priority}\n` +
                      `Root Cause: ${data.analysis.root_cause}\n\n` +
                      `Suggested Action: ${data.analysis.suggested_action}`);
                this.loadExceptions();
            } else {
                alert(`Error: ${data.error}`);
            }
        } catch (error) {
            console.error('Exception analysis error:', error);
            alert('Failed to analyze exception');
        }
    },

    async resolveException(orderId) {
        const notes = prompt('Enter resolution notes (optional):');

        try {
            const response = await fetch(`/api/exceptions/${orderId}/resolve`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ notes: notes || '' })
            });

            const data = await response.json();

            if (data.success) {
                alert(`✓ Exception resolved! Order ${orderId} moved back to processing.`);
                this.loadExceptions();
                this.loadDashboard();
            } else {
                alert(`Error: ${data.error}`);
            }
        } catch (error) {
            console.error('Exception resolution error:', error);
            alert('Failed to resolve exception');
        }
    },

    // ============= BATCHES =============
    async loadBatches() {
        try {
            const response = await fetch('/api/batches/suggest');
            const data = await response.json();

            if (data.success) {
                const grid = document.getElementById('batchesGrid');
                grid.innerHTML = '';

                data.batches.forEach(batch => {
                    const card = `
                        <div class="stat-card" style="display:flex; justify-content:space-between; align-items:center;">
                            <div>
                                <h3 style="margin-bottom:0.5rem;">${batch.name}</h3>
                                <p style="opacity:0.7;">${batch.description}</p>
                                <span style="background:${this.getBatchColor(batch.type)}; color:var(--oxford-blue); padding:0.3rem 0.7rem; border-radius:6px; font-size:0.8rem; font-weight:700; margin-top:0.5rem; display:inline-block;">
                                    ${batch.type.toUpperCase()} • ${batch.savings_minutes} min savings
                                </span>
                            </div>
                            <button class="btn btn-primary btn-small" onclick="app.createBatch('${JSON.stringify(batch).replace(/'/g, "\\'")}')">
                                Create Batch
                            </button>
                        </div>
                    `;
                    grid.innerHTML += card;
                });
            }
        } catch (error) {
            console.error('Batches load error:', error);
        }
    },

    async createBatch(batchJson) {
        try {
            const batch = JSON.parse(batchJson);

            const response = await fetch('/api/batches/create', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(batch)
            });

            const data = await response.json();

            if (data.success) {
                alert(`✓ Batch ${data.batch_id} created successfully!`);
                this.loadBatches();
            } else {
                alert(`Error: ${data.error}`);
            }
        } catch (error) {
            console.error('Batch creation error:', error);
            alert('Failed to create batch');
        }
    },

    // ============= COMMUNICATIONS =============
    async sendCommunication(event) {
        event.preventDefault();
        const formData = new FormData(event.target);

        const data = {
            order_id: formData.get('order_id'),
            event: formData.get('event')
        };

        try {
            const response = await fetch('/api/communications/send', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });

            const result = await response.json();

            if (result.success) {
                alert(`✓ Communication sent to customer!\n\nSubject: ${result.message.subject}`);
                event.target.reset();
            } else {
                alert(`Error: ${result.error}`);
            }
        } catch (error) {
            console.error('Communication send error:', error);
            alert('Failed to send communication');
        }
    },

    // ============= ANALYTICS =============
    async loadAnalytics() {
        try {
            const response = await fetch('/api/stats/dashboard');
            const data = await response.json();

            if (data.success) {
                document.getElementById('analytics-total').textContent = data.stats.total;

                const successRate = data.stats.total > 0
                    ? ((data.stats.completed / data.stats.total) * 100).toFixed(1)
                    : '0';
                document.getElementById('analytics-success').textContent = successRate + '%';
            }
        } catch (error) {
            console.error('Analytics load error:', error);
        }
    },

    // ============= NOTIFICATIONS =============
    async showNotifications() {
        const modal = document.getElementById('notificationModal');
        const list = document.getElementById('notificationsList');

        try {
            const response = await fetch('/api/exceptions?limit=10');
            const data = await response.json();

            if (data.success) {
                list.innerHTML = '';

                if (data.exceptions.length === 0) {
                    list.innerHTML = '<p style="text-align:center; opacity:0.7;">No notifications</p>';
                } else {
                    data.exceptions.forEach(order => {
                        const notif = `
                            <div style="padding:1rem; background:rgba(239,68,68,0.1); border-left:3px solid var(--danger); border-radius:8px; margin-bottom:1rem;">
                                <strong style="color:var(--danger);">Exception: ${order.order_id}</strong>
                                <p style="opacity:0.7; margin-top:0.5rem;">${order.validation?.errors?.[0] || 'Validation failed'}</p>
                            </div>
                        `;
                        list.innerHTML += notif;
                    });
                }
            }
        } catch (error) {
            console.error('Notifications error:', error);
            list.innerHTML = '<p style="text-align:center; opacity:0.7;">Error loading notifications</p>';
        }

        modal.classList.add('show');
    },

    // ============= UTILITIES =============
    handleSearch(query) {
        if (query.length < 2) return;
        console.log('Searching for:', query);
        // TODO: Implement search functionality
    },

    formatItems(items) {
        if (!items || items.length === 0) return 'No items';
        const first = items[0];
        return `${first.quantity || 0} ${first.name || 'item'}${items.length > 1 ? ` +${items.length - 1} more` : ''}`;
    },

    getOrderUrgency(order) {
        if (order.status === 'exception') return 'urgent';
        const created = new Date(order.created_at);
        const ageHours = (Date.now() - created.getTime()) / 3600000;
        return ageHours > 6 ? 'urgent' : ageHours > 3 ? 'moderate' : 'normal';
    },

    getBadgeStyle(status) {
        const colors = {
            'exception': 'background:#fee2e2; color:#991b1b;',
            'validated': 'background:#d1fae5; color:#065f46;',
            'shipped': 'background:#dbeafe; color:#1e40af;'
        };
        return colors[status] || 'background:#fef3c7; color:#92400e;';
    },

    getBatchColor(type) {
        const colors = {
            'region': 'var(--aquamarine)',
            'urgency': '#fee2e2',
            'product': '#dbeafe'
        };
        return colors[type] || '#fef3c7';
    },

    startAutoRefresh() {
        // Refresh dashboard stats every 30 seconds
        setInterval(() => {
            if (this.currentPage === 'dashboard') {
                this.loadDashboard();
            }
        }, 30000);
    }
};

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    app.init();
});
