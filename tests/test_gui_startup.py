import pytest


def test_launch_initializes_window_and_enters_tk_loop(monkeypatch):
    from shortsfactory import gui

    events = []

    class FakeRoot:
        def mainloop(self):
            events.append("mainloop")

    class FakeApp:
        def __init__(self, root):
            events.append(("app", root))

    monkeypatch.setattr(gui.tk, "Tk", FakeRoot)
    monkeypatch.setattr(gui, "ShortsFactoryApp", FakeApp)

    gui.launch()

    assert events[0][0] == "app"
    assert isinstance(events[0][1], FakeRoot)
    assert events[1] == "mainloop"


def test_real_gui_initialization_when_a_display_is_available(tmp_path, monkeypatch):
    import tkinter as tk
    import builtins
    from shortsfactory import gui

    try:
        root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"No graphical display on this runner: {exc}")

    monkeypatch.setattr(gui, "load_settings", lambda: {})
    monkeypatch.setattr(gui, "user_data_dir", lambda: tmp_path)
    original_import = builtins.__import__
    def fail_cairosvg(name, *args, **kwargs):
        if name == "cairosvg":
            raise RuntimeError("forced renderer failure for fallback test")
        return original_import(name, *args, **kwargs)
    monkeypatch.setattr(builtins, "__import__", fail_cairosvg)
    try:
        root.withdraw()
        app = gui.ShortsFactoryApp(root)
        assert root.title() == "OLV"
        assert app.logo_image is not None
        assert (tmp_path / "drafts").is_dir() is False
    finally:
        root.destroy()
