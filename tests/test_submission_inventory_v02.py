from scripts.submission.inventory_v02 import disposition, read_content


def test_scratch_and_manual_overrides_are_research_inputs():
    assert disposition('scratch/manual_check.py') == 'research_content'
    assert disposition('manual_overrides.csv') == 'research_content'


def test_generated_checkout_is_explicitly_accounted_for():
    assert disposition('qa/submission_v1/publish/evidence/a.csv') == 'generated_or_runtime'


def test_invalid_pdf_is_reported_not_silently_read(tmp_path):
    p=tmp_path/'broken.pdf';p.write_bytes(b'not a PDF')
    result=read_content(p)
    assert result['read_status']=='read_failed'


def test_nested_zip_member_is_indexed(tmp_path):
    import zipfile, io
    inner=io.BytesIO()
    with zipfile.ZipFile(inner,'w') as z:z.writestr('review.csv','status\nhuman_verified\n')
    p=tmp_path/'test.zip'
    with zipfile.ZipFile(p,'w') as z:z.writestr('inside.zip',inner.getvalue())
    result=read_content(p)
    assert 'inside.zip!review.csv' in result['archive_members']
