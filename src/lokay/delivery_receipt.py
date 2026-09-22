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
    if require_delivered:
        verify_provenance(receipt)
    if require_delivered and not (receipt.get('merge_sha') and receipt.get('merged_at') and receipt.get('issue_closed') is True and receipt.get('main_contains_head') is True):raise ValueError('delivery confirmation missing')
    return {'autonomous':True,'receipt_digest':supplied,'head_sha':observed_head}
def compact_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    """Bounded provenance projection, excluding arbitrary transport data."""
    scalars = REQUIRED - {'run_refs'} | {
        'schema', 'receipt_digest', 'branch', 'original_head_sha', 'reviewed_head_sha',
        'tested_head_sha', 'review_result_sha256', 'task_identity_sha256',
        'merge_sha', 'merged_at', 'issue_closed', 'main_contains_head',
        'acceptance_identity', 'acceptance_accepted',
    }
    out = {k:v for k,v in receipt.items() if k in scalars
           and (type(v) in (bool, int) or isinstance(v, str) and len(v) <= 1024)}
    for key, fields in (
        ('run_refs', {'db', 'run_id', 'path_id'}),
        ('repair_lineage', {'start_head_sha', 'target_head_sha', 'checkpoint_sha256', 'intent_sha256'}),
    ):
        if isinstance(receipt.get(key), list):
            out[key] = [{k:v for k,v in row.items() if k in fields and isinstance(v,str) and len(v)<=1024}
                        for row in receipt[key][:32] if isinstance(row,dict)]
    ref = receipt.get('test_run_ref')
    if isinstance(ref, dict):
        out['test_run_ref'] = {k:v for k,v in ref.items() if k in {'db','run_id','path_id'}
                               and isinstance(v,str) and len(v)<=1024}
    return out


def verify_provenance(receipt: dict[str, Any]) -> None:
    """Provisional placeholders are never evidence of completed delivery."""
    def identity(value: Any) -> bool:
        return (isinstance(value, str) and bool(value.strip())
                and value.strip().lower() not in {'pending', 'unavailable', 'unknown', 'none', 'null'})

    def ref(value: Any) -> bool:
        return isinstance(value, dict) and all(identity(value.get(k)) for k in ('db', 'run_id', 'path_id'))

    refs = receipt.get('run_refs')
    head = receipt.get('head_sha')
    if (not all(identity(receipt.get(k)) for k in ('builder_session', 'reviewer_session'))
            or not all(re.fullmatch(r'sha256:[a-f0-9]{64}', str(receipt.get(k) or ''))
                       for k in ('graph_digest', 'path_digest', 'acceptance_digest'))
            or receipt.get('work_id') != f"{receipt.get('repo')}#{receipt.get('issue')}"
            or receipt.get('acceptance_identity') != receipt.get('work_id')
            or receipt.get('acceptance_accepted') is not True
            or not isinstance(refs, list) or not refs or not all(ref(r) for r in refs)
            or not ref(receipt.get('test_run_ref'))
            or not re.fullmatch(r'[a-f0-9]{40}', str(head or ''))
            or receipt.get('reviewed_head_sha') != head or receipt.get('tested_head_sha') != head
            or not all(re.fullmatch(r'[a-f0-9]{64}', str(receipt.get(k) or ''))
                       for k in ('review_result_sha256', 'task_identity_sha256'))):
        raise ValueError('receipt_provenance_incomplete')


def finalize_receipt(receipt:dict[str,Any],*,merge_sha:str,merged_at:str,issue_closed:bool,main_contains_head:bool)->dict[str,Any]:
    if not (merge_sha and merged_at and issue_closed and main_contains_head):raise ValueError('delivery confirmation incomplete')
    verify_provenance(receipt)
    return signed({**receipt,'merge_sha':merge_sha,'merged_at':merged_at,'issue_closed':issue_closed,'main_contains_head':main_contains_head})
