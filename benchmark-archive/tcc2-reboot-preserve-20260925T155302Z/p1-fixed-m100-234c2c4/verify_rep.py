import json, glob, sys
from pathlib import Path
indir, expfile = sys.argv[1], sys.argv[2]
expected = [l.strip() for l in open(expfile) if l.strip()]
files=[p for p in glob.glob(f'{indir}/*.json') if 'summary' not in Path(p).name]
stems=sorted([Path(p).stem for p in files])
ok=True
if len(files)!=len(expected):
    print(f"FAIL count {len(files)} != expected {len(expected)}"); ok=False
if stems!=sorted(expected):
    print("FAIL stem mismatch"); print("missing:", sorted(set(expected)-set(stems))); print("extra:", sorted(set(stems)-set(expected))); ok=False
else:
    print(f"count/stems OK: {len(files)}")
issues=[]
for f in sorted(files):
    j=json.load(open(f))
    sc=j.get('scenario_config',{}); r=(j.get('runs') or [{}])[0]; lg=r.get('loadgen',{})
    stem=Path(f).stem
    if sc.get('workload_shape')!='fixed-clients': issues.append((stem,'workload_shape'))
    if sc.get('messages')!=100 or sc.get('requested_messages')!=100: issues.append((stem,f"messages {sc.get('messages')}/{sc.get('requested_messages')}"))
    topo=sc.get('client_topology',{})
    if topo.get('effective_mode')!='container-per-client': issues.append((stem,'topology '+str(topo.get('effective_mode'))))
    if topo.get('memory')!='96m': issues.append((stem,'memory '+str(topo.get('memory'))))
    tls_file=stem.endswith('-TLS'); tls_flag=bool(j.get('tls',{}).get('enabled',False))
    if tls_file!=tls_flag: issues.append((stem,f'tls file={tls_file} flag={tls_flag}'))
    # percentile ordering for all latency blocks with counts>0
    for blk in ['connect','publish','receive','subscribe','unsubscribe','disconnect','auth','token_refresh']:
        b=lg.get(blk)
        if isinstance(b,dict) and (b.get('count') or 0)>0:
            vals=[b.get(k) for k in ['min_ms','p50_ms','p95_ms','p99_ms','max_ms']]
            if any(v is None for v in vals): issues.append((stem,f'{blk} null pct')); continue
            if not (vals[0]<=vals[1]<=vals[2]<=vals[3]<=vals[4]): issues.append((stem,f'{blk} ordering {vals}'))
    errs=lg.get('errors',[]) or []
    for e in errs:
        s=str(e)
        # KICK expected signature only; B06 has no KICK scenarios so any error is unexpected
        issues.append((stem,f'unexpected error: {s[:120]}'))
    # raw sample counts sanity: raw_metrics publish/connect present when counts>0
    rm=lg.get('raw_metrics',{})
    if not isinstance(rm,dict): issues.append((stem,'raw_metrics missing'))
if issues:
    print(f"FAIL {len(issues)} issues:"); [print(' ',a,b) for a,b in issues[:30]]; ok=False
else:
    print("semantic/numerical checks OK (shape,messages,topology,memory,tls,percentiles,errors)")
sys.exit(0 if ok else 1)
