import copy, importlib.util, json, os, pathlib, tempfile, time, types, unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('cleaner',pathlib.Path(__file__).resolve().parents[1] / 'scripts/pipeline-upload-cleaner.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class FakeAPI:
 def __init__(self,tasks,lives):self.ts=tasks;self.ls=lives;self.removed=[]
 def tasks(self):return copy.deepcopy(self.ts)
 def lives(self):return copy.deepcopy(self.ls)
 def remove(self,tid):self.removed.append(tid);self.ts=[t for t in self.ts if t['taskId']!=tid]

class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.base=pathlib.Path(self.tmp.name);self.root=self.base/'video';self.root.mkdir()
  self.file=self.root/'测试主播-10月05日20时57分08秒-P01.flv';self.file.write_bytes(b'FLV'+b'X'*5000)
  s=self.file.stat();now=int(time.time()*1000)+100
  self.clock=now/1000+60;m.time=types.SimpleNamespace(time=lambda:self.clock,sleep=lambda _:None)
  self.child={'taskId':'child','pid':'parent','type':'biliUpload','status':'completed','startTime':now,'endTime':now+1000,'name':'上传视频：'+self.file.stem+'('+self.file.name+')',
    'extra':{'title':self.file.stem,'fileSize':s.st_size,'filePath':'/app/video/'+self.file.name,'sourceIdentity':{'dev':s.st_dev,'ino':s.st_ino,'size':s.st_size}}}
  self.parent={'taskId':'parent','type':'bili','status':'completed','startTime':now,'endTime':now+2000}
  self.part={'partId':'part','filePath':'/app/video/'+self.file.name,'rawFilePath':'/app/video/'+self.file.name,'recordStatus':'handled','uploadStatus':'uploaded','rawUploadStatus':'error','startTime':now-10000,'endTime':now-10}
  self.api=FakeAPI([self.child,self.parent],[{'eventId':'live','roomId':123456,'parts':[self.part]}])
  self.fds={};self.c=m.Cleaner(self.root,self.base/'state',self.api,lambda:self.fds,delete_final_failure=True)
 def tearDown(self):self.c.db.close();self.tmp.cleanup()
 def test_success(self):
  self.c.cycle(True);self.assertFalse(self.file.exists());self.assertEqual(self.api.removed,['parent','child'])
 def test_final_failure(self):
  self.api.ts[0]['status']='error';self.api.ts[1]['status']='error';self.api.ts[1].pop('endTime');self.c.cycle(True);self.assertFalse(self.file.exists())
 def test_public_default_keeps_final_failure(self):
  self.c.db.close();self.c=m.Cleaner(self.root,self.base/'state',self.api,lambda:self.fds)
  self.api.ts[0]['status']='error';self.api.ts[1]['status']='error';self.c.cycle(True)
  self.assertTrue(self.file.exists());self.assertEqual(self.api.removed,[])
 def test_public_default_still_deletes_success(self):
  self.c.db.close();self.c=m.Cleaner(self.root,self.base/'state',self.api,lambda:self.fds)
  self.c.cycle(True);self.assertFalse(self.file.exists())
 def test_restarting_with_policy_disabled_keeps_persisted_failure(self):
  self.api.ts[0]['status']='error';self.api.ts[1]['status']='error';self.c.cycle(False)
  self.c.db.close();self.api.ts=[];self.api.ls=[]
  self.c=m.Cleaner(self.root,self.base/'state',self.api,lambda:self.fds)
  self.c.cycle(True);self.assertTrue(self.file.exists())
 def test_unsettled_callback_survives_api_restart(self):
  self.api.ls[0]['parts'][0]['uploadStatus']='uploading';self.c.cycle(False)
  self.api.ts=[];self.api.ls=[];self.c.cycle(True);self.assertTrue(self.file.exists())
 def test_raw_callback_must_settle(self):
  self.api.ls[0]['parts'][0]['rawUploadStatus']='uploading'
  self.c.cycle(True);self.assertTrue(self.file.exists())
 def test_missing_active_sibling_survives_api_restart(self):
  self.api.ts.append({'taskId':'other','pid':'parent','type':'biliUpload','status':'running'})
  self.c.cycle(False);self.api.ts=[];self.api.ls=[];self.c.cycle(True)
  self.assertTrue(self.file.exists())
 def test_hardlink_kept(self):
  os.link(self.file,self.root/'alias.flv');self.c.cycle(True);self.assertTrue(self.file.exists())
 def test_fd_scan_failure_never_deletes(self):
  self.c.fd_scan=lambda:(_ for _ in ()).throw(PermissionError('fixture'))
  with self.assertRaises(PermissionError):self.c.cycle(True)
  self.assertTrue(self.file.exists())
 def test_change_after_intent_kept(self):
  event=self.c.event
  def changed(sid,kind,**data):
   event(sid,kind,**data)
   if kind=='delete_intent':self.file.write_bytes(b'changed')
  self.c.event=changed;self.c.cycle(True);self.assertTrue(self.file.exists())
 def test_api_failure_never_deletes(self):
  self.c.cycle(False)
  self.api.tasks=lambda:(_ for _ in ()).throw(ConnectionError('fixture'))
  with self.assertRaises(ConnectionError):self.c.cycle(True)
  self.assertTrue(self.file.exists())
 def test_canceled_child_of_final_failed_parent(self):
  self.api.ts[0]['status']='canceled';self.api.ts[1]['status']='error';self.c.cycle(True);self.assertFalse(self.file.exists())
 def test_manual_cancellation_kept(self):
  self.api.ts[0]['status']='canceled';self.api.ts[1]['status']='canceled';self.c.cycle(True);self.assertTrue(self.file.exists())
 def test_running_paused_pending_retry_kept(self):
  for state in ['running','paused','pending','retrying']:
   self.api.ts[0]['status']=state;self.c.cycle(True);self.assertTrue(self.file.exists(),state)
 def test_recording_kept(self):
  self.api.ls[0]['parts'][0]['recordStatus']='recording';self.c.cycle(True);self.assertTrue(self.file.exists())
 def test_parent_active_kept(self):
  self.api.ts[1]['status']='running';self.c.cycle(True);self.assertTrue(self.file.exists())
 def test_parent_completed_before_async_callback_kept(self):
  self.api.ls[0]['parts'][0]['uploadStatus']='uploading';self.c.cycle(True);self.assertTrue(self.file.exists());self.assertEqual(self.api.removed,[])
  self.api.ls[0]['parts'][0]['uploadStatus']='uploaded';self.c.cycle(True);self.assertFalse(self.file.exists())
 def test_native_deleted_file_waits_for_callback_before_record_retirement(self):
  self.c.cycle(False);self.file.unlink();self.api.ls[0]['parts'][0]['uploadStatus']='uploading';self.c.cycle(True);self.assertEqual(self.api.removed,[])
  self.api.ls[0]['parts'][0]['uploadStatus']='uploaded';self.c.cycle(True);self.assertEqual(self.api.removed,['parent','child'])
 def test_active_sibling_kept(self):
  self.api.ts.append({'taskId':'other','type':'biliUpload','pid':'parent','status':'running'});self.c.cycle(True);self.assertTrue(self.file.exists())
 def test_open_read_or_write_kept(self):
  s=self.file.stat();self.fds[(s.st_dev,s.st_ino)]=[{'pid':10,'write':False}];self.c.cycle(True);self.assertTrue(self.file.exists())
 def test_delete_failure_retries(self):
  with patch.object(m.os,'unlink',side_effect=PermissionError('fixture')):self.c.cycle(True)
  self.assertTrue(self.file.exists());self.assertEqual(self.c.db.execute('select attempts from sources').fetchone()[0],1)
  self.clock+=3;self.c.cycle(True);self.assertFalse(self.file.exists())
 def test_restart_and_duplicates(self):
  self.c.cycle(True);self.c.db.close();self.c=m.Cleaner(self.root,self.base/'state',self.api,lambda:self.fds,delete_final_failure=True)
  self.c.cycle(True);self.assertEqual(self.c.db.execute("select count(*) from events where kind='deleted'").fetchone()[0],1)
 def test_restart_with_persisted_terminal_evidence(self):
  self.c.cycle(False);self.api.ts=[];self.api.ls=[];self.c.db.close();self.c=m.Cleaner(self.root,self.base/'state',self.api,lambda:self.fds,delete_final_failure=True)
  self.c.cycle(True);self.assertFalse(self.file.exists())
 def test_missing_active_task_after_restart_is_not_final(self):
  self.api.ts[0]['status']='running';self.c.cycle(False);self.api.ts=[];self.api.ls=[];self.c.cycle(True);self.assertTrue(self.file.exists())
 def test_replaced_path_is_not_deleted(self):
  self.c.cycle(False);self.file.rename(self.root/'original.flv');self.file.write_bytes(b'NEW'+b'X'*5000)
  self.c.cycle(True);self.assertTrue(self.file.exists());self.assertTrue((self.root/'original.flv').exists())
 def test_callback_without_endtime_is_not_final(self):
  self.api.ts[0].pop('endTime');self.c.cycle(True);self.assertTrue(self.file.exists())
 def test_legacy_requires_closed_part_and_size(self):
  self.api.ts[0]['extra'].pop('filePath');self.api.ts[0]['extra'].pop('sourceIdentity');self.api.ts[0]['extra']['fileSize']+=1
  self.c.cycle(True);self.assertTrue(self.file.exists())
 def test_ambiguous_legacy_mapping_kept(self):
  self.api.ts[0]['extra'].pop('filePath');self.api.ts[0]['extra'].pop('sourceIdentity')
  d=self.root/'other';d.mkdir();(d/self.file.name).write_bytes(self.file.read_bytes());p=copy.deepcopy(self.part);p['filePath']='/app/video/other/'+self.file.name;p['rawFilePath']=p['filePath'];self.api.ls[0]['parts'].append(p)
  self.c.cycle(True);self.assertTrue(self.file.exists())
 def test_symlink_rejected(self):
  other=self.base/'outside.flv';other.write_bytes(self.file.read_bytes());self.file.unlink();self.file.symlink_to(other)
  self.c.cycle(True);self.assertTrue(other.exists())
 def test_status_recheck_prevents_race(self):
  original=self.api.tasks;calls=[0]
  def changed():
   calls[0]+=1
   if calls[0]>1:self.api.ts[0]['status']='running'
   return original()
  self.api.tasks=changed;self.c.cycle(True);self.assertTrue(self.file.exists())
 def test_delete_intent_crash_recovery(self):
  self.c.cycle(False);self.file.unlink();self.api.ts=[];self.api.ls=[];self.c.cycle(True)
  self.assertEqual(self.c.db.execute('select status,freed from sources').fetchone()[:],('absent',0))

if __name__=='__main__':unittest.main()
