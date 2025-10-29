def test_decorator(tmp_path):
    import invoke_depends

    src = tmp_path / "a.txt"
    dst = tmp_path / "b.txt"

    src.write_text("hi")

    @invoke_depends.on(deps=[src], creates=[dst])
    def do_thing():
        dst.write_text("done")
        return "ok"

    # The first call should create the file, reporting "ok"
    assert do_thing() == "ok"

    # The second call should do nothing and return None
    assert do_thing() is None
