# 🪵 WoodCraft ERP System
### Woodwork & Carpentry Management System

A full-featured ERP built with **Python Flask** + **MySQL** + modern HTML/CSS/JS frontend.

---

## 📋 Modules Included

| Module | Features |
|--------|----------|
| 🔐 **Authentication** | Login/logout, role-based access (Admin, Manager, Carpenter) |
| 👥 **Customers** | Add/edit/delete clients, full history view, order & invoice timeline |
| 📦 **Products** | Catalog with wood type, dimensions, finish, tiered pricing (base/labor/material) |
| 📋 **Orders** | Create orders, multi-product line items, real-time status tracking with progress bar |
| 🔨 **Works & Tasks** | Assign tasks to carpenters, track labor progress, link tasks to orders |
| 📦 **Inventory** | Manage wood stacks & materials, visual stock levels, automated low-stock alerts, restock modal |
| 💰 **Billing** | Auto-calculate totals (materials + labor + 18% GST), generate digital invoices, mark paid |
| 📊 **Reports** | Daily/monthly summaries, revenue charts, order volume, top products, top customers |

---

## 🚀 Setup Instructions

### 1. Prerequisites
- Python 3.9+
- MySQL 8.0+
- pip

### 2. Install Python Dependencies
```bash
cd woodwork-erp
pip install -r requirements.txt
```

### 3. Set Up the Database
```bash
# Log into MySQL
mysql -u root -p

# Run the schema file (creates DB, tables, and seed data)
source schema.sql
# OR:
mysql -u root -p < schema.sql
```

### 4. Configure Database Connection
Edit `app.py` (top section) with your MySQL credentials:
```python
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'YOUR_PASSWORD',
    'database': 'woodwork_erp'
}
```

### 5. Run the Application
```bash
python app.py
```

Visit: **http://localhost:5000**

---

## 🔑 Default Login Credentials

| Username | Password | Role |
|----------|----------|------|
| `admin` | `admin123` | Admin |
| `manager` | `manager123` | Manager |
| `rajan` | `rajan123` | Carpenter |
| `selvam` | `selvam123` | Carpenter |
| `murugan` | `murugan123` | Carpenter |

---

## 📁 Project Structure

```
woodwork-erp/
├── app.py                  # Flask application & all routes
├── schema.sql              # MySQL schema + seed data
├── requirements.txt
├── README.md
├── static/
│   ├── css/
│   │   └── main.css        # Full stylesheet (warm craftsman theme)
│   └── js/
│       └── main.js         # Modal, tab, flash helpers
└── templates/
    ├── base.html           # Layout with sidebar navigation
    ├── login.html          # Authentication page
    ├── dashboard.html      # Overview with live charts
    ├── customers.html      # Customer directory
    ├── customer_form.html  # Add/Edit customer
    ├── customer_history.html # Customer order & invoice history
    ├── products.html       # Product catalog
    ├── product_form.html   # Add/Edit product
    ├── orders.html         # Order list with status filters
    ├── order_form.html     # New order with dynamic item builder
    ├── order_detail.html   # Full order view with status update
    ├── inventory.html      # Stock management with visual bars
    ├── inventory_form.html # Add/Edit inventory item
    ├── tasks.html          # Works & task assignment
    ├── billing.html        # Invoice list
    ├── invoice_detail.html # Printable invoice with GST breakdown
    └── reports.html        # Charts: revenue, orders, top products
```

---

## 🎨 Design System

- **Font**: Playfair Display (headings) + DM Sans (body) + DM Mono (numbers)
- **Theme**: Warm craftsman — deep walnut (#2C1810), brass (#C9943A), linen (#F5F0E8)
- **Charts**: Chart.js 4.4 (bar, line, doughnut)
- **Icons**: Font Awesome 6.5

---

## 🔄 Key Workflows

### Creating an Order
1. Go to **Orders → New Order**
2. Select customer, set delivery date
3. Add products dynamically (select product + qty → Add Item)
4. Submit — order is created with `Pending` status

### Generating an Invoice
1. Open any order → click **Generate Invoice**
2. System auto-calculates: subtotal, 18% GST, total
3. Material & labor costs pulled from product catalog
4. View/print the invoice or mark it as **Paid**

### Managing Inventory
1. Go to **Inventory** — red alert banner shows low-stock items
2. Click the **+** (restock) button on any row
3. Enter quantity to add → stock updates immediately

### Tracking Works
1. Go to **Works & Tasks → Assign Task**
2. Link to an order, assign to a carpenter, set due date
3. Change status inline via dropdown (Pending → In Progress → Completed)

---

## 📊 Reports Available

- **Monthly Revenue** — bar + line combo chart per year
- **Order Status Distribution** — doughnut chart
- **Top 5 Products** by revenue
- **Top 5 Customers** by total spend
- **Daily Summary** — drill down to specific month

---

## 🔧 Customization Tips

- **Add users**: INSERT into `users` table with SHA2 hashed password
- **Change tax rate**: Search `0.18` in `app.py` → update to your GST rate
- **Add product categories**: Update the `<select>` options in `product_form.html`
- **Currency**: All amounts use ₹ (Indian Rupee) — search/replace for other currencies
