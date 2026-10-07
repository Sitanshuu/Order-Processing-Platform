# Database Design & Polyglot Persistence

## 1. Storage Strategy

The platform applies **Polyglot Persistence**, selecting storage engines based on the specific access patterns and consistency requirements of each microservice.

| Service | Database Engine | Primary Reason | Tables / Collections |
| :--- | :--- | :--- | :--- |
| **Order Service** | PostgreSQL | Strict ACID consistency for financial & lifecycle states, row locks, outbox atomicity. | `orders`, `order_items`, `outbox_events`, `processed_events` |
| **Product Service** | PostgreSQL + Redis | Relational categories/SKUs with high read-to-write ratio cached in Redis. | `products`, `categories` |
| **Inventory Service**| PostgreSQL | Pessimistic row locking (`SELECT FOR UPDATE`) to prevent overselling under high concurrency. | `inventory_items`, `inventory_reservations`, `processed_events` |
| **Payment Service**  | PostgreSQL | Financial ledger records, unique transaction IDs, refund linkages. | `payments`, `refunds`, `processed_events` |
| **Notification Service** | MongoDB (Beanie) | High-volume, semi-structured communication logs with flexible templating. | `notifications` |
| **Audit Service**    | MongoDB (Beanie) | Append-only event stream with dynamic JSON payload structures. | `audit_events` |

---

## 2. PostgreSQL Schemas

### 2.1 Order Service (`order_db`)
```sql
CREATE TABLE orders (
    id VARCHAR(36) PRIMARY KEY,
    customer_id VARCHAR(36) NOT NULL,
    total_amount DOUBLE PRECISION NOT NULL,
    currency VARCHAR(3) DEFAULT 'USD' NOT NULL,
    status VARCHAR(30) DEFAULT 'PENDING' NOT NULL,
    idempotency_key VARCHAR(64) UNIQUE NOT NULL,
    correlation_id VARCHAR(64) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

CREATE TABLE order_items (
    id VARCHAR(36) PRIMARY KEY,
    order_id VARCHAR(36) REFERENCES orders(id) ON DELETE CASCADE,
    product_id VARCHAR(36) NOT NULL,
    product_name VARCHAR(200) NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price DOUBLE PRECISION NOT NULL,
    subtotal DOUBLE PRECISION NOT NULL
);

CREATE TABLE outbox_events (
    id VARCHAR(36) PRIMARY KEY,
    aggregate_type VARCHAR(50) DEFAULT 'Order' NOT NULL,
    aggregate_id VARCHAR(36) NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    payload TEXT NOT NULL,
    status VARCHAR(20) DEFAULT 'PENDING' NOT NULL,
    retry_count INTEGER DEFAULT 0 NOT NULL,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    published_at TIMESTAMP WITH TIME ZONE
);
CREATE INDEX ix_outbox_status_created ON outbox_events(status, created_at);
```

### 2.2 Inventory Service (`inventory_db`)
```sql
CREATE TABLE inventory_items (
    id VARCHAR(36) PRIMARY KEY,
    product_id VARCHAR(36) UNIQUE NOT NULL,
    total_quantity INTEGER DEFAULT 0 NOT NULL CHECK (total_quantity >= 0),
    reserved_quantity INTEGER DEFAULT 0 NOT NULL CHECK (reserved_quantity >= 0),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    CONSTRAINT chk_reserved_lte_total CHECK (reserved_quantity <= total_quantity)
);

CREATE TABLE inventory_reservations (
    id VARCHAR(36) PRIMARY KEY,
    order_id VARCHAR(36) NOT NULL,
    product_id VARCHAR(36) NOT NULL,
    quantity INTEGER NOT NULL,
    status VARCHAR(30) DEFAULT 'RESERVED' NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);
CREATE INDEX ix_res_order_product ON inventory_reservations(order_id, product_id);
```

---

## 3. MongoDB Schemas (Beanie ODM)

### 3.1 Audit Event Document (`audit_db.audit_events`)
```json
{
  "_id": "ObjectId",
  "event_id": "UUID",
  "event_type": "OrderCreated",
  "event_version": 1,
  "source_service": "order-service",
  "correlation_id": "UUID",
  "causation_id": "UUID",
  "payload": {},
  "occurred_at": "ISO-8601 UTC",
  "ingested_at": "ISODate"
}
```
Indexes:
- `event_id` (Unique)
- `correlation_id`
- `event_type`
- `ingested_at`
