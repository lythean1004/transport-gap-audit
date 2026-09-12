"""사용자 검수대장 연결과 검증 상태 보존의 회귀검사."""
import hashlib
from scripts.submission.review_v02 import match_review, apply_review, review_bounds


def test_resolution_metadata_requires_same_original_and_review_status():
    from scripts.submission.review_v02 import merge_resolution
    base={'source_id':'s','sha256':'a','review_status':'human_verified','event_type':'occupancy_start'}
    final={'source_id':'s','sha256':'b','review_status':'verified','human_verified':'TRUE','human_verifier':'parkd'}
    assert merge_resolution(base,final,'hash')['resolution_import_status']=='blocked_identity_or_status'
    final['sha256']='a';final['human_verified_at']='2026-09-02T20:11:00+09:00'
    final['exact_excerpt']='corrected';final['event_type']='occupancy_first_actual'
    result=merge_resolution(base,final,'hash')
    assert result['verified_by']=='parkd'
    assert result['verified_at']==final['human_verified_at']
    assert result['exact_excerpt']=='corrected'
    assert result['event_type']=='occupancy_start'


def test_repeated_candidate_id_is_disambiguated_by_document_and_development():
    rows=[{'source_id':'one','cand_id':'A01','sha256':'a','local_path':'data/a.pdf','development':'화성 동탄2'},
          {'source_id':'two','cand_id':'A01','sha256':'a','local_path':'data/a.pdf','development':'위례'}]
    review={'candidate_id':'A01','sha256':'a','local_path':'data/a.pdf','development':'Wirye'}
    assert match_review(review,rows)['source_id']=='two'


def test_ambiguous_identity_is_not_promoted():
    row={'source_id':'one','cand_id':'A01','sha256':'a','local_path':'data/a.pdf','development':'위례'}
    assert match_review({'candidate_id':'A01','sha256':'a','local_path':'data/a.pdf','development':'위례'},[row,dict(row,source_id='two')]) is None


def test_document_change_blocks_import_of_human_verified(tmp_path):
    p=tmp_path/'evidence.txt';p.write_text('changed',encoding='utf-8')
    source={'source_id':'s','review_status':'needs_human','event_type':'promise_date'}
    review={'review_status':'human_verified','local_path':str(p),'sha256':hashlib.sha256(b'original').hexdigest()}
    row=apply_review(source,review,'review_hash',2)
    assert row['review_status']=='needs_human'
    assert row['review_import_status']=='blocked_document_hash'


def test_review_date_bounds_override_display_month_without_fabricated_day(tmp_path):
    p=tmp_path/'evidence.txt';p.write_text('same',encoding='utf-8')
    source={'source_id':'s','review_status':'needs_human'}
    review={'review_status':'human_verified','local_path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
            'event_date':'Jan-15','date_precision':'day','date_lower_bound':'2015-01-23','date_upper_bound':'2015-01-23','event_type':'occupancy_start','development':'Dongtan2'}
    row=apply_review(source,review,'review_hash',2)
    assert row['review_status']=='human_verified'
    assert row['event_date_lower']=='2015-01-23'
    assert row['verified_at']==''
    assert row['event_type']=='occupancy_start'


def test_invalid_bound_order_is_not_silently_fixed():
    assert review_bounds({'event_date_lower':'2026-09-12','event_date_upper':'2026-09-01'}) is None
