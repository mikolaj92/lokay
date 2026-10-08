from lokay.launch import launch


def test_gb10_down_launches_nothing():
    out = launch({"work_id": "o/r#1", "mode": "build"}, token=7, seq=1, gb10_up=False)
    assert out == {"launched": []}


def test_launch_argv_carries_the_work():
    out = launch({"work_id": "o/r#1", "mode": "build"}, token=7, seq=1)
    assert out["launched"][0]["argv"] == [
        "setsid", "lokay", "blueprint", "--work-id", "o/r#1",
        "--mode", "build", "--token", "7", "--seq", "1",
    ]
