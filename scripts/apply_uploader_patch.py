#!/usr/bin/python3
"""Run only after explicit approval, outside the live/merge window."""
import argparse, base64, datetime, hashlib, json, os, pathlib, shlex, shutil, subprocess, time, urllib.request

ROOT=pathlib.Path(os.environ.get('STACK_ROOT', '/opt/bililive-stack'))
STAGE=pathlib.Path(os.environ.get('PATCH_STAGE', str(ROOT/'patches/uploader-3.20.0')))
BACKUP=ROOT/'backups/uploader-backup'

def run(args):return subprocess.check_output(args,text=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 if not __debug__:raise SystemExit("Safety guard requires Python assertions; do not use -O")
 parser=argparse.ArgumentParser();parser.add_argument('--approved-window',action='store_true');parser.add_argument('--rollback',action='store_true');args=parser.parse_args()
 assert args.approved_window,'Explicit user approval is required before this script is run'
 env={}
 for l in (ROOT/'.env').read_text().splitlines():
  if '=' in l and not l.startswith('#'):
   k,v=l.split('=',1);a=shlex.split(v);env[k]=a[0] if a else ''
 rh={'Authorization':'Basic '+base64.b64encode((env['BREC_HTTP_BASIC_USER']+':'+env['BREC_HTTP_BASIC_PASS']).encode()).decode()}
 th={'Authorization':env['BILILIVE_TOOLS_PASSKEY'],'Content-Type':'application/json'}
 def api(base,path,headers,body=None):
  req=urllib.request.Request(base+path,headers=headers,data=None if body is None else json.dumps(body).encode())
  with urllib.request.urlopen(req,timeout=10) as r:return json.load(r)
 rec='http://127.0.0.1:2356';tools='http://127.0.0.1:18010'
 rooms=api(rec,'/api/room',rh);assert all(not r['streaming'] and not r['recording'] for r in rooms),'Room is live: no restart allowed'
 snapshot=api(tools,'/task/?pageSize=10000',th)
 assert snapshot['pagination']['total']==len(snapshot['list']),'Incomplete task snapshot'
 tasks=snapshot['list']
 assert all(t['status'] in ['completed','error','canceled'] for t in tasks),'Nonterminal tasks exist'
 lives=api(tools,'/common/webhook',th,{})
 assert all(p.get('uploadStatus')!='uploading' and p.get('rawUploadStatus')!='uploading' for l in lives for p in l.get('parts',[])),'Upload callbacks still active'
 latest=max((p.get('endTime',0) for l in lives for p in l.get('parts',[])),default=0)
 merge_minutes=max([json.loads((ROOT/'data/appConfig.json').read_text())['webhook'].get('partMergeMinute',10)]+[r.get('partMergeMinute',10) for r in json.loads((ROOT/'data/appConfig.json').read_text())['webhook'].get('rooms',{}).values()])
 assert datetime.datetime.now().timestamp()*1000-latest>(merge_minutes*60+60)*1000,'Still within normal manuscript merge window'
 config=json.loads((ROOT/'recorder/config.json').read_text())
 assert config['global']['CuttingMode']['Value']==2 and config['global']['CuttingNumber']['Value']==5120
 assert all(r['CuttingMode']['Value']==2 and r['CuttingNumber']['Value']==5120 for r in config['rooms'])
 assert 'ss秒' in config['global']['FileNameRecordTemplate']['Value']
 manifest=json.loads((STAGE/'manifest.json').read_text())
 assert sha(STAGE/'compose.yaml.patched')==manifest['patched_compose_sha256'],'Staged compose changed'
 expected=manifest['patched_compose_sha256'] if args.rollback else manifest['original_compose_sha256']
 assert sha(ROOT/'compose.yaml')==expected,'Compose changed since preparation'
 for name,h in manifest['patch_sha256'].items():assert sha(STAGE/name)==h,'Patch artifact changed'
 current_core=run(['docker','exec','bililive-api','sha256sum','/app/index-DQV9sVEn.cjs']).split()[0]
 current_server=run(['docker','exec','bililive-api','sha256sum','/app/index-ZJeYopVC.cjs']).split()[0]
 expected_core=manifest['patch_sha256']['index-DQV9sVEn.cjs'] if args.rollback else manifest['original_core_sha256']
 expected_server=manifest['patch_sha256']['index-ZJeYopVC.cjs'] if args.rollback else manifest['original_server_sha256']
 assert (current_core,current_server)==(expected_core,expected_server),'Installed source differs from audited source'
 prefix='rollback' if args.rollback else 'apply'
 evidence=BACKUP/(prefix+'-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S'));evidence.mkdir(mode=0o700)
 for name,data in [('tasks-before.json',tasks),('lives-before.json',lives)]:
  (evidence/name).write_text(json.dumps(data,ensure_ascii=False));(evidence/name).chmod(0o600)
 before=json.loads(run(['docker','inspect','bililive-recorder','bililive-api','bililive-web']))
 protected={r:sha(ROOT/r) for r in ['recorder/config.json','data/appConfig.json','data/presets.json']}
 shutil.copy2(ROOT/'compose.yaml',evidence/'compose.yaml.before')
 target=(BACKUP/'compose.yaml') if args.rollback else STAGE/'compose.yaml.patched'
 shutil.copy2(target,ROOT/'compose.yaml')
 run(['docker','compose','-f',str(ROOT/'compose.yaml'),'config','--quiet'])
 try:
  assert all(not r['streaming'] and not r['recording'] for r in api(rec,'/api/room',rh)),'Room is live: no restart allowed'
  snapshot=api(tools,'/task/?pageSize=10000',th)
  assert snapshot['pagination']['total']==len(snapshot['list']),'Incomplete task snapshot'
  assert all(t['status'] in ['completed','error','canceled'] for t in snapshot['list']),'Nonterminal tasks exist'
  result=run(['docker','compose','-f',str(ROOT/'compose.yaml'),'up','-d','--no-deps','--pull','never','bililive-api'])
 except Exception:
  shutil.copy2(evidence/'compose.yaml.before',ROOT/'compose.yaml')
  run(['docker','compose','-f',str(ROOT/'compose.yaml'),'up','-d','--no-deps','--pull','never','bililive-api'])
  raise
 after=json.loads(run(['docker','inspect','bililive-recorder','bililive-api','bililive-web']))
 for attempt in range(30):
  try:
   api(tools,'/task/?pageSize=10000',th)
   break
  except Exception:
   if attempt==29:
    shutil.copy2(evidence/'compose.yaml.before',ROOT/'compose.yaml')
    run(['docker','compose','-f',str(ROOT/'compose.yaml'),'up','-d','--no-deps','--pull','never','bililive-api'])
    raise
   time.sleep(1)
 desired_core=manifest['original_core_sha256'] if args.rollback else manifest['patch_sha256']['index-DQV9sVEn.cjs']
 desired_server=manifest['original_server_sha256'] if args.rollback else manifest['patch_sha256']['index-ZJeYopVC.cjs']
 assert run(['docker','exec','bililive-api','sha256sum','/app/index-DQV9sVEn.cjs']).split()[0]==desired_core
 assert run(['docker','exec','bililive-api','sha256sum','/app/index-ZJeYopVC.cjs']).split()[0]==desired_server
 for old,new in zip(before,after):
  if old['Name']!='/bililive-api':assert old['State']['Pid']==new['State']['Pid'] and old['State']['StartedAt']==new['State']['StartedAt']
 assert all(sha(ROOT/r)==h for r,h in protected.items())
 (evidence/'result.json').write_text(json.dumps({'result':result,'protected_config_sha256':protected,'before':[{k:x[k] for k in ['Name','Id','State']} for x in before],'after':[{k:x[k] for k in ['Name','Id','State']} for x in after]},ensure_ascii=False,indent=2));(evidence/'result.json').chmod(0o600)
 marker=STAGE/'applied.json'
 if not args.rollback:
  marker.write_text(json.dumps({'evidence':str(evidence),'applied_at':datetime.datetime.now().astimezone().isoformat()}));marker.chmod(0o600)
 elif marker.exists():marker.unlink()
 print(json.dumps({'evidence':str(evidence),'rollback':args.rollback,'recorder_not_restarted':True,'protected_configs_unchanged':True},ensure_ascii=False))

if __name__=='__main__':main()
