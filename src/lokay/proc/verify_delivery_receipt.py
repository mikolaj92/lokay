"""Read-only CLI verifier for one autonomous-delivery marker."""
from __future__ import annotations
import argparse,json
from pathlib import Path
from lokay.delivery_receipt import parse_marker,verify_receipt
from lokay.envelope import emit_exit,ok,err

def main(argv=None):
    p=argparse.ArgumentParser();p.add_argument('--body-file',required=True);p.add_argument('--head',required=True);p.add_argument('--require-delivered',action='store_true');a=p.parse_args(argv)
    try:
        receipt=parse_marker(Path(a.body_file).read_text())
        if receipt is None:return emit_exit(err('autonomous receipt missing',reason='unattributed'))
        return emit_exit(ok(**verify_receipt(receipt,observed_head=a.head,require_delivered=a.require_delivered)))
    except Exception as exc:return emit_exit(err(str(exc),reason='receipt_invalid'))
if __name__=='__main__':raise SystemExit(main())
