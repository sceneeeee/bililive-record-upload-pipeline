#!/usr/bin/python3
"""Conservative terminal upload cleanup. No age-based deletion or task restarts."""
import argparse
import collections
import datetime
import json
import os
from pathlib import Path
import shlex
import sqlite3
import stat
import sys
import time
import urllib.request
import errno

TERMINAL = {'completed', 'error'}
FILE_TASKS = {'biliUpload', 'ffmpeg', 'sync', 'danmu'}

def emit(event, **data):
    print(json.dumps({'time': datetime.datetime.now().astimezone().isoformat(), 'event': event, **data}, ensure_ascii=False), flush=True)

def identity(s):
    return [s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns]

def open_inodes():
    result = collections.defaultdict(list)
    for proc in Path('/proc').glob('[0-9]*'):
        if int(proc.name) == os.getpid():
            continue
        try:
            for fd in (proc / 'fd').iterdir():
                try:
                    s = fd.stat()
                    if not stat.S_ISREG(s.st_mode):
                        continue
                    target = os.readlink(fd)
                    flags = int(next(l.split()[1] for l in (proc / 'fdinfo' / fd.name).read_text().splitlines() if l.startswith('flags:')), 8)
                    result[(s.st_dev, s.st_ino)].append({'pid': int(proc.name), 'fd': fd.name, 'target': target, 'write': bool(flags & 3), 'blocks': s.st_blocks * 512})
                except PermissionError:
                    raise
                except OSError as e:
                    if e.errno not in {errno.ENOENT, errno.ESRCH}:
                        raise
        except FileNotFoundError:
            continue
        # PermissionError is intentionally fatal: an incomplete FD scan cannot authorize deletion.
    return result

class API:
    def __init__(self, env_path):
        env = {}
        for line in Path(env_path).read_text().splitlines():
            if '=' in line and not line.lstrip().startswith('#'):
                key, value = line.split('=', 1)
                values = shlex.split(value, comments=True)
                env[key.strip()] = values[0] if values else ''
        self.headers = {'Authorization': env['BILILIVE_TOOLS_PASSKEY'], 'Content-Type': 'application/json'}

    def req(self, path, body=None):
        request = urllib.request.Request(os.environ.get('TOOLS_API_URL', 'http://127.0.0.1:18010') + path, headers=self.headers,
            data=None if body is None else json.dumps(body).encode())
        with urllib.request.urlopen(request, timeout=5) as response:
            value = response.read().decode()
            try:
                return json.loads(value)
            except ValueError:
                return value

    def tasks(self):
        value = self.req('/task/?pageSize=10000')
        if value['pagination']['total'] != len(value['list']):
            raise RuntimeError('incomplete_task_snapshot')
        return value['list']

    def lives(self):
        return self.req('/common/webhook', {})

    def remove(self, task_id):
        return self.req('/task/' + task_id + '/removeRecord', {})

class Cleaner:
    def __init__(self, root, state, api, fd_scan=open_inodes, *, delete_final_failure=False):
        self.root = Path(root).resolve()
        self.state = Path(state)
        self.state.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.api = api
        self.fd_scan = fd_scan
        self.delete_final_failure = delete_final_failure
        self.db = sqlite3.connect(self.state / 'ledger.sqlite3')
        os.chmod(self.state / 'ledger.sqlite3', 0o600)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
            PRAGMA journal_mode=WAL;
            PRAGMA synchronous=FULL;
            CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS closed(path TEXT PRIMARY KEY, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS sources(id INTEGER PRIMARY KEY, path TEXT NOT NULL, identity TEXT NOT NULL,
              proof TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'waiting', attempts INTEGER NOT NULL DEFAULT 0,
              next_try REAL NOT NULL DEFAULT 0, error TEXT NOT NULL DEFAULT '', freed INTEGER NOT NULL DEFAULT 0,
              UNIQUE(path,identity));
            CREATE TABLE IF NOT EXISTS bindings(task_id TEXT PRIMARY KEY, source_id INTEGER NOT NULL, parent_id TEXT);
            CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY, at REAL NOT NULL, source_id INTEGER, kind TEXT NOT NULL, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS removed_tasks(id TEXT PRIMARY KEY);
        ''')

    def save_changed(self, table, key, payload):
        value = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        col = 'path' if table == 'closed' else 'id'
        old = self.db.execute(f'SELECT payload FROM {table} WHERE {col}=?', (key,)).fetchone()
        if old is None or old[0] != value:
            self.db.execute(f'INSERT OR REPLACE INTO {table}({col},payload) VALUES(?,?)', (key, value))

    def event(self, source_id, kind, **payload):
        self.db.execute('INSERT INTO events(at,source_id,kind,payload) VALUES(?,?,?,?)',
            (time.time(), source_id, kind, json.dumps(payload, ensure_ascii=False)))
        self.db.commit()
        emit(kind, source_id=source_id, **payload)

    def host_path(self, path):
        if path.startswith('/app/video/'):
            candidate = self.root / path[len('/app/video/'):]
        elif path.startswith(str(self.root) + '/'):
            candidate = Path(path)
        else:
            raise ValueError('outside_video_root')
        relative = candidate.relative_to(self.root)
        if '..' in relative.parts or candidate.resolve(strict=False) != candidate:
            raise ValueError('unsafe_path_or_symlink')
        if candidate.suffix.lower() not in {'.flv', '.mp4', '.mkv', '.ts'}:
            raise ValueError('not_video')
        return str(candidate)

    def ingest(self, tasks, lives):
        for task in tasks:
            self.save_changed('tasks', task['taskId'], task)
        for live in lives:
            for part in live.get('parts', []):
                if part.get('recordStatus') == 'recording' or not part.get('endTime'):
                    continue
                if part['endTime'] < part.get('startTime', 0):
                    continue
                for field in ['filePath', 'rawFilePath']:
                    try:
                        path = self.host_path(part[field])
                    except (KeyError, ValueError):
                        continue
                    self.save_changed('closed', path, {**part, 'liveEventId': live['eventId'], 'roomId': live['roomId']})
        closed = {r['path']: json.loads(r['payload']) for r in self.db.execute('SELECT * FROM closed')}
        # Historical API lacks filePath. A legacy association requires a unique closed part,
        # exact task title AND complete basename AND byte size AND ordering AND inode snapshot.
        # New tasks carry their actual uploader path and stat identity via the small adapter patch.
        for task in tasks:
            if task.get('type') != 'biliUpload':
                continue
            if self.db.execute('SELECT 1 FROM bindings WHERE task_id=?', (task['taskId'],)).fetchone():
                continue
            extra = task.get('extra', {})
            direct = extra.get('filePath')
            if direct:
                try:
                    paths = [self.host_path(direct)]
                except ValueError:
                    continue
                mode = 'uploader_exact_path'
            else:
                paths = [path for path in closed if Path(path).stem == extra.get('title')
                    and task.get('name') == '上传视频：' + str(extra.get('title')) + '(' + Path(path).name + ')']
                mode = 'legacy_closed_part_size_and_task'
            candidates = []
            for path in paths:
                proof = closed.get(path)
                if not proof or proof['endTime'] > task.get('startTime', 0) + 1000:
                    continue
                try:
                    s = os.lstat(path)
                except FileNotFoundError:
                    continue
                if not stat.S_ISREG(s.st_mode) or s.st_nlink != 1 or s.st_size != extra.get('fileSize'):
                    continue
                if s.st_mtime_ns / 1e6 > task.get('startTime', 0) + 1000 or s.st_ctime_ns / 1e6 > task.get('startTime', 0) + 1000:
                    continue
                observed = extra.get('sourceIdentity')
                if observed and (observed['dev'] != s.st_dev or observed['ino'] != s.st_ino or observed['size'] != s.st_size):
                    continue
                candidates.append((path, s, proof))
            if len(candidates) != 1:
                continue
            path, s, proof = candidates[0]
            ident = json.dumps(identity(s))
            source_proof = json.dumps({'mode': mode, 'part': proof, 'initial_task': task}, ensure_ascii=False)
            self.db.execute('INSERT OR IGNORE INTO sources(path,identity,proof) VALUES(?,?,?)', (path, ident, source_proof))
            sid = self.db.execute('SELECT id FROM sources WHERE path=? AND identity=?', (path, ident)).fetchone()[0]
            self.db.execute('INSERT INTO bindings VALUES(?,?,?)', (task['taskId'], sid, task.get('pid')))
        self.db.commit()

    def plan(self, tasks, lives, fds):
        current = {t['taskId']: t for t in tasks}
        stored = {r['id']: json.loads(r['payload']) for r in self.db.execute('SELECT * FROM tasks')}
        bindings = {r['task_id']: dict(r) for r in self.db.execute('SELECT * FROM bindings')}
        active_paths = set()
        # Missing API lives after a restart cannot settle an unfinished callback.
        live_parts = {r['path']: json.loads(r['payload']) for r in self.db.execute('SELECT * FROM closed')}
        unresolved = []
        known = {**stored, **current}
        for t in known.values():
            if t.get('status') in TERMINAL or t.get('status') == 'canceled':
                continue
            if t.get('type') in FILE_TASKS:
                try:
                    active_paths.add(self.host_path(t['extra']['filePath']))
                except (KeyError, ValueError):
                    b = bindings.get(t['taskId'])
                    if b:
                        active_paths.add(self.db.execute('SELECT path FROM sources WHERE id=?', (b['source_id'],)).fetchone()[0])
                    else:
                        unresolved.append(t['taskId'])
        for live in lives:
            for part in live.get('parts', []):
                for field in ['filePath', 'rawFilePath']:
                    try:
                        live_parts[self.host_path(part[field])] = part
                    except (KeyError, ValueError):
                        pass
                if part.get('recordStatus') == 'recording':
                    for field in ['filePath', 'rawFilePath']:
                        try:
                            active_paths.add(self.host_path(part[field]))
                        except (KeyError, ValueError):
                            pass
        plans = []
        for source in self.db.execute("SELECT * FROM sources WHERE status NOT IN ('deleted','absent')"):
            item = dict(source)
            related = [b for b in bindings.values() if b['source_id'] == source['id']]
            blocked = []
            if unresolved:
                blocked.append('unresolved_active_file_tasks')
            if source['path'] in active_paths:
                blocked.append('active_source_reference')
            # Upstream marks a parent completed before its async FileRefManager
            # callback has resolved. Wait for the live part's callback outcome too;
            # retiring child records earlier can emit a detached-parent error.
            live_part = live_parts.get(source['path'])
            if not live_part:
                blocked.append('missing_closed_part_evidence')
            elif any(live_part.get(status) not in {'uploaded', 'error'}
                     for field, status in [('filePath', 'uploadStatus'), ('rawFilePath', 'rawUploadStatus')]
                     if live_part.get(field) and self.host_path(live_part[field]) == source['path']):
                blocked.append('post_upload_callback_not_settled')
            for binding in related:
                t = current.get(binding['task_id'], stored.get(binding['task_id'], {}))
                parent_id = binding['parent_id']
                parent = current.get(parent_id, stored.get(parent_id, {}))
                if not self.delete_final_failure and (t.get('status') == 'error' or parent.get('status') == 'error'):
                    blocked.append('final_failure_deletion_disabled')
                canceled_by_failure = t.get('status') == 'canceled' and parent.get('status') == 'error'
                if (t.get('status') not in TERMINAL and not canceled_by_failure) or not t.get('endTime'):
                    blocked.append('upload_not_final')
                if t.get('endTime', 0) > time.time() * 1000 - 1000:
                    blocked.append('terminal_callback_settling')
                if parent_id and parent.get('status') not in TERMINAL:
                    blocked.append('parent_not_final')
                siblings = [s for s in known.values() if parent_id and s.get('pid') == parent_id]
                if any(s.get('status') not in TERMINAL and not (s.get('status') == 'canceled' and parent.get('status') == 'error') for s in siblings):
                    blocked.append('sibling_not_final')
            ident = json.loads(source['identity'])
            owners = fds.get((ident[0], ident[1]), [])
            if owners:
                blocked.append('file_still_open')
            item.update(task_ids=[b['task_id'] for b in related], parent_ids=sorted({b['parent_id'] for b in related if b['parent_id']}),
                blocked=sorted(set(blocked)), owners=owners, eligible=bool(related) and not blocked)
            plans.append(item)
        return plans

    def unlink_checked(self, source):
        path = Path(source['path'])
        rel = path.relative_to(self.root)
        directory = os.open(self.root, os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            for component in rel.parts[:-1]:
                nxt = os.open(component, os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
                os.close(directory)
                directory = nxt
            try:
                s = os.stat(rel.name, dir_fd=directory, follow_symlinks=False)
            except FileNotFoundError:
                return 'absent', 0
            if identity(s) != json.loads(source['identity']) or not stat.S_ISREG(s.st_mode) or s.st_nlink != 1:
                raise RuntimeError('source_identity_changed')
            if self.fd_scan().get((s.st_dev, s.st_ino)):
                raise RuntimeError('file_opened_during_final_check')
            self.event(source['id'], 'delete_intent', path=str(path), task_ids=source['task_ids'])
            # The durable intent can take time to fsync; recheck before unlink.
            if identity(os.stat(rel.name, dir_fd=directory, follow_symlinks=False)) != identity(s):
                raise RuntimeError('source_identity_changed_after_intent')
            if self.fd_scan().get((s.st_dev, s.st_ino)):
                raise RuntimeError('file_opened_after_intent')
            os.unlink(rel.name, dir_fd=directory)
            os.fsync(directory)
            if self.fd_scan().get((s.st_dev, s.st_ino)):
                raise RuntimeError('deleted_but_inode_still_open')
            return 'deleted', s.st_blocks * 512
        finally:
            os.close(directory)

    def retire_records(self, tasks):
        current = {t['taskId']: t for t in tasks}
        groups = collections.defaultdict(list)
        for b in self.db.execute('SELECT * FROM bindings'):
            groups[b['parent_id']].append(dict(b))
        for parent, bs in groups.items():
            ids = [b['task_id'] for b in bs]
            children = [t for t in tasks if t.get('pid') == parent]
            if any(t['taskId'] not in ids or (t['status'] not in TERMINAL and not (t['status'] == 'canceled' and current.get(parent, {}).get('status') == 'error')) for t in children):
                continue
            if parent in current and current[parent]['status'] not in TERMINAL:
                continue
            statuses = [self.db.execute('SELECT status FROM sources WHERE id=?', (b['source_id'],)).fetchone()[0] for b in bs]
            if any(s not in {'deleted','absent'} for s in statuses):
                continue
            # Archive the complete task metadata before the UI history is retired.
            # Removing a child can make upstream's detached parent emit an error;
            # the durable tombstone prevents that duplicate event from reauthorizing deletion.
            for tid in ([parent] if parent else []) + ids:
                if tid not in current or self.db.execute('SELECT 1 FROM removed_tasks WHERE id=?', (tid,)).fetchone():
                    continue
                self.api.remove(tid)
                self.db.execute('INSERT OR IGNORE INTO removed_tasks VALUES(?)', (tid,))
                self.event(None, 'terminal_task_record_retired', task_id=tid)
        self.db.commit()

    def cycle(self, apply=False):
        tasks, lives = self.api.tasks(), self.api.lives()
        self.ingest(tasks, lives)
        plans = self.plan(tasks, lives, self.fd_scan())
        if apply:
            for item in plans:
                if not item['eligible'] or item['next_try'] > time.time():
                    continue
                try:
                    # Re-query real statuses immediately before each individual deletion.
                    fresh_tasks, fresh_lives = self.api.tasks(), self.api.lives()
                    self.ingest(fresh_tasks, fresh_lives)
                    fresh = next(x for x in self.plan(fresh_tasks, fresh_lives, self.fd_scan()) if x['id'] == item['id'])
                    if not fresh['eligible']:
                        continue
                    vfs = os.statvfs(self.root)
                    before = vfs.f_bfree * vfs.f_frsize
                    status, freed = self.unlink_checked(fresh)
                    after = os.statvfs(self.root)
                    self.db.execute('UPDATE sources SET status=?,freed=?,error=? WHERE id=?', (status, freed, '', item['id']))
                    self.event(item['id'], status, path=item['path'], allocated_bytes_released=freed,
                        measured_free_delta=after.f_bfree * after.f_frsize - before, task_ids=item['task_ids'])
                except Exception as e:
                    attempts = item['attempts'] + 1
                    self.db.execute('UPDATE sources SET attempts=?,next_try=?,error=? WHERE id=?',
                        (attempts, time.time() + min(60, 2 ** min(attempts, 6)), type(e).__name__ + ':' + str(e), item['id']))
                    self.event(item['id'], 'cleanup_error', path=item['path'], error=type(e).__name__ + ':' + str(e), attempt=attempts)
            self.retire_records(self.api.tasks())
        summary = {'timestamp': time.time(), 'apply': apply, 'sources': len(plans), 'eligible': sum(x['eligible'] for x in plans),
            'blocked': [{'path': x['path'], 'reasons': x['blocked'], 'owners': x['owners']} for x in plans if x['blocked']],
            'errors': [dict(r) for r in self.db.execute("SELECT path,attempts,error,next_try FROM sources WHERE error<>'' AND status NOT IN ('deleted','absent')")],
            'totals': {r[0]: {'files': r[1], 'released_bytes': r[2]} for r in self.db.execute('SELECT status,count(*),sum(freed) FROM sources GROUP BY status')}}
        temp = self.state / 'status.tmp'
        temp.write_text(json.dumps(summary, ensure_ascii=False, indent=2))
        temp.chmod(0o600)
        temp.replace(self.state / 'status.json')
        return plans, summary

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', default=os.environ.get('STACK_ROOT', '/opt/bililive-stack') + '/video')
    parser.add_argument('--state', default=os.environ.get('CLEANER_STATE', '/var/lib/pipeline-upload-cleaner'))
    parser.add_argument('--env', default=os.environ.get('STACK_ROOT', '/opt/bililive-stack') + '/.env')
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--serve', action='store_true')
    parser.add_argument('--delete-final-failure', action='store_true',
                        help='irreversibly delete proven final failures as well as successes')
    args = parser.parse_args()
    import fcntl
    Path(args.state).mkdir(mode=0o700, parents=True, exist_ok=True)
    lock = open(Path(args.state) / 'lock', 'a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    cleaner = Cleaner(args.root, args.state, API(args.env), delete_final_failure=args.delete_final_failure)
    last_report = 0
    while True:
        try:
            plans, summary = cleaner.cycle(args.apply)
            if not args.serve:
                print(json.dumps({'plan': plans, 'summary': summary}, ensure_ascii=False, indent=2))
                return
            if time.time() - last_report > 60:
                emit('status', **summary)
                last_report = time.time()
        except Exception as e:
            emit('cycle_error', error=type(e).__name__ + ':' + str(e))
            if not args.serve:
                raise
        time.sleep(2)

if __name__ == '__main__':
    main()
