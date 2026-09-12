import csv
with open('bldg_query_plan.csv', 'r', encoding='utf-8-sig') as f:
    for row in csv.DictReader(f):
        if row['lookup_status'] == 'MISS':
            print(f"{row['cluster_id']} | {row['pilot_id']} | sg:{row['sigunguCd']} | {row['addr_legal']} | token:{row['dong_token']}")
