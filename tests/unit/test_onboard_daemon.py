"""Unit tests for daemon detection logic in cmd_onboard."""
from __future__ import annotations

from unittest.mock import patch, MagicMock

from ocw.cli.cmd_onboard import _daemon_already_running


class TestDaemonAlreadyRunning:
    def test_darwin_plist_exists_and_loaded(self, tmp_path, monkeypatch):
        """Returns True on macOS when plist exists and launchctl list succeeds."""
        monkeypatch.setattr("ocw.cli.cmd_onboard.platform.system", lambda: "Darwin")
        plist = tmp_path / "Library" / "LaunchAgents" / "com.openclawwatch.serve.plist"
        plist.parent.mkdir(parents=True)
        plist.write_text("<plist/>")
        monkeypatch.setattr("ocw.cli.cmd_onboard.Path.home", lambda: tmp_path)

        result_mock = MagicMock(returncode=0)
        with patch("ocw.cli.cmd_onboard.subprocess.run", return_value=result_mock) as run_mock:
            assert _daemon_already_running() is True
            run_mock.assert_called_once_with(
                ["launchctl", "list", "com.openclawwatch.serve"],
                capture_output=True, text=True,
            )

    def test_darwin_plist_missing(self, tmp_path, monkeypatch):
        """Returns False on macOS when plist does not exist."""
        monkeypatch.setattr("ocw.cli.cmd_onboard.platform.system", lambda: "Darwin")
        monkeypatch.setattr("ocw.cli.cmd_onboard.Path.home", lambda: tmp_path)
        assert _daemon_already_running() is False

    def test_darwin_plist_exists_but_not_loaded(self, tmp_path, monkeypatch):
        """Returns False on macOS when plist exists but launchctl list fails."""
        monkeypatch.setattr("ocw.cli.cmd_onboard.platform.system", lambda: "Darwin")
        plist = tmp_path / "Library" / "LaunchAgents" / "com.openclawwatch.serve.plist"
        plist.parent.mkdir(parents=True)
        plist.write_text("<plist/>")
        monkeypatch.setattr("ocw.cli.cmd_onboard.Path.home", lambda: tmp_path)

        result_mock = MagicMock(returncode=3)
        with patch("ocw.cli.cmd_onboard.subprocess.run", return_value=result_mock):
            assert _daemon_already_running() is False

    def test_linux_active(self, monkeypatch):
        """Returns True on Linux when systemctl reports active."""
        monkeypatch.setattr("ocw.cli.cmd_onboard.platform.system", lambda: "Linux")
        result_mock = MagicMock(returncode=0, stdout="active\n")
        with patch("ocw.cli.cmd_onboard.subprocess.run", return_value=result_mock) as run_mock:
            assert _daemon_already_running() is True
            run_mock.assert_called_once_with(
                ["systemctl", "--user", "is-active", "openclawwatch"],
                capture_output=True, text=True,
            )

    def test_linux_inactive(self, monkeypatch):
        """Returns False on Linux when systemctl reports inactive."""
        monkeypatch.setattr("ocw.cli.cmd_onboard.platform.system", lambda: "Linux")
        result_mock = MagicMock(returncode=3, stdout="inactive\n")
        with patch("ocw.cli.cmd_onboard.subprocess.run", return_value=result_mock):
            assert _daemon_already_running() is False

    def test_unsupported_platform(self, monkeypatch):
        """Returns False on unsupported platforms."""
        monkeypatch.setattr("ocw.cli.cmd_onboard.platform.system", lambda: "Windows")
        assert _daemon_already_running() is False
