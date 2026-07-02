"""Rules node-set routing: writes and reads must land on the same names.

Regression tests for the bug where ``improve`` wrote rules into a node set
built from the caller's *read* namespaces (e.g. ``coding_agent_rules_demo+public``
for the admin) while every reader searched per-namespace names — so distilled
rules were never recallable by anyone.
"""
from app.cognee_runtime.improve import RULES_NODESET, _nodesets_to_search, nodeset_for


def test_nodeset_for_is_per_namespace():
    assert nodeset_for("demo") == "coding_agent_rules_demo"
    assert nodeset_for("acme") == "coding_agent_rules_acme"


def test_nodeset_for_defaults_to_demo():
    assert nodeset_for("") == "coding_agent_rules_demo"


def test_anonymous_reader_sees_demo_and_legacy_sets():
    # Anonymous read scope is {demo}: must cover the demo set AND the legacy
    # unsuffixed set that pre-tenant deployments distilled into.
    assert _nodesets_to_search({"demo"}) == ["coding_agent_rules_demo", RULES_NODESET]
    assert _nodesets_to_search(None) == ["coding_agent_rules_demo", RULES_NODESET]


def test_tenant_reader_is_isolated():
    # An API-key tenant reads only their own set: no demo, no legacy global.
    assert _nodesets_to_search({"acme"}) == ["coding_agent_rules_acme"]


def test_admin_reader_sees_all_readable_sets():
    names = _nodesets_to_search({"demo", "public"})
    assert names == ["coding_agent_rules_demo", "coding_agent_rules_public", RULES_NODESET]


def test_admin_write_target_is_readable_by_anonymous():
    # The operator curates the demo sample: what admin improve writes
    # (rules_namespace="demo") must be in the anonymous search list.
    assert nodeset_for("demo") in _nodesets_to_search({"demo"})


def test_tenant_write_target_is_readable_by_same_tenant():
    assert nodeset_for("acme") in _nodesets_to_search({"acme"})
