def test_invoke_task_integration(tmp_path):
    import invoke
    import invoke_depends

    src = tmp_path / "a.txt"
    dst = tmp_path / "b.txt"

    src.write_text("hi")

    # use both decorators in normal order
    @invoke.task(name="do-thing")
    @invoke_depends.on(deps=[src], creates=[dst], verbose=True)
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
