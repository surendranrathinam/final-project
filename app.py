from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from datetime import datetime, timedelta
import mysql.connector
import hashlib
import os
import json
from functools import wraps

app = Flask(__name__)
app.secret_key = 'woodcraft_erp_secret_2024'

# Jinja2 helpers
app.jinja_env.globals['enumerate'] = enumerate

@app.context_processor
def inject_globals():
    from datetime import date
    return {'today': date.today(), 'now': datetime.now(), 'now_date': date.today().isoformat()}

# ─── DB CONFIG ────────────────────────────────────────────────────────────────
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'woodwork_erp'
}

def get_db():
    return mysql.connector.connect(**DB_CONFIG)

def query(sql, params=(), fetchone=False, commit=False):
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute(sql, params)
    if commit:
        conn.commit()
        result = cur.lastrowid
    elif fetchone:
        result = cur.fetchone()
    else:
        result = cur.fetchall()
    cur.close()
    conn.close()
    return result

# ─── AUTH ─────────────────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def hash_pw(password):
    return hashlib.sha256(password.encode()).hexdigest()

@app.route('/', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = hash_pw(request.form['password'])
        user = query("SELECT * FROM users WHERE username=%s AND password=%s", (username, password), fetchone=True)
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            return redirect(url_for('dashboard'))
        error = 'Invalid credentials'
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ─── DASHBOARD ────────────────────────────────────────────────────────────────
@app.route('/dashboard')
@login_required
def dashboard():
    stats = {
        'total_customers': query("SELECT COUNT(*) as c FROM customers", fetchone=True)['c'],
        'active_orders': query("SELECT COUNT(*) as c FROM orders WHERE status NOT IN ('Delivered','Cancelled')", fetchone=True)['c'],
        'pending_tasks': query("SELECT COUNT(*) as c FROM tasks WHERE status='Pending'", fetchone=True)['c'],
        'low_stock': query("SELECT COUNT(*) as c FROM inventory WHERE quantity <= min_stock", fetchone=True)['c'],
        'monthly_revenue': query("SELECT COALESCE(SUM(total_amount),0) as r FROM invoices WHERE MONTH(created_at)=MONTH(NOW()) AND YEAR(created_at)=YEAR(NOW())", fetchone=True)['r'],
        'total_orders_month': query("SELECT COUNT(*) as c FROM orders WHERE MONTH(created_at)=MONTH(NOW())", fetchone=True)['c'],
    }
    recent_orders = query("SELECT o.*, c.name as customer_name FROM orders o JOIN customers c ON o.customer_id=c.id ORDER BY o.created_at DESC LIMIT 5")
    recent_tasks = query("SELECT t.*, u.username as carpenter_name FROM tasks t LEFT JOIN users u ON t.assigned_to=u.id ORDER BY t.created_at DESC LIMIT 5")
    monthly_data = query("""
        SELECT MONTH(created_at) as month, SUM(total_amount) as revenue, COUNT(*) as orders
        FROM invoices WHERE YEAR(created_at)=YEAR(NOW())
        GROUP BY MONTH(created_at) ORDER BY month
    """)
    return render_template('dashboard.html', stats=stats, recent_orders=recent_orders,
                           recent_tasks=recent_tasks, monthly_data=json.dumps(monthly_data, default=str))

# ─── CUSTOMERS ────────────────────────────────────────────────────────────────
@app.route('/customers')
@login_required
def customers():
    search = request.args.get('search', '')
    if search:
        rows = query("SELECT * FROM customers WHERE name LIKE %s OR email LIKE %s OR phone LIKE %s ORDER BY name",
                     (f'%{search}%', f'%{search}%', f'%{search}%'))
    else:
        rows = query("SELECT * FROM customers ORDER BY name")
    return render_template('customers.html', customers=rows, search=search)

@app.route('/customers/add', methods=['GET', 'POST'])
@login_required
def add_customer():
    if request.method == 'POST':
        query("INSERT INTO customers (name,email,phone,address,notes) VALUES (%s,%s,%s,%s,%s)",
              (request.form['name'], request.form['email'], request.form['phone'],
               request.form['address'], request.form['notes']), commit=True)
        flash('Customer added successfully', 'success')
        return redirect(url_for('customers'))
    return render_template('customer_form.html', customer=None, action='Add')

@app.route('/customers/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_customer(id):
    customer = query("SELECT * FROM customers WHERE id=%s", (id,), fetchone=True)
    if request.method == 'POST':
        query("UPDATE customers SET name=%s,email=%s,phone=%s,address=%s,notes=%s WHERE id=%s",
              (request.form['name'], request.form['email'], request.form['phone'],
               request.form['address'], request.form['notes'], id), commit=True)
        flash('Customer updated', 'success')
        return redirect(url_for('customers'))
    return render_template('customer_form.html', customer=customer, action='Edit')

@app.route('/customers/<int:id>/delete', methods=['POST'])
@login_required
def delete_customer(id):
    query("DELETE FROM customers WHERE id=%s", (id,), commit=True)
    flash('Customer deleted', 'warning')
    return redirect(url_for('customers'))

@app.route('/customers/<int:id>/history')
@login_required
def customer_history(id):
    customer = query("SELECT * FROM customers WHERE id=%s", (id,), fetchone=True)
    orders = query("SELECT * FROM orders WHERE customer_id=%s ORDER BY created_at DESC", (id,))
    invoices = query("SELECT * FROM invoices WHERE customer_id=%s ORDER BY created_at DESC", (id,))
    total_spent = query("SELECT COALESCE(SUM(total_amount),0) as t FROM invoices WHERE customer_id=%s", (id,), fetchone=True)['t']
    return render_template('customer_history.html', customer=customer, orders=orders,
                           invoices=invoices, total_spent=total_spent)

# ─── PRODUCTS ─────────────────────────────────────────────────────────────────
@app.route('/products')
@login_required
def products():
    rows = query("SELECT * FROM products ORDER BY category, name")
    return render_template('products.html', products=rows)

@app.route('/products/add', methods=['GET', 'POST'])
@login_required
def add_product():
    if request.method == 'POST':
        query("INSERT INTO products (name,category,description,wood_type,dimensions,finish,base_price,labor_cost,material_cost) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
              (request.form['name'], request.form['category'], request.form['description'],
               request.form['wood_type'], request.form['dimensions'], request.form['finish'],
               request.form['base_price'], request.form['labor_cost'], request.form['material_cost']), commit=True)
        flash('Product added', 'success')
        return redirect(url_for('products'))
    return render_template('product_form.html', product=None, action='Add')

@app.route('/products/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_product(id):
    product = query("SELECT * FROM products WHERE id=%s", (id,), fetchone=True)
    if request.method == 'POST':
        query("UPDATE products SET name=%s,category=%s,description=%s,wood_type=%s,dimensions=%s,finish=%s,base_price=%s,labor_cost=%s,material_cost=%s WHERE id=%s",
              (request.form['name'], request.form['category'], request.form['description'],
               request.form['wood_type'], request.form['dimensions'], request.form['finish'],
               request.form['base_price'], request.form['labor_cost'], request.form['material_cost'], id), commit=True)
        flash('Product updated', 'success')
        return redirect(url_for('products'))
    return render_template('product_form.html', product=product, action='Edit')

@app.route('/products/<int:id>/delete', methods=['POST'])
@login_required
def delete_product(id):
    query("DELETE FROM products WHERE id=%s", (id,), commit=True)
    flash('Product deleted', 'warning')
    return redirect(url_for('products'))

# ─── ORDERS ───────────────────────────────────────────────────────────────────
@app.route('/orders')
@login_required
def orders():
    status_filter = request.args.get('status', '')
    if status_filter:
        rows = query("SELECT o.*,c.name as customer_name FROM orders o JOIN customers c ON o.customer_id=c.id WHERE o.status=%s ORDER BY o.created_at DESC", (status_filter,))
    else:
        rows = query("SELECT o.*,c.name as customer_name FROM orders o JOIN customers c ON o.customer_id=c.id ORDER BY o.created_at DESC")
    return render_template('orders.html', orders=rows, status_filter=status_filter)

@app.route('/orders/new', methods=['GET', 'POST'])
@login_required
def new_order():
    customers_list = query("SELECT id,name FROM customers ORDER BY name")
    products_list = query("SELECT * FROM products ORDER BY name")
    if request.method == 'POST':
        customer_id = request.form['customer_id']
        delivery_date = request.form['delivery_date']
        notes = request.form['notes']
        items = json.loads(request.form['items'])
        total = sum(float(i['price']) * int(i['qty']) for i in items)
        order_id = query("INSERT INTO orders (customer_id,delivery_date,notes,total_amount,status) VALUES (%s,%s,%s,%s,'Pending')",
                         (customer_id, delivery_date, notes, total), commit=True)
        for item in items:
            query("INSERT INTO order_items (order_id,product_id,quantity,unit_price) VALUES (%s,%s,%s,%s)",
                  (order_id, item['product_id'], item['qty'], item['price']), commit=True)
        flash(f'Order #{order_id} created', 'success')
        return redirect(url_for('orders'))
    return render_template('order_form.html', customers=customers_list, products=products_list)

@app.route('/orders/<int:id>')
@login_required
def order_detail(id):
    order = query("SELECT o.*,c.name as customer_name,c.email,c.phone FROM orders o JOIN customers c ON o.customer_id=c.id WHERE o.id=%s", (id,), fetchone=True)
    items = query("SELECT oi.*,p.name as product_name,p.wood_type FROM order_items oi JOIN products p ON oi.product_id=p.id WHERE oi.order_id=%s", (id,))
    tasks = query("SELECT t.*,u.username as carpenter FROM tasks t LEFT JOIN users u ON t.assigned_to=u.id WHERE t.order_id=%s", (id,))
    invoice = query("SELECT * FROM invoices WHERE order_id=%s", (id,), fetchone=True)
    return render_template('order_detail.html', order=order, items=items, tasks=tasks, invoice=invoice)

@app.route('/orders/<int:id>/status', methods=['POST'])
@login_required
def update_order_status(id):
    status = request.form['status']
    query("UPDATE orders SET status=%s WHERE id=%s", (status, id), commit=True)
    flash('Order status updated', 'success')
    return redirect(url_for('order_detail', id=id))

# ─── INVENTORY ────────────────────────────────────────────────────────────────
@app.route('/inventory')
@login_required
def inventory():
    rows = query("SELECT * FROM inventory ORDER BY category, name")
    low_stock = query("SELECT * FROM inventory WHERE quantity <= min_stock ORDER BY quantity")
    return render_template('inventory.html', inventory=rows, low_stock=low_stock)

@app.route('/inventory/add', methods=['GET', 'POST'])
@login_required
def add_inventory():
    if request.method == 'POST':
        query("INSERT INTO inventory (name,category,unit,quantity,min_stock,cost_per_unit,supplier,location) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
              (request.form['name'], request.form['category'], request.form['unit'],
               request.form['quantity'], request.form['min_stock'], request.form['cost_per_unit'],
               request.form['supplier'], request.form['location']), commit=True)
        flash('Item added to inventory', 'success')
        return redirect(url_for('inventory'))
    return render_template('inventory_form.html', item=None, action='Add')

@app.route('/inventory/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_inventory(id):
    item = query("SELECT * FROM inventory WHERE id=%s", (id,), fetchone=True)
    if request.method == 'POST':
        query("UPDATE inventory SET name=%s,category=%s,unit=%s,quantity=%s,min_stock=%s,cost_per_unit=%s,supplier=%s,location=%s WHERE id=%s",
              (request.form['name'], request.form['category'], request.form['unit'],
               request.form['quantity'], request.form['min_stock'], request.form['cost_per_unit'],
               request.form['supplier'], request.form['location'], id), commit=True)
        flash('Inventory updated', 'success')
        return redirect(url_for('inventory'))
    return render_template('inventory_form.html', item=item, action='Edit')

@app.route('/inventory/<int:id>/restock', methods=['POST'])
@login_required
def restock(id):
    qty = float(request.form['quantity'])
    query("UPDATE inventory SET quantity=quantity+%s WHERE id=%s", (qty, id), commit=True)
    flash('Stock updated', 'success')
    return redirect(url_for('inventory'))

# ─── TASKS / WORKS ────────────────────────────────────────────────────────────
@app.route('/tasks')
@login_required
def tasks():
    rows = query("""SELECT t.*,u.username as carpenter,o.id as order_num,c.name as customer_name
                    FROM tasks t
                    LEFT JOIN users u ON t.assigned_to=u.id
                    LEFT JOIN orders o ON t.order_id=o.id
                    LEFT JOIN customers c ON o.customer_id=c.id
                    ORDER BY t.due_date ASC""")
    carpenters = query("SELECT id,username FROM users WHERE role='carpenter'")
    orders_list = query("SELECT o.id,c.name FROM orders o JOIN customers c ON o.customer_id=c.id WHERE o.status NOT IN ('Delivered','Cancelled')")
    return render_template('tasks.html', tasks=rows, carpenters=carpenters, orders=orders_list)

@app.route('/tasks/add', methods=['POST'])
@login_required
def add_task():
    query("INSERT INTO tasks (order_id,assigned_to,title,description,due_date,status,labor_hours) VALUES (%s,%s,%s,%s,%s,'Pending',%s)",
          (request.form['order_id'] or None, request.form['assigned_to'] or None,
           request.form['title'], request.form['description'],
           request.form['due_date'], request.form['labor_hours'] or 0), commit=True)
    flash('Task assigned', 'success')
    return redirect(url_for('tasks'))

@app.route('/tasks/<int:id>/status', methods=['POST'])
@login_required
def update_task_status(id):
    status = request.form['status']
    query("UPDATE tasks SET status=%s WHERE id=%s", (status, id), commit=True)
    if status == 'Completed':
        task = query("SELECT * FROM tasks WHERE id=%s", (id,), fetchone=True)
        if task and task['inventory_item_id']:
            query("UPDATE inventory SET quantity=quantity-%s WHERE id=%s",
                  (task['material_used'], task['inventory_item_id']), commit=True)
    return jsonify({'success': True})

# ─── BILLING ──────────────────────────────────────────────────────────────────
@app.route('/billing')
@login_required
def billing():
    invoices = query("""SELECT i.*,c.name as customer_name,o.id as order_num
                        FROM invoices i JOIN customers c ON i.customer_id=c.id
                        JOIN orders o ON i.order_id=o.id
                        ORDER BY i.created_at DESC""")
    return render_template('billing.html', invoices=invoices)

@app.route('/billing/generate/<int:order_id>', methods=['POST'])
@login_required
def generate_invoice(order_id):
    existing = query("SELECT id FROM invoices WHERE order_id=%s", (order_id,), fetchone=True)
    if existing:
        flash('Invoice already exists', 'warning')
        return redirect(url_for('order_detail', id=order_id))
    order = query("SELECT * FROM orders WHERE id=%s", (order_id,), fetchone=True)
    items = query("SELECT oi.*,p.labor_cost,p.material_cost FROM order_items oi JOIN products p ON oi.product_id=p.id WHERE oi.order_id=%s", (order_id,))
    material_total = sum(float(i['material_cost']) * int(i['quantity']) for i in items)
    labor_total = sum(float(i['labor_cost']) * int(i['quantity']) for i in items)
    subtotal = float(order['total_amount'])
    tax = round(subtotal * 0.18, 2)
    total = round(subtotal + tax, 2)
    inv_id = query("INSERT INTO invoices (order_id,customer_id,subtotal,tax,total_amount,material_cost,labor_cost,status) VALUES (%s,%s,%s,%s,%s,%s,%s,'Unpaid')",
                   (order_id, order['customer_id'], subtotal, tax, total, material_total, labor_total), commit=True)
    flash(f'Invoice #{inv_id} generated', 'success')
    return redirect(url_for('invoice_detail', id=inv_id))

@app.route('/billing/invoice/<int:id>')
@login_required
def invoice_detail(id):
    invoice = query("""SELECT i.*,c.name as customer_name,c.email,c.phone,c.address,o.id as order_num,o.delivery_date
                       FROM invoices i JOIN customers c ON i.customer_id=c.id JOIN orders o ON i.order_id=o.id
                       WHERE i.id=%s""", (id,), fetchone=True)
    items = query("""SELECT oi.*,p.name as product_name,p.wood_type,p.finish
                     FROM order_items oi JOIN products p ON oi.product_id=p.id
                     WHERE oi.order_id=%s""", (invoice['order_id'],))
    return render_template('invoice_detail.html', invoice=invoice, items=items)

@app.route('/billing/invoice/<int:id>/pay', methods=['POST'])
@login_required
def mark_paid(id):
    query("UPDATE invoices SET status='Paid', paid_at=NOW() WHERE id=%s", (id,), commit=True)
    flash('Invoice marked as paid', 'success')
    return redirect(url_for('invoice_detail', id=id))

# ─── REPORTS ──────────────────────────────────────────────────────────────────
@app.route('/reports')
@login_required
def reports():
    period = request.args.get('period', 'monthly')
    year = int(request.args.get('year', datetime.now().year))
    month = int(request.args.get('month', datetime.now().month))

    if period == 'daily':
        sales_data = query("""SELECT DATE(created_at) as date, COUNT(*) as orders, SUM(total_amount) as revenue
                               FROM invoices WHERE MONTH(created_at)=%s AND YEAR(created_at)=%s
                               GROUP BY DATE(created_at) ORDER BY date""", (month, year))
    else:
        sales_data = query("""SELECT MONTH(created_at) as month, COUNT(*) as orders, SUM(total_amount) as revenue
                               FROM invoices WHERE YEAR(created_at)=%s
                               GROUP BY MONTH(created_at) ORDER BY month""", (year,))

    summary = query("""SELECT
        COUNT(DISTINCT o.id) as total_orders,
        COALESCE(SUM(i.total_amount),0) as total_revenue,
        COALESCE(SUM(i.material_cost),0) as total_materials,
        COALESCE(SUM(i.labor_cost),0) as total_labor,
        COALESCE(AVG(i.total_amount),0) as avg_order_value
        FROM orders o LEFT JOIN invoices i ON o.id=i.order_id
        WHERE YEAR(o.created_at)=%s""", (year,), fetchone=True)

    top_products = query("""SELECT p.name, p.category, SUM(oi.quantity) as units_sold,
                             SUM(oi.quantity*oi.unit_price) as revenue
                             FROM order_items oi JOIN products p ON oi.product_id=p.id
                             JOIN orders o ON oi.order_id=o.id WHERE YEAR(o.created_at)=%s
                             GROUP BY p.id ORDER BY revenue DESC LIMIT 5""", (year,))

    order_status = query("""SELECT status, COUNT(*) as count FROM orders
                             WHERE YEAR(created_at)=%s GROUP BY status""", (year,))

    top_customers = query("""SELECT c.name, COUNT(o.id) as orders, SUM(i.total_amount) as spent
                              FROM customers c JOIN orders o ON c.id=o.customer_id
                              LEFT JOIN invoices i ON o.id=i.order_id
                              WHERE YEAR(o.created_at)=%s
                              GROUP BY c.id ORDER BY spent DESC LIMIT 5""", (year,))

    return render_template('reports.html', sales_data=json.dumps(sales_data, default=str),
                           summary=summary, top_products=top_products, order_status=order_status,
                           top_customers=top_customers, period=period, year=year, month=month)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
