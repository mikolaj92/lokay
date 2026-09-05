from lokay.models import Issue
from lokay.split import plan_split, validate_split_plan, stable_child_marker


def test_trusted_large_issue_gets_bounded_acyclic_implementable_children():
    parent=Issue(number=9,title='Large migration',body='1. Migrate adapter identity\n2. Update consumers\n3. Verify smoke',labels=[],assignees=['mikolaj92'],state='OPEN',url='u',repo='a/b')
    plan=plan_split(parent,reason='too_large_split')
    checked=validate_split_plan(plan.to_dict(),parent=parent)
    assert checked['valid'] and 2 <= len(plan.children) <= 5
    assert all('## Done means' in child.body for child in plan.children)
    assert [stable_child_marker(parent,i) for i in range(1,4)]==[stable_child_marker(parent,i) for i in range(1,4)]


def test_cycle_or_missing_parent_coverage_fails_closed():
    parent=Issue(number=9,title='Large',body='x',labels=[],assignees=['mikolaj92'],state='OPEN',url='u',repo='a/b')
    plan={'children':[{'title':'A','body':'## Done means\n- [ ] A','source':'x','depends_on':[2]},{'title':'B','body':'## Done means\n- [ ] B','source':'x','depends_on':[1]}]}
    out=validate_split_plan(plan,parent=parent)
    assert not out['valid'] and out['reason']=='dependency_cycle'
