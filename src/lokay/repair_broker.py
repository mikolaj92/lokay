"""Parent-owned authorization broker for the unhealthy self-repair lane."""
from __future__ import annotations
import json, os, socket, struct, subprocess, tempfile, threading
from pathlib import Path
from typing import Any

_ALLOWED = {"assign_issue", "worktree_add", "commit_all", "push", "pr_create", "pr_label", "pr_review", "pr_merge"}

class RepairBroker:
    def __init__(self, *, issue: int, fingerprint: str, deadline: float):
        self.issue, self.fingerprint, self.deadline = int(issue), str(fingerprint), float(deadline)
        self.pr: int | None = None; self.branch = ""; self.head_sha = ""
        self.dir = Path(tempfile.mkdtemp(prefix="lokay-repair-broker-")); self.path=self.dir/"broker.sock"
        self.sock=socket.socket(socket.AF_UNIX, socket.SOCK_STREAM); self.sock.bind(str(self.path)); self.path.chmod(0o600); self.sock.listen(8)
        self.stop=False; self.thread=threading.Thread(target=self._serve,daemon=True); self.thread.start()
    def _peer_pid(self, conn):
        if hasattr(socket,"SO_PEERCRED"):
            return struct.unpack("3i",conn.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))[0]
        try: return struct.unpack("i",conn.getsockopt(getattr(socket,"SOL_LOCAL",0),2,4))[0]
        except OSError: return -1
    def _is_atom(self,pid):
        if pid <= 0:return False
        try:
            cmd=subprocess.run(["ps","-p",str(pid),"-o","command="],capture_output=True,text=True,timeout=2).stdout
            return "lokay.fala_organ" in cmd
        except Exception:return False
    def _serve(self):
        import time
        while not self.stop:
            try: conn,_=self.sock.accept()
            except OSError: break
            with conn:
                try:
                    req=json.loads(conn.recv(4096)); pid=self._peer_pid(conn)
                    identity_ok = self.pr is None or (
                        int(req.get("pr") or 0) == self.pr and req.get("branch") == self.branch
                        and (not self.head_sha or req.get("head_sha") == self.head_sha)
                    )
                    ok=(time.monotonic()<self.deadline and self._is_atom(pid) and req.get("repo")=="mikolaj92/lokay" and int(req.get("issue") or 0)==self.issue and req.get("fingerprint")==self.fingerprint and req.get("atom") in _ALLOWED and identity_ok)
                    conn.sendall(json.dumps({"ok":ok}).encode())
                except Exception: conn.sendall(b'{"ok":false}')
    def bind_pr(self, *, pr: int, branch: str, head_sha: str) -> None:
        self.pr, self.branch, self.head_sha = int(pr), str(branch), str(head_sha)
    def env(self): return {"LOKAY_REPAIR_BROKER":str(self.path),"LOKAY_REPAIR_ISSUE":str(self.issue),"LOKAY_REPAIR_FINGERPRINT":self.fingerprint}
    def close(self):
        self.stop=True; self.sock.close()
        try:self.path.unlink();self.dir.rmdir()
        except OSError:pass

def broker_authorized()->bool:
    path=os.environ.get("LOKAY_REPAIR_BROKER","")
    if not path:return False
    req={"repo":os.environ.get("LOKAY_REPAIR_REPO",""),"issue":os.environ.get("LOKAY_REPAIR_ISSUE","0"),"fingerprint":os.environ.get("LOKAY_REPAIR_FINGERPRINT",""),"atom":os.environ.get("LOKAY_FALA_ATOM",""),"pr":os.environ.get("LOKAY_REPAIR_PR","0"),"branch":os.environ.get("LOKAY_REPAIR_BRANCH",""),"head_sha":os.environ.get("LOKAY_REPAIR_HEAD_SHA","")}
    try:
        s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);s.settimeout(2);s.connect(path);s.sendall(json.dumps(req).encode());out=json.loads(s.recv(1024));s.close();return out.get("ok") is True
    except Exception:return False
