"""Settings page — language, sound, notifications."""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout,
    QComboBox, QCheckBox, QLabel, QPushButton, QSpinBox, QLineEdit,
    QScrollArea,
)
from PyQt5.QtCore import pyqtSignal
from gui.win95 import (
    BUTTON_STYLE, ERROR, FIELD_STYLE, FONT_UI, GROUP_STYLE, PRIMARY_BUTTON_STYLE,
    SHADOW, SUCCESS,
)
from i18n import get_string as _t


def _write_toml_fallback(path, cfg: dict) -> None:
    """Write TOML without external libs — handles nested tables and basic types."""
    lines: list[str] = []
    top_keys = {k: v for k, v in cfg.items() if not isinstance(v, dict)}
    table_keys = {k: v for k, v in cfg.items() if isinstance(v, dict)}
    for k, v in top_keys.items():
        lines.append(f"{k} = {_toml_value(v)}")
    for section, values in table_keys.items():
        nested = {k: v for k, v in values.items() if isinstance(v, dict)}
        flat = {k: v for k, v in values.items() if not isinstance(v, dict)}
        if flat:
            lines.append(f"\n[{section}]")
            for k, v in flat.items():
                lines.append(f"{k} = {_toml_value(v)}")
        for sub, sub_values in nested.items():
            lines.append(f"\n[{section}.{sub}]")
            for k, v in sub_values.items():
                lines.append(f"{k} = {_toml_value(v)}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _toml_value(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, str):
        return f'"{v}"'
    if isinstance(v, list):
        items = ", ".join(_toml_value(i) for i in v)
        return f"[{items}]"
    return f'"{v}"'


class SettingsPage(QWidget):
    settings_changed = pyqtSignal(dict)  # emits changed config keys

    def __init__(self, config: dict):
        super().__init__()
        self._config = config

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        container = QWidget()
        layout = QVBoxLayout(container)
        scroll.setWidget(container)
        outer.addWidget(scroll)

        # --- HaikuHoff ---
        haiku_group = QGroupBox("HaikuHoff")
        haiku_group.setStyleSheet(GROUP_STYLE)
        hg = QFormLayout()

        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.Password)
        self.api_key_input.setPlaceholderText("sk-ant-...")
        self.api_key_input.setStyleSheet(FIELD_STYLE)
        current_key = config.get("haiku", {}).get("api_key", "")
        self.api_key_input.setText(current_key)
        hg.addRow("HaikuHoff Key:", self.api_key_input)

        haiku_hint = QLabel(_t("haiku_hint"))
        haiku_hint.setStyleSheet(
            f"color: #666; font-size: 11px; font-style: italic; font-family: {FONT_UI};"
        )
        haiku_hint.setWordWrap(True)
        hg.addRow(haiku_hint)

        test_row = QHBoxLayout()
        self.btn_test_haiku = QPushButton(_t("haiku_test"))
        self.btn_test_haiku.setFixedWidth(80)
        self.btn_test_haiku.setStyleSheet(BUTTON_STYLE)
        self.btn_test_haiku.clicked.connect(self._test_haiku)
        test_row.addWidget(self.btn_test_haiku)
        self.haiku_status = QLabel("")
        self.haiku_status.setStyleSheet(
            f"font-style: italic; padding-left: 8px; font-family: {FONT_UI};"
        )
        test_row.addWidget(self.haiku_status)
        test_row.addStretch()
        hg.addRow(test_row)

        haiku_group.setLayout(hg)
        layout.addWidget(haiku_group)

        # --- Language ---
        lang_group = QGroupBox(_t("lang_group"))
        lang_group.setStyleSheet(GROUP_STYLE)
        lg = QFormLayout()
        self.lang_combo = QComboBox()
        self.lang_combo.addItems(["en", "ua"])
        self.lang_combo.setStyleSheet(FIELD_STYLE)
        current_lang = config.get("general", {}).get("language", "en")
        self.lang_combo.setCurrentText(current_lang)
        lg.addRow(_t("language") + ":", self.lang_combo)
        lang_group.setLayout(lg)
        layout.addWidget(lang_group)

        # --- Sound ---
        sound_group = QGroupBox(_t("sound_group"))
        sound_group.setStyleSheet(GROUP_STYLE)
        sg = QFormLayout()

        self.sound_enabled = QCheckBox(_t("enable_fart"))
        self.sound_enabled.setChecked(config.get("sounds", {}).get("enabled", True))
        sg.addRow(self.sound_enabled)

        self.sound_mode = QComboBox()
        self.sound_mode.addItems(["classic", "fart"])
        self.sound_mode.setStyleSheet(FIELD_STYLE)
        current_mode = config.get("sounds", {}).get("mode", "classic")
        self.sound_mode.setCurrentText(current_mode)
        sg.addRow(_t("sound_mode") + ":", self.sound_mode)

        self.notif_enabled = QCheckBox(_t("enable_notif"))
        self.notif_enabled.setChecked(config.get("alerts", {}).get("desktop_notifications", True))
        sg.addRow(self.notif_enabled)

        self.popup_enabled = QCheckBox(_t("enable_popup"))
        self.popup_enabled.setChecked(config.get("alerts", {}).get("popup_notifications", True))
        sg.addRow(self.popup_enabled)

        sound_group.setLayout(sg)
        layout.addWidget(sound_group)

        # --- Alerts ---
        alerts_group = QGroupBox(_t("alerts_group"))
        alerts_group.setStyleSheet(GROUP_STYLE)
        ag = QFormLayout()
        ag.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

        filters = config.get("alert_filters", {})

        self.alert_docker = QCheckBox(_t("alert_docker"))
        self.alert_docker.setChecked(filters.get("docker", True))
        ag.addRow(self.alert_docker)

        self.alert_security = QCheckBox(_t("alert_security"))
        self.alert_security.setChecked(filters.get("security", True))
        ag.addRow(self.alert_security)

        self.alert_ports = QCheckBox(_t("alert_ports"))
        self.alert_ports.setChecked(filters.get("ports", True))
        ag.addRow(self.alert_ports)

        self.alert_usage = QCheckBox(_t("alert_usage"))
        self.alert_usage.setChecked(filters.get("usage", True))
        ag.addRow(self.alert_usage)

        self.cooldown_spin = QSpinBox()
        self.cooldown_spin.setRange(60, 3600)
        self.cooldown_spin.setSuffix(" sec")
        self.cooldown_spin.setStyleSheet(FIELD_STYLE)
        self.cooldown_spin.setValue(config.get("alerts", {}).get("cooldown_seconds", 300))
        ag.addRow(_t("alert_cooldown"), self.cooldown_spin)

        alerts_group.setLayout(ag)
        layout.addWidget(alerts_group)

        # --- Tests ---
        layout.addWidget(self._build_tests_group())

        # --- Apply ---
        self.btn_apply = QPushButton(_t("apply_save"))
        self.btn_apply.setStyleSheet(
            PRIMARY_BUTTON_STYLE.replace("padding: 6px 14px", "padding: 8px 24px")
        )
        self.btn_apply.clicked.connect(self._apply)
        layout.addWidget(self.btn_apply)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet(
            f"color: {SUCCESS}; font-style: italic; padding: 4px; font-family: {FONT_UI};"
        )
        layout.addWidget(self.status_label)

        layout.addStretch()

    def _build_tests_group(self) -> QGroupBox:
        from PyQt5.QtWidgets import (
            QCheckBox, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
            QSpinBox, QVBoxLayout,
        )
        box = QGroupBox(_t("settings_tests_group"))
        box.setStyleSheet(GROUP_STYLE)
        v = QVBoxLayout(box)

        self._cb_tests_save_point = QCheckBox(_t("settings_tests_save_point"))
        self._cb_tests_save_point.setChecked(
            bool(self._config.get("tests", {}).get("trigger_on_save_point", False))
        )
        v.addWidget(self._cb_tests_save_point)

        self._cb_tests_watch = QCheckBox(_t("settings_tests_watch"))
        self._cb_tests_watch.setChecked(
            bool(self._config.get("tests", {}).get("watch", False))
        )
        try:
            import watchdog  # noqa: F401
        except ImportError:
            self._cb_tests_watch.setEnabled(False)
            self._cb_tests_watch.setToolTip(_t("settings_tests_watch_disabled"))
        v.addWidget(self._cb_tests_watch)

        cmd_row = QHBoxLayout()
        cmd_row.addWidget(QLabel(_t("settings_tests_command") + ":"))
        self._le_tests_cmd = QLineEdit(self._config.get("tests", {}).get("command", ""))
        self._le_tests_cmd.setPlaceholderText(_t("settings_tests_command_placeholder"))
        self._le_tests_cmd.setStyleSheet(FIELD_STYLE)
        cmd_row.addWidget(self._le_tests_cmd, 1)
        v.addLayout(cmd_row)

        timeout_row = QHBoxLayout()
        timeout_row.addWidget(QLabel(_t("settings_tests_timeout") + ":"))
        self._sb_tests_timeout = QSpinBox()
        self._sb_tests_timeout.setRange(10, 7200)
        self._sb_tests_timeout.setValue(int(self._config.get("tests", {}).get("timeout_s", 600)))
        self._sb_tests_timeout.setStyleSheet(FIELD_STYLE)
        timeout_row.addWidget(self._sb_tests_timeout)
        timeout_row.addStretch()
        v.addLayout(timeout_row)

        return box

    def _test_haiku(self):
        status_base = f"font-style: italic; padding-left: 8px; font-family: {FONT_UI};"
        key = self.api_key_input.text().strip()
        if not key:
            self.haiku_status.setText(_t("haiku_no_key"))
            self.haiku_status.setStyleSheet(f"color: {ERROR}; {status_base}")
            return
        self.haiku_status.setText(_t("haiku_testing"))
        self.haiku_status.setStyleSheet(f"color: {SHADOW}; {status_base}")
        from core.haiku_client import HaikuClient
        client = HaikuClient(api_key=key)
        client._min_interval = 0
        result = client.ask("Say OK", max_tokens=5)
        if result:
            self.haiku_status.setText(_t("haiku_connected"))
            self.haiku_status.setStyleSheet(f"color: {SUCCESS}; {status_base}")
        else:
            self.haiku_status.setText(_t("haiku_failed"))
            self.haiku_status.setStyleSheet(f"color: {ERROR}; {status_base}")

    def _apply(self):
        """Save settings to config.toml — cross-platform."""
        from core.platform import get_platform

        self._config.setdefault("haiku", {})
        self._config["haiku"]["api_key"] = self.api_key_input.text().strip()

        self._config["general"]["language"] = self.lang_combo.currentText()
        self._config["sounds"]["enabled"] = self.sound_enabled.isChecked()
        self._config["sounds"]["mode"] = self.sound_mode.currentText()
        self._config["alerts"]["desktop_notifications"] = self.notif_enabled.isChecked()
        self._config["alerts"]["popup_notifications"] = self.popup_enabled.isChecked()
        self._config["alerts"]["cooldown_seconds"] = self.cooldown_spin.value()

        # Tests settings
        self._config.setdefault("tests", {})
        self._config["tests"]["trigger_on_save_point"] = self._cb_tests_save_point.isChecked()
        self._config["tests"]["watch"] = self._cb_tests_watch.isChecked()
        self._config["tests"]["command"] = self._le_tests_cmd.text()
        self._config["tests"]["timeout_s"] = self._sb_tests_timeout.value()

        # Custom alert filters
        self._config.setdefault("alert_filters", {})
        self._config["alert_filters"]["docker"] = self.alert_docker.isChecked()
        self._config["alert_filters"]["security"] = self.alert_security.isChecked()
        self._config["alert_filters"]["ports"] = self.alert_ports.isChecked()
        self._config["alert_filters"]["usage"] = self.alert_usage.isChecked()

        # Write config — same location where it was loaded from
        from pathlib import Path
        from core.config import _project_root
        config_path = _project_root() / "config.toml"

        try:
            try:
                import tomli_w
                with open(config_path, "wb") as f:
                    tomli_w.dump(self._config, f)
            except ImportError:
                _write_toml_fallback(config_path, self._config)
            self.status_label.setText(_t("saved_ok"))
            self.status_label.setStyleSheet(
                f"color: {SUCCESS}; font-style: italic; padding: 4px; font-family: {FONT_UI};"
            )
            self.settings_changed.emit(self._config)
        except Exception as e:
            self.status_label.setText(_t("save_error").format(e))
            self.status_label.setStyleSheet(
                f"color: {ERROR}; font-style: italic; padding: 4px; font-family: {FONT_UI};"
            )

