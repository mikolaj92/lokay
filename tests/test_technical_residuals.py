import pytest
from lokay.technical_route import classify_technical_route

@pytest.mark.parametrize('title,body,route',[('Bump BOM dependency','Update foo from 1 to 2','implement'),('Migrate identity adapters','Replace legacy adapter identity mechanically','implement'),('Split god file','Break src/app.py into focused modules','split'),('Move UI to HTMX fragments','Replace client state with server-rendered fragments','implement')])
def test_trusted_technical_work_never_needs_human(title,body,route):assert classify_technical_route(title,body)=={'route':route,'reason':'technical_'+route}
def test_only_missing_normative_result_is_human_with_exact_machine_reason():
 out=classify_technical_route('Choose product behavior','Should this charge monthly or yearly? Desired result is not specified.')
 assert out=={'route':'needs_human','reason':'missing_normative_decision','missing':'billing cadence: monthly or yearly'}
