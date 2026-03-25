-- ============================================================
--  Woodwork & Carpentry ERP — MySQL Schema
--  Run: mysql -u root -p < schema.sql
-- ============================================================

CREATE DATABASE IF NOT EXISTS woodwork_erp CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE woodwork_erp;

-- Users (Admin, Manager, Carpenter)
CREATE TABLE IF NOT EXISTS users (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    username    VARCHAR(50) UNIQUE NOT NULL,
    password    VARCHAR(64) NOT NULL,  -- SHA-256 hex
    role        ENUM('admin','manager','carpenter') DEFAULT 'carpenter',
    email       VARCHAR(100),
    phone       VARCHAR(20),
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Customers
CREATE TABLE IF NOT EXISTS customers (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    name       VARCHAR(100) NOT NULL,
    email      VARCHAR(100),
    phone      VARCHAR(20),
    address    TEXT,
    notes      TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Products / Catalog
CREATE TABLE IF NOT EXISTS products (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    name           VARCHAR(100) NOT NULL,
    category       VARCHAR(50),
    description    TEXT,
    wood_type      VARCHAR(50),
    dimensions     VARCHAR(100),
    finish         VARCHAR(50),
    base_price     DECIMAL(10,2) NOT NULL DEFAULT 0,
    labor_cost     DECIMAL(10,2) NOT NULL DEFAULT 0,
    material_cost  DECIMAL(10,2) NOT NULL DEFAULT 0,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Orders
CREATE TABLE IF NOT EXISTS orders (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    customer_id   INT NOT NULL,
    status        ENUM('Pending','In Progress','Quality Check','Ready','Delivered','Cancelled') DEFAULT 'Pending',
    delivery_date DATE,
    notes         TEXT,
    total_amount  DECIMAL(10,2) DEFAULT 0,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE
);

-- Order Items
CREATE TABLE IF NOT EXISTS order_items (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    order_id    INT NOT NULL,
    product_id  INT NOT NULL,
    quantity    INT DEFAULT 1,
    unit_price  DECIMAL(10,2),
    FOREIGN KEY (order_id)   REFERENCES orders(id)   ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(id)
);

-- Inventory
CREATE TABLE IF NOT EXISTS inventory (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    name           VARCHAR(100) NOT NULL,
    category       VARCHAR(50),
    unit           VARCHAR(20) DEFAULT 'pcs',
    quantity       DECIMAL(10,2) DEFAULT 0,
    min_stock      DECIMAL(10,2) DEFAULT 5,
    cost_per_unit  DECIMAL(10,2) DEFAULT 0,
    supplier       VARCHAR(100),
    location       VARCHAR(100),
    updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Tasks / Work Assignments
CREATE TABLE IF NOT EXISTS tasks (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    order_id          INT,
    assigned_to       INT,
    title             VARCHAR(200) NOT NULL,
    description       TEXT,
    due_date          DATE,
    status            ENUM('Pending','In Progress','Completed','On Hold') DEFAULT 'Pending',
    labor_hours       DECIMAL(5,2) DEFAULT 0,
    inventory_item_id INT,
    material_used     DECIMAL(10,2) DEFAULT 0,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (order_id)    REFERENCES orders(id)    ON DELETE SET NULL,
    FOREIGN KEY (assigned_to) REFERENCES users(id)     ON DELETE SET NULL,
    FOREIGN KEY (inventory_item_id) REFERENCES inventory(id) ON DELETE SET NULL
);

-- Invoices
CREATE TABLE IF NOT EXISTS invoices (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    order_id       INT NOT NULL,
    customer_id    INT NOT NULL,
    subtotal       DECIMAL(10,2) DEFAULT 0,
    tax            DECIMAL(10,2) DEFAULT 0,
    total_amount   DECIMAL(10,2) DEFAULT 0,
    material_cost  DECIMAL(10,2) DEFAULT 0,
    labor_cost     DECIMAL(10,2) DEFAULT 0,
    status         ENUM('Unpaid','Paid','Overdue') DEFAULT 'Unpaid',
    paid_at        TIMESTAMP NULL,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (order_id)    REFERENCES orders(id)    ON DELETE CASCADE,
    FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE
);

-- ============================================================
--  SEED DATA
-- ============================================================

-- Default admin user (password: admin123)
INSERT INTO users (username, password, role, email) VALUES
('admin',    SHA2('admin123',256),    'admin',     'admin@woodcraft.com'),
('manager',  SHA2('manager123',256),  'manager',   'manager@woodcraft.com'),
('rajan',    SHA2('rajan123',256),    'carpenter', 'rajan@woodcraft.com'),
('selvam',   SHA2('selvam123',256),   'carpenter', 'selvam@woodcraft.com'),
('murugan',  SHA2('murugan123',256),  'carpenter', 'murugan@woodcraft.com');

-- Sample customers
INSERT INTO customers (name, email, phone, address, notes) VALUES
('Aravind Kumar',    'aravind@example.com',  '9876543210', '12, Anna Nagar, Chennai',       'Prefers teak wood'),
('Priya Rajesh',     'priya@example.com',    '9765432109', '45, RS Puram, Coimbatore',       'Corporate client'),
('Senthil Nathan',   'senthil@example.com',  '9654321098', '78, Fairlands, Salem',           ''),
('Meena Sundaram',   'meena@example.com',    '9543210987', '23, Brookfields, Trichy',        'Repeat customer'),
('Vijay Anandan',    'vijay@example.com',    '9432109876', '56, Peelamedu, Coimbatore',      'Budget conscious'),
('Kavitha Raman',    'kavitha@example.com',  '9321098765', '89, Alagapuram, Salem',          '');

-- Product catalog
INSERT INTO products (name, category, description, wood_type, dimensions, finish, base_price, labor_cost, material_cost) VALUES
('Dining Table 6-Seater',   'Furniture',   'Classic solid wood dining table',      'Teak',       '180x90x75 cm',   'Polished',    25000, 8000, 12000),
('King Bed Frame',           'Furniture',   'Sturdy king-size bed frame',            'Rosewood',   '200x180x45 cm',  'Lacquered',   32000, 10000, 15000),
('Wardrobe 3-Door',          'Storage',     'Three-door sliding wardrobe',           'Plywood',    '210x150x60 cm',  'Laminated',   18000, 6000,  9000),
('Kitchen Cabinet Set',      'Cabinetry',   'Modular kitchen cabinet set (10 units)','MDF',        'Custom',         'PU Coated',   45000, 15000, 22000),
('Bookshelf 5-Tier',         'Storage',     'Open bookshelf unit',                   'Sheesham',   '180x90x30 cm',   'Natural Oil', 8500,  2500,  4000),
('TV Unit Modern',           'Furniture',   'Low-lying TV cabinet with drawers',     'Plywood+MDF','160x45x40 cm',   'Matte',       12000, 4000,  6000),
('Wooden Front Door',        'Doors',       'Solid panel main entrance door',        'Teak',       '210x90x6 cm',    'Varnished',   18000, 7000,  9000),
('Study Table',              'Furniture',   'Student/home office work table',        'Sheesham',   '120x60x75 cm',   'Polished',    7500,  2000,  3500),
('Corner Cabinet',           'Storage',     'L-shaped corner storage unit',          'MDF',        '90x90x180 cm',   'Laminated',   9500,  3000,  4500),
('Pooja Mandir Unit',        'Specialty',   'Traditional wooden pooja unit',         'Teak',       '180x60x30 cm',   'Gold Paint',  14000, 5000,  7000);

-- Inventory
INSERT INTO inventory (name, category, unit, quantity, min_stock, cost_per_unit, supplier, location) VALUES
('Teak Planks',       'Wood',      'sqft',  450,   50,   85,   'Sriram Timber, Salem',      'Rack A1'),
('Rosewood Planks',   'Wood',      'sqft',  200,   30,   120,  'Timber World, Coimbatore',  'Rack A2'),
('Sheesham Wood',     'Wood',      'sqft',  180,   30,   75,   'Sriram Timber, Salem',      'Rack A3'),
('Plywood 18mm',      'Sheet',     'sheet', 80,    15,   1200, 'National Ply, Chennai',     'Rack B1'),
('MDF 12mm',          'Sheet',     'sheet', 60,    10,   800,  'National Ply, Chennai',     'Rack B2'),
('PU Polish',         'Finish',    'ltr',   25,    5,    450,  'Asian Paints, Salem',       'Cabinet C1'),
('Lacquer',           'Finish',    'ltr',   18,    5,    380,  'Asian Paints, Salem',       'Cabinet C1'),
('Wood Screws Box',   'Hardware',  'box',   40,    10,   250,  'Hardware Hub, Salem',       'Cabinet C2'),
('Hinges (pairs)',    'Hardware',  'pcs',   120,   20,   45,   'Hardware Hub, Salem',       'Cabinet C2'),
('Sandpaper Roll',    'Consumable','roll',  35,    10,   150,  'Local Supplier',            'Cabinet C3'),
('Wood Glue',         'Consumable','kg',    22,    5,    280,  'Fevicol Distributor',       'Cabinet C3'),
('Teak Oil',          'Finish',    'ltr',   12,    3,    520,  'Asian Paints, Salem',       'Cabinet C1');

-- Sample orders
INSERT INTO orders (customer_id, status, delivery_date, notes, total_amount) VALUES
(1, 'In Progress',   DATE_ADD(NOW(), INTERVAL 14 DAY), 'Please use first grade teak',  25000),
(2, 'Pending',       DATE_ADD(NOW(), INTERVAL 21 DAY), 'Corporate office furniture',   57000),
(3, 'Quality Check', DATE_ADD(NOW(), INTERVAL 5 DAY),  '',                             18000),
(4, 'Ready',         DATE_ADD(NOW(), INTERVAL 2 DAY),  'Call before delivery',         32000),
(5, 'Delivered',     DATE_SUB(NOW(), INTERVAL 5 DAY),  '',                             7500),
(1, 'Pending',       DATE_ADD(NOW(), INTERVAL 30 DAY), 'Second order - full bedroom',  32000);

-- Order items
INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES
(1, 1, 1, 25000),
(2, 4, 1, 45000), (2, 8, 1, 7500), (2, 6, 1, 4500),
(3, 3, 1, 18000),
(4, 2, 1, 32000),
(5, 5, 1, 7500),
(6, 2, 1, 32000);

-- Tasks
INSERT INTO tasks (order_id, assigned_to, title, description, due_date, status, labor_hours) VALUES
(1, 3, 'Cut teak planks to size',        'Cut planks for dining table top and legs', DATE_ADD(NOW(), INTERVAL 3 DAY),  'In Progress', 8),
(1, 4, 'Assemble table frame',           'Join legs and supports, sand edges',       DATE_ADD(NOW(), INTERVAL 7 DAY),  'Pending',     12),
(2, 3, 'Kitchen cabinet cutting',        'Cut MDF sheets per kitchen layout',        DATE_ADD(NOW(), INTERVAL 10 DAY), 'Pending',     16),
(3, 5, 'Wardrobe final finishing',       'Apply laminate and fit sliding doors',     DATE_ADD(NOW(), INTERVAL 2 DAY),  'In Progress', 6),
(4, 4, 'Bed frame quality check',        'Check joints, polish, and pack for delivery', DATE_ADD(NOW(), INTERVAL 1 DAY), 'Pending', 4);

-- Invoices
INSERT INTO invoices (order_id, customer_id, subtotal, tax, total_amount, material_cost, labor_cost, status, paid_at) VALUES
(5, 5, 7500, 1350, 8850, 3500, 2000, 'Paid', NOW()),
(4, 4, 32000, 5760, 37760, 15000, 10000, 'Unpaid', NULL);
