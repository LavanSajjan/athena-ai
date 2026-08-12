ADR-0010: Query Resource Governance

Status: Accepted

Decision

Athena establishes an initial bounded policy for public dataset queries:

- external DuckDB access is disabled;
- DuckDB memory is limited to 512 MB per query connection;
- query execution is interrupted after 30 seconds; and
- the public API rejects results over 10,000 rows.

These values are configurable through application settings. DuckDB enforces
external-access and memory controls in its isolated in-memory connection. The
DuckDB adapter owns the execution timeout because it owns the connection;
DatasetQueryService owns the API result-row policy. Results are rejected rather
than silently truncated so callers know the response exceeded the public bound.

Context and consequences

Public SELECT syntax alone does not prevent unbounded resource consumption.
These controls keep the existing DatasetQueryService -> DuckDBQueryEngine flow
and do not change Dataset identity or ADR-0008 reference semantics.

Background jobs, streaming, SQL parsing or AST governance, authorization,
per-user quotas, and distributed execution are intentionally not introduced.
They require separate product and operational decisions.
