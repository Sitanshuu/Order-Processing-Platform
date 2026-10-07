import os
import sys
import re
from grpc_tools import protoc

def compile_proto():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    proto_dir = os.path.join(base_dir, "proto")
    out_dir = os.path.join(base_dir, "shared", "grpc_gen", "proto")
    
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(base_dir, "shared", "grpc_gen", "__init__.py"), "w") as f:
        f.write("# Generated gRPC package\n")
    with open(os.path.join(out_dir, "__init__.py"), "w") as f:
        f.write("# Proto package\n")
            
    proto_files = [
        "common.proto",
        "inventory.proto",
        "product.proto",
        "order.proto",
    ]
    
    for pf in proto_files:
        proto_path = os.path.join(proto_dir, pf)
        cmd = [
            "grpc_tools.protoc",
            f"-I{proto_dir}",
            f"--python_out={out_dir}",
            f"--grpc_python_out={out_dir}",
            f"--pyi_out={out_dir}",
            proto_path
        ]
        print(f"Compiling {pf}...")
        res = protoc.main(cmd)
        if res != 0:
            print(f"Error compiling {proto_path}")
            sys.exit(res)
            
    # Fix imports in generated python files so they import from shared.grpc_gen.proto
    for fname in os.listdir(out_dir):
        if fname.endswith(".py"):
            fpath = os.path.join(out_dir, fname)
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()

            # Replace 'import common_pb2 as' -> 'from shared.grpc_gen.proto import common_pb2 as'
            content = re.sub(
                r'import (common_pb2|inventory_pb2|product_pb2|order_pb2) as',
                r'from shared.grpc_gen.proto import \1 as',
                content
            )
            # Replace 'from proto import' -> 'from shared.grpc_gen.proto import'
            content = re.sub(
                r'from proto import',
                r'from shared.grpc_gen.proto import',
                content
            )
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(content)

    print("All proto files successfully compiled and patched in shared/grpc_gen/proto!")

if __name__ == "__main__":
    compile_proto()
