from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

from .config import EDGES


class NativeWindow(QtWidgets.QMainWindow):
    def __init__(self, app) -> None:
        super().__init__()
        self.app = app
        self.setWindowTitle("CrossMouse")
        self.resize(420, 620)
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.FramelessWindowHint)
        self.setStyleSheet(
            "QMainWindow, QWidget#central { background: #0f141b; }"
            "QLabel { color: #e6edf3; font-size: 14px; }"
            "QPushButton { background: #1d2834; color: #e6edf3; border: 1px solid #263242; "
            "border-radius: 8px; padding: 8px 12px; }"
            "QPushButton:checked { background: #4dd4ac; color: #08130f; border-color: #4dd4ac; }"
            "QPushButton:disabled { color: #6b7787; background: #141b24; border-color: #1d2834; }"
            "QPushButton#connect_switch { background: #4dd4ac; color: #08130f; font-weight: 700; }"
            "QLineEdit, QComboBox { background: #0d131a; color: #e6edf3; "
            "border: 1px solid #263242; border-radius: 7px; padding: 8px; }"
            "QMenu { background: #171f29; color: #e6edf3; }"
        )
        self._drag_position = None

        central = QtWidgets.QWidget(self)
        central.setObjectName("central")
        self.setCentralWidget(central)
        root = QtWidgets.QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        titlebar = QtWidgets.QFrame(central)
        titlebar.setObjectName("titlebar")
        titlebar.setFixedHeight(36)
        title_layout = QtWidgets.QHBoxLayout(titlebar)
        title_layout.setContentsMargins(14, 0, 8, 0)
        title = QtWidgets.QLabel("CrossMouse", titlebar)
        title.setObjectName("title_text")
        title_layout.addWidget(title)
        title_layout.addStretch(1)
        minimize = QtWidgets.QPushButton("–", titlebar)
        minimize.setObjectName("minimize_button")
        minimize.clicked.connect(self.showMinimized)
        title_layout.addWidget(minimize)
        close = QtWidgets.QPushButton("×", titlebar)
        close.setObjectName("close_button")
        close.clicked.connect(self.close)
        title_layout.addWidget(close)
        root.addWidget(titlebar)

        self.pages = QtWidgets.QStackedWidget(central)
        self.pages.setObjectName("pages")
        root.addWidget(self.pages)
        self.pages.addWidget(self._build_status_page())
        self.pages.addWidget(self._build_settings_sheet())
        self._build_tray()

    def mousePressEvent(self, event) -> None:
        if event.button() == QtCore.Qt.LeftButton:
            self._drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_position is not None and event.buttons() & QtCore.Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_position)
            event.accept()

    def mouseReleaseEvent(self, event) -> None:
        self._drag_position = None

    def _build_tray(self) -> None:
        if not QtWidgets.QSystemTrayIcon.isSystemTrayAvailable():
            self.tray = None
            self.tray_toggle = None
            return
        self.tray = QtWidgets.QSystemTrayIcon(self)
        self.tray.setObjectName("tray")
        pixmap = QtGui.QPixmap(16, 16)
        pixmap.fill(QtGui.QColor("#4dd4ac"))
        self.tray.setIcon(QtGui.QIcon(pixmap))
        self.tray_menu = QtWidgets.QMenu()
        self.tray_show = self.tray_menu.addAction("Show")
        self.tray_show.setObjectName("tray_show")
        self.tray_show.triggered.connect(self.show_normal)
        self.tray_toggle = self.tray_menu.addAction("Connect")
        self.tray_toggle.setObjectName("tray_toggle")
        self.tray_toggle.triggered.connect(self._toggle_connection)
        self.tray_quit = self.tray_menu.addAction("Quit")
        self.tray_quit.setObjectName("tray_quit")
        self.tray_quit.triggered.connect(self.quit_from_tray)
        self.tray.setContextMenu(self.tray_menu)
        if QtWidgets.QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()

    def show_normal(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()

    def quit_from_tray(self) -> None:
        self.app.stop()
        qt_app = QtWidgets.QApplication.instance()
        if qt_app is not None:
            qt_app.quit()

    def closeEvent(self, event) -> None:
        if QtWidgets.QSystemTrayIcon.isSystemTrayAvailable():
            event.ignore()
            self.hide()
        else:
            self.app.stop()
            event.accept()

    def _build_status_page(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget(self.pages)
        page.setObjectName("status_page")
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(14)

        self.link_text = QtWidgets.QLabel("Disconnected", page)
        self.link_text.setObjectName("link_text")
        self.link_text.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(self.link_text)

        self.connect_switch = QtWidgets.QPushButton("Connect", page)
        self.connect_switch.setObjectName("connect_switch")
        self.connect_switch.setMinimumHeight(52)
        self.connect_switch.clicked.connect(self._toggle_connection)
        layout.addWidget(self.connect_switch)

        self.role_pills = QtWidgets.QWidget(page)
        self.role_pills.setObjectName("role_pills")
        role_layout = QtWidgets.QHBoxLayout(self.role_pills)
        role_layout.setContentsMargins(0, 0, 0, 0)
        role_layout.setSpacing(6)
        self.role_listener = QtWidgets.QPushButton("Listener", self.role_pills)
        self.role_listener.setObjectName("role_listener")
        self.role_listener.setCheckable(True)
        self.role_listener.clicked.connect(self._choose_listener)
        self.role_controller = QtWidgets.QPushButton("Controller", self.role_pills)
        self.role_controller.setObjectName("role_controller")
        self.role_controller.setCheckable(True)
        self.role_controller.clicked.connect(self._choose_controller)
        role_layout.addWidget(self.role_listener)
        role_layout.addWidget(self.role_controller)
        layout.addWidget(self.role_pills)

        self.address_strip = QtWidgets.QLabel("", page)
        self.address_strip.setObjectName("address_strip")
        self.address_strip.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(self.address_strip)

        self.detail_rows = QtWidgets.QWidget(page)
        self.detail_rows.setObjectName("detail_rows")
        detail_layout = QtWidgets.QFormLayout(self.detail_rows)
        self.detail_role = QtWidgets.QLabel("", self.detail_rows)
        self.detail_role.setObjectName("detail_role")
        self.detail_mode = QtWidgets.QLabel("", self.detail_rows)
        self.detail_mode.setObjectName("detail_mode")
        self.detail_screens = QtWidgets.QLabel("", self.detail_rows)
        self.detail_screens.setObjectName("detail_screens")
        detail_layout.addRow("Role", self.detail_role)
        detail_layout.addRow("Control", self.detail_mode)
        detail_layout.addRow("Screens", self.detail_screens)
        layout.addWidget(self.detail_rows)

        self.handoff_button = QtWidgets.QPushButton("Hand off", page)
        self.handoff_button.setObjectName("handoff_button")
        self.handoff_button.clicked.connect(self.app.handoff)
        layout.addWidget(self.handoff_button)
        layout.addStretch(1)

        self.settings_button = QtWidgets.QPushButton("Settings", page)
        self.settings_button.setObjectName("settings_button")
        self.settings_button.clicked.connect(self.open_settings)
        layout.addWidget(self.settings_button)
        return page

    def _build_settings_sheet(self) -> QtWidgets.QWidget:
        sheet = QtWidgets.QWidget(self.pages)
        sheet.setObjectName("settings_sheet")
        layout = QtWidgets.QVBoxLayout(sheet)
        layout.setContentsMargins(18, 14, 18, 18)
        layout.setSpacing(12)

        back = QtWidgets.QPushButton("‹ Back", sheet)
        back.setObjectName("settings_back")
        back.clicked.connect(self.close_settings)
        layout.addWidget(back)

        tabs = QtWidgets.QTabWidget(sheet)
        tabs.setObjectName("settings_tabs")
        layout.addWidget(tabs)

        config_page = QtWidgets.QWidget(tabs)
        config_page.setObjectName("tab_config")
        form = QtWidgets.QFormLayout(config_page)

        self.secret_field = QtWidgets.QLineEdit(config_page)
        self.secret_field.setObjectName("secret_field")
        self.secret_field.setEchoMode(QtWidgets.QLineEdit.Password)
        secret_row = QtWidgets.QHBoxLayout()
        secret_row.addWidget(self.secret_field)
        self.reveal_secret = QtWidgets.QPushButton("View", config_page)
        self.reveal_secret.setObjectName("reveal_secret")
        self.reveal_secret.setCheckable(True)
        self.reveal_secret.toggled.connect(self._toggle_secret_echo)
        secret_row.addWidget(self.reveal_secret)
        self.copy_secret = QtWidgets.QPushButton("Copy", config_page)
        self.copy_secret.setObjectName("copy_secret")
        self.copy_secret.clicked.connect(self._copy_secret)
        secret_row.addWidget(self.copy_secret)
        form.addRow("Secret", secret_row)

        self.peer_ip_field = QtWidgets.QLineEdit(config_page)
        self.peer_ip_field.setObjectName("peer_ip_field")
        form.addRow("Peer IP", self.peer_ip_field)

        self.port_field = QtWidgets.QLineEdit(config_page)
        self.port_field.setObjectName("port_field")
        form.addRow("Port", self.port_field)

        self.edge_field = QtWidgets.QComboBox(config_page)
        self.edge_field.setObjectName("edge_field")
        self.edge_field.addItems(["right", "left", "top", "bottom"])
        form.addRow("Edge", self.edge_field)

        self.clipboard_toggle = QtWidgets.QCheckBox("Sync clipboard", config_page)
        self.clipboard_toggle.setObjectName("clipboard_toggle")
        form.addRow(self.clipboard_toggle)

        self.primary_toggle = QtWidgets.QCheckBox("Physical mouse on this machine", config_page)
        self.primary_toggle.setObjectName("primary_toggle")
        form.addRow(self.primary_toggle)

        self.autostart_toggle = QtWidgets.QCheckBox("Connect on startup", config_page)
        self.autostart_toggle.setObjectName("autostart_toggle")
        form.addRow(self.autostart_toggle)

        self.debug_toggle = QtWidgets.QCheckBox("Debug logging", config_page)
        self.debug_toggle.setObjectName("debug_toggle")
        self.debug_toggle.toggled.connect(self.app.set_debug)
        form.addRow(self.debug_toggle)

        self.config_error = QtWidgets.QLabel("", config_page)
        self.config_error.setObjectName("config_error")
        self.config_error.setStyleSheet("color: #f2686f;")
        form.addRow(self.config_error)

        self.save_button = QtWidgets.QPushButton("Save & reconnect", config_page)
        self.save_button.setObjectName("save_button")
        self.save_button.clicked.connect(self._save_config)
        form.addRow(self.save_button)
        tabs.addTab(config_page, "Configuration")

        log_page = QtWidgets.QWidget(tabs)
        log_page.setObjectName("tab_log")
        log_layout = QtWidgets.QVBoxLayout(log_page)
        self.log_view = QtWidgets.QTextEdit(log_page)
        self.log_view.setObjectName("log_view")
        self.log_view.setReadOnly(True)
        log_layout.addWidget(self.log_view)
        tabs.addTab(log_page, "Event log")
        return sheet

    def _toggle_connection(self) -> None:
        status = self.app.status()
        if status.get("connected") or status.get("connecting"):
            self.app.disconnect()
        else:
            self.app.reconnect()

    def _choose_listener(self) -> None:
        self.app.save_config({"peer_ip": None})

    def _choose_controller(self) -> None:
        if not self.app.config.to_dict().get("peer_ip"):
            self.open_settings()
            self.peer_ip_field.setFocus()
        else:
            self.refresh()

    def open_settings(self) -> None:
        config = self.app.config.to_dict()
        self.secret_field.setText(str(config.get("secret", "")))
        self.peer_ip_field.setText(str(config.get("peer_ip") or ""))
        self.port_field.setText(str(config.get("port", 52800)))
        self.edge_field.setCurrentText(str(config.get("edge", "right")))
        self.clipboard_toggle.setChecked(bool(config.get("clipboard", True)))
        self.primary_toggle.setChecked(bool(config.get("primary", True)))
        self.autostart_toggle.setChecked(bool(config.get("auto_start", False)))
        self.debug_toggle.blockSignals(True)
        self.debug_toggle.setChecked(bool(config.get("debug", False)))
        self.debug_toggle.blockSignals(False)
        self._update_log()
        self.pages.setCurrentWidget(self.findChild(QtWidgets.QWidget, "settings_sheet"))

    def close_settings(self) -> None:
        self.pages.setCurrentWidget(self.findChild(QtWidgets.QWidget, "status_page"))

    def _toggle_secret_echo(self, checked: bool) -> None:
        self.secret_field.setEchoMode(
            QtWidgets.QLineEdit.Normal if checked else QtWidgets.QLineEdit.Password
        )
        self.reveal_secret.setText("Hide" if checked else "View")

    def _copy_secret(self) -> None:
        QtGui.QGuiApplication.clipboard().setText(self.secret_field.text())

    def _save_config(self) -> None:
        self.config_error.setText("")
        try:
            port = int(self.port_field.text())
        except ValueError:
            self.config_error.setText("Port must be a number")
            return
        data = {
            "secret": self.secret_field.text(),
            "peer_ip": self.peer_ip_field.text().strip() or None,
            "port": port,
            "edge": self.edge_field.currentText(),
            "clipboard": self.clipboard_toggle.isChecked(),
            "primary": self.primary_toggle.isChecked(),
            "auto_start": self.autostart_toggle.isChecked(),
        }
        if not data["secret"]:
            self.config_error.setText("Secret is required")
            return
        if not 1 <= port <= 65535:
            self.config_error.setText("Port must be between 1 and 65535")
            return
        if data["edge"] not in EDGES:
            self.config_error.setText("Invalid edge")
            return
        try:
            self.app.save_config(data)
        except (OSError, ValueError):
            self.config_error.setText("Could not save configuration")
            return
        self.close_settings()

    def _update_log(self) -> None:
        self.log_view.setPlainText("\n".join(self.app.log_lines()))

    def refresh(self) -> None:
        status = self.app.status()
        connected = bool(status.get("connected"))
        connecting = bool(status.get("connecting"))
        paused = bool(status.get("paused"))
        role = status.get("role", "listener")
        if role == "connector":
            role = "controller"

        if connected:
            self.link_text.setText("Connected")
            self.connect_switch.setText("Disconnect")
        elif connecting and not paused:
            self.link_text.setText("Connecting")
            self.connect_switch.setText("Disconnect")
        else:
            self.link_text.setText("Disconnected")
            self.connect_switch.setText("Connect")

        self.role_listener.setChecked(role == "listener")
        self.role_controller.setChecked(role == "controller")
        self.role_listener.setEnabled(not connected)
        self.role_controller.setEnabled(not connected)

        address = ""
        if role == "listener":
            address = f"Listening on {status.get('local_ip', '')}:{status.get('port', '')}"
        self.address_strip.setText(address)
        self.address_strip.setVisible(bool(address))

        self.detail_rows.setVisible(connected)
        if connected:
            self.detail_role.setText(str(role))
            self.detail_mode.setText(str(status.get("mode", "idle")))
            local = "×".join(str(part) for part in status.get("local_screen", []))
            peer = "×".join(str(part) for part in status.get("peer_screen", []))
            self.detail_screens.setText(f"{local} → {peer}")

        self.handoff_button.setEnabled(status.get("mode") == "controlling")
        if self.tray_toggle is not None:
            self.tray_toggle.setText("Disconnect" if connected else "Connect")
        if self.pages.currentWidget() is self.findChild(QtWidgets.QWidget, "settings_sheet"):
            self._update_log()


class NativeUI:
    @staticmethod
    def start(app) -> int:
        qt_app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        app.start_background()
        window = NativeWindow(app)
        window.refresh()
        window.show()
        timer = QtCore.QTimer(window)
        timer.timeout.connect(window.refresh)
        timer.start(250)
        result = qt_app.exec()
        app.stop()
        return result
