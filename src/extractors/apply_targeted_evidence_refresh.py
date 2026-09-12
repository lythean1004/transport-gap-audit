"""Apply verified-source extraction drafts for the 15 user-selected source rows."""

from __future__ import annotations

import csv
import hashlib
import html
import json
import re
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "evidence"
STAGED = ROOT / "data" / "staged"
CURATED = ROOT / "data" / "curated"
REGISTRY = CURATED / "source_registry.csv"
TARGET_HTML = RAW / "documents" / "target_refresh_20260902"
RETRIEVED_AT = "2026-09-02T18:00:00+09:00"


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clean_html(path: Path) -> str:
    value = path.read_text(encoding="utf-8", errors="ignore")
    value = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", value)
    value = re.sub(r"(?s)<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def normalize(value: str) -> str:
    return re.sub(r"\s+", "", value or "")


def pdf_page_for(path: Path, excerpt: str) -> int:
    import fitz

    needle = normalize(excerpt)
    with fitz.open(path) as document:
        for page_no, page in enumerate(document, 1):
            if needle in normalize(page.get_text("text")):
                return page_no
    raise ValueError(f"excerpt not found in PDF: {path.name}: {excerpt}")


def html_text_file(path: Path) -> Path:
    digest = file_hash(path)
    target = STAGED / "html_text" / f"{digest}.txt"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(clean_html(path), encoding="utf-8")
    return target


def row_base(source_id: str, rows_by_id: dict[str, dict[str, str]]) -> dict[str, str]:
    if source_id not in rows_by_id:
        raise KeyError(source_id)
    return deepcopy(rows_by_id[source_id])


def apply_file(row: dict[str, str], local_path: Path, *, is_pdf: bool, excerpt: str) -> None:
    digest = file_hash(local_path)
    row["local_path"] = str(local_path)
    row["sha256"] = digest
    row["bytes"] = str(local_path.stat().st_size)
    row["file_kind"] = "pdf" if is_pdf else "html"
    row["http_status"] = "200"
    row["exact_excerpt"] = excerpt
    if is_pdf:
        row["page_or_section"] = f"PDF p.{pdf_page_for(local_path, excerpt)}"
        row["local_text_path"] = str(STAGED / "pdf_text" / f"{digest}.txt")
        row["raw_pdf_path"] = str(local_path)
        row["pdf_sha256"] = digest
    else:
        text = clean_html(local_path)
        if normalize(excerpt) not in normalize(text):
            raise ValueError(f"excerpt not found in HTML: {local_path.name}: {excerpt}")
        row["local_text_path"] = str(html_text_file(local_path))
        row["page_or_section"] = row.get("page_or_section") or "HTML 본문"


def attach_pdf(row: dict[str, str], path: Path, inventory_by_hash: dict[str, dict[str, str]], source_url: str = "") -> None:
    digest = file_hash(path)
    row["attachment_local_path"] = str(path)
    row["attachment_sha256"] = digest
    row["attachment_source_url"] = source_url or inventory_by_hash.get(digest, {}).get("source_url", "").replace("\x00", "")
    row["raw_pdf_path"] = str(path)
    row["pdf_sha256"] = digest
    row["pdf_id"] = inventory_by_hash.get(digest, {}).get("pdf_id", "")
    row["pdf_match_method"] = "targeted_manual_mapping"
    row["pdf_match_confidence"] = "1.0"


def main() -> None:
    with REGISTRY.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames or [])
        rows = list(reader)
    rows_by_id = {row["source_id"]: row for row in rows}
    with (STAGED / "pdf_inventory.csv").open("r", encoding="utf-8-sig", newline="") as handle:
        inventory = list(csv.DictReader(handle))
    inventory_by_hash = {row["sha256"]: row for row in inventory if not row.get("duplicate_of_pdf_id")}

    urls = {
        "SRC-E1-A04": "https://apply.lh.or.kr/lhapply/apply/wt/wrtanc/selectWrtancInfo.do?panId=0000061160&ccrCnntSysDsCd=02&uppAisTpCd=06&aisTpCd=08&mi=1026",
        "SRC-E1-A08": "https://www.myhome.go.kr/hws/portal/sch/selectRsdtRcritNtcDetailView.do?pblancId=6410",
        "SRC-E1-A10": "https://www.myhome.go.kr/hws/portal/sch/selectRsdtRcritNtcDetailView.do?pblancId=920",
        "SRC-E1-B02": "https://www.molit.go.kr/USR/NEWS/m_71/dtl.jsp?id=95086846",
        "SRC-E1-B05": "https://www.molit.go.kr/mta/USR/N0201/m_36770/dtl.jsp?lcmspage=1&id=95087500",
        "SRC-E1-B08": "https://www.korea.kr/news/policyNewsView.do?newsId=148931611",
        "SRC-E1-B10": "https://www.korea.kr/briefing/policyBriefingView.do?newsId=148775695",
        "SRC-E1-C08": "https://www.nyj.go.kr/www/selectBbsNttView.do?key=2498&bbsNo=68&pageIndex=405&pageUnit=8&searchCnd=all&nttNo=432164",
        "SRC-E2-C07": "https://www.molit.go.kr/LCMS/DWN.jsp?fold=koreaNews/mobile/file&fileName=250724%28%EC%84%9D%EA%B0%84%29+3%EA%B8%B0+%EC%8B%A0%EB%8F%84%EC%8B%9C+%EB%82%A8%EC%96%91%EC%A3%BC%EC%99%95%EC%88%99+%EC%B2%AB+%EA%B3%B5%EA%B8%89+%EA%B0%9C%EC%8B%9C%28%EA%B3%B5%EA%B3%B5%ED%83%9D%EC%A7%80%EA%B4%80%EB%A6%AC%EA%B3%BC%29.pdf",
        "SRC-E2-C08": "https://www.myhome.go.kr/hws/portal/bbs/selectBoardHappyNewsDetailView.do?nttId=797",
        "SRC-E2-C09": "https://apply.lh.or.kr/lhapply/apply/wt/wrtanc/selectWrtancInfo.do?panId=0000061134&ccrCnntSysDsCd=02&uppAisTpCd=05&aisTpCd=05&mi=1027",
        "SRC-E2-C10": "https://apply.lh.or.kr/lhapply/apply/wt/wrtanc/selectWrtancInfo.do?panId=0000060706&ccrCnntSysDsCd=02&uppAisTpCd=05&aisTpCd=05&mi=1027",
    }
    html_path = {sid: TARGET_HTML / f"{sid}_2026-09-02.html" for sid in urls if sid != "SRC-E2-C07"}

    pdf = {
        "a04": RAW / "김포한강Ac-05블록(센트럴블루힐)10년공공임대주택리츠예비입주자모집공고문(26.08.25).pdf",
        "a08": RAW / "＇25년 상반기 경기행복주택 예비입주자 추가모집 공고.pdf",
        "a10a24": RAW / "미사강변도시 A24블록 10년 공공임대주택리츠 입주자 모집.pdf",
        "a10a25": RAW / "미사강변도시 A25블록 10년 공공임대주택리츠 입주자 모집.pdf",
        "b02": RAW / "220617(조간)_호매실_동탄2_광역교통_개선을_위해_주민의견_듣는다(광역교통정책과).pdf",
        "b08": RAW / "240719(조간)_수도권_동부지역__출퇴근_30분_시대_실현_4.4조원_규모의_철도·도로_사업_본격_추진(광역교통정책과) (1).pdf",
        "b10": RAW / "하남미사지구 광역교통개선대책 변경, 확정된 바 없어.pdf",
        "media": RAW / "화성 동탄신도시∼김포공항 버스 노선 내달 1일부터 운행 _ 연합뉴스.pdf",
        "e2c07": RAW / "250724(석간) 3기 신도시 남양주왕숙 첫 공급 개시(공공택지관리과).pdf",
        "e2c08": RAW / "(최종)250331_교산푸르지오더퍼스트_입주자모집공고.pdf",
        "e2c09s3": RAW / "(정정)(정정)고양창릉S-3블록입주자모집공고문.pdf",
        "e2c09s4": RAW / "(정정)(정정)고양창릉S-4블록공공분양입주자모집공고문.pdf",
        "e2c10": RAW / "(정정공고)인천계양A-2블록공공분양입주자모집공고문.pdf",
    }
    for path in [*html_path.values(), *pdf.values()]:
        if not path.exists():
            raise FileNotFoundError(path)

    updates: list[dict[str, str]] = []

    row = row_base("SRC-E1-A04", rows_by_id)
    row.update(source_url=urls[row["source_id"]], published_date="2026-08-25", retrieved_at=RETRIEVED_AT,
               title="김포한강 Ac-05블록 10년 공공임대주택리츠 예비입주자 모집공고(2026.08.25)",
               event_type="occupancy_planned_block", event_date="2017-08", date_precision="month",
               event_date_normalized="2017-08-31", event_date_lower="2017-08-01", event_date_upper="2017-08-31",
               block_name="Ac-05", scope="block", confidence="high", review_status="needs_human",
               page_or_section="공급정보 > 김포한강Ac-05", notes="기존 2020년 6월 주장은 현재 공식 링크에서 확인되지 않음; 공식 화면은 입주예정월 2017년 08월로 표시")
    apply_file(row, html_path[row["source_id"]], is_pdf=False, excerpt="입주예정월 : 2017년 08월")
    attach_pdf(row, pdf["a04"], inventory_by_hash)
    updates.append(row)

    row = row_base("SRC-E1-A08", rows_by_id)
    row.update(source_url=urls[row["source_id"]], retrieved_at=RETRIEVED_AT, event_date="", date_precision="unknown",
               event_date_normalized="", event_date_lower="", event_date_upper="", block_name="A2", scope="block",
               confidence="high", review_status="needs_human", notes="제시된 마이홈 링크는 2019-12-16 추가모집 화면이며 최초 입주일 값이 비어 있음; 2025 추가모집 PDF도 정확한 입주시기를 개별 통보한다고만 명시")
    apply_file(row, pdf["a08"], is_pdf=True, excerpt="입주예정 시기는 입주자격심사 종료 후 개별적으로 알려드립니다.")
    row["attachment_source_url"] = "https://www.nyj.go.kr/www/downloadBbsFile.do?bbsNo=62&nttNo=494806&atchmnflNo=1504230"
    updates.append(row)

    row = row_base("SRC-E1-A10", rows_by_id)
    row.update(source_url=urls[row["source_id"]], retrieved_at=RETRIEVED_AT, event_type="occupancy_planned_block",
               event_date="2018-11", date_precision="month", event_date_normalized="2018-11-30",
               event_date_lower="2018-11-01", event_date_upper="2018-11-30", block_name="A24", scope="block",
               confidence="high", review_status="needs_human", notes="A24와 A25의 최초 입주시기가 달라 블록별 레코드로 분리")
    apply_file(row, pdf["a10a24"], is_pdf=True, excerpt="최초 입주 시기\n2018년 11월")
    updates.append(row)
    row2 = deepcopy(row)
    row2.update(source_id="SRC-E1-A10-A25", cand_id_namespaced="E1-A10-A25", event_date="2018-10",
                event_date_normalized="2018-10-31", event_date_lower="2018-10-01", event_date_upper="2018-10-31",
                block_name="A25", title="미사강변도시 A25블록 10년 공공임대주택리츠 입주자 모집")
    apply_file(row2, pdf["a10a25"], is_pdf=True, excerpt="최초 입주 시기\n2018년 10월")
    updates.append(row2)

    row = row_base("SRC-E1-B02", rows_by_id)
    row.update(source_url=urls[row["source_id"]], retrieved_at=RETRIEVED_AT, event_date="", date_precision="unknown",
               event_date_normalized="", event_date_lower="", event_date_upper="", mode="multimodal",
               line_name="GTX-A 삼성~동탄; 서울방면 광역버스 특별대책", scope="district",
               promise_verb_원문표기="주민간담회를 개최할 계획이다; 특별 대책을 마련하고 있다",
               confidence="high", review_status="rejected", reject_reason="completion_target_absent",
               notes="공식 PDF 확보; 2022-06-21은 주민간담회 날짜이며 교통시설 완공·개통 목표일이 아님")
    apply_file(row, pdf["b02"], is_pdf=True, excerpt="서울 방면 등에 대한 광역버스 증차")
    updates.append(row)

    row = row_base("SRC-E1-B05", rows_by_id)
    row.update(source_url=urls[row["source_id"]], published_date="2022-11-28", retrieved_at=RETRIEVED_AT,
               title="위례신도시 노면전차 사업으로 교통이 편리해진다", event_date="2025-09",
               date_precision="month", event_date_normalized="2025-09-30", event_date_lower="2025-09-01",
               event_date_upper="2025-09-30", mode="tram", line_name="위례선 트램", scope="corridor",
               promise_verb_원문표기="’25년 9월 개통할 예정이다", confidence="high", review_status="rejected",
               reject_reason="source_identity_mismatch", dup_of="SRC-E1-C05",
               notes="제시된 URL은 2014-05-15 광역교통대책 확정 자료가 아니라 2022-11-28 위례선 사업계획 승인 자료; canonical SRC-E1-C05와 중복")
    apply_file(row, html_path[row["source_id"]], is_pdf=False, excerpt="’22년 11월 사업을 본격 착공하여 ’25년 9월 개통할 예정이다.")
    updates.append(row)

    row = row_base("SRC-E1-B08", rows_by_id)
    row.update(source_url=urls[row["source_id"]], retrieved_at=RETRIEVED_AT, event_date="2024-08-10",
               date_precision="day", event_date_normalized="2024-08-10", event_date_lower="2024-08-10",
               event_date_upper="2024-08-10", mode="multimodal", line_name="별내선; 다산역 연계버스 9개 노선",
               scope="district", promise_verb_원문표기="개통에 맞춰; 9개 노선 변경 및 16대를 증차한다",
               confidence="high", review_status="needs_human", notes="정책브리핑 HTML과 국토교통부 보도자료 PDF를 함께 보관")
    apply_file(row, pdf["b08"], is_pdf=True, excerpt="별내선 개통(8.10)에 맞춰 버스 18개 노선, 34대 증차 등 촘촘한 연계환승체계 구축")
    row["attachment_local_path"] = str(html_path[row["source_id"]])
    row["attachment_sha256"] = file_hash(html_path[row["source_id"]])
    updates.append(row)

    row = row_base("SRC-E1-B10", rows_by_id)
    row.update(source_url=urls[row["source_id"]], retrieved_at=RETRIEVED_AT, event_date="", date_precision="unknown",
               event_date_normalized="", event_date_lower="", event_date_upper="", mode="road",
               line_name="천호대로 지하차도 변경 검토", scope="corridor", promise_verb_원문표기="결정할 계획",
               confidence="high", review_status="rejected", reject_reason="completion_target_absent",
               notes="공식 해명자료는 방침 미확정 상태만 확인하며 시설 완공·개통 목표일은 제시하지 않음")
    apply_file(row, html_path[row["source_id"]], is_pdf=False, excerpt="하남미사지구 광역교통개선대책 변경은 현재까지 방침이 확정된 바 없으며 전문가의 충분한 검토를 거쳐 결정할 계획이라고 밝혔다.")
    attach_pdf(row, pdf["b10"], inventory_by_hash)
    updates.append(row)

    media_excerpt = "경기 화성 동탄신도시에서 김포공항을 연결하는 8840번 공항버스가 내달 1일 운행을 시작한다."
    for source_id in ("SRC-E1-C01", "SRC-E1-C02", "SRC-E1-C04"):
        row = row_base(source_id, rows_by_id)
        row.update(source_type="언론 단서", publisher="연합뉴스", source_url="", retrieved_at=RETRIEVED_AT,
                   event_date="2023-02-01", date_precision="day", event_date_normalized="2023-02-01",
                   event_date_lower="2023-02-01", event_date_upper="2023-02-01", mode="express_bus",
                   line_name="8840번 동탄~김포공항 공항버스", scope="corridor", confidence="medium",
                   review_status="rejected", reject_reason="official_operation_source_missing",
                   notes="단서기사: https://www.yna.co.kr/view/AKR20230131105400061 ; 공식 화성시·운영기관 운행개시 원문 미확보")
        if source_id == "SRC-E1-C02":
            row["dup_of"] = "SRC-E1-C01"
        if source_id == "SRC-E1-C04":
            row["reject_reason"] = "development_scope_mismatch"
            row["notes"] += "; 김포공항 연결 노선은 김포한강지구 운행 개시 증거가 아님"
        apply_file(row, pdf["media"], is_pdf=True, excerpt=media_excerpt)
        updates.append(row)

    row = row_base("SRC-E1-C08", rows_by_id)
    row.update(source_url=urls[row["source_id"]], published_date="2023-02-28", retrieved_at=RETRIEVED_AT,
               title="남양주시, 땡큐버스 등 6개 노선 개편으로 시민 불편 해소", event_date="2023-03-01",
               date_precision="day", event_date_normalized="2023-03-01", event_date_lower="2023-03-01",
               event_date_upper="2023-03-01", mode="bus", line_name="땡큐11·12·50·60·90번",
               scope="corridor", confidence="high", review_status="needs_human",
               notes="제시된 공식 URL은 기존 2022-12-29/2023-01-01 후보가 아니라 2023-02-28 공지 및 2023-03-01 시행 자료")
    apply_file(row, html_path[row["source_id"]], is_pdf=False, excerpt="오는 3 월 1 일부터 시행한다고 28 일 밝혔다.")
    updates.append(row)

    row = row_base("SRC-E2-C07", rows_by_id)
    row.update(source_type="국토교통부 보도자료", publisher="국토교통부", source_url=urls[row["source_id"]],
               retrieved_at=RETRIEVED_AT, title="3기 신도시 남양주왕숙 첫 공급 개시", event_date="2028-08",
               date_precision="month", event_date_normalized="2028-08-31", event_date_lower="2028-08-01",
               event_date_upper="2028-08-31", block_name="A-1;A-2", scope="block", confidence="high",
               review_status="needs_human", notes="언론 단서를 국토교통부 1차 보도자료 PDF로 교체")
    apply_file(row, pdf["e2c07"], is_pdf=True, excerpt="입주는 ’28년 8월 예정이다.")
    updates.append(row)

    row = row_base("SRC-E2-C08", rows_by_id)
    row.update(source_type="공공기관 소식", publisher="LH 마이홈", source_url=urls[row["source_id"]], retrieved_at=RETRIEVED_AT,
               title="하남교산 A2블록 공공분양 청약", event_date="2029-06", date_precision="month",
               event_date_normalized="2029-06-30", event_date_lower="2029-06-01", event_date_upper="2029-06-30",
               block_name="A-2", scope="block", confidence="high", review_status="needs_human",
               notes="언론 단서를 마이홈 공식 본문과 LH 공고 PDF로 교체")
    apply_file(row, html_path[row["source_id"]], is_pdf=False, excerpt="준공은 2028년 12월, 입주는 2029년 6월 예정")
    attach_pdf(row, pdf["e2c08"], inventory_by_hash)
    updates.append(row)

    row = row_base("SRC-E2-C09", rows_by_id)
    row.update(source_type="공공기관 공고", publisher="LH", source_url=urls[row["source_id"]], retrieved_at=RETRIEVED_AT,
               title="고양창릉 S-4블록 공공분양주택 입주자모집공고", event_date="2030-03",
               date_precision="month", event_date_normalized="2030-03-31", event_date_lower="2030-03-01",
               event_date_upper="2030-03-31", block_name="S-4", scope="block", confidence="high",
               review_status="needs_human", notes="기존 언론 단서의 2029년 하반기와 달리 최신 정정 공고 PDF는 2030년 3월로 명시")
    apply_file(row, pdf["e2c09s4"], is_pdf=True, excerpt="입주예정 시기는 ‘30년 3월입니다.")
    row["attachment_source_url"] = inventory_by_hash[file_hash(pdf["e2c09s4"])]["source_url"].replace("\x00", "")
    updates.append(row)
    row2 = deepcopy(row)
    row2.update(source_id="SRC-E2-C09-S3", cand_id_namespaced="E2-C09-S3", title="고양창릉 S-3블록 공공분양주택 입주자모집공고",
                source_url=inventory_by_hash[file_hash(pdf["e2c09s3"])]["source_url"].replace("\x00", ""),
                event_date="2030-02", event_date_normalized="2030-02-28", event_date_lower="2030-02-01",
                event_date_upper="2030-02-28", block_name="S-3", notes="S-3와 S-4의 입주예정월이 달라 블록별 레코드로 분리")
    apply_file(row2, pdf["e2c09s3"], is_pdf=True, excerpt="입주예정 시기는 ‘30년 2월입니다.")
    updates.append(row2)

    row = row_base("SRC-E2-C10", rows_by_id)
    row.update(source_url=urls[row["source_id"]], retrieved_at=RETRIEVED_AT, event_date="", date_precision="unknown",
               event_date_normalized="", event_date_lower="", event_date_upper="", confidence="high",
               review_status="rejected", reject_reason="development_scope_mismatch", dup_of="SRC-E2-A06",
               notes="제시된 공식 URL과 PDF는 부천대장이 아니라 인천계양 A2(입주예정 2026년 12월); 부천대장 증거로 사용 금지")
    apply_file(row, html_path[row["source_id"]], is_pdf=False, excerpt="공급위치 : 인천광역시 계양구 귤현동, 동양동, 박촌동, 병방동, 상야동 일원 공공주택지구 내 A-2블록")
    attach_pdf(row, pdf["e2c10"], inventory_by_hash)
    updates.append(row)

    for row in updates:
        row["document_verified"] = "false"
        row["verification_method"] = "ai_extraction_pending_human_page_check"
        row["verified_at"] = ""
        rows_by_id[row["source_id"]] = row
    supplemental_ids = {"SRC-E1-A10-A25", "SRC-E2-C09-S3"}
    output_rows = [rows_by_id[row["source_id"]] for row in rows if row["source_id"] not in supplemental_ids]
    for source_id in sorted(supplemental_ids):
        output_rows.append(rows_by_id[source_id])
    for row in output_rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    temp = REGISTRY.with_suffix(".csv.tmp")
    with temp.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(output_rows)
    temp.replace(REGISTRY)

    extraction_fields = [
        "evidence_id", "source_id", "development", "claim_type", "event_type", "event_date", "date_precision",
        "event_date_lower", "event_date_upper", "mode", "line_name", "scope", "block_name",
        "promise_verb_원문표기", "page_or_section", "exact_excerpt", "confidence", "review_status",
        "source_url", "local_path", "sha256", "attachment_local_path", "attachment_sha256", "notes",
    ]
    extraction_rows = []
    for row in updates:
        event_type = row.get("event_type", "")
        claim_type = "occupancy" if event_type.startswith("occupancy") else "promise" if event_type == "promise_date" else "operation" if event_type == "actual_operation" else "service"
        item = {field: row.get(field, "") for field in extraction_fields}
        item["evidence_id"] = "EV-" + row["source_id"].removeprefix("SRC-")
        item["claim_type"] = claim_type
        extraction_rows.append(item)
    target_path = CURATED / "targeted_evidence_extraction.csv"
    with target_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=extraction_fields)
        writer.writeheader()
        writer.writerows(extraction_rows)
    summary = {
        "generated_at": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds"),
        "requested_source_rows": 15,
        "supplemental_block_rows": 2,
        "extraction_rows": len(extraction_rows),
        "needs_human": sum(row["review_status"] == "needs_human" for row in updates),
        "rejected": sum(row["review_status"] == "rejected" for row in updates),
        "registry_rows": len(output_rows),
    }
    (CURATED / "targeted_evidence_extraction_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
