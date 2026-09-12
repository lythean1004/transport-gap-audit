"""Evidence document downloader, domain validator, hash validator, and text-excerpt verifier.

Enhanced with ALLOW/DENY domains, magic-byte check, retry/backoff, duplicate detection,
and sliding-window sequence matching for paraphrases.
"""

import csv
import datetime
import difflib
import hashlib
import io
import pathlib
import re
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Union
import html2text
import requests

from src.config import sanitize_log

ALLOW = ("go.kr", "lh.or.kr", "gh.or.kr", "korea.kr", "srail.or.kr", "ggc.go.kr")
DENY = (
    "yna.co.kr",
    "kyeonggi.com",
    "hani.co.kr",
    "newsis.com",
    "kihoilbo.co.kr",
    "ekn.kr",
    "blog.naver.com",
    "cafe.daum.net",
    "zippoom.com",
    "v.daum.net",
)
HDRS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://www.google.com/",
}


def norm(s: Optional[str]) -> str:
    """Normalize string by removing whitespaces, zero-width spaces, and quotes."""
    return re.sub(r"[\s\u200b]+", "", s or "").strip("\"'“”\u201c\u201d")


def extract_url(text: Optional[str]) -> str:
    """Extract clean URL from text, removing '원문:' or markdown wrappers."""
    if not text:
        return ""
    cleaned = re.sub(r"^\s*원문\s*:\s*", "", str(text).strip())
    match = re.search(r"https?://[^\s\"'>)]+", cleaned)
    if match:
        return match.group(0).rstrip(".,;")
    return cleaned.strip()


def extract_text_from_pdf(pdf_path: pathlib.Path, txt_path: pathlib.Path) -> str:
    """Extract text from PDF using PyMuPDF (preferred) or pdftotext CLI."""
    try:
        import pymupdf  # PyMuPDF
        doc = pymupdf.open(str(pdf_path))
        text = "\n".join([page.get_text() for page in doc])
        txt_path.write_text(text, encoding="utf-8", errors="ignore")
        return text
    except Exception:
        # Fallback to pdftotext command line if available
        subprocess.run(["pdftotext", "-layout", str(pdf_path), str(txt_path)], check=True)
        return txt_path.read_text(encoding="utf-8", errors="ignore")


def extract_text_from_html(body: Union[bytes, str, pathlib.Path], txt_path: pathlib.Path) -> str:
    """Extract clean text from HTML using html2text."""
    h = html2text.HTML2Text()
    h.ignore_links = True
    h.ignore_images = True
    if isinstance(body, pathlib.Path):
        decoded_html = body.read_text(encoding="utf-8", errors="ignore")
    elif isinstance(body, bytes):
        decoded_html = body.decode("utf-8", errors="ignore")
    else:
        decoded_html = str(body)

    text = h.handle(decoded_html)
    txt_path.write_text(text, encoding="utf-8", errors="ignore")
    return text



def resolve_candidate_file(
    input_path: Union[str, pathlib.Path],
    base_dir: Optional[pathlib.Path] = None
) -> pathlib.Path:
    """Resolves candidate file path.

    If a .psv file does not exist, it automatically checks/fetches .csv (and vice-versa).
    Also searches within data/raw/, data/raw/evidence/, and inbox/ directories.
    """
    if base_dir is None:
        base_dir = pathlib.Path.cwd()

    path = pathlib.Path(input_path)

    # 1. Direct existence check
    if path.is_file():
        return path

    # 2. Check candidate search paths
    search_dirs = [
        path.parent if path.parent != pathlib.Path("") else base_dir,
        base_dir / "data" / "raw",
        base_dir / "data" / "raw" / "evidence",
        base_dir / "evidence",
        base_dir / "inbox",
    ]

    candidate_stems = [path.stem]
    extensions_to_try = [".csv", ".psv"]
    if path.suffix.lower() == ".psv":
        extensions_to_try = [".psv", ".csv"]
    elif path.suffix.lower() == ".csv":
        extensions_to_try = [".csv", ".psv"]

    for d in search_dirs:
        if not d.exists():
            continue
        for stem in candidate_stems:
            for ext in extensions_to_try:
                candidate = d / f"{stem}{ext}"
                if candidate.is_file():
                    return candidate

    raise FileNotFoundError(
        f"후보 파일을 찾을 수 없습니다: '{input_path}'. (.psv 및 .csv 경로 검색 완료)"
    )


def read_candidate_rows(file_path: pathlib.Path) -> List[Dict[str, str]]:

    """Reads a PSV, Markdown-pipe CSV, or standard CSV file cleanly."""
    encodings = ["utf-8-sig", "utf-8", "cp949", "euc-kr"]
    raw_content = None
    used_encoding = "utf-8"

    for enc in encodings:
        try:
            raw_content = file_path.read_text(encoding=enc)
            used_encoding = enc
            break
        except UnicodeDecodeError:
            continue

    if raw_content is None:
        raise ValueError(f"파일 인코딩을 해석할 수 없습니다: {file_path}")

    lines = raw_content.splitlines()
    cleaned_lines = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        # Strip outer quotes if entire line is quoted
        if (stripped.startswith('"') and stripped.endswith('"')) or (
            stripped.startswith("'") and stripped.endswith("'")
        ):
            stripped = stripped[1:-1].strip()
        # Skip markdown table header separator rows like `---|---|...` or `---`
        if re.match(r"^[-| :]+$", stripped) and "-" in stripped:
            continue
        cleaned_lines.append(stripped)

    if not cleaned_lines:
        return []

    first_line = cleaned_lines[0]
    if "|" in first_line:
        delimiter = "|"
    elif "\t" in first_line:
        delimiter = "\t"
    else:
        delimiter = ","

    f_io = io.StringIO("\n".join(cleaned_lines))
    reader = csv.DictReader(f_io, delimiter=delimiter)

    parsed_rows = []
    for r in reader:
        clean_row = {}
        for k, v in r.items():
            if k is None:
                continue
            clean_row[k.strip()] = v.strip() if v else ""

        cand_id = clean_row.get("cand_id", clean_row.get("source_id", ""))
        if cand_id and not re.match(r"^[-]+$", cand_id):
            parsed_rows.append(clean_row)

    return parsed_rows


def verify_evidence_file(
    raw_path: Union[str, pathlib.Path],
    base_dir: Optional[pathlib.Path] = None,
    seen_raw: Optional[Dict[str, str]] = None,
) -> pathlib.Path:
    """Process a raw candidates PSV/CSV file according to the enhanced verification pipeline."""
    if base_dir is None:
        base_dir = pathlib.Path.cwd()
    if seen_raw is None:
        seen_raw = {}

    resolved_path = pathlib.Path(raw_path)
    if not resolved_path.is_file():
        resolved_path = base_dir / raw_path
    if not resolved_path.is_file():
        raise FileNotFoundError(f"파일을 찾을 수 없습니다: {raw_path}")

    doc_dir = base_dir / "evidence" / "documents"
    txt_dir = base_dir / "evidence" / "text"
    doc_dir.mkdir(parents=True, exist_ok=True)
    txt_dir.mkdir(parents=True, exist_ok=True)

    out_path = resolved_path.with_name(resolved_path.stem + "_checked.csv")
    rows = read_candidate_rows(resolved_path)

    print(f"\n========================================================")
    print(f"[*] 검증 실행 시작: {resolved_path.relative_to(base_dir) if resolved_path.is_relative_to(base_dir) else resolved_path}")
    print(f"[*] 총 후보 행 수: {len(rows)}개")
    print(f"========================================================")

    # Required standard output columns
    standard_fields = [
        "cand_id", "development", "event_type", "source_type", "title", "publisher",
        "published_date", "source_url", "url_clean", "domain_check", "file_kind",
        "file_kind_actual", "kind_mismatch", "http_status", "bytes", "sha256_raw",
        "sha256_text", "dup_of", "local_path", "excerpt_found", "excerpt_sim",
        "review_status", "reject_reason", "retrieved_at", "exact_excerpt", "notes"
    ]

    for idx, r in enumerate(rows, 1):
        # 1. URL 정제 및 도메인 검증 (ALLOW / DENY / UNKNOWN)
        raw_url = (r.get("source_url") or "").strip()
        url_clean = extract_url(raw_url)
        r["url_clean"] = url_clean

        if any(d in url_clean for d in DENY):
            domain_check = "DENY"
        elif any(a in url_clean for a in ALLOW):
            domain_check = "ALLOW"
        else:
            domain_check = "UNKNOWN"
        r["domain_check"] = domain_check

        title_short = (r.get("title") or f"doc_{idx}")[:25]
        dev = r.get("development", "common").strip() or "common"
        print(f"[{idx:02d}/{len(rows):02d}] [{dev}] {title_short} (도메인: {domain_check})")

        # 비원문 또는 DENY 도메인 차단
        if not url_clean.startswith("http") or domain_check == "DENY":
            r.update(
                review_status="rejected",
                reject_reason="비원문/URL불량",
                file_kind_actual="",
                kind_mismatch="",
                http_status="DENIED" if domain_check == "DENY" else "INVALID_URL",
                bytes="0",
                sha256_raw="",
                sha256_text="",
                dup_of="",
                local_path="",
                excerpt_found="",
                excerpt_sim="",
                retrieved_at=datetime.datetime.now().astimezone().isoformat(timespec="seconds")
            )
            continue

        # 2. 백오프 재시도 다운로드 (3회)
        body: Optional[bytes] = None
        last_status = "0"
        for attempt in range(3):
            try:
                resp = requests.get(url_clean, headers=HDRS, timeout=60)
                last_status = str(resp.status_code)
                if resp.ok and len(resp.content) >= 500:
                    body = resp.content
                    break
                time.sleep(4 * (attempt + 1))
            except Exception as e:
                last_status = sanitize_log(f"ERR:{e.__class__.__name__}")
                time.sleep(4 * (attempt + 1))

        time.sleep(2.0)  # 레이트리밋 방지 딜레이

        r["http_status"] = last_status

        if body is None:
            r.update(
                review_status="refetch_required",
                reject_reason="차단/과소응답",
                file_kind_actual="",
                kind_mismatch="",
                bytes="0",
                sha256_raw="",
                sha256_text="",
                dup_of="",
                local_path="",
                excerpt_found="",
                excerpt_sim="",
                retrieved_at=datetime.datetime.now().astimezone().isoformat(timespec="seconds")
            )
            continue

        # 3. 매직바이트 검사 (%PDF) 및 해시 계산
        is_pdf = body[:4] == b"%PDF"
        file_kind_actual = "pdf" if is_pdf else "html"
        r["file_kind_actual"] = file_kind_actual
        declared_kind = r.get("file_kind", "").strip().lower()
        r["kind_mismatch"] = "Y" if (declared_kind and declared_kind != file_kind_actual) else ""
        r["sha256_raw"] = hashlib.sha256(body).hexdigest()
        r["bytes"] = str(len(body))

        # 4. 문서 저장
        target_dev_dir = doc_dir / dev
        target_dev_dir.mkdir(parents=True, exist_ok=True)
        pub = (r.get("published_date") or "nodate").strip()[:10] or "nodate"
        safe_title = re.sub(r"[^\w가-힣._-]", "_", r.get("title", f"doc_{idx}"))[:60]
        doc_path = target_dev_dir / f"{pub}_{safe_title}.{file_kind_actual}"
        doc_path.write_bytes(body)
        r["local_path"] = str(
            doc_path.relative_to(base_dir) if doc_path.is_relative_to(base_dir) else doc_path
        )

        # 5. 본문 텍스트 추출 및 정규화 텍스트 해시
        txt_path = txt_dir / f"{doc_path.stem}.txt"
        try:
            if is_pdf:
                text = extract_text_from_pdf(doc_path, txt_path)
            else:
                text = extract_text_from_html(body, txt_path)
        except Exception:
            r.update(
                review_status="needs_human",
                reject_reason="본문추출실패",
                sha256_text="",
                dup_of="",
                excerpt_found="",
                excerpt_sim="",
                retrieved_at=datetime.datetime.now().astimezone().isoformat(timespec="seconds")
            )
            continue

        norm_text = norm(text)
        sha256_text = hashlib.sha256(norm_text.encode("utf-8")).hexdigest()
        r["sha256_text"] = sha256_text

        # 6. 동일 문서 재수집 탐지
        cand_id = r.get("cand_id", f"C_{idx}")
        dup = seen_raw.get(sha256_text)
        r["dup_of"] = dup or ""
        seen_raw.setdefault(sha256_text, cand_id)

        # 7. 인용 검증: 연속 구절 요구 + 유사도(SequenceMatcher) 보조
        nb = norm_text
        ne = norm(r.get("exact_excerpt", ""))
        
        if len(ne) < 40:
            r["excerpt_found"] = "TOO_SHORT"
            r["excerpt_sim"] = ""
        elif ne in nb:
            r["excerpt_found"] = "Y"
            r["excerpt_sim"] = "1.0"
        else:
            best = max(
                (
                    difflib.SequenceMatcher(None, ne[:80], nb[i : i + 80]).ratio()
                    for i in range(0, max(1, len(nb) - 80), 40)
                ),
                default=0.0,
            )
            r["excerpt_found"] = "PARAPHRASE" if best > 0.82 else "N"
            r["excerpt_sim"] = str(round(best, 3))

        r["retrieved_at"] = datetime.datetime.now().astimezone().isoformat(timespec="seconds")

        # 8. 최종 review_status 판정
        if (
            r["excerpt_found"] == "Y"
            and r["domain_check"] == "ALLOW"
            and not r["kind_mismatch"]
        ):
            r["review_status"] = "link_verified"
            r["reject_reason"] = ""
        else:
            r["review_status"] = "needs_human"
            reasons = []
            if r["domain_check"] != "ALLOW":
                reasons.append(f"도메인:{r['domain_check']}")
            if r["kind_mismatch"]:
                reasons.append("파일형식불일치")
            if r["excerpt_found"] != "Y":
                reasons.append(f"인용문:{r['excerpt_found']}")
            r["reject_reason"] = "; ".join(reasons)

    # Determine CSV output columns
    all_keys = list(rows[0].keys()) if rows else standard_fields
    for sf in standard_fields:
        if sf not in all_keys:
            all_keys.append(sf)

    def safe_write_csv(path: pathlib.Path, fieldnames: List[str], data_rows: List[Dict[str, str]]) -> pathlib.Path:
        tmp_path = path.with_name(f"{path.stem}_tmp_{int(time.time())}.csv")
        with tmp_path.open("w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            w.writeheader()
            w.writerows(data_rows)
        for _ in range(5):
            try:
                if path.exists():
                    path.unlink()
                tmp_path.rename(path)
                return path
            except (PermissionError, OSError):
                time.sleep(1.0)
        print(f"[!] 알림: {path.name} 파일이 잠겨 있어 임시 파일({tmp_path.name})로 저장되었습니다.")
        return tmp_path

    saved_path = safe_write_csv(out_path, all_keys, rows)


    verified_cnt = sum(r.get("review_status") == "link_verified" for r in rows)
    rejected_cnt = sum(r.get("review_status") == "rejected" for r in rows)
    refetch_cnt = sum(r.get("review_status") == "refetch_required" for r in rows)
    needs_human_cnt = sum(r.get("review_status") == "needs_human" for r in rows)

    print(f"\n[*] 결과 저장 완료: {out_path.name}")
    print(f"    - link_verified (검증완료): {verified_cnt}")
    print(f"    - needs_human   (수동검토): {needs_human_cnt}")
    print(f"    - rejected      (반려/비원문): {rejected_cnt}")
    print(f"    - refetch_req   (재수집필요): {refetch_cnt}")
    print(f"    - 합계: {len(rows)}건")

    return out_path


def main():
    target_files = [
        "data/raw/historical_validation_candidates.psv",
        "data/raw/forward_monitoring_candidates.psv",
        "data/raw/evidence/선단지_RAW.csv",
        "data/raw/evidence/후기단지_RAW.csv",
    ]

    if len(sys.argv) > 1:
        target_files = sys.argv[1:]

    seen_raw: Dict[str, str] = {}
    for target in target_files:
        p = pathlib.Path(target)
        if p.exists():
            verify_evidence_file(p, seen_raw=seen_raw)
        else:
            print(f"[!] 파일을 찾을 수 없습니다: {target}")


if __name__ == "__main__":
    main()
