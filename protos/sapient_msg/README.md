# SAPIENT (BSI Flex 335) Protocol Definitions

This directory contains the vendored Protocol Buffer (`.proto`) sources for the BSI Flex 335 v2.0 SAPIENT message set — the wire format this generator's synthetic sensor output is compliant with.

## Provenance

Sourced from Dstl's public [`dstl/SAPIENT-Proto-Files`](https://github.com/dstl/SAPIENT-Proto-Files) repository (Crown Copyright, Apache 2.0), `bsi_flex_335_v2_0/` and `proto_options.proto` at the repository root, verified byte-identical against the `main` branch as of 2026-08-04.

The version in use is `BSI_Flex_335_v2.0`, as declared by `sapient_msg.bsi_flex_335_v2_0.sapient_message`'s `(file_options).standard_version`.

## Generated bindings

`src/sapient_msg/**/*_pb2.py` is generated from this tree and checked in; nothing under `src/sapient_msg/` should be hand-edited. Regenerate after changing anything under `protos/` with `grpcio-tools==1.78.0` installed (available via the `dev` extra: `pip install -e ".[dev]"`), from the repository root:

```bash
python -m grpc_tools.protoc \
  --proto_path=protos \
  --python_out=src \
  protos/sapient_msg/proto_options.proto \
  protos/sapient_msg/bsi_flex_335_v2_0/*.proto
```

This is the exact command and pinned tool version used to generate the checked-in modules: running it from the repository root should regenerate the tree in place and produce no `git diff`.
