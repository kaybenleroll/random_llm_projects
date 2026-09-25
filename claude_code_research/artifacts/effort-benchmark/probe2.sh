#!/usr/bin/env bash
source "$(dirname "$0")/env_clean.sh"
cd "$(dirname "$0")/cwd"
export CLAUDE_CODE_DISABLE_AUTO_MEMORY=1
for cfg in "claude-sonnet-5 xhigh" "claude-opus-5-5 max"; do set -- $cfg
"${CLEAN_ENV[@]}" claude -p --setting-sources "" --tools "" --strict-mcp-config --disable-slash-commands --model $1 --effort $2 --output-format stream-json --verbose --include-hook-events "What is 17*23? Answer with just the number." < /dev/null > ../logs/probe_eff_$2.jsonl 2>&1; echo rc=$? $cfg
python3 - $2 <<'PY'
import json,sys
ev=[json.loads(l) for l in open(f'../logs/probe_eff_{sys.argv[1]}.jsonl') if l.startswith('{')]
from collections import Counter
print(Counter((e['type'],e.get('subtype')) for e in ev))
print({k:v for k,v in ev[0].items() if 'effort' in k.lower() or k in('model','session_id')})
print(ev[-1].get('result'), ev[-1]['usage'])
print([k for k in ev[-1].keys()])
PY
done
