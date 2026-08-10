"""テストランナーが動作することの確認（Issue #4）。"""


def test_package_is_importable():
    import taskcli

    assert taskcli.__version__
