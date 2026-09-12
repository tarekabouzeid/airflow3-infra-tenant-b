"""Lightweight integration test: KubernetesPodOperator, run once locally and once against this
tenant's remote cluster (kubernetes_conn_id="k8s_remote", sourced from Vault via the Airflow
secrets backend - see docs/architecture.md in the platform repo). Both tasks read a value from
the ESO-synced "<tenant>-workload-secrets" Secret (see deploy/workloads/), proving the full
Vault -> ExternalSecret -> pod path in both clusters with a single DAG run.
"""
from datetime import datetime, timezone

from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from kubernetes.client import models as k8s

TENANT = "tenant-b"
NAMESPACE = f"{TENANT}-workloads"

# Kueue queue selection. This label is the ONE governance knob a tenant holds: it picks which of
# this tenant's two ClusterQueues the task's quota is drawn from.
#
#   "high" - the tenant's guaranteed share. Capacity reserved for this tenant whether or not
#            anyone else is busy, and reclaimed from anyone who borrowed it.
#   "low"  - opportunistic. Runs on capacity the cluster is not otherwise using, and is the first
#            thing evicted when someone wants it back. Costs nothing against the guaranteed share.
#
# Omit the label entirely and the task lands in "low": the platform creates a LocalQueue literally
# named "default" pointing at the low lane, which Kueue applies to anything unlabelled. There is
# no way to opt OUT of queueing - the platform sets manageJobsWithoutQueueName on these namespaces
# - and Kueue's own queueing priority (a WorkloadPriorityClass) is derived from this label by the
# platform, so the lane and the queueing priority cannot be set to disagree.
#
# Everything else about how this task is scheduled - gang scheduling, how big each lane is,
# preemption policy - is cluster-wide and platform-owned. See the platform repo's
# docs/runbook-governance.md.
QUEUE_LABEL = "kueue.x-k8s.io/queue-name"

SECRET_ENV = [
    k8s.V1EnvVar(
        name="GREETING",
        value_from=k8s.V1EnvVarSource(
            secret_key_ref=k8s.V1SecretKeySelector(name=f"{TENANT}-workload-secrets", key="greeting")
        ),
    )
]

with DAG(
    dag_id="it_kubernetes_pod_operator",
    description="Integration test: KubernetesPodOperator, local + remote cluster",
    schedule=None,
    catchup=False,
    max_active_runs=1,
    start_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
    default_args={"retries": 0},
    tags=["integration-test", TENANT],
) as dag:
    local_pod = KubernetesPodOperator(
        task_id="local_pod",
        namespace=NAMESPACE,
        name="it-kpo-local",
        image="busybox:1.36",
        cmds=["sh", "-c"],
        arguments=["echo LOCAL: $GREETING"],
        env_vars=SECRET_ENV,
        # The guaranteed lane: this task is the one the integration test actually gates on, so it
        # should not be waiting behind opportunistic work.
        labels={QUEUE_LABEL: "high"},
        in_cluster=True,
        is_delete_operator_pod=True,
        get_logs=True,
    )

    remote_pod = KubernetesPodOperator(
        task_id="remote_pod",
        namespace=NAMESPACE,
        name="it-kpo-remote",
        image="busybox:1.36",
        cmds=["sh", "-c"],
        arguments=["echo REMOTE: $GREETING"],
        env_vars=SECRET_ENV,
        # The opportunistic lane, deliberately different from local_pod above: between them the
        # two tasks exercise both of this tenant's ClusterQueues in a single DAG run, which is the
        # only way this repo's integration test covers the low lane at all.
        labels={QUEUE_LABEL: "low"},
        kubernetes_conn_id="k8s_remote",
        is_delete_operator_pod=True,
        get_logs=True,
    )
