from pathlib import Path

from infra.architecture_context import load_current_architecture


def test_loads_supported_files_in_stable_order_and_skips_readme(tmp_path: Path):
    (tmp_path / "20-runtime.md").write_text("Runtime facts", encoding="utf-8")
    (tmp_path / "10-modules.md").write_text("Module facts", encoding="utf-8")
    (tmp_path / "README.md").write_text("Loader instructions", encoding="utf-8")
    (tmp_path / "ignored.bin").write_bytes(b"ignored")

    context = load_current_architecture(tmp_path)

    assert context.is_loaded
    assert context.files == ("10-modules.md", "20-runtime.md")
    assert context.content.index("Module facts") < context.content.index("Runtime facts")
    assert "Loader instructions" not in context.content


def test_missing_directory_returns_empty_context(tmp_path: Path):
    context = load_current_architecture(tmp_path / "missing")

    assert not context.is_loaded
    assert context.root is None
    assert context.files == ()


def test_marks_context_when_character_limit_is_reached(tmp_path: Path):
    (tmp_path / "system.md").write_text("x" * 500, encoding="utf-8")

    context = load_current_architecture(tmp_path, max_chars=80)

    assert context.truncated
    assert "TRUNCATED" in context.content
