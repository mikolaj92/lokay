"""Pure selector for a serial, dependency-aware cross-repo release train."""
from __future__ import annotations
from typing import Any

def next_release_action(plan:dict[str,Any],state:dict[str,Any])->dict[str,Any]:
 source=plan['source'];cursor=int(state.get('cursor') or 0)
 if not state.get('source_on_main'):return {'route':'wait_source','effect':None}
 tag_sha=state.get('tag_sha')
 if tag_sha and tag_sha!=source['sha']:return {'route':'conflict','effect':None,'reason':'immutable_tag_mismatch'}
 if not tag_sha:return {'route':'create_release','effect':'create_release','tag':source['tag'],'sha':source['sha']}
 consumers=plan.get('consumers') or []
 if cursor>=len(consumers):return {'route':'done','effect':None}
 repo=consumers[cursor]['repo']
 if not state.get('issue'):return {'route':'open_consumer_issue','effect':'open_issue','cursor':cursor,'repo':repo}
 if not state.get('pr'):return {'route':'bump_and_verify','effect':'issue_to_pr','cursor':cursor,'repo':repo,'verify':consumers[cursor]['verify']}
 if not state.get('consumer_merged'):return {'route':'confirm_consumer','effect':None,'cursor':cursor,'repo':repo}
 return {'route':'advance_cursor','effect':'advance_cursor','cursor':cursor+1,'repo':repo}
