ADR-0009: Durable Dataset Catalog

Status: Accepted

Date: 2026-08-12

Decision

Athena persists registered Datasets through a DatasetRepository port. The first
adapter is SQLiteDatasetRepository, implemented with Python's sqlite3 module.
It uses transactional, numbered schema migrations and is initialized and closed
by the FastAPI lifespan.

DatasetService remains responsible for Dataset lifecycle operations and depends
on the repository port rather than an in-memory registry. Profiling and query
services continue to resolve Dataset IDs only through DatasetService.

Identity and provider boundary

ADR-0008 remains in force. Dataset.id is catalog identity; Dataset.reference is
stored unchanged as an opaque provider retrieval handle; Dataset.asset_uri is
descriptive metadata and is never used to reconstruct a reference. A generic
provider_id is persisted for provenance and future provider routing, without
placing provider-specific semantics in the Dataset domain. provider_id is not
exposed by the public Dataset API.

Consequences

Registrations survive application restart on the configured host. SQLite is a
zero-dependency, single-host catalog choice appropriate to the present local
provider architecture. It is not the future multi-host or horizontally scaled
catalog solution; a later Postgres adapter can implement the same repository
port. Source revalidation, duplicate policy, status transitions, provider
routing, and profile-result persistence remain outside this decision.
