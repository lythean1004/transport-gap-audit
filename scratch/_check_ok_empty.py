import csv
with open('evidence/arrival_ledger.csv','r',encoding='utf-8') as f:
    rows = list(csv.DictReader(f))
out = open('scratch/_ok_empty_context.txt','w',encoding='utf-8')
for r in rows:
    if r['outcome']=='ok_empty':
        od = r['obs_date']
        sh = r['slot_hhmm']
        out.write('=== ok_empty: %s %s ===\n' % (od, sh))
        same_day = sorted([x for x in rows if x['obs_date']==od], key=lambda x: x['slot_hhmm'])
        idx = next(i for i,x in enumerate(same_day) if x['slot_hhmm']==sh and x['outcome']=='ok_empty')
        for j in range(max(0,idx-3), min(len(same_day),idx+4)):
            x = same_day[j]
            mark = ' <<< OK_EMPTY' if j==idx else ''
            line = '  slot=%s ic=%s outcome=%s rc=%s%s\n' % (x['slot_hhmm'], x['item_count'], x['outcome'], x['result_code'], mark)
            out.write(line)
        out.write('\n')
out.close()
