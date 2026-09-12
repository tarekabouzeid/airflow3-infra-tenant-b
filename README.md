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

## Choosing a queue

Every pod this tenant runs in `tenant-b-workloads` goes through Kueue before it is allowed to
start. You pick which of **two lanes** it draws capacity from, with one label:

| Lane   | What you get                                                                  | Use it for |
|--------|-------------------------------------------------------------------------------|------------|
| `high` | This tenant's **guaranteed** share. Reserved whether or not anyone else is busy, and reclaimed from anyone who borrowed it. | Work with a deadline; anything downstream depends on. |
| `low`  | **Opportunistic.** Runs on capacity nobody is using right now, and is the first thing evicted when they want it back. Costs nothing against the guaranteed share. | Backfills, retries, anything that can wait. |

On a `KubernetesPodOperator` task, as a pod label:

```python
KubernetesPodOperator(
    ...,
    labels={"kueue.x-k8s.io/queue-name": "high"},
)
```

On a `SparkApplication`, on the **SparkApplication's own** `metadata.labels` - not on the driver
or executor pod templates (see `dags/spark/spark_pi.yaml`):

```yaml
metadata:
  labels:
    kueue.x-k8s.io/queue-name: low
```

Omit the label and the task runs in `low`. There is no way to opt out of queueing - the platform
manages every workload in this namespace whether or not it carries a queue label - and the pod's
scheduling `priorityClassName` is derived from this label by the platform, so the lane and the
priority cannot be set to disagree.

### What is not yours to set

These are cluster-wide and platform-owned, and there is no value you can put in a DAG that
changes them:

- **Gang scheduling.** A Spark job is admitted only when its driver *and every executor* fit at
  once; it never half-starts with a driver holding capacity its executors are still waiting for.
  This applies in both lanes.
- **How big each lane is.** Set per-tenant per-cluster in the platform registry
  (`platform/tenants/tenant-b/workloads-<cluster>.yaml`). Ask the platform team.
- **Which registries you may pull from, per-container resource ceilings, the PriorityClasses you
  may name, Pod Security Standards, host ports, node pinning, Service types.** Enforced at
  admission - a pod that breaks one of these is rejected by the API server, not silently
  deprioritised. The platform repo's `docs/runbook-governance.md` lists every rule and what it
  rejects.

See the platform repo's `docs/runbook-tenant-onboarding.md` for how this repo is wired in,
`docs/runbook-governance.md` for the governance model, and `docs/architecture.md` for the full
design.
