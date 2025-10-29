import pathlib
import time

import invoke


def test_expand_templates_basic():
    import invoke_depends.arg_templates as m

    def fn(x, y="bar"):
        pass

    result = m.expand(
        ["${x}/${y}.txt"],
        args=("foo",),
        kwargs={},
        fn=fn,
    )
    assert result == [pathlib.Path("foo/bar.txt")]


def test_invoke_task_integration(tmp_path):
    import invoke_depends

    src = tmp_path / "a.txt"
    dst = tmp_path / "b.txt"

    src.write_text("hi")

    # use both decorators in normal order
    @invoke.task(name="do-thing")
    @invoke_depends.on(inps=[src], outs=[dst], verbose=True)
    def do_thing(c, foo: str, baa: int = 10):
        dst.write_text(f"done {foo=} {baa=}")
        return "ok"

    # Check that calling the Task executes our dependency logic
    # Normally invoke runs Task.__call__(context, *args), but we can simulate that:
    ctx = invoke.Context()
    result = do_thing(ctx, foo="bar")

    assert result == "ok"
    assert dst.exists() and dst.read_text() == "done foo='bar' baa=10"

    # Calling again should skip (depends logic should short-circuit)
    result2 = do_thing(ctx, foo="bar")
    assert result2 is None


def test_should_run_and_call_with_templates(tmp_path):
    import invoke_depends.mod as dep

    ctx = invoke.Context()

    src = tmp_path / "input.txt"
    dst = tmp_path / "output-main.txt"

    # Task A: produce src
    @invoke.task(name="produce_src")
    @dep.on(
        inps=[],  # nothing depends on it
        outs=[src],
        verbose=True,
    )
    def produce_src(c, text: str):
        src.write_text(text)
        src.touch()
        return "src updated"

    # Task B: depends on src, produces dst
    @invoke.task(name="make_file")
    @dep.on(
        inps=[src],
        outs=[str(tmp_path / "output-${name}.txt")],
        verbose=True,
    )
    def make_file(c, name: str):
        out = tmp_path / f"output-{name}.txt"
        data = src.read_text()
        out.write_text(f"processed: {data}")
        return "main updated"

    # --- First build ---
    got = produce_src(ctx, "first write")
    assert got == "src updated"
    assert src.exists()

    src_first_mtime = src.stat().st_mtime_ns

    got = make_file(ctx, name="main")
    assert got == "main updated"
    dst_first_mtime = dst.stat().st_mtime_ns

    # --- Second build, no changes: should skip both ---
    assert produce_src(ctx, "first write") is None
    assert make_file(ctx, name="main") is None
    assert dst.stat().st_mtime_ns == dst_first_mtime

    # --- Regenerate src (new content) ---
    time.sleep(0.01)
    assert produce_src(ctx, "new content") == "src updated"

    assert src.read_text() == "new content"
    assert src.stat().st_mtime_ns > src_first_mtime

    # Now make_file should detect that src is newer
    got = make_file(ctx, name="main")
    assert got == "main updated"
    assert dst.stat().st_mtime_ns > dst_first_mtime
