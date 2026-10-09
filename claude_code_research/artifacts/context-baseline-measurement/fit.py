import json,sys,glob,os
def go(sid):
    f=glob.glob(os.path.join(os.path.expanduser(os.environ.get('CLAUDE_HOME','~/.claude')),'projects/*/'+sid+'*.jsonl'))[0]
    tot=0;comp={}
    for l in open(f):
        d=json.loads(l)
        if d.get('type')=='assistant':
            u=d['message']['usage'];T=u['input_tokens']+u['cache_creation_input_tokens']+u['cache_read_input_tokens'];break
        a=d.get('attachment')
        if d.get('type')=='user':
            c=d['message']['content'];tot+=len(c if isinstance(c,str) else json.dumps(c));continue
        if not a: continue
        t=a['type']
        if t=='instructions': n=sum(len(x['content']) for x in a['files'])
        elif t=='prompt_snapshot': n=sum(len(s) for s in a['systemPrompt'])
        elif t=='skill_listing': n=len(a['content'])
        elif t=='deferred_tools_delta': n=len(', '.join(a['addedNames']))+60
        elif t=='agent_listing_delta': n=len(json.dumps(a))
        elif t=='mcp_instructions_delta': n=sum(len(b) for b in a['addedBlocks'])
        elif t=='hook_success': n=len(str(a.get('content','')))
        elif t in('environment','model','session_context','date','credential_org','remote_session_change','total_tokens_reminder'): n=len(json.dumps(a))
        else: n=0
        tot+=n
    return T,tot
for s in sys.argv[1:]: print(s,go(s))
