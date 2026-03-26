# 🪵 WoodCraft ERP System

WoodCraft ERP is a Flask-based carpentry business management app that now runs on **MongoDB**.

## Tech Stack
- Python 3.9+
- Flask
- MongoDB (local or cloud)
- HTML/CSS/JS frontend templates (already included in `templates/` and `static/`)

## Quick Start

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Start MongoDB (example local default):
   ```bash
   mongod --dbpath /path/to/your/db
   ```

3. Set environment variables (optional):
   ```bash
   export MONGO_URI="mongodb://localhost:27017"
   export MONGO_DB_NAME="woodcraft_erp"
   export FLASK_SECRET_KEY="change-me"
   ```

4. Run the server:
   ```bash
   python app.py
   ```

5. Open:
   `http://localhost:5000`

## Demo Login
- `admin / admin123`
- `manager / manager123`
- `rajan / rajan123`

Default demo users are automatically seeded on first run.

## MongoDB Collections Used
- `users`
- `customers`
- `products`
- `orders`
- `order_items`
- `tasks`
- `inventory`
- `invoices`
- `counters` (for incremental integer IDs used by templates)

## Features Included
- Authentication (session based)
- Customer CRUD + customer history page
- Product CRUD
- Order creation with line items + status tracking
- Invoice generation and mark-as-paid flow
- Task management with carpenter assignment
- Inventory CRUD + restock flow + low stock alerts
- Dashboard and reports pages fed from MongoDB data
