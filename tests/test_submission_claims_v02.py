from scripts.submission.claims_v02 import compare_document_date


def test_source_claim_requires_matching_hash_and_anchor():
    r={'sha256':'abc','anchor':'입주 시작','lower':'2015-01-30','upper':'2015-01-30'}
    assert compare_document_date(r,'입주 시작','different') is None
    assert compare_document_date(r,'다른 본문','abc') is None
    assert compare_document_date(r,'이달 30일부터 입주 시작','abc')[0].isoformat()=='2015-01-30'
