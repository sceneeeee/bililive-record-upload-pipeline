#!/usr/bin/python3
"""Read-only recording/upload checks; writes only its own small state file and journal."""
import base64
import collections
import datetime
import glob
import json
import os
from pathlib import Path
import re
import shlex
import stat
import subprocess
import sys
import time
import urllib.request

STACK = Path(os.environ.get('STACK_ROOT', '/opt/bililive-stack'))
STATE = Path(os.environ.get('MONITOR_STATE', '/var/lib/pipeline-recorder-monitor/status.json'))
GIB = 1024 ** 3

def command(args):
    result = subprocess.run(args, capture_output=True, text=True, timeout=8)
    if result.returncode:
        raise RuntimeError('command_failed:' + args[0])
    return result.stdout

def http_json(url, headers):
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=4) as response:
        return json.load(response)

def env_file():
    result = {}
    for line in (STACK / '.env').read_text().splitlines():
        if line.strip() and not line.lstrip().startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            values = shlex.split(value, comments=True)
            result[key.strip()] = values[0] if values else ''
    return result

def disk_issue(available, total):
    if available < 6 * GIB or available / total < 0.10:
        return 'CRITICAL:disk_free_below_6GiB_or_10percent'
    if available < 10 * GIB or available / total < 0.20:
        return 'WARN:disk_free_below_10GiB_or_20percent'
    return None

def main():
    now = time.time()
    try:
        previous = json.loads(STATE.read_text())
    except (OSError, ValueError):
        previous = {}
    report = {'timestamp': datetime.datetime.now().astimezone().isoformat(), 'epoch': now, 'alerts': []}
    alerts = report['alerts']
    vfs = os.statvfs(STACK / 'video')
    free, total = vfs.f_bavail * vfs.f_frsize, vfs.f_blocks * vfs.f_frsize
    report['disk_free_bytes'] = free
    patch_stage = Path(os.environ.get('PATCH_STAGE', str(STACK / 'patches/uploader-3.20.0')))
    if (patch_stage / 'failed.json').exists():
        alerts.append('CRITICAL:approved_api_patch_failed_manual_review_required')
    report['approved_api_patch'] = ('applied' if (patch_stage / 'applied.json').exists() else 'pending' if (patch_stage / 'approved.json').exists() else 'not_scheduled')
    try:
        cleanup = json.loads(Path(os.environ.get('CLEANER_STATE', '/var/lib/pipeline-upload-cleaner') + '/status.json').read_text())
        report['terminal_cleanup'] = cleanup
        if now - cleanup['timestamp'] > 90:
            alerts.append('CRITICAL:terminal_cleanup_heartbeat_stale')
        if cleanup.get('blocked'):
            alerts.append('WARN:terminal_cleanup_blocked:' + str(len(cleanup['blocked'])))
        if cleanup.get('errors'):
            alerts.append('CRITICAL:terminal_cleanup_delete_errors:' + str(len(cleanup['errors'])))
    except (OSError, ValueError, KeyError):
        alerts.append('CRITICAL:terminal_cleanup_status_unavailable')
    issue = disk_issue(free, total)
    if issue:
        alerts.append(issue)
    if vfs.f_favail / vfs.f_files < .10:
        alerts.append('CRITICAL:inode_free_below_10percent')
    mem = dict((k, int(v.split()[0])) for k, v in (l.split(':', 1) for l in Path('/proc/meminfo').read_text().splitlines()))
    report['memory_available_kib'] = mem['MemAvailable']
    report['loadavg'] = os.getloadavg()
    if mem['MemAvailable'] < 150 * 1024:
        alerts.append('WARN:memory_available_below_150MiB')
    containers = []
    for name in ['bililive-recorder', 'bililive-api', 'bililive-web']:
        try:
            d = json.loads(command(['docker', 'inspect', name]))[0]
            item = {'name': name, 'running': d['State']['Running'], 'pid': d['State']['Pid'], 'restart_count': d['RestartCount'], 'oom_killed': d['State']['OOMKilled']}
            containers.append(item)
            if not item['running'] or item['oom_killed']:
                alerts.append('CRITICAL:container_state:' + name)
            old = next((c for c in previous.get('containers', []) if c['name'] == name), None)
            if old and (item['restart_count'] > old['restart_count'] or item['pid'] != old['pid']):
                alerts.append('WARN:container_restarted:' + name)
        except Exception as e:
            alerts.append('CRITICAL:container_inspect:' + name + ':' + type(e).__name__)
    report['containers'] = containers
    try:
        env = env_file()
        auth = base64.b64encode((env['BREC_HTTP_BASIC_USER'] + ':' + env['BREC_HTTP_BASIC_PASS']).encode()).decode()
        rooms = http_json('http://127.0.0.1:2356/api/room', {'Authorization': 'Basic ' + auth})
        report['rooms'] = []
        for room in rooms:
            old = next((r for r in previous.get('rooms', []) if r['room_id'] == room['roomId']), {})
            item = {'room_id': room['roomId'], 'streaming': room['streaming'], 'recording': room['recording'], 'auto_record': room['autoRecord'], 'bytes': room.get('recordingStats', {}).get('totalInputBytes', 0)}
            bad = room['autoRecord'] and room['streaming'] and (not room['recording'] or (old.get('recording') and item['bytes'] == old.get('bytes')))
            item['stagnant_since'] = old.get('stagnant_since') or now if bad else None
            if bad and now - item['stagnant_since'] >= 600:
                alerts.append('CRITICAL:live_recording_stalled:' + str(room['roomId']))
            report['rooms'].append(item)
        data = http_json('http://127.0.0.1:18010/task/?pageSize=300', {'Authorization': env['BILILIVE_TOOLS_PASSKEY']})
        counts = collections.Counter(str(t.get('status', 'unknown')) for t in data['list'])
        report['task_status_counts'] = dict(counts)
        report['failed_tasks'] = [{'id': t.get('id') or t.get('taskId'), 'type': t.get('type'), 'status': t.get('status')} for t in data['list'] if t.get('status') in ['error', 'failed']]
        if report['failed_tasks']:
            alerts.append('WARN:failed_tasks:' + str(len(report['failed_tasks'])))
        active = [t for t in data['list'] if t.get('status') == 'running']
        fingerprint = json.dumps([{k: t.get(k) for k in ['id','taskId','progress','status']} for t in active], sort_keys=True)
        stagnant = bool(active) and fingerprint == previous.get('active_tasks_fingerprint')
        since = previous.get('tasks_stagnant_since') or now if stagnant else None
        report['active_tasks_fingerprint'] = fingerprint
        report['tasks_stagnant_since'] = since
        if since and now - since >= 1800:
            alerts.append('WARN:task_progress_unchanged_30min_review_manually')
    except Exception as e:
        # Exception strings can include URLs; emit only the type.
        alerts.append('WARN:application_probe:' + type(e).__name__)
    files = list((STACK / 'video').rglob('*.flv'))
    stale = [p for p in files if p.stat().st_size >= 20 * 1024**2 and now - p.stat().st_mtime > 3600]
    report['old_large_flv'] = {'count': len(stale), 'bytes': sum(p.stat().st_size for p in stale)}
    if stale:
        alerts.append('WARN:old_video_backlog_review_upload_state:' + str(len(stale)))
    allocated, seen = 0, set()
    for c in containers:
        if not c['pid']:
            continue
        for fd in glob.glob('/proc/' + str(c['pid']) + '/fd/*'):
            try:
                target = os.readlink(fd)
                s = os.stat(fd)
                if target.startswith(('/app/video/', '/rec/')) and target.endswith(' (deleted)') and stat.S_ISREG(s.st_mode):
                    inode = (s.st_dev, s.st_ino)
                    if inode not in seen:
                        seen.add(inode)
                        allocated += s.st_blocks * 512
            except OSError:
                pass
    report['deleted_video_open_allocated_bytes'] = allocated
    if allocated > 128 * 1024**2:
        alerts.append('WARN:deleted_video_still_open_bytes:' + str(allocated))
    report['recent_errors'] = {}
    for name in ['bililive-recorder', 'bililive-api']:
        try:
            logs = subprocess.run(['docker', 'logs', '--since', '5m', '--tail', '2000', name], capture_output=True, text=True, timeout=6)
            if logs.returncode:
                raise RuntimeError('docker_logs_failed')
            text = logs.stdout + logs.stderr
            patterns = {'stall': '检测到录制卡住', 'collision': '录制文件名冲突', 'network_or_tls': r'unexpected EOF|decryption operation|certificate has expired|socket hang up', 'upload_failed': r'task .* error:.*Upload|Upload task failed', 'storage_error': r'ENOSPC|No space left|Read-only file system'}
            counts = {k: len(re.findall(p, text, re.I)) for k, p in patterns.items()}
            report['recent_errors'][name] = counts
            if any(counts.values()):
                alerts.append('WARN:recent_record_or_upload_errors:' + name)
        except Exception as e:
            alerts.append('WARN:log_probe:' + name + ':' + type(e).__name__)
    STATE.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temp = STATE.with_suffix('.tmp')
    temp.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    temp.chmod(0o600)
    temp.replace(STATE)
    print(json.dumps(report, ensure_ascii=False))
    # Journal priority is set by systemd; warnings are explicit in the JSON alerts field.
    return 0

if __name__ == '__main__':
    sys.exit(main())
