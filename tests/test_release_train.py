from lokay.release_train import next_release_action
PLAN={'source':{'repo':'mikolaj92/Fala','sha':'abc','tag':'v1'},'consumers':[{'repo':'mikolaj92/lokay','verify':['uv','run','pytest']},{'repo':'mikolaj92/app','verify':['true']}]}
def test_source_must_be_confirmed_main_and_release_is_idempotent():
 assert next_release_action(PLAN,{'source_on_main':False})['route']=='wait_source'
 assert next_release_action(PLAN,{'source_on_main':True,'tag_sha':'wrong'})['route']=='conflict'
 assert next_release_action(PLAN,{'source_on_main':True,'tag_sha':'abc','cursor':0})['route']=='open_consumer_issue'
def test_cursor_waits_for_confirmed_merge_and_restart_does_not_duplicate():
 state={'source_on_main':True,'tag_sha':'abc','cursor':0,'issue':9,'pr':10,'consumer_merged':False}
 assert next_release_action(PLAN,state)['route']=='confirm_consumer'
 state['consumer_merged']=True
 assert next_release_action(PLAN,state)=={'route':'advance_cursor','effect':'advance_cursor','cursor':1,'repo':'mikolaj92/lokay'}
