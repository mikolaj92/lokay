"""Canonical provenance marker for autonomous PR delivery."""
from __future__ import annotations
import hashlib,json,re
from typing import Any
PREFIX='<!-- lokay-autonomous-delivery:'
PATTERN=re.compile(r'<!-- lokay-autonomous-delivery:(\{.*?\}) -->')
REQUIRED={'repo','issue','work_id','graph_digest','path_digest','run_refs','builder_session','reviewer_session','acceptance_digest','head_sha'}

def _canonical(v:dict[str,Any])->str:return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False)
def _digest(v:dict[str,Any])->str:return 'sha256:'+hashlib.sha256(_canonical(v).encode()).hexdigest()
def signed(receipt:dict[str,Any])->dict[str,Any]:
    body={**receipt,'schema':'lokay.autonomous-delivery/1'};body.pop('receipt_digest',None);body['receipt_digest']=_digest(body);return body
def marker(receipt:dict[str,Any])->str:return PREFIX+_canonical(signed(receipt))+' -->'
def parse_marker(text:str)->dict[str,Any]|None:
    found=PATTERN.findall(text)
    if not found:return None
    if len(found)!=1:raise ValueError('multiple autonomous delivery markers')
    value=json.loads(found[0]);verify_receipt(value,observed_head=str(value.get('head_sha') or ''));return value
def verify_receipt(receipt:dict[str,Any],*,observed_head:str,require_delivered:bool=False)->dict[str,Any]:
    if not REQUIRED<=receipt.keys():raise ValueError('receipt required fields missing')
    if receipt['head_sha']!=observed_head:raise ValueError('receipt head mismatch')
    supplied=receipt.get('receipt_digest');body=dict(receipt);body.pop('receipt_digest',None)
    if supplied!=_digest(body):raise ValueError('receipt digest mismatch')
    if require_delivered and not (receipt.get('merge_sha') and receipt.get('merged_at') and receipt.get('issue_closed') is True and receipt.get('main_contains_head') is True):raise ValueError('delivery confirmation missing')
    return {'autonomous':True,'receipt_digest':supplied,'head_sha':observed_head}
def finalize_receipt(receipt:dict[str,Any],*,merge_sha:str,merged_at:str,issue_closed:bool,main_contains_head:bool)->dict[str,Any]:
    if not (merge_sha and merged_at and issue_closed and main_contains_head):raise ValueError('delivery confirmation incomplete')
    return signed({**receipt,'merge_sha':merge_sha,'merged_at':merged_at,'issue_closed':issue_closed,'main_contains_head':main_contains_head})
