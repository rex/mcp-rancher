# Capability Catalog

This file describes the capability taxonomy for the "perfect" Rancher MCP server.

The machine-readable source of truth is [catalog/capabilities.yaml](/Users/pierce/Code/mcp-servers/mcp-rancher/catalog/capabilities.yaml).

## Principles

- Primary compatibility target is Rancher `2.6.5`
- Discovery and schema coverage are mandatory
- Generic fallback tools are mandatory for exhaustiveness
- Curated operator tools are mandatory for usability
- Multi-instance support is a first-class concern

## Capability Families

- discovery and schema
- server settings and health
- authentication and identity
- users, groups, API keys, principals
- global authorization and role templates
- cluster lifecycle and access
- provisioning infrastructure and drivers
- nodes
- projects, namespaces, quotas, and limits
- cluster and project RBAC
- workloads
- pods
- services and networking
- storage and snapshots
- Longhorn
- config, secrets, and service accounts
- catalogs, apps, Helm, and extensions
- Fleet and GitOps
- monitoring, alerting, and notifications
- logging
- compliance and policy
- certificates and TLS
- backup, restore, and disaster recovery
- diagnostics and observability
- generic Kubernetes and Rancher escape hatches

## Strategy

The implementation strategy is:

1. encode the capability surface in machine-readable form
2. build discovery and generic fallback tools first
3. layer curated operator workflows on top
4. validate capability behavior against live Rancher `2.6.5`
