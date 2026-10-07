# Domain Event Catalog

Every domain event in the platform is strictly defined, versioned, and includes CloudEvents-aligned tracing metadata.

## Standard Envelope Contract
```json
{
  "event_id": "9f3e0987-a417-4828-97c1-11a5b82e21bb",
  "event_type": "OrderCreated",
  "event_version": 1,
  "occurred_at": "2026-10-07T10:00:00.000000Z",
  "correlation_id": "a6b1e6e2-2a78-4395-8839-81fc7e8a9190",
  "causation_id": "c1f72891-b3b4-4e3b-9a88-662ad788102a",
  "source": "order-service",
  "payload": {}
}
```

---

## Event Catalog Reference

| Event Type | Producer | Consumers | Exchange / Routing Key | Description |
| :--- | :--- | :--- | :--- | :--- |
| **`OrderCreated`** | `order-service` | `payment-service`, `notification-service`, `audit-service` | `order.events` / `order.created` | Emitted when order is placed and committed to local outbox. Initiates payment processing. |
| **`OrderConfirmed`** | `order-service` | `notification-service`, `audit-service` | `order.events` / `order.confirmed` | Emitted when both payment and inventory reservation succeed. |
| **`OrderCancelled`** | `order-service` | `inventory-service`, `notification-service`, `audit-service` | `order.events` / `order.cancelled` | Emitted on explicit customer cancellation or failed Saga steps. Triggers inventory stock release hold. |
| **`PaymentCompleted`** | `payment-service` | `inventory-service`, `order-service`, `notification-service`, `audit-service` | `payment.events` / `payment.completed` | Emitted upon successful payment charge. Triggers inventory stock reservation. |
| **`PaymentFailed`** | `payment-service` | `order-service`, `notification-service`, `audit-service` | `payment.events` / `payment.failed` | Emitted when payment is declined. Triggers order cancellation. |
| **`PaymentRefunded`** | `payment-service` | `order-service`, `notification-service`, `audit-service` | `payment.events` / `payment.refunded` | Emitted when compensation refund completes after inventory failure. |
| **`InventoryReserved`**| `inventory-service` | `order-service`, `notification-service`, `audit-service` | `inventory.events` / `inventory.reserved` | Emitted when stock is locked for the order items. Confirms order. |
| **`InventoryReservationFailed`** | `inventory-service` | `payment-service`, `order-service`, `notification-service`, `audit-service` | `inventory.events` / `inventory.reservation_failed` | Emitted when items are out of stock. Triggers compensating refund. |
| **`InventoryReleased`**| `inventory-service` | `notification-service`, `audit-service` | `inventory.events` / `inventory.released` | Emitted when reserved stock is returned to the available inventory pool. |
| **`NotificationSent`** | `notification-service` | `audit-service` | `notification.events` / `notification.sent` | Emitted when email/SMS simulated message is logged. |
