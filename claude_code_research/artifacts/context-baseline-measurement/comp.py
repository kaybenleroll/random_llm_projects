import json,sys,glob,os
f=glob.glob(os.path.join(os.path.expanduser(os.environ.get('CLAUDE_HOME','~/.claude')),'projects/*/'+sys.argv[1]+'*.jsonl'))[0]
for l in open(f):
    d=json.loads(l)
    if d.get('type')=='assistant':
        u=d['message']['usage'];print('USAGE',u.get('input_tokens'),u.get('cache_creation_input_tokens'),u.get('cache_read_input_tokens'));break
    a=d.get('attachment')
    if not a: continue
    t=a.get('type')
    if t=='instructions':
        for x in a['files']: print('  FILE',len(x['content']),x['path'],x.get('type'))
    elif t=='prompt_snapshot':
        print('PS keys',list(a.keys()))
        for k,v in a.items():
            print('  ',k,len(json.dumps(v)))
        sp=a['systemPrompt']; print('  sp parts',[len(s) for s in sp])
    elif t=='skill_listing':
        c=a['content'];print('SKILL lines',len(c.splitlines()),len(c))
    elif t=='deferred_tools_delta': print('DEFERRED',len(a['addedNames']),len(json.dumps(a)))
    elif t=='agent_listing_delta': print('AGENTS',len(a['addedTypes']),len(json.dumps(a)))
    elif t=='mcp_instructions_delta': print('MCPI',len(json.dumps(a)))
    elif t=='hook_success': print('HOOK',len(json.dumps(a.get('content',''))),a.get('hookName'),str(a.get('content'))[:90])
