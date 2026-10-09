import json,sys,glob,os
rows=[]
for f in glob.glob(os.path.join(os.path.expanduser(os.environ.get('CLAUDE_HOME','~/.claude')),'projects/*/*.jsonl')):
    try:
        for l in open(f):
            try:d=json.loads(l)
            except: continue
            if d.get('type')=='assistant' and not d.get('isSidechain'):
                u=d['message'].get('usage',{})
                rows.append((d.get('timestamp'),f.split('/')[-2],f.split('/')[-1][:8],d['message'].get('model'),u.get('input_tokens',0),u.get('cache_creation_input_tokens',0),u.get('cache_read_input_tokens',0)))
                break
    except Exception as e: pass
rows.sort(reverse=True)
for r in rows[:int(sys.argv[1]) if len(sys.argv)>1 else 10]: print(*r)
