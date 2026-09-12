"""
전체 실행 후 결과 검증 스크립트.
complex_geocode.csv의 품질을 다각도로 점검한다.
"""
import pandas as pd
import math

def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371008.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    h = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2*R*math.asin(math.sqrt(h))

df = pd.read_csv("exports/complex_geocode.csv")
df_plan = pd.read_csv("bldg_query_plan.csv")

print("=" * 60)
print("VWorld Geocoder v3 전체 실행 검증")
print("=" * 60)

# 1. 기본 통계
print(f"\n[1] 기본 통계")
print(f"  총 행: {len(df)}")
print(f"  needs_review=True: {df['needs_review'].sum()}")
print(f"  needs_review=False: {(~df['needs_review'].astype(bool)).sum()}")

# 2. 오버라이드 적용 현황
ov = df[df["override_decision"].notna() & (df["override_decision"] != "")]
print(f"\n[2] 오버라이드 적용: {len(ov)}건")
for _, r in ov.iterrows():
    print(f"  {r.cluster_id} | {r.override_decision} | {r.addr_variant_used} | {r.type} | basis={r.coord_geom_basis}")

# 3. representative_method 분포
print(f"\n[3] representative_method 분포")
print(df["representative_method"].value_counts().to_string())

# 4. coord_geom_basis 분포
print(f"\n[4] coord_geom_basis 분포")
print(df["coord_geom_basis"].value_counts().to_string())

# 5. centroid 행의 basis 검증
centroid_rows = df[df["representative_method"] == "centroid"]
if len(centroid_rows) > 0:
    bad = centroid_rows[~centroid_rows["coord_geom_basis"].astype(str).str.startswith("centroid_of_")]
    if len(bad) > 0:
        print(f"\n  [FAIL] centroid인데 basis 오표기: {bad['cluster_id'].tolist()}")
    else:
        print(f"\n  [OK] centroid {len(centroid_rows)}건 모두 basis 정상")
else:
    print(f"\n  centroid 행 없음")

# 6. spread > 300m인 행
big_spread = df[df["centroid_spread_m"] > 300]
if len(big_spread) > 0:
    print(f"\n[6] spread > 300m: {len(big_spread)}건")
    for _, r in big_spread.iterrows():
        print(f"  {r.cluster_id} | method={r.representative_method} | spread={r.centroid_spread_m}m | basis={r.coord_geom_basis}")
else:
    print(f"\n[6] spread > 300m: 없음 [OK]")

# 7. 좌표 충돌 검사 (1m 이내)
print(f"\n[7] 좌표 충돌 검사 (1m 이내)")
ids = df["cluster_id"].tolist()
lats = df["lat"].tolist()
lons = df["lon"].tolist()
collisions = 0
for i in range(len(ids)):
    for j in range(i+1, len(ids)):
        if ids[i] == ids[j]:
            continue
        d = haversine_m(lats[i], lons[i], lats[j], lons[j])
        if d < 1.0:
            print(f"  [충돌] {ids[i]} vs {ids[j]}: {d:.2f}m")
            collisions += 1
if collisions == 0:
    print(f"  충돌 없음 [OK]")

# 8. 꼬리 하이픈 검사
bad_hyp = df[df["addr_query"].astype(str).str.endswith("-")]
if len(bad_hyp) > 0:
    print(f"\n[8] 꼬리 하이픈 잔존: {bad_hyp['cluster_id'].tolist()}")
else:
    print(f"\n[8] 꼬리 하이픈: 없음 [OK]")

# 9. qa_flag 분포
print(f"\n[9] qa_flag 분포")
flags = df["qa_flag"].dropna()
flags = flags[flags != ""]
if len(flags) > 0:
    all_flags = []
    for f in flags:
        all_flags.extend(str(f).split("|"))
    from collections import Counter
    c = Counter(all_flags)
    for k, v in c.most_common():
        print(f"  {k}: {v}건")
else:
    print(f"  플래그 없음 [OK]")

# 10. 건수 정합
plan_total = len(df_plan)
plan_valid = len(df_plan[(df_plan['needs_review'] == False) & (df_plan['parse_status'] == 'SUCCESS')])
plan_clusters = df_plan[(df_plan['needs_review'] == False) & (df_plan['parse_status'] == 'SUCCESS')]['cluster_id'].nunique()
print(f"\n[10] 건수 정합")
print(f"  5A Plan rows: {plan_total}")
print(f"  5A Valid parcels: {plan_valid}")
print(f"  5A Unique clusters: {plan_clusters}")
print(f"  6B Success clusters: {len(df)}")
print(f"  6B + override 추가분: {len(ov)}건")

# 11. san_substituted 원래 6건 확인
print(f"\n[11] 원 needs_review 6건 상태")
target_ids = ["A10026126", "A10026206", "A10025583", "A10026990", "A10027957", "A10027692"]
for tid in target_ids:
    row = df[df["cluster_id"] == tid]
    if row.empty:
        print(f"  {tid}: 누락!")
    else:
        r = row.iloc[0]
        print(f"  {tid} | review={r.needs_review} | variant={r.addr_variant_used} | type={r.type} | basis={r.coord_geom_basis} | override={r.get('override_decision','')}")

print(f"\n{'=' * 60}")
print("검증 완료")
