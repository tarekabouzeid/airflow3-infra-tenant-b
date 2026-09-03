"""Zero-import-errors check for this tenant's DAGs. Deliberately minimal - the platform repo's
e2e-kind.yaml is what actually runs these DAGs against a live cluster; this only guards against
syntax errors / bad imports reaching Argo CD's dag-loader Job."""
from airflow.models import DagBag


def test_no_import_errors():
    dag_bag = DagBag(dag_folder="dags", include_examples=False)
    assert not dag_bag.import_errors, f"DAG import errors: {dag_bag.import_errors}"


def test_expected_dags_present():
    dag_bag = DagBag(dag_folder="dags", include_examples=False)
    assert "it_kubernetes_pod_operator" in dag_bag.dags
    assert "it_spark" in dag_bag.dags
