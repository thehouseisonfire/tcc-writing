import json, glob
from pathlib import Path
dirs=[f'mqtt-auth-biscuit/benchmarks/results-final-p1-234c2c4-fixed-clients-m100-idx126-149-r{i}' for i in (1,2,3)]
# compare deterministic semantic counters across reps: connect count, publish count, receive count, qos, fanout, control
import collections
keys=['connect','publish','receive','subscribe']
for d in dirs: print(d, len([p for p in glob.glob(d+'/*.json') if 'summary' not in p]))
# per-stem compare
stems=sorted([Path(p).stem for p in glob.glob(dirs[0]+'/*.json') if 'summary' not in p])
mismatch=0
for s in stems:
    vals=[]
    for d in dirs:
        j=json.load(open(f'{d}/{s}.json')); lg=j['runs'][0]['loadgen']
        tup=(lg.get('connect',{}).get('count'), lg.get('publish',{}).get('count'), lg.get('received_messages',{}).get('count') if isinstance(lg.get('received_messages'),dict) else str(type(lg.get('received_messages'))), lg.get('publish_outcomes',{}).get('attempted'), lg.get('control',{}).get('count') if isinstance(lg.get('control'),dict) else None, lg.get('control_effect',{}).get('notifications'), lg.get('fanout_metrics',{}) if isinstance(lg.get('fanout_metrics'),dict) else None, j.get('fanout_metrics'))
        vals.append(tup)
    if not (vals[0]==vals[1]==vals[2]):
        mismatch+=1
        print('MISMATCH',s,vals)
print('triplet deterministic mismatches:',mismatch)
