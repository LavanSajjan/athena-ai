ADR-0008: Dataset Asset Identity and Retrieval Reference

Status: Accepted

Date: 2026-08-10

Decision Type: Architecture

Scope: Dataset domain, storage boundary, dataset loading, profiling orchestration

Context

Athena AI has a Dataset domain, a provider-oriented storage abstraction, CSV/Excel loaders, and a DatasetProfiler.

The current flow for registering a dataset is:

DatasetService.register(reference)
        |
        v
StorageProvider.describe(reference)
        |
        v
StorageAsset
        |
        v
Dataset
        |
        v
DatasetRegistry

StorageAsset contains both descriptive metadata and the original storage retrieval reference.

The relevant distinction is:

StorageAsset.reference
    = retrieval input used by StorageProvider and loaders

StorageAsset.uri
    = provider-produced descriptive URI

Dataset.id
    = registered Dataset identity

Dataset.asset_uri
    = Dataset-level descriptive/public metadata

The existing loaders require the original provider-relative reference.

However, DatasetService.register() currently retains metadata such as name, extension/source_type, uri, size_bytes, and sha256, but discards StorageAsset.reference.

As a result, the current Dataset API can register and retrieve a Dataset by UUID, but it cannot subsequently resolve that Dataset into the reference required by the existing loaders.

The Dataset.asset_uri field cannot be treated as a replacement for the provider reference.

The current LocalStorageProvider accepts provider-relative references and rejects absolute paths and URI strings as retrieval inputs. The storage abstraction also does not define a reversible URI -> reference operation.

This distinction becomes more important as Athena is intended to support additional storage providers in the future:

LocalStorageProvider
S3StorageProvider
AzureBlobStorageProvider
GCSStorageProvider

Each provider may have its own reference semantics.

Decision

Athena will retain the original storage-provider reference when a Dataset is registered.

The retained reference is treated as an opaque provider-owned retrieval handle.

It is not interpreted by the Dataset domain.

The Dataset domain must not attempt to understand filesystem paths, S3 bucket/key semantics, Azure container/blob semantics, GCS bucket/object semantics, or provider-specific URI formats.

The provider reference is passed back through the appropriate storage/provider abstraction when the underlying asset needs to be loaded.

Identity distinction

Athena will maintain the following distinction:

Dataset.id
    = public/registry identity of the Dataset

Dataset.reference
    = opaque provider retrieval reference

Dataset.asset_uri
    = descriptive/public asset metadata

These values serve different purposes and must not be conflated.

API Boundary

The provider retrieval reference is an internal implementation concern.

It will not automatically be exposed through the public Dataset API.

The existing Dataset API remains conceptually:

POST /api/v1/datasets
GET  /api/v1/datasets
GET  /api/v1/datasets/{dataset_id}

The API may expose asset_uri as descriptive metadata, but clients should not be required to provide or understand the provider-specific retrieval reference.

A future profiling endpoint should therefore use the Dataset UUID:

POST /api/v1/datasets/{dataset_id}/profile

rather than requiring clients to resupply a storage reference.

Consequences

Positive consequences

A registered Dataset retains enough information to locate its underlying source again.

Existing CSV and Excel loaders can continue to consume their existing reference: str contract.

DatasetService does not need to reconstruct a reference from asset_uri.

The system does not require a URI-to-reference reverse-resolution mechanism.

Provider-specific storage semantics remain behind the storage boundary.

Future storage providers can define their own reference formats while satisfying the existing storage abstraction.

The public Dataset API does not need to expose infrastructure-specific retrieval details.

Negative consequences

The Dataset domain now retains an opaque provider-owned retrieval value.

The meaning of the reference depends on the configured storage provider.

A future persistent Dataset repository may need to persist provider identity together with the opaque reference.

The current in-memory DatasetRegistry does not provide durable Dataset storage.

Rejected Alternatives

Option A — Reconstruct the reference from asset_uri

Rejected.

The current storage abstraction does not guarantee that asset_uri -> reference is reversible.

For the local provider, multiple normalized references can resolve to the same underlying path/URI.

Therefore, treating asset_uri as a canonical retrieval locator would create an unsupported reverse-resolution contract.

Option B — Add URI-to-reference resolution to StorageProvider

Rejected as the primary solution.

The current StorageProvider contract does not establish URI reversibility.

Requiring every future provider to implement resolve_reference(asset_uri) would impose a capability that is not guaranteed to exist for all storage systems.

The retrieval reference should instead be retained when it is first supplied.

Option C — Store provider-specific storage metadata in Dataset

Rejected.

The Dataset domain should not gain knowledge of concepts such as bucket, container, object key, filesystem root, or blob path.

Such information belongs behind the storage/provider boundary.

Option D — Introduce persistence or caching

Not part of this decision.

The current Profiling API milestone is intentionally non-persistent.

Profiling persistence, caching, and durable Dataset storage are separate future architectural decisions.

Application-Service Boundary

DatasetService remains responsible for Dataset lifecycle operations:

register()
get()
list()

It should not become responsible for loader selection, data loading, profiling, or query execution.

A future profiling orchestration boundary should compose the existing components approximately as follows:

DatasetProfilingService
        |
        +-- DatasetService
        |
        +-- Loader selection
        |
        +-- Loader
        |
        +-- DatasetProfiler

Conceptually:

Dataset ID
    |
    v
DatasetProfilingService
    |
    +--> DatasetService.get()
    |
    +--> obtain opaque Dataset.reference
    |
    +--> select appropriate loader
    |
    +--> loader.load(reference)
    |
    +--> DatasetProfiler.profile(result)
    |
    v
ProfileResult

The responsibilities remain separated:

DatasetService
    -> Dataset lifecycle

StorageProvider
    -> storage access

Loader
    -> source parsing/loading

DatasetProfiler
    -> deterministic profiling

Profiling orchestration service
    -> composition of these capabilities

Future Provider Compatibility

The retained reference must be treated as opaque.

For example, future providers may use references with different semantics:

Local:
    data/customer.csv

S3:
    bucket/key

Azure:
    container/blob

GCS:
    bucket/object

The Dataset domain should not parse or interpret these formats.

Instead:

Dataset.reference
        |
        v
appropriate StorageProvider
        |
        v
underlying asset

This preserves the provider-oriented architecture.

A future persistent architecture may additionally need explicit provider identity together with the opaque reference.

That is intentionally deferred until durable multi-provider storage is introduced.

Profiling Implication

This decision enables the next planned milestone:

POST /api/v1/datasets/{dataset_id}/profile

The intended non-persistent flow is:

Dataset ID
    |
    v
DatasetService
    |
    v
Dataset
    |
    v
opaque provider reference
    |
    v
loader selection
    |
    v
CSVLoader / ExcelLoader
    |
    v
TabularLoadResult
    |
    v
DatasetProfiler
    |
    v
ProfileResult
    |
    v
API response

No profiling result persistence is introduced by this ADR.

Scope Boundaries

This ADR does not authorize:

redesigning StorageProvider

adding URI reverse resolution

redesigning loaders

adding a loader framework beyond what the profiling orchestration requires

adding a database

adding caching

adding background processing

changing DatasetProfiler behavior

implementing the Profiling API itself

implementing future storage providers

Those decisions require separate analysis if they become necessary.

Validation Principle

The implementation following this ADR must preserve the existing project quality gates:

uv run ruff check .

uv run mypy apps packages tests

uv run pytest

No architectural change described by this ADR should be considered complete unless the existing test and static-analysis baseline remains intact.

Decision Summary

The decision can be summarized as:

Dataset.id
    = Dataset identity

Dataset.asset_uri
    = descriptive/public metadata

Dataset.reference
    = opaque provider retrieval handle

The reference is retained because it is required to reload the underlying asset and cannot safely be reconstructed from asset_uri.

The reference remains internal and provider-opaque.

DatasetService remains focused on Dataset lifecycle.

A future profiling orchestration service will compose DatasetService, loader selection, loaders, and DatasetProfiler without introducing persistence.