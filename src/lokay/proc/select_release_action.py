from __future__ import annotations
import json,sys
from lokay.envelope import emit_exit,err
from lokay.release_train import next_release_action

def select(value:dict)->dict:return {'ok':True,**next_release_action(dict(value.get('plan') or {}),dict(value.get('state') or {}))}
def main(argv=None):
 try:return emit_exit(select(json.load(sys.stdin)))
 except Exception as exc:return emit_exit(err(str(exc)))
if __name__=='__main__':raise SystemExit(main())
