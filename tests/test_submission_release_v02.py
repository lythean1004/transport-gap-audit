from scripts.submission.release_v02 import allowed


def test_release_excludes_generated_archives_and_private_material():
    assert not allowed('exports/transport-gap-audit_submission_v1.zip')
    assert not allowed('exports/transport-gap-audit_submission_v02.zip')
    assert not allowed('.env')
    assert not allowed('docs/붙임1-참가신청서_서명.pdf')
    assert not allowed('qa/submission_v02/temp.txt')
    assert allowed('scratch/calc_headway_v7.py')
    assert allowed('evidence/arrival_raw/2026-09-11/a.json')
