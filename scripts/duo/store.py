"""SQLite atomically saves state, active pointer, command deduplication and history."""
import contextlib
import json
import os
import sqlite3
from pathlib import Path
from .common import require, StateError
from .engine import validate
from .visibility import migrate, audit_view

class Store:
    def __init__(self, root):
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / 'sessions.sqlite3'
        self.db = sqlite3.connect(str(self.path), timeout=30)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY, body TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS tables(name TEXT PRIMARY KEY, session TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS commands(table_name TEXT, request_id TEXT, result TEXT NOT NULL, PRIMARY KEY(table_name, request_id));
        CREATE TABLE IF NOT EXISTS history(session TEXT, revision INTEGER, body TEXT NOT NULL, PRIMARY KEY(session, revision));
        CREATE TABLE IF NOT EXISTS faults(table_name TEXT PRIMARY KEY, reason TEXT NOT NULL);
        ''')
        self.db.commit()
        os.chmod(self.path, 0o600)

    @contextlib.contextmanager
    def transaction(self):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            yield
            self.db.commit()
        except BaseException:
            self.db.rollback(); raise

    def active(self, table):
        if self.db.execute('SELECT 1 FROM faults WHERE table_name=?',(table,)).fetchone():
            raise StateError('此桌已因状态校验失败暂停。')
        row = self.db.execute('SELECT s.body FROM tables t JOIN sessions s ON s.id=t.session WHERE t.name=?',(table,)).fetchone()
        if not row: return None
        try: s = migrate(json.loads(row[0])); validate(s)
        except (ValueError,KeyError,TypeError,IndexError):
            raise StateError('存档结构或内容校验失败。') from None
        return s

    def freeze(self, table):
        self.db.rollback()
        self.db.execute('INSERT OR REPLACE INTO faults VALUES(?,?)',(table,'状态校验失败'))
        self.db.commit()

    def clear_fault(self, table):
        self.db.execute('DELETE FROM faults WHERE table_name=?',(table,))

    def save(self, table, s):
        validate(s); body = json.dumps(s, ensure_ascii=False, sort_keys=True)
        self.db.execute('INSERT OR REPLACE INTO sessions VALUES(?,?)',(s['session_id'],body))
        self.db.execute('INSERT OR REPLACE INTO tables VALUES(?,?)',(table,s['session_id']))
        self.db.execute('INSERT OR REPLACE INTO history VALUES(?,?,?)',(s['session_id'],s['revision'],body))

    def previous_result(self, table, request_id):
        if not request_id: return None
        row = self.db.execute('SELECT result FROM commands WHERE table_name=? AND request_id=?',(table,request_id)).fetchone()
        if not row: return None
        out = json.loads(row[0])
        if out.get('output_contract') != 2:
            return {'ok':False,'error':'该消息已在旧版执行，未重复执行；请查看当前状态。',
                    'view':None,'text':'该消息已在旧版执行，未重复执行；请说“查看状态”。','output_contract':2}
        if out.get('view'): audit_view(out['view'],'human')
        return out

    def record_result(self, table, request_id, result):
        if request_id:
            self.db.execute('INSERT INTO commands VALUES(?,?,?)',(table,request_id,json.dumps(result,ensure_ascii=False)))

    def close(self): self.db.close()
