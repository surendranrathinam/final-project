import json
import logging
import os
from datetime import datetime
from functools import wraps

from flask import Flask, flash, redirect, render_template, request, session, url_for
from pymongo import MongoClient, ReturnDocument
from pymongo.errors import PyMongoError
from waitress import serve

# ─── FIX 1: Configure logging BEFORE anything else ───────────────────────────
# Without this, waitress.serve() blocks silently → server looks "frozen"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
# ─── FIX 2: Set Flask logger level so app.logger.info() is visible ───────────
app.logger.setLevel(logging.INFO)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-key")
app.jinja_env.globals.update(enumerate=enumerate)

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "woodcraft_erp")
MONGO_TIMEOUT_MS = int(os.getenv("MONGO_TIMEOUT_MS", "5000"))

# Initialize MongoDB client
mongo_client = None
db = None
mongo_available = False


def init_mongo():
    global mongo_client, db, mongo_available
    try:
        mongo_client = MongoClient(
            MONGO_URI,
            serverSelectionTimeoutMS=MONGO_TIMEOUT_MS,
            connect=False,
        )
        mongo_client.admin.command("ping")
        db = mongo_client[MONGO_DB_NAME]
        mongo_available = True
        logger.info("✓ MongoDB connected: %s / %s", MONGO_URI, MONGO_DB_NAME)
        return True
    except PyMongoError as error:
        mongo_available = False
        logger.warning("✗ MongoDB unavailable: %s", error)
        return False


def check_mongo_connection() -> bool:
    global mongo_available, mongo_client, db
    if mongo_available:
        return True

    try:
        if mongo_client is None:
            # ─── FIX 3: Was missing connect=False → caused blocking connection ──
            mongo_client = MongoClient(
                MONGO_URI,
                serverSelectionTimeoutMS=MONGO_TIMEOUT_MS,
                connect=False,
            )
        mongo_client.admin.command("ping")
        db = mongo_client[MONGO_DB_NAME]
        mongo_available = True
        logger.info("✓ MongoDB reconnected")
    except PyMongoError as error:
        mongo_available = False
        logger.warning("✗ MongoDB unavailable: %s", error)

    return mongo_available


def get_next_id(counter_name: str) -> int:
    if not check_mongo_connection():
        raise RuntimeError("MongoDB is not available")

    # ─── FIX 4: Removed broken fallback that did DB ops inside PyMongoError ───
    # The old except block called count_documents/insert_one/find_one inside a
    # PyMongoError handler — those calls would also fail. Now we let callers
    # handle the error via their own try/except blocks (which they all have).
    counter = db.counters.find_one_and_update(
        {"_id": counter_name},
        {"$inc": {"value": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return counter["value"]


def normalize(doc):
    if not doc:
        return None
    clean = dict(doc)
    clean.pop("_id", None)
    return clean


def normalize_many(cursor):
    return [normalize(item) for item in cursor]


def parse_date(value: str):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return None


def parse_int(value, default=None):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def parse_items_json(value):
    try:
        parsed = json.loads(value or "[]")
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    return parsed if isinstance(parsed, list) else []


def parse_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return func(*args, **kwargs)
    return wrapper


@app.before_request
def require_db():
    # ─── FIX 5: endpoint can be None on 404/error pages → guard against it ───
    endpoint = request.endpoint or ""
    if endpoint in ("login", "static"):
        return
    if not check_mongo_connection():
        return render_template(
            "login.html",
            error="Database unavailable. Ensure MongoDB is running and MONGO_URI is correct.",
        ), 503


def seed_users():
    if not check_mongo_connection():
        return

    try:
        if db.users.count_documents({}) > 0:
            return

        users = [
            {"id": get_next_id("users"), "username": "admin",   "password": "admin123",   "role": "Admin"},
            {"id": get_next_id("users"), "username": "manager",  "password": "manager123", "role": "Manager"},
            {"id": get_next_id("users"), "username": "rajan",    "password": "rajan123",   "role": "Carpenter"},
            {"id": get_next_id("users"), "username": "selvam",   "password": "selvam123",  "role": "Carpenter"},
            {"id": get_next_id("users"), "username": "murugan",  "password": "murugan123", "role": "Carpenter"},
        ]
        db.users.insert_many(users)
        logger.info("✓ Demo users seeded successfully")
    except PyMongoError as error:
        logger.warning("✗ Error seeding users: %s", error)


# ─────────────────────────────────────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if not check_mongo_connection():
            return render_template("login.html", error="Database unavailable. Please try again later.")

        try:
            user = db.users.find_one({"username": username, "password": password})
            if user:
                session["user_id"] = user["id"]
                session["username"] = user["username"]
                session["role"] = user["role"]
                return redirect(url_for("dashboard"))
            return render_template("login.html", error="Invalid username or password")
        except PyMongoError:
            return render_template("login.html", error="Database error. Please try again.")

    return render_template("login.html", error=None)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def dashboard():
    if not check_mongo_connection():
        flash("Database connection issue. Some data may not be available.", "warning")
        return render_template("dashboard.html", stats={}, recent_orders=[], recent_tasks=[], monthly_data="[]", now=datetime.utcnow())

    now = datetime.utcnow()
    month_start = datetime(now.year, now.month, 1)

    try:
        paid_invoices = normalize_many(db.invoices.find({"created_at": {"$gte": month_start}, "status": "Paid"}))
        monthly_revenue = sum(inv.get("total_amount", 0) for inv in paid_invoices)

        stats = {
            "total_customers":  db.customers.count_documents({}),
            "active_orders":    db.orders.count_documents({"status": {"$in": ["Pending", "In Progress", "Quality Check", "Ready"]}}),
            "pending_tasks":    db.tasks.count_documents({"status": {"$in": ["Pending", "In Progress"]}}),
            "low_stock":        db.inventory.count_documents({"$expr": {"$lte": ["$quantity", "$min_stock"]}}),
            "monthly_revenue":  monthly_revenue,
            "total_orders_month": db.orders.count_documents({"created_at": {"$gte": month_start}}),
        }

        customer_map = {c["id"]: c for c in normalize_many(db.customers.find({}))}
        user_map = {u["id"]: u for u in normalize_many(db.users.find({}))}

        recent_orders = normalize_many(db.orders.find({}).sort("created_at", -1).limit(5))
        for order in recent_orders:
            order["customer_name"] = customer_map.get(order.get("customer_id"), {}).get("name", "Unknown")

        recent_tasks = normalize_many(db.tasks.find({}).sort("created_at", -1).limit(5))
        for task in recent_tasks:
            task["carpenter_name"] = user_map.get(task.get("assigned_to"), {}).get("username")

        monthly_data = []
        for month in range(1, 13):
            start = datetime(now.year, month, 1)
            end = datetime(now.year + 1, 1, 1) if month == 12 else datetime(now.year, month + 1, 1)
            month_orders = normalize_many(db.orders.find({"created_at": {"$gte": start, "$lt": end}}))
            monthly_data.append({
                "month": month,
                "orders": len(month_orders),
                "revenue": sum(o.get("total_amount", 0) for o in month_orders),
            })

        return render_template(
            "dashboard.html",
            stats=stats,
            recent_orders=recent_orders,
            recent_tasks=recent_tasks,
            monthly_data=json.dumps(monthly_data, default=str),
            now=now,
        )
    except PyMongoError as e:
        app.logger.error("Dashboard error: %s", e)
        flash("Error loading dashboard data", "error")
        return render_template("dashboard.html", stats={}, recent_orders=[], recent_tasks=[], monthly_data="[]", now=now)


@app.route("/customers")
@login_required
def customers():
    if not check_mongo_connection():
        flash("Database unavailable", "error")
        return render_template("customers.html", customers=[], search="")

    search = request.args.get("search", "").strip()
    query = {}
    if search:
        query = {
            "$or": [
                {"name":  {"$regex": search, "$options": "i"}},
                {"email": {"$regex": search, "$options": "i"}},
                {"phone": {"$regex": search, "$options": "i"}},
            ]
        }
    try:
        customer_list = normalize_many(db.customers.find(query).sort("name", 1))
        return render_template("customers.html", customers=customer_list, search=search)
    except PyMongoError as e:
        app.logger.error("Customers error: %s", e)
        flash("Error loading customers", "error")
        return render_template("customers.html", customers=[], search=search)


@app.route("/customers/add", methods=["GET", "POST"])
@login_required
def add_customer():
    if request.method == "POST":
        if not check_mongo_connection():
            flash("Database unavailable", "error")
            return redirect(url_for("customers"))

        try:
            payload = {
                "id":         get_next_id("customers"),
                "name":       request.form.get("name", "").strip(),
                "phone":      request.form.get("phone", "").strip(),
                "email":      request.form.get("email", "").strip(),
                "address":    request.form.get("address", "").strip(),
                "notes":      request.form.get("notes", "").strip(),
                "created_at": datetime.utcnow(),
            }
            db.customers.insert_one(payload)
            flash("Customer added successfully", "success")
            return redirect(url_for("customers"))
        except PyMongoError as e:
            app.logger.error("Add customer error: %s", e)
            flash("Error adding customer", "error")
            return redirect(url_for("customers"))

    return render_template("customer_form.html", action="Add", customer=None)


@app.route("/customers/<int:id>/edit", methods=["GET", "POST"])
@login_required
def edit_customer(id):
    if not check_mongo_connection():
        flash("Database unavailable", "error")
        return redirect(url_for("customers"))

    try:
        customer = normalize(db.customers.find_one({"id": id}))
        if not customer:
            flash("Customer not found", "warning")
            return redirect(url_for("customers"))

        if request.method == "POST":
            db.customers.update_one(
                {"id": id},
                {"$set": {
                    "name":    request.form.get("name", "").strip(),
                    "phone":   request.form.get("phone", "").strip(),
                    "email":   request.form.get("email", "").strip(),
                    "address": request.form.get("address", "").strip(),
                    "notes":   request.form.get("notes", "").strip(),
                }},
            )
            flash("Customer updated successfully", "success")
            return redirect(url_for("customers"))

        return render_template("customer_form.html", action="Edit", customer=customer)
    except PyMongoError as e:
        app.logger.error("Edit customer error: %s", e)
        flash("Error editing customer", "error")
        return redirect(url_for("customers"))


@app.route("/customers/<int:id>/delete", methods=["POST"])
@login_required
def delete_customer(id):
    if not check_mongo_connection():
        flash("Database unavailable", "error")
        return redirect(url_for("customers"))

    try:
        db.customers.delete_one({"id": id})
        flash("Customer deleted", "success")
    except PyMongoError as e:
        app.logger.error("Delete customer error: %s", e)
        flash("Error deleting customer", "error")
    return redirect(url_for("customers"))


@app.route("/customers/<int:id>/history")
@login_required
def customer_history(id):
    if not check_mongo_connection():
        flash("Database unavailable", "error")
        return redirect(url_for("customers"))

    try:
        customer = normalize(db.customers.find_one({"id": id}))
        if not customer:
            flash("Customer not found", "warning")
            return redirect(url_for("customers"))

        orders   = normalize_many(db.orders.find({"customer_id": id}).sort("created_at", -1))
        invoices = normalize_many(db.invoices.find({"customer_id": id}).sort("created_at", -1))
        total_spent = sum(inv.get("total_amount", 0) for inv in invoices)

        return render_template(
            "customer_history.html",
            customer=customer, orders=orders,
            invoices=invoices, total_spent=total_spent,
        )
    except PyMongoError as e:
        app.logger.error("Customer history error: %s", e)
        flash("Error loading customer history", "error")
        return redirect(url_for("customers"))


@app.route("/products")
@login_required
def products():
    if not check_mongo_connection():
        flash("Database unavailable", "error")
        return render_template("products.html", products=[])

    try:
        product_list = normalize_many(db.products.find({}).sort("name", 1))
        return render_template("products.html", products=product_list)
    except PyMongoError as e:
        app.logger.error("Products error: %s", e)
        flash("Error loading products", "error")
        return render_template("products.html", products=[])


@app.route("/products/add", methods=["GET", "POST"])
@login_required
def add_product():
    if request.method == "POST":
        if not check_mongo_connection():
            flash("Database unavailable", "error")
            return redirect(url_for("products"))

        try:
            product = {
                "id":            get_next_id("products"),
                "name":          request.form.get("name", "").strip(),
                "category":      request.form.get("category", "").strip(),
                "wood_type":     request.form.get("wood_type", "").strip(),
                "finish":        request.form.get("finish", "").strip(),
                "dimensions":    request.form.get("dimensions", "").strip(),
                "description":   request.form.get("description", "").strip(),
                "base_price":    parse_float(request.form.get("base_price")),
                "labor_cost":    parse_float(request.form.get("labor_cost")),
                "material_cost": parse_float(request.form.get("material_cost")),
                "created_at":    datetime.utcnow(),
            }
            db.products.insert_one(product)
            flash("Product added successfully", "success")
            return redirect(url_for("products"))
        except PyMongoError as e:
            app.logger.error("Add product error: %s", e)
            flash("Error adding product", "error")
            return redirect(url_for("products"))

    return render_template("product_form.html", action="Add", product=None)


@app.route("/products/<int:id>/edit", methods=["GET", "POST"])
@login_required
def edit_product(id):
    if not check_mongo_connection():
        flash("Database unavailable", "error")
        return redirect(url_for("products"))

    try:
        product = normalize(db.products.find_one({"id": id}))
        if not product:
            flash("Product not found", "warning")
            return redirect(url_for("products"))

        if request.method == "POST":
            db.products.update_one(
                {"id": id},
                {"$set": {
                    "name":          request.form.get("name", "").strip(),
                    "category":      request.form.get("category", "").strip(),
                    "wood_type":     request.form.get("wood_type", "").strip(),
                    "finish":        request.form.get("finish", "").strip(),
                    "dimensions":    request.form.get("dimensions", "").strip(),
                    "description":   request.form.get("description", "").strip(),
                    "base_price":    parse_float(request.form.get("base_price")),
                    "labor_cost":    parse_float(request.form.get("labor_cost")),
                    "material_cost": parse_float(request.form.get("material_cost")),
                }},
            )
            flash("Product updated", "success")
            return redirect(url_for("products"))

        return render_template("product_form.html", action="Edit", product=product)
    except PyMongoError as e:
        app.logger.error("Edit product error: %s", e)
        flash("Error editing product", "error")
        return redirect(url_for("products"))


@app.route("/products/<int:id>/delete", methods=["POST"])
@login_required
def delete_product(id):
    if not check_mongo_connection():
        flash("Database unavailable", "error")
        return redirect(url_for("products"))

    try:
        db.products.delete_one({"id": id})
        flash("Product deleted", "success")
    except PyMongoError as e:
        app.logger.error("Delete product error: %s", e)
        flash("Error deleting product", "error")
    return redirect(url_for("products"))


@app.route("/orders")
@login_required
def orders():
    if not check_mongo_connection():
        flash("Database unavailable", "error")
        return render_template("orders.html", orders=[], status_filter="")

    status_filter = request.args.get("status", "")
    query = {"status": status_filter} if status_filter else {}

    try:
        customer_map = {c["id"]: c for c in normalize_many(db.customers.find({}))}
        order_list = normalize_many(db.orders.find(query).sort("created_at", -1))
        for order in order_list:
            order["customer_name"] = customer_map.get(order.get("customer_id"), {}).get("name", "Unknown")
        return render_template("orders.html", orders=order_list, status_filter=status_filter)
    except PyMongoError as e:
        app.logger.error("Orders error: %s", e)
        flash("Error loading orders", "error")
        return render_template("orders.html", orders=[], status_filter=status_filter)


@app.route("/orders/new", methods=["GET", "POST"])
@login_required
def new_order():
    if not check_mongo_connection():
        flash("Database unavailable", "error")
        return redirect(url_for("orders"))

    if request.method == "POST":
        try:
            customer_id = parse_int(request.form.get("customer_id"))
            raw_items   = parse_items_json(request.form.get("items"))
            if customer_id is None:
                flash("Please select a valid customer", "warning")
                return redirect(url_for("new_order"))

            products_map = {p["id"]: p for p in normalize_many(db.products.find({}))}

            items = []
            total = 0.0
            for item in raw_items:
                product_id = parse_int(item.get("product_id"))
                qty        = parse_int(item.get("qty"), 1)
                if product_id is None or qty is None or qty <= 0:
                    continue
                product = products_map.get(product_id)
                if not product:
                    continue
                unit_price = parse_float(product.get("base_price", 0))
                total += unit_price * qty
                items.append({
                    "id":         get_next_id("order_items"),
                    "product_id": product_id,
                    "quantity":   qty,
                    "unit_price": unit_price,
                })

            if not items:
                flash("Add at least one valid order item", "warning")
                return redirect(url_for("new_order"))

            order_id = get_next_id("orders")
            order = {
                "id":            order_id,
                "customer_id":   customer_id,
                "delivery_date": parse_date(request.form.get("delivery_date", "")),
                "notes":         request.form.get("notes", "").strip(),
                "status":        "Pending",
                "total_amount":  total,
                "created_at":    datetime.utcnow(),
            }
            db.orders.insert_one(order)

            for item in items:
                item["order_id"] = order_id
            db.order_items.insert_many(items)

            flash("Order created successfully", "success")
            return redirect(url_for("order_detail", id=order_id))
        except PyMongoError as e:
            app.logger.error("New order error: %s", e)
            flash("Error creating order", "error")
            return redirect(url_for("new_order"))

    try:
        return render_template(
            "order_form.html",
            customers=normalize_many(db.customers.find({}).sort("name", 1)),
            products=normalize_many(db.products.find({}).sort("name", 1)),
            now_date=datetime.utcnow().strftime("%Y-%m-%d"),
        )
    except PyMongoError as e:
        app.logger.error("New order form error: %s", e)
        flash("Error loading form", "error")
        return redirect(url_for("orders"))


@app.route("/orders/<int:id>")
@login_required
def order_detail(id):
    if not check_mongo_connection():
        flash("Database unavailable", "error")
        return redirect(url_for("orders"))

    try:
        order = normalize(db.orders.find_one({"id": id}))
        if not order:
            flash("Order not found", "warning")
            return redirect(url_for("orders"))

        customer = normalize(db.customers.find_one({"id": order["customer_id"]})) or {}
        order.update({
            "customer_name": customer.get("name", "Unknown"),
            "phone":  customer.get("phone"),
            "email":  customer.get("email"),
        })

        products_map = {p["id"]: p for p in normalize_many(db.products.find({}))}
        items = normalize_many(db.order_items.find({"order_id": id}))
        for item in items:
            product = products_map.get(item.get("product_id"), {})
            item["product_name"] = product.get("name", "Unknown")
            item["wood_type"]    = product.get("wood_type", "")

        invoice = normalize(db.invoices.find_one({"order_num": id}))

        users_map = {u["id"]: u for u in normalize_many(db.users.find({}))}
        tasks = normalize_many(db.tasks.find({"order_id": id}).sort("created_at", -1))
        for task in tasks:
            task["carpenter"] = users_map.get(task.get("assigned_to"), {}).get("username")

        return render_template("order_detail.html", order=order, items=items, invoice=invoice, tasks=tasks)
    except PyMongoError as e:
        app.logger.error("Order detail error: %s", e)
        flash("Error loading order details", "error")
        return redirect(url_for("orders"))


@app.route("/orders/<int:id>/status", methods=["POST"])
@login_required
def update_order_status(id):
    if not check_mongo_connection():
        flash("Database unavailable", "error")
        return redirect(url_for("order_detail", id=id))

    try:
        db.orders.update_one({"id": id}, {"$set": {"status": request.form.get("status", "Pending")}})
        flash("Order status updated", "success")
    except PyMongoError as e:
        app.logger.error("Update order status error: %s", e)
        flash("Error updating order status", "error")
    return redirect(url_for("order_detail", id=id))


@app.route("/orders/<int:order_id>/generate-invoice", methods=["POST"])
@login_required
def generate_invoice(order_id):
    if not check_mongo_connection():
        flash("Database unavailable", "error")
        return redirect(url_for("order_detail", id=order_id))

    try:
        order = normalize(db.orders.find_one({"id": order_id}))
        if not order:
            flash("Order not found", "warning")
            return redirect(url_for("orders"))

        if db.invoices.find_one({"order_num": order_id}):
            flash("Invoice already exists for this order", "warning")
            return redirect(url_for("order_detail", id=order_id))

        customer    = normalize(db.customers.find_one({"id": order["customer_id"]})) or {}
        products_map = {p["id"]: p for p in normalize_many(db.products.find({}))}
        order_items = normalize_many(db.order_items.find({"order_id": order_id}))

        material_cost = 0.0
        labor_cost    = 0.0
        subtotal      = 0.0
        for item in order_items:
            qty     = item.get("quantity", 0)
            product = products_map.get(item.get("product_id"), {})
            subtotal      += parse_float(item.get("unit_price", 0)) * qty
            material_cost += parse_float(product.get("material_cost", 0)) * qty
            labor_cost    += parse_float(product.get("labor_cost", 0)) * qty

        tax          = subtotal * 0.18
        total_amount = subtotal + tax

        invoice_id = get_next_id("invoices")
        invoice = {
            "id":             invoice_id,
            "order_num":      order_id,
            "customer_id":    order.get("customer_id"),
            "customer_name":  customer.get("name", "Unknown"),
            "phone":          customer.get("phone", ""),
            "email":          customer.get("email", ""),
            "address":        customer.get("address", ""),
            "delivery_date":  order.get("delivery_date"),
            "subtotal":       subtotal,
            "tax":            tax,
            "material_cost":  material_cost,
            "labor_cost":     labor_cost,
            "total_amount":   total_amount,
            "status":         "Unpaid",
            "created_at":     datetime.utcnow(),
            "paid_at":        None,
            "payment_method": None,
        }
        db.invoices.insert_one(invoice)
        flash("Invoice generated", "success")
        return redirect(url_for("invoice_detail", id=invoice_id))
    except PyMongoError as e:
        app.logger.error("Generate invoice error: %s", e)
        flash("Error generating invoice", "error")
        return redirect(url_for("order_detail", id=order_id))


@app.route("/billing")
@login_required
def billing():
    if not check_mongo_connection():
        flash("Database unavailable", "error")
        return render_template("billing.html", invoices=[])

    try:
        invoices = normalize_many(db.invoices.find({}).sort("created_at", -1))
        return render_template("billing.html", invoices=invoices)
    except PyMongoError as e:
        app.logger.error("Billing error: %s", e)
        flash("Error loading invoices", "error")
        return render_template("billing.html", invoices=[])


@app.route("/invoices/<int:id>")
@login_required
def invoice_detail(id):
    if not check_mongo_connection():
        flash("Database unavailable", "error")
        return redirect(url_for("billing"))

    try:
        invoice = normalize(db.invoices.find_one({"id": id}))
        if not invoice:
            flash("Invoice not found", "warning")
            return redirect(url_for("billing"))

        products_map = {p["id"]: p for p in normalize_many(db.products.find({}))}
        items = normalize_many(db.order_items.find({"order_id": invoice["order_num"]}))
        for item in items:
            product = products_map.get(item.get("product_id"), {})
            item["product_name"] = product.get("name", "Unknown")
            item["wood_type"]    = product.get("wood_type", "")
            item["finish"]       = product.get("finish", "")

        return render_template("invoice_detail.html", invoice=invoice, items=items)
    except PyMongoError as e:
        app.logger.error("Invoice detail error: %s", e)
        flash("Error loading invoice details", "error")
        return redirect(url_for("billing"))


@app.route("/invoices/<int:id>/mark-paid", methods=["POST"])
@login_required
def mark_paid(id):
    if not check_mongo_connection():
        flash("Database unavailable", "error")
        return redirect(url_for("invoice_detail", id=id))

    try:
        payment_method = request.form.get("payment_method", "").strip() or "QR Code"
        db.invoices.update_one(
            {"id": id},
            {"$set": {"status": "Paid", "paid_at": datetime.utcnow(), "payment_method": payment_method}},
        )
        flash(f"Payment received using {payment_method}", "success")
    except PyMongoError as e:
        app.logger.error("Mark paid error: %s", e)
        flash("Error processing payment", "error")
    return redirect(url_for("invoice_detail", id=id))


@app.route("/tasks")
@login_required
def tasks():
    if not check_mongo_connection():
        flash("Database unavailable", "error")
        return render_template("tasks.html", tasks=[], carpenters=[], orders=[], today=datetime.utcnow())

    try:
        tasks_list   = normalize_many(db.tasks.find({}).sort("created_at", -1))
        users_map    = {u["id"]: u for u in normalize_many(db.users.find({}))}
        customer_map = {c["id"]: c for c in normalize_many(db.customers.find({}))}
        orders       = normalize_many(db.orders.find({}).sort("created_at", -1))

        for task in tasks_list:
            task["carpenter"] = users_map.get(task.get("assigned_to"), {}).get("username")
            order = next((o for o in orders if o["id"] == task.get("order_id")), None)
            task["customer_name"] = customer_map.get(order.get("customer_id"), {}).get("name") if order else None

        carpenter_users = normalize_many(db.users.find({"role": "Carpenter"}).sort("username", 1))
        order_options = []
        for order in orders:
            customer_name = customer_map.get(order.get("customer_id"), {}).get("name", "Unknown")
            order_options.append({"id": order["id"], "name": customer_name})

        return render_template(
            "tasks.html",
            tasks=tasks_list,
            carpenters=carpenter_users,
            orders=order_options,
            today=datetime.utcnow(),
        )
    except PyMongoError as e:
        app.logger.error("Tasks error: %s", e)
        flash("Error loading tasks", "error")
        return render_template("tasks.html", tasks=[], carpenters=[], orders=[], today=datetime.utcnow())


@app.route("/tasks/add", methods=["POST"])
@login_required
def add_task():
    if not check_mongo_connection():
        flash("Database unavailable", "error")
        return redirect(url_for("tasks"))

    assigned_to = parse_int(request.form.get("assigned_to"))
    order_id    = parse_int(request.form.get("order_id"))

    if assigned_to is None or order_id is None:
        flash("Please choose both a carpenter and an order", "warning")
        return redirect(url_for("tasks"))

    try:
        payload = {
            "id":          get_next_id("tasks"),
            "title":       request.form.get("title", "").strip(),
            "description": request.form.get("description", "").strip(),
            "assigned_to": assigned_to,
            "order_id":    order_id,
            "due_date":    parse_date(request.form.get("due_date", "")),
            "labor_hours": parse_float(request.form.get("labor_hours")),
            "status":      "Pending",
            "created_at":  datetime.utcnow(),
        }
        db.tasks.insert_one(payload)
        flash("Task assigned", "success")
    except PyMongoError as e:
        app.logger.error("Add task error: %s", e)
        flash("Error adding task", "error")
    return redirect(url_for("tasks"))


@app.route("/tasks/<int:id>/status", methods=["POST"])
@login_required
def update_task_status(id):
    if not check_mongo_connection():
        flash("Database unavailable", "error")
        return redirect(url_for("tasks"))

    try:
        db.tasks.update_one({"id": id}, {"$set": {"status": request.form.get("status", "Pending")}})
        flash("Task status updated", "success")
    except PyMongoError as e:
        app.logger.error("Update task status error: %s", e)
        flash("Error updating task status", "error")
    return redirect(url_for("tasks"))


@app.route("/inventory")
@login_required
def inventory():
    if not check_mongo_connection():
        flash("Database unavailable", "error")
        return render_template("inventory.html", inventory=[], low_stock=[])

    try:
        inventory_list = normalize_many(db.inventory.find({}).sort("name", 1))
        low_stock = [item for item in inventory_list if item.get("quantity", 0) <= item.get("min_stock", 0)]
        return render_template("inventory.html", inventory=inventory_list, low_stock=low_stock)
    except PyMongoError as e:
        app.logger.error("Inventory error: %s", e)
        flash("Error loading inventory", "error")
        return render_template("inventory.html", inventory=[], low_stock=[])


@app.route("/inventory/add", methods=["GET", "POST"])
@login_required
def add_inventory():
    if request.method == "POST":
        if not check_mongo_connection():
            flash("Database unavailable", "error")
            return redirect(url_for("inventory"))

        try:
            item = {
                "id":           get_next_id("inventory"),
                "name":         request.form.get("name", "").strip(),
                "category":     request.form.get("category", "").strip(),
                "quantity":     parse_float(request.form.get("quantity")),
                "unit":         request.form.get("unit", "").strip(),
                "min_stock":    parse_float(request.form.get("min_stock")),
                "cost_per_unit":parse_float(request.form.get("cost_per_unit")),
                "supplier":     request.form.get("supplier", "").strip(),
                "location":     request.form.get("location", "").strip(),
                "notes":        request.form.get("notes", "").strip(),
                "created_at":   datetime.utcnow(),
            }
            db.inventory.insert_one(item)
            flash("Inventory item added", "success")
            return redirect(url_for("inventory"))
        except PyMongoError as e:
            app.logger.error("Add inventory error: %s", e)
            flash("Error adding inventory item", "error")
            return redirect(url_for("inventory"))

    return render_template("inventory_form.html", action="Add", item=None)


@app.route("/inventory/<int:id>/edit", methods=["GET", "POST"])
@login_required
def edit_inventory(id):
    if not check_mongo_connection():
        flash("Database unavailable", "error")
        return redirect(url_for("inventory"))

    try:
        item = normalize(db.inventory.find_one({"id": id}))
        if not item:
            flash("Inventory item not found", "warning")
            return redirect(url_for("inventory"))

        if request.method == "POST":
            db.inventory.update_one(
                {"id": id},
                {"$set": {
                    "name":          request.form.get("name", "").strip(),
                    "category":      request.form.get("category", "").strip(),
                    "quantity":      parse_float(request.form.get("quantity")),
                    "unit":          request.form.get("unit", "").strip(),
                    "min_stock":     parse_float(request.form.get("min_stock")),
                    "cost_per_unit": parse_float(request.form.get("cost_per_unit")),
                    "supplier":      request.form.get("supplier", "").strip(),
                    "location":      request.form.get("location", "").strip(),
                    "notes":         request.form.get("notes", "").strip(),
                }},
            )
            flash("Inventory item updated", "success")
            return redirect(url_for("inventory"))

        return render_template("inventory_form.html", action="Edit", item=item)
    except PyMongoError as e:
        app.logger.error("Edit inventory error: %s", e)
        flash("Error editing inventory item", "error")
        return redirect(url_for("inventory"))


@app.route("/inventory/<int:id>/restock", methods=["POST"])
@login_required
def restock_inventory(id):
    if not check_mongo_connection():
        flash("Database unavailable", "error")
        return redirect(url_for("inventory"))

    quantity = parse_float(request.form.get("quantity"))
    try:
        db.inventory.update_one({"id": id}, {"$inc": {"quantity": quantity}})
        flash("Inventory restocked", "success")
    except PyMongoError as e:
        app.logger.error("Restock inventory error: %s", e)
        flash("Error restocking inventory", "error")
    return redirect(url_for("inventory"))


@app.route("/reports")
@login_required
def reports():
    if not check_mongo_connection():
        flash("Database unavailable", "error")
        now = datetime.utcnow()
        return render_template("reports.html", period="monthly", year=now.year, month=now.month,
                               summary={}, sales_data="[]", order_status=[], top_products=[], top_customers=[])

    period = request.args.get("period", "monthly")
    now    = datetime.utcnow()
    year   = int(request.args.get("year")  or now.year)
    month  = int(request.args.get("month") or now.month)

    try:
        orders   = normalize_many(db.orders.find({}))
        items    = normalize_many(db.order_items.find({}))
        products  = {p["id"]: p for p in normalize_many(db.products.find({}))}
        customers = {c["id"]: c for c in normalize_many(db.customers.find({}))}

        selected_orders = [o for o in orders if o.get("created_at") and o["created_at"].year == year]
        if period == "daily":
            selected_orders = [o for o in selected_orders if o["created_at"].month == month]

        total_revenue   = sum(o.get("total_amount", 0) for o in selected_orders)
        total_orders    = len(selected_orders)
        avg_order_value = total_revenue / total_orders if total_orders else 0

        order_ids = {o["id"] for o in selected_orders}
        selected_items = [i for i in items if i.get("order_id") in order_ids]
        total_materials = sum(products.get(i.get("product_id"), {}).get("material_cost", 0) * i.get("quantity", 0) for i in selected_items)
        total_labor     = sum(products.get(i.get("product_id"), {}).get("labor_cost", 0)    * i.get("quantity", 0) for i in selected_items)

        summary = {
            "total_revenue":   total_revenue,
            "total_orders":    total_orders,
            "avg_order_value": avg_order_value,
            "total_materials": total_materials,
            "total_labor":     total_labor,
        }

        sales_data = []
        if period == "monthly":
            for m in range(1, 13):
                subset = [o for o in selected_orders if o["created_at"].month == m]
                sales_data.append({"month": m, "orders": len(subset), "revenue": sum(o.get("total_amount", 0) for o in subset)})
        else:
            days = sorted({o["created_at"].date() for o in selected_orders})
            for d in days:
                subset = [o for o in selected_orders if o["created_at"].date() == d]
                sales_data.append({"date": d.isoformat(), "orders": len(subset), "revenue": sum(o.get("total_amount", 0) for o in subset)})

        status_counts = {}
        for order in selected_orders:
            status = order.get("status", "Pending")
            status_counts[status] = status_counts.get(status, 0) + 1
        order_status = [{"status": k, "count": v} for k, v in status_counts.items()]

        product_stats  = {}
        customer_stats = {}
        for item in selected_items:
            product = products.get(item.get("product_id"), {})
            pid     = item.get("product_id")
            revenue = item.get("quantity", 0) * item.get("unit_price", 0)
            if pid not in product_stats:
                product_stats[pid] = {"name": product.get("name", "Unknown"), "category": product.get("category", "Other"), "units_sold": 0, "revenue": 0}
            product_stats[pid]["units_sold"] += item.get("quantity", 0)
            product_stats[pid]["revenue"]    += revenue

        for order in selected_orders:
            cid = order.get("customer_id")
            if cid not in customer_stats:
                customer_stats[cid] = {"name": customers.get(cid, {}).get("name", "Unknown"), "orders": 0, "spent": 0}
            customer_stats[cid]["orders"] += 1
            customer_stats[cid]["spent"]  += order.get("total_amount", 0)

        top_products  = sorted(product_stats.values(),  key=lambda x: x["revenue"], reverse=True)[:5]
        top_customers = sorted(customer_stats.values(), key=lambda x: x["spent"],   reverse=True)[:5]

        return render_template(
            "reports.html",
            period=period, year=year, month=month,
            summary=summary,
            sales_data=json.dumps(sales_data),
            order_status=order_status,
            top_products=top_products,
            top_customers=top_customers,
        )
    except PyMongoError as e:
        app.logger.error("Reports error: %s", e)
        flash("Error loading reports", "error")
        now = datetime.utcnow()
        return render_template("reports.html", period=period, year=year, month=month,
                               summary={}, sales_data="[]", order_status=[], top_products=[], top_customers=[])


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    host   = os.getenv("HOST", "0.0.0.0")
    port   = int(os.getenv("PORT", "5000"))
    is_dev = os.getenv("FLASK_ENV", "").lower() == "development" or os.getenv("FLASK_DEBUG") == "1"

    logger.info("=" * 52)
    logger.info("  WoodCraft ERP — Starting up")
    logger.info("=" * 52)

    # Connect to MongoDB
    if not init_mongo():
        logger.warning("MongoDB not available — server will start but pages will show DB error until MongoDB is reachable.")
    else:
        # Seed demo users on first run
        try:
            seed_users()
        except Exception as error:
            logger.warning("Could not seed users: %s", error)

    # ─── FIX 6: Print startup URL so user knows the server is running ─────────
    # waitress.serve() is a BLOCKING call — the terminal will appear "frozen"
    # which is normal. Open your browser to the URL shown below.
    logger.info("-" * 52)
    logger.info("  Server:  http://%s:%s", "localhost" if host == "0.0.0.0" else host, port)
    logger.info("  Mode:    %s", "development" if is_dev else "production")
    logger.info("  Login:   admin / admin123")
    logger.info("-" * 52)
    logger.info("  Press Ctrl+C to stop")
    logger.info("=" * 52)

    if is_dev:
        app.run(debug=True, host=host, port=port)
    else:
        serve(app, host=host, port=port)
