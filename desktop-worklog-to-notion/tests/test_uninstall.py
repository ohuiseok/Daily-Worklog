from __future__ import annotations

from worklog.uninstall import build_uninstall_plan, uninstall


def test_uninstall_removes_shortcut_install_root_and_settings(tmp_path):
    shortcut = tmp_path / "Roaming" / "Startup" / "Desktop Worklog to Notion.lnk"
    install_root = tmp_path / "Local" / "DesktopWorklogToNotion"
    settings = tmp_path / "Roaming" / "DesktopWorklogToNotion" / "settings.json"
    shortcut.parent.mkdir(parents=True)
    install_root.mkdir(parents=True)
    settings.parent.mkdir(parents=True)
    shortcut.write_text("shortcut", encoding="utf-8")
    (install_root / "app.exe").write_text("exe", encoding="utf-8")
    settings.write_text("{}", encoding="utf-8")

    result = uninstall(
        build_uninstall_plan(
            shortcut_path=shortcut,
            install_root_path=install_root,
            settings_path=settings,
        )
    )

    assert result.success is True
    assert shortcut in result.removed
    assert install_root in result.removed
    assert settings in result.removed
    assert not shortcut.exists()
    assert not install_root.exists()
    assert not settings.exists()


def test_uninstall_can_keep_settings(tmp_path):
    shortcut = tmp_path / "Startup" / "Desktop Worklog to Notion.lnk"
    install_root = tmp_path / "Local" / "DesktopWorklogToNotion"
    settings = tmp_path / "Roaming" / "DesktopWorklogToNotion" / "settings.json"
    shortcut.parent.mkdir(parents=True)
    install_root.mkdir(parents=True)
    settings.parent.mkdir(parents=True)
    shortcut.write_text("shortcut", encoding="utf-8")
    settings.write_text("{}", encoding="utf-8")

    result = uninstall(
        build_uninstall_plan(
            shortcut_path=shortcut,
            install_root_path=install_root,
            settings_path=settings,
            remove_settings=False,
        )
    )

    assert result.success is True
    assert settings not in result.removed
    assert settings.exists()
    assert not shortcut.exists()
    assert not install_root.exists()
