# gRPC & Protocol Buffer Contracts

## 1. Why gRPC Internally?
While public clients communicate via HTTP/JSON REST through the API Gateway, internal synchronous RPCs between microservices (e.g. Order Service querying Product catalog validation) utilize **gRPC / Protocol Buffers** over **HTTP/2**:
1. **Binary Serialization**: Protobuf serialization is up to 5-10x faster and significantly more compact than JSON.
2. **Strict Schema Contracts**: Strongly-typed `.proto` files act as a single source of truth across service boundaries.
3. **HTTP/2 Multiplexing**: Multiple concurrent requests share a single persistent TCP connection, eliminating connection handshake latency.
4. **Timeouts & Deadlines**: Built-in deadline propagation across distributed hops.

---

## 2. Proto Service Definitions

### 2.1 Product Service Contract (`proto/product.proto`)
```protobuf
syntax = "proto3";

package product;

service ProductService {
  rpc GetProduct (GetProductRequest) returns (ProductResponse);
  rpc ValidateProducts (ValidateProductsRequest) returns (ValidateProductsResponse);
}
```

### 2.2 Inventory Service Contract (`proto/inventory.proto`)
```protobuf
syntax = "proto3";

package inventory;

service InventoryService {
  rpc GetStock (GetStockRequest) returns (GetStockResponse);
  rpc ReserveStock (ReserveStockRequest) returns (ReserveStockResponse);
  rpc ReleaseStock (ReleaseStockRequest) returns (ReleaseStockResponse);
  rpc ConfirmStock (ConfirmStockRequest) returns (ConfirmStockResponse);
}
```

### 2.3 Order Service Contract (`proto/order.proto`)
```protobuf
syntax = "proto3";

package order;

service OrderService {
  rpc GetOrder (GetOrderRequest) returns (OrderResponse);
  rpc GetOrderStatus (GetOrderStatusRequest) returns (OrderStatusResponse);
}
```

---

## 3. Compilation & Regeneration
To recompile all Protocol Buffer stubs into Python code:
```bash
make compile-proto
# or:
uv run python scripts/compile_proto.py
```
Generated files are placed in `shared/grpc_gen/proto/` and automatically patched for clean Python module imports.
