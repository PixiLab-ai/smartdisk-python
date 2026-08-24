"""Direct tests for _util helpers."""


def test_peel_export_tolerates_extra_envelope_keys():
    """The live proxy envelope carries `time` (and sometimes `token`) beside
    data/result — exact-set matching returned the envelope unpeeled (caught
    live 2026-08-24: 0 facts visible)."""
    from smartdisk._util import peel_export

    graph = '{"facts": [1], "edges": []}'
    wrapped = '{"data": {"facts": [1], "edges": []}, "result": "success", "time": 0.12, "token": "x"}'
    import json
    assert json.loads(peel_export(wrapped)) == json.loads(graph)
    # bare bodies still pass through byte-for-byte
    assert peel_export(graph) == graph
    assert peel_export("@prefix sd: <x> .") == "@prefix sd: <x> ."
