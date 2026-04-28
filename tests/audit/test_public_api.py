def test_public_api_imports():
    from net_alpha.audit import (
        ProvenanceTrace,
        decode_metric_ref,
        encode_metric_ref,
        provenance_for,
    )

    assert callable(provenance_for)
    assert callable(encode_metric_ref)
    assert callable(decode_metric_ref)
    assert ProvenanceTrace.__name__ == "ProvenanceTrace"
