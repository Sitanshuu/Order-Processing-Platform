# Distributed Systems & SDE-2 Interview Preparation Guide

---

## 1. The 90-Second Project Elevator Pitch

> *"I designed and built an **Event-Driven Order Processing Platform** using Python 3.12, FastAPI, gRPC, RabbitMQ, PostgreSQL, MongoDB, and Redis, structured strictly around the **database-per-service** microservices architecture.*
>
> *The system coordinates distributed order lifecycles across six autonomous services. To solve the classic **dual-write problem**, I implemented the **Transactional Outbox Pattern** in the Order Service, ensuring that DB state commits and message publications to RabbitMQ are atomic. To manage distributed data consistency without fragile distributed 2PC transactions, I implemented a **Choreographed Saga Pattern** with automated compensating actions—such as auto-refunding payments if inventory reservation fails.*
>
> *For high-concurrency hotspots like checkout, I prevented overselling using **atomic conditional updates and row-level locking** in PostgreSQL. I also built **multi-layered idempotency** using Redis distributed locks and DB unique constraints to guarantee that at-least-once message delivery never creates duplicate charges or reservations. Finally, I used **gRPC/Protocol Buffers over HTTP/2** for low-latency internal queries and **MongoDB** for append-only distributed event auditing and trace reconstruction."*

---

## 2. Comprehensive Interview Question Bank

### Category 1: Architecture & Design Decisions

#### Q1: Why microservices instead of a modular monolith for this system?
- **Short Answer:** To isolate failure domains, scale read-heavy services (Product/Catalog) independently from write-heavy transactional services (Order/Inventory), and enforce strict data boundaries with database-per-service.
- **Detailed Technical Answer:** In an e-commerce checkout platform, different services experience vastly different traffic characteristics. The Product Service experiences 90%+ read traffic (suitable for aggressive Redis cache-aside), while the Inventory and Payment services handle high-write contention requiring strict row-level isolation and event stream processing. Decoupling them prevents a spike in payment gateway retries from degrading catalog browsing or inventory lookups.
- **Trade-offs:** Microservices introduce network latency, distributed data consistency challenges (requiring Sagas and Outbox patterns), and operational complexity.
- **Code Reference:** See `docker-compose.yml` and `services/`.

#### Q2: Why use both RabbitMQ (Asynchronous) and gRPC (Synchronous)?
- **Short Answer:** gRPC is used for point-to-point, low-latency, synchronous queries (e.g., Order Service validating catalog price with Product Service); RabbitMQ is used for state-changing, decoupled event workflows (e.g., Order Created -> Payment -> Stock Reservation).
- **Detailed Explanation:** 
  - **Synchronous (gRPC)**: Query operations where the caller cannot proceed without an immediate response. Protobuf binary encoding and HTTP/2 multiplexing reduce serialization overhead and connection handshake times.
  - **Asynchronous (RabbitMQ)**: Mutating business actions across service boundaries. If Payment Service experiences temporary latency or downstream spikes, asynchronous message buffering ensures the Order Service doesn't block or drop client requests.
- **Code Reference:** `proto/inventory.proto`, `shared/messaging/rabbitmq.py`.

---

### Category 2: RabbitMQ & Message Broker Mechanics

#### Q3: How do you prevent message loss and poison-pill crashes in RabbitMQ?
- **Short Answer:** Durable exchanges and queues, persistent delivery mode (`delivery_mode=2`), explicit manual ACKs, and Dead Letter Exchanges (DLX).
- **Detailed Explanation:**
  1. Messages are written to disk (`delivery_mode=PERSISTENT`).
  2. The consumer disables `auto_ack=True`. Only when the business transaction successfully commits is `message.ack()` called.
  3. If an unrecoverable exception occurs, the consumer rejects the message (`message.reject(requeue=False)`), causing RabbitMQ to route the message to `dlx.events` (DLX) and into `*.dlq` queues rather than infinite crash-looping.
- **Code Reference:** `shared/messaging/rabbitmq.py` lines 40-120.

#### Q4: What is Prefetch Count (QoS) and why is it crucial?
- **Short Answer:** It limits the number of unacknowledged messages RabbitMQ delivers to a consumer worker at one time.
- **Detailed Explanation:** Without prefetch limits (default is unlimited), RabbitMQ pushes all queued messages to the first connected consumer. If that consumer becomes slow or encounters a heavy task, it holds all messages in memory while other worker replicas remain idle. Setting `prefetch_count=10` ensures even load distribution and prevents consumer Out-Of-Memory (OOM) crashes.

---

### Category 3: Distributed Transactions, Saga & Transactional Outbox

#### Q5: What is the Dual-Write Problem and how does the Transactional Outbox solve it?
- **Short Answer:** The dual-write problem occurs when an application must update a database and publish a message to a broker. If the broker is unreachable or the app crashes between the DB commit and the broker publish, state becomes permanently inconsistent.
- **Detailed Explanation:** The Transactional Outbox pattern guarantees atomicity by writing the entity and an `outbox_events` record in the **same local database transaction**. A separate background worker (`OutboxPublisherWorker`) asynchronously reads unpublished records, publishes them to RabbitMQ, and marks them as `PUBLISHED`.
- **Code Reference:** `services/order_service/repository.py` (`create_order_with_outbox`), `services/order_service/outbox_publisher.py`.

#### Q6: Explain how your Saga handles compensating rollbacks.
- **Short Answer:** Choreographed Saga using domain events: if inventory reservation fails, an `InventoryReservationFailed` event is published, triggering `PaymentService` to execute a refund and `OrderService` to transition the order to `CANCELLED`.
- **Detailed Flow:**
  1. `OrderCreated` -> `PaymentCompleted`
  2. `PaymentCompleted` -> `InventoryReservationFailed` (Stock was 0)
  3. `PaymentService` consumes `InventoryReservationFailed` -> executes refund -> publishes `PaymentRefunded`.
  4. `OrderService` consumes `PaymentRefunded` -> transitions order state from `REFUND_PENDING` -> `REFUNDED` -> `CANCELLED`.
- **Code Reference:** `tests/integration/test_saga_flow.py` (`test_saga_failure_and_compensating_refund`).

---

### Category 4: Concurrency & Database Locking

#### Q7: How do you guarantee zero overselling under 100 concurrent requests for 1 remaining item?
- **Short Answer:** Using atomic conditional SQL updates with row-level locks: `UPDATE inventory_items SET reserved_quantity = reserved_quantity + :qty WHERE product_id = :id AND (total_quantity - reserved_quantity) >= :qty`.
- **Detailed Explanation:** The database engine's row lock guarantees that only the first transaction satisfying the conditional clause modifies the row and returns `rowcount = 1`. All subsequent 99 concurrent transactions evaluate against the updated state, find `rowcount = 0`, and immediately raise `InsufficientStockException`.
- **Code Reference:** `services/inventory_service/repository.py` (`reserve_stock`), `tests/concurrency/test_inventory_concurrency.py`.

---

### Category 5: Idempotency & Caching

#### Q8: How does the system handle duplicate requests and redelivered events?
- **Short Answer:** A two-tier idempotency strategy: Redis distributed locks (`SETNX` with TTL) for HTTP requests and PostgreSQL unique constraint tables (`processed_events`) for event consumers.
- **Detailed Explanation:**
  - **API Layer**: Clients send `Idempotency-Key: <UUID>`. The gateway/service queries Redis `idempotency:<key>`. If status is `COMPLETED`, it returns the cached response immediately.
  - **Consumer Layer**: Each event has a unique `event_id`. When a consumer processes a message, it inserts `event_id` into `processed_events`. If a duplicate message arrives due to network redelivery, the consumer detects the existing record and ACKs without re-executing side effects.
- **Code Reference:** `shared/idempotency/redis_idempotency.py`, `services/order_service/routes.py`.
