import json
from zipfile import ZipFile

import pytest

from tools.export_source_document import build_plan, project_source, wrap_source_line, write_source_zip


def test_source_projection_preserves_hashes_inside_strings_and_docstring_only_bodies():
    source = '''"""Document summary."""
value = "#literal"  # actual comment
def empty():
    """This is documentation."""
    return None
text = """first

# still a literal
last"""
'''
    projection = project_source(source)
    assert [line["text"] for line in projection["lines"]] == [
        'value = "#literal"', "def empty():", "    return None", 'text = """first',
        "", "# still a literal", 'last"""',
    ]
    assert projection["effective_code_lines"] == 6
    assert projection["preserved_literal_blank_lines"] == 1
    assert projection["logical_statement_lines"] == 4


def test_inline_docstring_never_discards_other_code():
    source = 'def 中文(): "description"; return "# kept"\n'
    projection = project_source(source)
    assert projection["lines"][0]["text"] == source.rstrip()
    assert projection["preserved_inline_docstrings"] == 1


def test_soft_wrap_is_reversible_and_tracks_width():
    value = "    text = '你好world " * 10
    rows = wrap_source_line(value, lambda text: sum(2 if ord(c) > 127 else 1 for c in text), 30)
    assert "".join(rows) == value
    assert all(sum(2 if ord(c) > 127 else 1 for c in row) <= 30 for row in rows)


def test_plan_uses_first_and_last_30_full_pages_and_original_line_mapping(tmp_path):
    source = "\n".join(f"value_{index} = {index}" for index in range(3600)) + "\n"
    (tmp_path / "main.py").write_text(source, encoding="utf-8")
    plan = build_plan(tmp_path, lambda text: len(text), rows_per_page=58)
    assert plan["totals"]["effective_code_lines"] == 3600
    assert len(plan["pages"]) == 63
    assert len(plan["selected"]) == 60
    assert plan["selected"][:30] == list(range(30))
    assert plan["selected"][30:] == list(range(33, 63))
    assert plan["pages"][33][0]["number"] == 1915
    assert plan["pages"][33][0]["source_line"] == 1915
    assert plan["nonfinal_pages_below_50_code_lines"] == []


def test_clean_project_archive_includes_build_and_tests_but_excludes_user_data(tmp_path):
    source = '# 原始注释必须保留\nvalue = "中文"\n'
    files = {
        "main.py": source, "README.md": "使用说明", "requirements-build.txt": "pyinstaller",
        "ScreenQualityAnalyzer.spec": "# Build definition", "tests/test_main.py": "assert True",
        "tools/build_windows.py": "print('build')", "docs/DEVELOPMENT.md": "开发说明",
        ".github/workflows/tests.yml": "name: test", "data/analysis.sqlite3": "private",
        "samples/private.mp4": "video", "screenshots/main.png": "image",
        ".venv/private.py": "secret", "build/main.py": "build", "dist/main.py": "dist",
        "tests/__pycache__/private.py": "cache", "tools/data/private.py": "private",
    }
    for name, content in files.items():
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    plan = build_plan(tmp_path, len)
    archive_path = tmp_path / "complete.zip"
    package_manifest = write_source_zip(tmp_path, plan, archive_path)
    with ZipFile(archive_path) as archive:
        assert set(archive.namelist()) == {
            "main.py", "README.md", "requirements-build.txt", "ScreenQualityAnalyzer.spec",
            "tests/test_main.py", "tools/build_windows.py", "docs/DEVELOPMENT.md",
            ".github/workflows/tests.yml", "SOURCE_PACKAGE_MANIFEST.json",
        }
        assert archive.read("main.py") == (tmp_path / "main.py").read_bytes()
        assert json.loads(archive.read("SOURCE_PACKAGE_MANIFEST.json")) == package_manifest
    second_path = tmp_path / "second.zip"
    write_source_zip(tmp_path, plan, second_path)
    assert second_path.read_bytes() == archive_path.read_bytes()


def test_source_changes_after_planning_are_rejected(tmp_path):
    source = tmp_path / "main.py"
    source.write_text("value = 1\n", encoding="utf-8")
    plan = build_plan(tmp_path, len)
    source.write_text("value = 2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Source changed after document planning"):
        write_source_zip(tmp_path, plan, tmp_path / "complete.zip")
