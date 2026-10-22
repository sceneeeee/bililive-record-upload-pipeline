#!/usr/bin/python3
import os
"""Install this scheduler only after the user approves the safe maintenance window."""
import json
from pathlib import Path
import subprocess

stage=Path(os.environ.get('PATCH_STAGE', os.environ.get('STACK_ROOT', '/opt/bililive-stack') + '/patches/uploader-3.20.0'))
if not (stage/'approved.json').exists():
    raise SystemExit('No explicit approval recorded; maintenance disabled')
if (stage/'failed.json').exists():
    raise SystemExit('Previous maintenance failed; manual review required')
if (stage/'applied.json').exists():
    raise SystemExit(0)
result=subprocess.run(['python3',str(stage/'apply.py'),'--approved-window'],capture_output=True,text=True)
expected=['Room is live: no restart allowed','Nonterminal tasks exist','Still within normal manuscript merge window','Upload callbacks still active']
if result.returncode and any(s in result.stderr for s in expected):
    print(json.dumps({'event':'safe_window_not_ready','action':'no_change'}))
    raise SystemExit(0)
print(result.stdout)
if result.returncode:
    print(result.stderr)
    failure=stage/'failed.json'
    failure.write_text(json.dumps({'event':'patch_failed_manual_review_required','exit':result.returncode}))
    failure.chmod(0o600)
raise SystemExit(result.returncode)
