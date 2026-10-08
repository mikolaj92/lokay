import inspect
import lokay.gh as gh


def test_write_functions_do_not_label_or_assign():
    text = "\n".join(inspect.getsource(getattr(gh, name)) for name in gh.WRITES)
    for word in ("ensure_labels", "assign_issue", "--label", "--add-label"):
        assert word not in text
