from marionette.dataset import count_files_hunks, is_multi


def test_count_single_file_single_hunk():
    patch = "diff --git a/x.py b/x.py\n@@ -1 +1 @@\n-a\n+b\n"
    assert count_files_hunks(patch) == (1, 1)
    assert not is_multi(patch)


def test_count_multi_file():
    patch = (
        "diff --git a/x.py b/x.py\n@@ -1 +1 @@\n-a\n+b\n"
        "diff --git a/y.py b/y.py\n@@ -1 +1 @@\n-c\n+d\n"
    )
    assert count_files_hunks(patch) == (2, 2)
    assert is_multi(patch)


def test_single_file_multi_hunk_is_multi():
    patch = "diff --git a/x.py b/x.py\n@@ -1 +1 @@\n-a\n+b\n@@ -5 +5 @@\n-e\n+f\n"
    files, hunks = count_files_hunks(patch)
    assert files == 1 and hunks == 2
    assert is_multi(patch)


def test_empty_patch():
    assert count_files_hunks("") == (0, 0)
    assert not is_multi("")
