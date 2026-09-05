# Conventions for working in this repo

This is **tenant-b**'s repo on the [airflow3-infra](https://github.com/tarekabouzeid/airflow3-infra)
multi-tenant Airflow 3 / Argo CD platform. It is a *tenant* repo, not the platform repo: the
platform (chart shape, RBAC, namespaces, Vault wiring, Argo CD `Application`/`ApplicationSet`
resources) lives in `airflow3-infra` and is out of scope here. If a task looks like it needs a
change there, say so instead of trying to replicate it in this repo.

tenant-b's home cluster is `af-work-b`; its remote workload cluster is `af-work-a` — deliberately
the mirror image of tenant-a (home `af-work-a`, remote `af-work-b`), so together the two tenants
exercise both clusters as "home" and as "remote". See `airflow3-infra-tenant-a` if you need the
counterpart.

## What this repo owns

Exactly three things — nothing else, by design:

1. **`deploy/airflow/values.yaml`** — Helm value overrides for this tenant's Airflow deployment
   (image tag, resource requests/limits, replica counts). Merged *underneath* the platform's own
   wiring values (`platform/bootstrap/appset-tenant-airflow.yaml` in the platform repo), so nothing
   here can override the Vault/ServiceAccount/DAG-source/executor configuration the platform
   controls. Adding a values key here that the platform's wiring already sets is a no-op at best.
2. **`deploy/workloads/`** — a small Helm chart deployed into `tenant-b-workloads` on every
   cluster this tenant targets. Declares a `SecretStore` + `ExternalSecret` pulling this tenant's
   workload secrets out of Vault (mount point `tenant-b`, ESO role `tenant-b-eso`).
3. **`dags/`** — this tenant's DAGs, loaded onto the Airflow DAGs PVC by a platform-owned loader
   Job on every Argo CD sync. Exactly two DAGs live here by design: one integration test per
   supported workload type (`KubernetesPodOperator`, `SparkKubernetesOperator`), each running once
   against the local cluster and once against the remote cluster. Don't add production DAGs
   speculatively — this repo is an integration-test fixture for the platform, not a general
   scheduling surface.

## Hard rules

1. **Never author an `Application` or `ApplicationSet` resource here.** The trust boundary is the
   platform repo's `platform/tenants/tenant-b/tenant.yaml` (+ `workloads-*.yaml`) registry plus its
   `AppProject`. This repo contributes Helm values and DAGs only — Argo CD reads from here, it is
   never configured from here.
2. **The Airflow image tag in `deploy/airflow/values.yaml` must match a tag actually published
   from the platform's `images/airflow/` build**, which is pinned by `AIRFLOW_APP_VERSION` in the
   platform repo's `versions.env`. Don't bump it to an arbitrary tag without checking that image
   exists.
3. **Secrets never enter git.** Workload secrets are pulled from Vault via `deploy/workloads/`'s
   `ExternalSecret`, never hardcoded in values files or DAGs.
4. **DAGs must import cleanly and stay in the two-DAG integration-test shape** —
   `tests/test_dags_import.py` and `.github/workflows/dag-validate.yaml` enforce this in CI; run
   them (or trust CI) before considering a DAG change done.
5. **This environment has no local Docker/KIND/Argo CD access.** GitHub Actions
   (`.github/workflows/lint.yaml`, `dag-validate.yaml`) is the verification loop here; the
   platform repo's `e2e-kind.yaml` is what actually deploys this repo's contents into a live
   cluster. Treat CI failure as ground truth, not a flake, unless proven otherwise.

## Where to look for more context

- Platform repo `docs/runbook-tenant-onboarding.md` — how this repo is wired into the platform.
- Platform repo `docs/architecture.md` — full as-built design, including why the tenant/platform
  split is drawn where it is.
- Platform repo `platform/tenants/tenant-b/` — this tenant's registry entry (home cluster, Vault
  mount point/roles) that the platform's ApplicationSets consume.
