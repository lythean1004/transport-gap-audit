#!/usr/bin/env python3
# fix_pilot_citycode_map.py
# exports/pilot_citycode_map.csv 의 candidate_citycode / match_flag /
# citycode_confirmed_by 를 확정한다.
#
# 2단계 구조:
#   Step 1 (offline) : 부분일치 오매칭 해소 + 참조표로 코드 채움 -> pending_live_verify
#   Step 2 (live)    : TAGO getCtyCodeList 실측으로 confirmed_by 덮어쓰기
#
# 실행:
#   python fix_pilot_citycode_map.py                 # offline 정리만
#   python fix_pilot_citycode_map.py --live          # getCtyCodeList 실측까지

import argparse
import csv
import datetime as dt
import os
import sys
from pathlib import Path

SRC = Path("exports/pilot_citycode_map.csv")
DST = Path("exports/pilot_citycode_map.csv")
BAK_DIR = Path("exports/_backup")
QA = Path("qa/citycode_resolution_log.csv")

TAGO_BASE = "https://apis.data.go.kr/1613000/BusSttnInfoInqireService"
OP_CITY = "getCtyCodeList"

# ---------------------------------------------------------------
# 참조표: 출처가 확인된 값만 넣는다. 기억으로 채우지 않는다.
#   gg_gits  = 경기도 교통정보센터 오픈API '연계된 지방자치단체 ID' 표
#   kostat   = 통계청 계열 시군구코드(노인실태조사 매뉴얼 등 교차확인)
# 주의: 이 체계가 TAGO citycode와 동일하다는 보장은 없다.
#       그래서 offline 단계에서는 confirmed_by 를 pending_live_verify 로 둔다.
# ---------------------------------------------------------------
REF = {
    "화성시":       {"code": "31240", "src": "gg_gits+kostat"},
    "김포시":       {"code": "31230", "src": "kostat"},
    "하남시":       {"code": "31180", "src": "kostat"},
    "성남시":       {"code": "31020", "src": "gg_gits"},
    "남양주시":     {"code": "31130", "src": "gg_gits"},
    # 오매칭 방지용으로만 보유. pilot 대상 아님.
    "광주시":       {"code": "31250", "src": "gg_gits+kostat"},
    "양주시":       {"code": "31260", "src": "kostat"},
}

# 서울 자치구는 TAGO 지원 여부 미확인 -> 별도 소스로 에스컬레이션
SEOUL_GU_SUFFIX = "구"
SEOUL_GU_NAMES = {"송파구", "강동구", "강남구"}  # 필요 시 확장

# 시 단위만 제공되어 구 단위로 좁힐 수 없는 경우
CITY_LEVEL_ONLY = {"성남시 수정구": "성남시",
                   "성남시 중원구": "성남시",
                   "성남시 분당구": "성남시"}

OUT_COLS = ["development_id", "sigungu", "candidate_cityname",
            "candidate_citycode", "match_flag", "citycode_confirmed_by",
            "code_source", "resolution_note"]


def normalize(name: str) -> str:
    return (name or "").strip()


def resolve(sigungu: str):
    """returns (cityname, citycode, match_flag, code_source, note)"""
    s = normalize(sigungu)

    # 1) 서울 자치구 -> TAGO 지원 미확인. 공란 유지.
    if s in SEOUL_GU_NAMES or (s.endswith(SEOUL_GU_SUFFIX) and "시" not in s):
        return ("", "", "NO_MATCH", "",
                "TAGO 서울 지원 미확인(공식 BIS는 bus.go.kr 별도). "
                "서울 열린데이터광장 정류소 위치정보로 별도 처리 필요.")

    # 2) 일반구 포함 -> 시 단위로 축약
    if s in CITY_LEVEL_ONLY:
        city = CITY_LEVEL_ONLY[s]
        ref = REF[city]
        return (city, ref["code"], "OK_CITY_LEVEL", ref["src"],
                f"{s}는 구 단위 코드 없음. {city} 전체 코드로 조회되므로 "
                f"좌표반경(getCrdntPrxmtSttnList)으로 구 경계 보정 필요.")

    # 3) 완전일치 우선 (부분일치가 MULTIPLE_MATCH를 만든 원인)
    if s in REF:
        ref = REF[s]
        return (s, ref["code"], "OK", ref["src"], "exact_match")

    # 4) 부분일치 후보 열거 -> 그래도 확정 안 하면 수동
    cands = [k for k in REF if k in s or s in k]
    if len(cands) == 1:
        ref = REF[cands[0]]
        return (cands[0], ref["code"], "RESOLVED", ref["src"],
                f"exact miss, unique substring match: {cands[0]}")
    if len(cands) > 1:
        return ("MULTIPLE: " + ", ".join(sorted(cands)), "", "MULTIPLE_MATCH",
                "", "완전일치 실패. 수동 확정 필요.")

    return ("", "", "NO_MATCH", "", "참조표에 없음. getCtyCodeList 실측 필요.")


def load_live_citycodes(service_key: str):
    """TAGO getCtyCodeList 실측. {cityname: citycode}"""
    import requests  # live 모드에서만 필요

    params = {
        "serviceKey": service_key,   # 반드시 Decoding 키 (params= 사용 시 이중인코딩 방지)
        "numOfRows": 1000,
        "pageNo": 1,
        "_type": "json",
    }
    r = requests.get(f"{TAGO_BASE}/{OP_CITY}", params=params, timeout=20)
    r.raise_for_status()
    body = r.json()["response"]

    head = body["header"]
    if head.get("resultCode") != "00":
        raise RuntimeError(
            f"getCtyCodeList 실패 resultCode={head.get('resultCode')} "
            f"msg={head.get('resultMsg')}\n"
            "20/30이면 키 철자보다 데이터셋 15098534 활용신청 상태를 먼저 확인."
        )

    items = body["body"]["items"]["item"]
    if isinstance(items, dict):
        items = [items]
    return {str(i["cityname"]).strip(): str(i["citycode"]).strip() for i in items}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true",
                    help="getCtyCodeList 실측으로 confirmed_by 확정")
    ap.add_argument("--src", default=str(SRC))
    args = ap.parse_args()

    src = Path(args.src)
    if not src.exists():
        sys.exit(f"입력 없음: {src}")

    rows = list(csv.DictReader(src.open(encoding="utf-8-sig")))

    live_map = {}
    if args.live:
        from dotenv import load_dotenv
        load_dotenv()
        key = os.environ.get("TAGO_API_KEY")
        if not key:
            sys.exit("환경변수 TAGO_API_KEY 없음 (Decoding 키를 넣으세요)")
        live_map = load_live_citycodes(key)
        print(f"[live] getCtyCodeList 수신 {len(live_map)}건")

    today = dt.date.today().isoformat()
    out, log = [], []

    for r in rows:
        dev = r.get("development_id", "")
        sig = normalize(r.get("sigungu"))
        before = (r.get("candidate_citycode", ""), r.get("match_flag", ""))

        name, code, flag, csrc, note = resolve(sig)

        if flag == "NO_MATCH" and not name:
            confirmed_by = "escalate_to_seoul_api" if sig in SEOUL_GU_NAMES else ""
        elif flag == "MULTIPLE_MATCH":
            confirmed_by = ""
        else:
            confirmed_by = "pending_live_verify"

        # live 실측 결과로 덮어쓰기
        if args.live and name and not name.startswith("MULTIPLE"):
            if name in live_map:
                live_code = live_map[name]
                if live_code != code:
                    note += f" | LIVE_MISMATCH: ref={code} live={live_code} -> live 채택"
                    code = live_code
                    csrc = "getCtyCodeList"
                confirmed_by = f"getCtyCodeList:{today}"
                flag = "OK" if flag == "OK" else flag
            else:
                confirmed_by = "not_served_by_tago"
                flag = "NO_TAGO_COVERAGE"
                note += " | getCtyCodeList 응답에 해당 시명 없음. 0건을 접근성 0점으로 환산 금지."

        out.append({
            "development_id": dev,
            "sigungu": sig,
            "candidate_cityname": name,
            "candidate_citycode": code,
            "match_flag": flag,
            "citycode_confirmed_by": confirmed_by,
            "code_source": csrc,
            "resolution_note": note,
        })
        log.append({
            "development_id": dev, "sigungu": sig,
            "before_code": before[0], "before_flag": before[1],
            "after_code": code, "after_flag": flag,
            "confirmed_by": confirmed_by, "note": note,
        })

    BAK_DIR.mkdir(parents=True, exist_ok=True)
    bak = BAK_DIR / f"pilot_citycode_map.{dt.datetime.now():%Y%m%d_%H%M%S}.csv"
    bak.write_bytes(src.read_bytes())

    with DST.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=OUT_COLS)
        w.writeheader()
        w.writerows(out)

    QA.parent.mkdir(parents=True, exist_ok=True)
    with QA.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(log[0].keys()))
        w.writeheader()
        w.writerows(log)

    print(f"backup : {bak}")
    print(f"written: {DST}  ({len(out)} rows)")
    print(f"qa log : {QA}")

    unresolved = [r for r in out if r["match_flag"] in
                  ("MULTIPLE_MATCH", "NO_MATCH", "NO_TAGO_COVERAGE")]
    if unresolved:
        print("\n[수동 확인 필요]")
        for r in unresolved:
            print(f"  - {r['development_id']} / {r['sigungu']} "
                  f"/ {r['match_flag']} / {r['resolution_note']}")


if __name__ == "__main__":
    main()
