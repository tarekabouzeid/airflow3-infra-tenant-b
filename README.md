# airflow3-infra-tenant-b

Tenant configuration for **tenant-b** on the [airflow3-infra](https://github.com/tarekabouzeid/airflow3-infra)
multi-tenant Airflow 3 / Argo CD platform.

tenant-b's home cluster is `af-work-b`, with `af-work-a` as its remote workload cluster -
deliberately the mirror image of tenant-a (home `af-work-a`, remote `af-work-b`), so together the
two tenants exercise both clusters as "home" and as "remote".

This repo owns exactly three things - the platform owns everything else (chart shape, RBAC,
namespaces, Vault wiring):

- `deploy/airflow/values.yaml` - Helm value overrides for this tenant's Airflow deployment
  (image tag, resource sizing). Merged *underneath* the platform's own wiring values, so nothing
  here can override the Vault/ServiceAccount/DAG-source configuration the platform controls.
- `deploy/workloads/` - a small Helm chart deployed into `tenant-b-workloads` on every cluster
  this tenant targets (its home cluster and any remote cluster). Declares a `SecretStore` +
  `ExternalSecret` pulling this tenant's workload secrets out of Vault.
- `dags/` - this tenant's DAGs, loaded onto the Airflow DAGs PVC by a platform-owned loader Job
  on every Argo CD sync. Exactly two DAGs live here by design: one integration test per
  supported workload type (`KubernetesPodOperator`, `SparkKubernetesOperator`), each running
  once against the local cluster and once against the remote cluster.

See the platform repo's `docs/runbook-tenant-onboarding.md` for how this repo is wired in, and
`docs/architecture.md` for the full design.
