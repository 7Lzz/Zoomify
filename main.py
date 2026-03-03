import sys
import ctypes
import time
import json
import os
from pathlib import Path

if sys.platform == 'win32':
    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
    os.environ["QT_SCALE_FACTOR_ROUNDING_POLICY"] = "PassThrough"

import cv2
import dxcam
import numpy as np
from pynput import keyboard, mouse
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QPushButton, QComboBox, 
                             QDoubleSpinBox, QSystemTrayIcon, QMenu, QFrame,
                             QCheckBox, QSpinBox, QScrollArea)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject, QEvent
from PyQt6.QtGui import (QIcon, QPixmap, QImage, QPainter, QPainterPath, 
                        QColor, QAction, QFont, QPen)


# Win32 constants
if sys.platform == 'win32':
    WDA_EXCLUDEFROMCAPTURE = 0x00000011
    GWL_EXSTYLE = -20
    WS_EX_TRANSPARENT = 0x00000020
    WS_EX_NOACTIVATE = 0x08000000

# CV2 interpolation mapping
CV2_INTERPOLATION = {
    "nearest": cv2.INTER_NEAREST,
    "bilinear": cv2.INTER_LINEAR,
    "bicubic": cv2.INTER_CUBIC
}


class ConfigManager:
    def __init__(self):
        self.config_dir = Path("C:/Seven's Scripts/Zoomify")
        self.config_file = self.config_dir / "config.json"
        self.defaults = {
            "toggle_key": "f1",
            "zoom_level": 2.5,
            "min_zoom": 1.5,
            "max_zoom": 8.0,
            "zoom_step": 0.25,
            "window_size": 350,
            "quality": "bicubic",
            "update_ms": 10.00,
            "scroll_zoom_enabled": False,
            "mode": "toggle",
            "zoom_in_key": "=",
            "zoom_out_key": "-",
            "spyglass_enabled": True,
            "spyglass_size_pct": 65,
            "spyglass_vignette": True,
            "smooth_zoom": True,
            "smooth_zoom_speed": 0.15,
            "follow_cursor": False,
        }
        self.config = self.load_config()
    
    def load_config(self):
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    loaded = json.load(f)
                    merged = {**self.defaults, **loaded}
                    for old_key in ["capture_visible", "crosshair_enabled", 
                                    "crosshair_color", "crosshair_size",
                                    "crosshair_thickness", "spyglass_key"]:
                        merged.pop(old_key, None)
                    return merged
            else:
                self.config_dir.mkdir(parents=True, exist_ok=True)
                with open(self.config_file, 'w') as f:
                    json.dump(self.defaults, f, indent=4)
                print(f"Created default config at {self.config_file}")
                return self.defaults.copy()
        except Exception as e:
            print(f"Config load error: {e}")
            return self.defaults.copy()
    
    def save_config(self):
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            print(f"Failed to save config: {e}")
    
    def get(self, key):
        return self.config.get(key, self.defaults.get(key))
    
    def set(self, key, value):
        self.config[key] = value
        self.save_config()


class IconHandler:
    def __init__(self, icon_path=None):
        self.icon_path = icon_path
        self.resolved_path = self._get_path()
        
    def _get_path(self):
        try:
            if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
                base_path = sys._MEIPASS
            else:
                base_path = os.path.dirname(os.path.abspath(__file__))
            if self.icon_path:
                path = os.path.join(base_path, self.icon_path)
                if os.path.isfile(path):
                    return path
            return None
        except:
            return None
    
    def get_qicon(self):
        if self.resolved_path and os.path.isfile(self.resolved_path):
            return QIcon(self.resolved_path)
        pixmap = QPixmap(64, 64)
        pixmap.fill(QColor(45, 45, 45))
        painter = QPainter(pixmap)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 120, 212))
        painter.drawEllipse(16, 16, 32, 32)
        painter.end()
        return QIcon(pixmap)


class KeyCaptureButton(QPushButton):
    key_captured = pyqtSignal(str)
    
    def __init__(self, initial_key=""):
        super().__init__()
        self.current_key = initial_key
        self.is_capturing = False
        self.setFixedHeight(32)
        self.setMinimumWidth(100)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFont(QFont("Segoe UI", 9))
        self.update_display()
        
    def update_display(self):
        if self.is_capturing:
            self.setText("Press any key...")
            self.setStyleSheet("""
                QPushButton {
                    background-color: #0078d4; color: white;
                    border: 1px solid #005a9e; border-radius: 4px;
                    padding: 6px 12px; text-align: center;
                }
            """)
        else:
            self.setText(self.current_key.upper() if self.current_key else "Click to set")
            self.setStyleSheet("""
                QPushButton {
                    background-color: #2d2d2d; color: #ffffff;
                    border: 1px solid #3d3d3d; border-radius: 4px;
                    padding: 6px 12px; text-align: center;
                }
                QPushButton:hover { background-color: #333333; border: 1px solid #0078d4; }
            """)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_capturing = True
            self.update_display()
    
    def keyPressEvent(self, event):
        if self.is_capturing:
            key = event.key()
            key_map = {
                Qt.Key.Key_F1: "f1", Qt.Key.Key_F2: "f2", Qt.Key.Key_F3: "f3",
                Qt.Key.Key_F4: "f4", Qt.Key.Key_F5: "f5", Qt.Key.Key_F6: "f6",
                Qt.Key.Key_F7: "f7", Qt.Key.Key_F8: "f8", Qt.Key.Key_F9: "f9",
                Qt.Key.Key_F10: "f10", Qt.Key.Key_F11: "f11", Qt.Key.Key_F12: "f12",
                Qt.Key.Key_Space: "space", Qt.Key.Key_Tab: "tab",
                Qt.Key.Key_CapsLock: "caps_lock", Qt.Key.Key_Shift: "shift",
                Qt.Key.Key_Control: "ctrl", Qt.Key.Key_Alt: "alt",
            }
            key_str = key_map.get(key, event.text().lower())
            if key_str:
                self.current_key = key_str
                self.key_captured.emit(key_str)
            self.is_capturing = False
            self.update_display()
            self.clearFocus()


# ─── Settings Window ────────────────────────────────────────────────────────────

class SettingsCanvas(QMainWindow):
    settings_changed = pyqtSignal(dict)
    close_application = pyqtSignal()
    
    def __init__(self, config_manager, icon_handler):
        super().__init__()
        self.config = config_manager
        self.icon_handler = icon_handler
        self.offset = None
        
        self.setWindowTitle("Zoomify Settings")
        self.setFixedSize(480, 720)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        
        if self.icon_handler.resolved_path:
            self.setWindowIcon(self.icon_handler.get_qicon())
        
        if sys.platform == 'win32':
            try:
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Zoomify.Settings")
            except:
                pass
        
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet("QMainWindow { background-color: transparent; }")
        self.init_ui()
    
    def showEvent(self, event):
        super().showEvent(event)
        screen = QApplication.primaryScreen()
        if screen:
            sg = screen.availableGeometry()
            self.move(sg.x() + (sg.width() - self.width()) // 2,
                      sg.y() + (sg.height() - self.height()) // 2)
        self.original_config = self.get_current_settings()
        self.settings_applied = False

    def get_current_settings(self):
        quality_map = {0: "nearest", 1: "bilinear", 2: "bicubic"}
        return {
            "toggle_key": self.toggle_key_input.current_key or "f1",
            "zoom_in_key": self.zoom_in_key_input.current_key or "=",
            "zoom_out_key": self.zoom_out_key_input.current_key or "-",
            "zoom_level": self.zoom_level_input.value(),
            "zoom_step": self.zoom_step_input.value(),
            "window_size": self.window_size_input.value(),
            "update_ms": self.update_ms_input.value(),
            "quality": quality_map[self.quality_input.currentIndex()],
            "mode": self.mode_input.currentText().lower(),
            "scroll_zoom_enabled": self.scroll_zoom_enabled_input.isChecked(),
            "min_zoom": self.config.get("min_zoom"),
            "max_zoom": self.config.get("max_zoom"),
            "spyglass_enabled": self.spyglass_enabled_input.isChecked(),
            "spyglass_size_pct": self.spyglass_size_pct_input.value(),
            "spyglass_vignette": self.spyglass_vignette_input.isChecked(),
            "smooth_zoom": self.smooth_zoom_input.isChecked(),
            "smooth_zoom_speed": self.smooth_zoom_speed_input.value(),
            "follow_cursor": self.follow_cursor_input.isChecked(),
        }
    
    def update_live_settings(self):
        self.settings_changed.emit(self.get_current_settings())
    
    def minimize_window(self):
        if not self.settings_applied and self.original_config:
            self.settings_changed.emit(self.original_config)
        self.hide()

    def paintEvent(self, event):
        OW = 0.75
        CR = 10
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        h = OW / 2
        path = QPainterPath()
        path.addRoundedRect(h, h, self.width() - OW, self.height() - OW, CR - h, CR - h)
        painter.fillPath(path, QColor(24, 24, 24))
        painter.setPen(QPen(QColor(70, 70, 70), OW))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)
        painter.end()

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        central.setStyleSheet("background-color: transparent;")
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(1, 1, 1, 1)
        main_layout.setSpacing(0)
        
        # ── Title Bar ──
        title_bar = QWidget()
        title_bar.setFixedHeight(44)
        title_bar.setStyleSheet("background-color: #202020; border-top-left-radius: 10px; border-top-right-radius: 10px;")
        tl = QHBoxLayout(title_bar)
        tl.setContentsMargins(16, 0, 8, 0)
        
        if self.icon_handler.resolved_path:
            il = QLabel()
            il.setPixmap(QPixmap(self.icon_handler.resolved_path).scaled(
                20, 20, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            il.setFixedSize(20, 20)
            il.setStyleSheet("background: transparent;")
            tl.addWidget(il)
            tl.addSpacing(8)

        title = QLabel("Zoomify Settings")
        title.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
        title.setStyleSheet("color: white; background: transparent;")
        tl.addWidget(title)
        tl.addStretch()
        
        for txt, fs, slot, hc in [("─", 16, self.minimize_window, "#2d2d2d"), ("×", 18, self.close_application.emit, "#e81123")]:
            b = QPushButton(txt)
            b.setFixedSize(40, 32)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(f"QPushButton {{ background-color: transparent; color: #cccccc; border: none; font-size: {fs}px; border-radius: 4px; }} QPushButton:hover {{ background-color: {hc}; color: white; }}")
            b.clicked.connect(slot)
            tl.addWidget(b)
        
        main_layout.addWidget(title_bar)
        sep = QFrame(); sep.setFixedHeight(1); sep.setStyleSheet("background-color: #2d2d2d;")
        main_layout.addWidget(sep)
        
        # ── Scroll Area ──
        sa = QScrollArea()
        sa.setWidgetResizable(True)
        sa.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        sa.setStyleSheet("""
            QScrollArea { background-color: #181818; border: none; border-bottom-left-radius: 10px; border-bottom-right-radius: 10px; }
            QScrollBar:vertical { background-color: #181818; width: 8px; }
            QScrollBar::handle:vertical { background-color: #3d3d3d; min-height: 30px; border-radius: 4px; }
            QScrollBar::handle:vertical:hover { background-color: #555555; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
        """)
        
        content = QWidget()
        content.setStyleSheet("background-color: #181818;")
        L = QVBoxLayout(content)
        L.setContentsMargins(24, 24, 24, 30)
        L.setSpacing(18)
        
        # ===== KEYBINDS =====
        L.addWidget(self._sec("Keybinds")); L.addSpacing(-8)
        g = self._grp()
        g.layout().addWidget(self.create_keybind_row("Toggle Zoom", "toggle_key"))
        g.layout().addWidget(self.create_keybind_row("Zoom In", "zoom_in_key"))
        g.layout().addWidget(self.create_keybind_row("Zoom Out", "zoom_out_key"))
        L.addWidget(g)
        
        # ===== ZOOM SETTINGS =====
        L.addWidget(self._sec("Zoom Settings")); L.addSpacing(-8)
        g = self._grp()
        g.layout().addWidget(self.create_slider_row("Default Zoom", "zoom_level", 1.5, 8.0, 0.1, "x"))
        g.layout().addWidget(self.create_slider_row("Zoom Step", "zoom_step", 0.1, 1.0, 0.05, "x"))
        g.layout().addWidget(self.create_slider_row("Window Size", "window_size", 100, 600, 10, "px", is_int=True))
        g.layout().addWidget(self.create_slider_row("Update Speed", "update_ms", 0.1, 100, 0.1, "ms"))
        g.layout().addWidget(self.create_quality_row())
        L.addWidget(g)
        
        # ===== BEHAVIOR =====
        L.addWidget(self._sec("Behavior")); L.addSpacing(-8)
        g = self._grp()
        g.layout().addWidget(self.create_mode_row())
        g.layout().addWidget(self.create_checkbox_row("Enable scroll wheel zoom", "scroll_zoom_enabled"))
        g.layout().addWidget(self.create_checkbox_row("Follow mouse cursor", "follow_cursor"))
        L.addWidget(g)
        
        # ===== SPYGLASS =====
        L.addWidget(self._sec("Spyglass Mode")); L.addSpacing(-8)
        d = QLabel("Replaces the small zoom window with a large\noverlay covering the center of your screen.\nUses the same toggle key.")
        d.setFont(QFont("Segoe UI", 8)); d.setStyleSheet("color: #888888; background: transparent;")
        L.addWidget(d); L.addSpacing(-6)
        g = self._grp()
        g.layout().addWidget(self.create_checkbox_row("Enable spyglass mode", "spyglass_enabled"))
        g.layout().addWidget(self.create_slider_row("Spyglass Size", "spyglass_size_pct", 30, 95, 5, "%", is_int=True))
        g.layout().addWidget(self.create_checkbox_row("Vignette edge fade", "spyglass_vignette"))
        L.addWidget(g)
        
        # ===== SMOOTH ZOOM =====
        L.addWidget(self._sec("Smooth Zoom")); L.addSpacing(-8)
        g = self._grp()
        g.layout().addWidget(self.create_checkbox_row("Enable smooth zoom transitions", "smooth_zoom"))
        g.layout().addWidget(self.create_slider_row("Smoothing Speed", "smooth_zoom_speed", 0.05, 0.5, 0.01, ""))
        L.addWidget(g)
        
        # ── Connect Signals ──
        for w in ["toggle_key_input", "zoom_in_key_input", "zoom_out_key_input"]:
            getattr(self, w).key_captured.connect(lambda: self.update_live_settings())
        for w in ["zoom_level_input", "zoom_step_input", "window_size_input", "update_ms_input", "spyglass_size_pct_input", "smooth_zoom_speed_input"]:
            getattr(self, w).valueChanged.connect(self.update_live_settings)
        for w in ["quality_input", "mode_input"]:
            getattr(self, w).currentIndexChanged.connect(self.update_live_settings)
        for w in ["scroll_zoom_enabled_input", "follow_cursor_input", "spyglass_enabled_input", "spyglass_vignette_input", "smooth_zoom_input"]:
            getattr(self, w).stateChanged.connect(self.update_live_settings)
        
        L.addStretch()
        
        save = QPushButton("Apply Settings")
        save.setFixedHeight(40)
        save.setCursor(Qt.CursorShape.PointingHandCursor)
        save.setFont(QFont("Segoe UI", 10))
        save.setStyleSheet("QPushButton { background-color: #0078d4; color: white; border: none; border-radius: 4px; } QPushButton:hover { background-color: #106ebe; } QPushButton:pressed { background-color: #005a9e; }")
        save.clicked.connect(self.apply_settings)
        L.addWidget(save)
        
        sa.setWidget(content)
        main_layout.addWidget(sa)
        
        title_bar.mousePressEvent = self.title_mouse_press
        title_bar.mouseMoveEvent = self.title_mouse_move
        title_bar.mouseReleaseEvent = self.title_mouse_release
        title.mousePressEvent = self.title_mouse_press
        title.mouseMoveEvent = self.title_mouse_move
    
    # ── UI Helpers ──
    def _sec(self, t):
        l = QLabel(t); l.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
        l.setStyleSheet("color: #ffffff; background: transparent;"); l.setFixedHeight(24); return l
    
    def _grp(self):
        w = QWidget(); v = QVBoxLayout(w); v.setContentsMargins(0,0,0,0); v.setSpacing(12); return w
    
    def _combo_css(self):
        return """
            QComboBox { background-color: #2d2d2d; color: white; border: 1px solid #3d3d3d; border-radius: 4px; padding: 4px 8px; }
            QComboBox:focus { border: 1px solid #0078d4; }
            QComboBox::drop-down { border: none; width: 0px; }
            QComboBox QAbstractItemView { background-color: #2d2d2d; color: white; selection-background-color: #0078d4; border: 1px solid #3d3d3d; border-radius: 4px; outline: none; }
        """
    
    def create_keybind_row(self, label_text, config_key):
        row = QWidget(); row.setFixedHeight(40); row.setStyleSheet("background: transparent;")
        lo = QHBoxLayout(row); lo.setContentsMargins(0,0,0,0); lo.setSpacing(16)
        la = QLabel(label_text); la.setFont(QFont("Segoe UI", 9)); la.setStyleSheet("color: #cccccc; background: transparent;")
        btn = KeyCaptureButton(self.config.get(config_key)); btn.setFixedWidth(145)
        setattr(self, f"{config_key}_input", btn)
        lo.addWidget(la); lo.addStretch(); lo.addWidget(btn)
        return row
    
    def create_slider_row(self, label_text, config_key, min_val, max_val, step, suffix="", is_int=False):
        row = QWidget(); row.setFixedHeight(40); row.setStyleSheet("background: transparent;")
        lo = QHBoxLayout(row); lo.setContentsMargins(0,0,0,0); lo.setSpacing(16)
        la = QLabel(label_text); la.setFont(QFont("Segoe UI", 9)); la.setStyleSheet("color: #cccccc; background: transparent;")
        if is_int:
            sb = QSpinBox(); sb.setRange(int(min_val), int(max_val)); sb.setSingleStep(int(step)); sb.setValue(int(self.config.get(config_key)))
        else:
            sb = QDoubleSpinBox(); sb.setRange(min_val, max_val); sb.setSingleStep(step); sb.setValue(self.config.get(config_key))
        sb.setSuffix(suffix); sb.setFixedWidth(145); sb.setFixedHeight(32); sb.setFont(QFont("Segoe UI", 9))
        sb.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        sb.setStyleSheet("QSpinBox, QDoubleSpinBox { background-color: #2d2d2d; color: white; border: 1px solid #3d3d3d; border-radius: 4px; padding: 4px 12px; } QSpinBox:focus, QDoubleSpinBox:focus { border: 1px solid #0078d4; }")
        setattr(self, f"{config_key}_input", sb)
        lo.addWidget(la); lo.addStretch(); lo.addWidget(sb)
        return row
    
    def create_quality_row(self):
        row = QWidget(); row.setFixedHeight(40); row.setStyleSheet("background: transparent;")
        lo = QHBoxLayout(row); lo.setContentsMargins(0,0,0,0); lo.setSpacing(16)
        la = QLabel("Zoom Quality"); la.setFont(QFont("Segoe UI", 9)); la.setStyleSheet("color: #cccccc; background: transparent;")
        c = QComboBox(); c.addItems(["Nearest (Fastest)", "Bilinear", "Bicubic (Best)"])
        c.setCurrentIndex({"nearest": 0, "bilinear": 1, "bicubic": 2}.get(self.config.get("quality"), 0))
        c.setFixedWidth(145); c.setFixedHeight(32); c.setCursor(Qt.CursorShape.PointingHandCursor)
        c.setFont(QFont("Segoe UI", 9)); c.setStyleSheet(self._combo_css())
        self.quality_input = c
        lo.addWidget(la); lo.addStretch(); lo.addWidget(c)
        return row

    def create_mode_row(self):
        row = QWidget(); row.setFixedHeight(40); row.setStyleSheet("background: transparent;")
        lo = QHBoxLayout(row); lo.setContentsMargins(0,0,0,0); lo.setSpacing(16)
        la = QLabel("Zoom Mode"); la.setFont(QFont("Segoe UI", 9)); la.setStyleSheet("color: #cccccc; background: transparent;")
        c = QComboBox(); c.addItems(["Toggle", "Hold"]); c.setCurrentText(self.config.get("mode").capitalize())
        c.setFixedWidth(145); c.setFixedHeight(32); c.setCursor(Qt.CursorShape.PointingHandCursor)
        c.setFont(QFont("Segoe UI", 9)); c.setStyleSheet(self._combo_css())
        self.mode_input = c
        lo.addWidget(la); lo.addStretch(); lo.addWidget(c)
        return row
    
    def create_checkbox_row(self, label_text, config_key):
        row = QWidget(); row.setFixedHeight(32)
        rl = QHBoxLayout(row); rl.setContentsMargins(0,0,0,0)
        cb = QCheckBox(label_text); cb.setChecked(self.config.get(config_key))
        cb.setCursor(Qt.CursorShape.PointingHandCursor); cb.setFont(QFont("Segoe UI", 9))
        cb.setStyleSheet("""
            QCheckBox { color: #cccccc; background: transparent; spacing: 8px; }
            QCheckBox::indicator { width: 18px; height: 18px; border-radius: 3px; border: 1px solid #3d3d3d; background-color: #2d2d2d; }
            QCheckBox::indicator:hover { border: 1px solid #0078d4; }
            QCheckBox::indicator:checked { background-color: #0078d4; border: 1px solid #0078d4; }
        """)
        setattr(self, f"{config_key}_input", cb)
        rl.addWidget(cb)
        return row
    
    def apply_settings(self):
        nc = self.get_current_settings()
        for k, v in nc.items(): self.config.set(k, v)
        self.settings_changed.emit(nc)
        self.settings_applied = True
        self.hide()
    
    def title_mouse_press(self, e):
        if e.button() == Qt.MouseButton.LeftButton: self.offset = e.globalPosition().toPoint() - self.pos()
    def title_mouse_move(self, e):
        if self.offset and e.buttons() == Qt.MouseButton.LeftButton: self.move(e.globalPosition().toPoint() - self.offset)
    def title_mouse_release(self, e):
        self.offset = None


# ─── Key Events ──────────────────────────────────────────────────────────────────

class KeyEvent(QEvent):
    TOGGLE   = QEvent.Type(QEvent.Type.User + 1)
    SHOW     = QEvent.Type(QEvent.Type.User + 2)
    HIDE     = QEvent.Type(QEvent.Type.User + 3)
    ZOOM_IN  = QEvent.Type(QEvent.Type.User + 4)
    ZOOM_OUT = QEvent.Type(QEvent.Type.User + 5)
    
    def __init__(self, action):
        super().__init__(action)
        self.action = action


# ─── Core Zoom Engine ────────────────────────────────────────────────────────────

class ScreenZoom(QObject):
    def __init__(self, config_manager):
        super().__init__()
        self.config = config_manager
        
        self.toggle_key = self.config.get("toggle_key")
        self.zoom_in_key = self.config.get("zoom_in_key")
        self.zoom_out_key = self.config.get("zoom_out_key")
        self.zoom_level = self.config.get("zoom_level")
        self.min_zoom = self.config.get("min_zoom")
        self.max_zoom = self.config.get("max_zoom")
        self.zoom_step = self.config.get("zoom_step")
        self.window_size = self.config.get("window_size")
        self.update_ms = self.config.get("update_ms")
        self.scroll_enabled = self.config.get("scroll_zoom_enabled")
        self.mode = self.config.get("mode")
        self.quality = self.config.get("quality")
        self.spyglass_enabled = self.config.get("spyglass_enabled")
        self.spyglass_size_pct = self.config.get("spyglass_size_pct")
        self.spyglass_vignette = self.config.get("spyglass_vignette")
        self.smooth_zoom = self.config.get("smooth_zoom")
        self.smooth_zoom_speed = self.config.get("smooth_zoom_speed")
        self.follow_cursor = self.config.get("follow_cursor")
        
        # Smooth zoom
        self.target_zoom = self.zoom_level
        self.current_zoom = self.zoom_level
        
        self.visible = False
        self.running = True
        self.key_pressed = False
        self.mouse_x = 0
        self.mouse_y = 0
        
        # dxcam
        self.camera = dxcam.create(output_idx=0, output_color="RGB")
        if self.camera:
            self.screen_width, self.screen_height = self.camera.width, self.camera.height
        else:
            self.screen_width, self.screen_height = 1920, 1080
        self.center_x = self.screen_width // 2
        self.center_y = self.screen_height // 2
        self.mouse_x = self.center_x
        self.mouse_y = self.center_y
        
        self.app = QApplication.instance() or QApplication(sys.argv)
        
        self.spyglass_px = int(min(self.screen_width, self.screen_height) * (self.spyglass_size_pct / 100.0))
        
        self.window = self._make_overlay()
        self._position_window(self.window, self._out_size())
        self.label = QLabel(self.window)
        self.label.setFixedSize(self._out_size(), self._out_size())
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        if sys.platform == 'win32':
            hwnd = int(self.window.winId())
            ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)
            self._make_passthrough(hwnd)
        
        self._vignette_alpha = None
        self._vignette_size = -1
        self._rgba_buf = None
        self._rebuild_vignette()
        
        self.timer = QTimer()
        self.timer.timeout.connect(self.update)
        self.last_scroll = 0
        
        self.setup_input()
    
    def _make_overlay(self):
        w = QWidget()
        w.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool | Qt.WindowType.WindowTransparentForInput |
            Qt.WindowType.BypassWindowManagerHint)
        w.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        w.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        w.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        w.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        w.setAttribute(Qt.WidgetAttribute.WA_PaintOnScreen)
        return w
    
    def _make_passthrough(self, hwnd):
        ex = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        ex |= WS_EX_TRANSPARENT | WS_EX_NOACTIVATE
        ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex)
    
    def _out_size(self):
        return self.spyglass_px if self.spyglass_enabled else self.window_size
    
    def _position_window(self, win, size):
        win.setFixedSize(size, size)
        win.move((self.screen_width - size) // 2, (self.screen_height - size) // 2)
    
    def _rebuild_vignette(self):
        if not self.spyglass_enabled or not self.spyglass_vignette:
            self._vignette_alpha = None
            return
        
        size = self.spyglass_px
        if size == self._vignette_size and self._vignette_alpha is not None:
            return
        
        center = size / 2.0
        max_r = center
        inner_r = max_r * 0.72
        
        y, x = np.ogrid[:size, :size]
        dist = np.sqrt((x - center) ** 2 + (y - center) ** 2).astype(np.float32)
        
        alpha = np.full((size, size), 255, dtype=np.uint8)
        transition = (dist > inner_r) & (dist < max_r)
        t = (dist[transition] - inner_r) / (max_r - inner_r)
        t_smooth = t * t * (3.0 - 2.0 * t)
        alpha[transition] = (255 * (1.0 - t_smooth)).astype(np.uint8)
        alpha[dist >= max_r] = 0
        
        self._vignette_alpha = alpha
        self._vignette_size = size
        self._rgba_buf = np.empty((size, size, 4), dtype=np.uint8)
    
    def setup_input(self):
        self.kb = keyboard.Listener(on_press=self.on_key_press, on_release=self.on_key_release)
        self.kb.start()
        self.ms = mouse.Listener(on_scroll=self.on_scroll, on_move=self.on_mouse_move)
        self.ms.start()
    
    def on_mouse_move(self, x, y):
        self.mouse_x = x
        self.mouse_y = y
    
    def normalize_key(self, key):
        if hasattr(key, 'char') and key.char:
            return key.char.lower()
        kmap = {
            keyboard.Key.f1: "f1", keyboard.Key.f2: "f2", keyboard.Key.f3: "f3",
            keyboard.Key.f4: "f4", keyboard.Key.f5: "f5", keyboard.Key.f6: "f6",
            keyboard.Key.f7: "f7", keyboard.Key.f8: "f8", keyboard.Key.f9: "f9",
            keyboard.Key.f10: "f10", keyboard.Key.f11: "f11", keyboard.Key.f12: "f12",
            keyboard.Key.space: "space", keyboard.Key.tab: "tab",
            keyboard.Key.caps_lock: "caps_lock", keyboard.Key.shift: "shift",
            keyboard.Key.ctrl: "ctrl", keyboard.Key.alt: "alt",
        }
        return kmap.get(key, None)
    
    def on_key_press(self, key):
        try:
            nk = self.normalize_key(key)
            if not nk: return
            if nk == self.toggle_key:
                if self.mode == "toggle":
                    self.app.postEvent(self, KeyEvent(KeyEvent.TOGGLE))
                elif self.mode == "hold" and not self.key_pressed:
                    self.key_pressed = True
                    self.app.postEvent(self, KeyEvent(KeyEvent.SHOW))
            elif nk in [self.zoom_in_key, '+', '=']:
                self.app.postEvent(self, KeyEvent(KeyEvent.ZOOM_IN))
            elif nk in [self.zoom_out_key, '-', '_']:
                self.app.postEvent(self, KeyEvent(KeyEvent.ZOOM_OUT))
            if hasattr(key, 'name') and key.name == 'esc':
                self.app.postEvent(self, KeyEvent(KeyEvent.HIDE))
        except Exception as e:
            print(f"Key error: {e}")
    
    def on_key_release(self, key):
        try:
            if self.mode == "hold":
                nk = self.normalize_key(key)
                if nk == self.toggle_key:
                    self.key_pressed = False
                    self.app.postEvent(self, KeyEvent(KeyEvent.HIDE))
        except:
            pass
    
    def on_scroll(self, x, y, dx, dy):
        if not self.visible or not self.scroll_enabled: return
        now = time.time()
        if now - self.last_scroll < 0.05: return
        self.last_scroll = now
        self.app.postEvent(self, KeyEvent(KeyEvent.ZOOM_IN if dy > 0 else KeyEvent.ZOOM_OUT))
    
    def event(self, event):
        if isinstance(event, KeyEvent):
            a = event.action
            if a == KeyEvent.TOGGLE: self.toggle()
            elif a == KeyEvent.SHOW: self.show_zoom()
            elif a == KeyEvent.HIDE: self.hide_zoom()
            elif a == KeyEvent.ZOOM_IN: self.set_zoom(self.zoom_step)
            elif a == KeyEvent.ZOOM_OUT: self.set_zoom(-self.zoom_step)
            return True
        return super().event(event)
    
    def set_zoom(self, delta):
        self.target_zoom = max(self.min_zoom, min(self.max_zoom, self.target_zoom + delta))
        if not self.smooth_zoom:
            self.zoom_level = self.target_zoom
            self.current_zoom = self.target_zoom
        print(f"Zoom: {self.target_zoom:.1f}x")
    
    def _lerp(self):
        if not self.smooth_zoom:
            self.current_zoom = self.target_zoom
        else:
            diff = self.target_zoom - self.current_zoom
            if abs(diff) < 0.005:
                self.current_zoom = self.target_zoom
            else:
                self.current_zoom += diff * self.smooth_zoom_speed
        self.zoom_level = self.current_zoom
    
    def update(self):
        if not self.visible or not self.running:
            return
        try:
            self._lerp()
            
            out = self._out_size()
            cap = max(10, int(out / self.zoom_level))
            
            cx = self.mouse_x if self.follow_cursor else self.center_x
            cy = self.mouse_y if self.follow_cursor else self.center_y
            
            left = max(0, cx - cap // 2)
            top = max(0, cy - cap // 2)
            right = left + cap
            bottom = top + cap
            
            if right > self.screen_width:
                right = self.screen_width; left = max(0, right - cap)
            if bottom > self.screen_height:
                bottom = self.screen_height; top = max(0, bottom - cap)
            
            frame = self.camera.grab(region=(left, top, right, bottom))
            if frame is None:
                return
            
            # Fast cv2 resize
            interp = CV2_INTERPOLATION.get(self.quality, cv2.INTER_CUBIC)
            resized = cv2.resize(frame, (out, out), interpolation=interp)
            
            # Vignette compositing
            use_vig = (self.spyglass_enabled and self.spyglass_vignette 
                      and self._vignette_alpha is not None)
            
            if use_vig:
                buf = self._rgba_buf
                if buf is None or buf.shape[0] != out:
                    buf = np.empty((out, out, 4), dtype=np.uint8)
                    self._rgba_buf = buf
                buf[:, :, :3] = resized
                buf[:, :, 3] = self._vignette_alpha
                qimg = QImage(buf.data, out, out, out * 4, QImage.Format.Format_RGBA8888)
            else:
                qimg = QImage(resized.data, out, out, out * 3, QImage.Format.Format_RGB888)
            
            self.label.setPixmap(QPixmap.fromImage(qimg))
                    
        except Exception as e:
            print(f"Update error: {e}")
    
    def show_zoom(self):
        if not self.visible:
            self.visible = True
            self.window.show()
            self.timer.start(int(self.update_ms))
            print(f"{'Spyglass' if self.spyglass_enabled else 'Zoom'}: ON")
    
    def hide_zoom(self):
        if self.visible:
            self.visible = False
            self.timer.stop()
            self.window.hide()
            print(f"{'Spyglass' if self.spyglass_enabled else 'Zoom'}: OFF")
    
    def toggle(self):
        self.hide_zoom() if self.visible else self.show_zoom()
    
    def _resize_window(self, size):
        self.window.setFixedSize(size, size)
        self.label.setFixedSize(size, size)
        self.window.move((self.screen_width - size) // 2, (self.screen_height - size) // 2)
    
    def update_settings(self, nc):
        self.toggle_key = nc["toggle_key"]
        self.zoom_in_key = nc["zoom_in_key"]
        self.zoom_out_key = nc["zoom_out_key"]
        self.zoom_level = nc["zoom_level"]
        self.target_zoom = nc["zoom_level"]
        self.current_zoom = nc["zoom_level"]
        self.zoom_step = nc["zoom_step"]
        self.scroll_enabled = nc["scroll_zoom_enabled"]
        self.mode = nc["mode"]
        self.quality = nc["quality"]
        self.smooth_zoom = nc.get("smooth_zoom", True)
        self.smooth_zoom_speed = nc.get("smooth_zoom_speed", 0.15)
        self.follow_cursor = nc.get("follow_cursor", False)
        
        old_ms = self.update_ms
        self.update_ms = nc["update_ms"]
        
        old_out = self._out_size()
        
        self.window_size = nc["window_size"]
        self.spyglass_enabled = nc.get("spyglass_enabled", False)
        self.spyglass_size_pct = nc.get("spyglass_size_pct", 65)
        self.spyglass_vignette = nc.get("spyglass_vignette", True)
        self.spyglass_px = int(min(self.screen_width, self.screen_height) * (self.spyglass_size_pct / 100.0))
        
        new_out = self._out_size()
        
        if old_out != new_out:
            self._resize_window(new_out)
        self._rebuild_vignette()
        
        if old_ms != self.update_ms and self.visible:
            self.timer.setInterval(int(self.update_ms))
        
        print("Settings updated")
    
    def quit(self):
        self.running = False
        self.kb.stop()
        self.ms.stop()
        self.timer.stop()
        if self.camera:
            del self.camera
        self.window.close()


# ─── Main ────────────────────────────────────────────────────────────────────────

def main():
    config_manager = ConfigManager()
    icon_handler = IconHandler("Icon/icon.ico")
    
    app = QApplication.instance() or QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    
    if sys.platform == 'win32':
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('sevens.zoomify.settings.1')
        except:
            pass
    
    zoom = ScreenZoom(config_manager)
    settings_window = SettingsCanvas(config_manager, icon_handler)
    settings_window.settings_changed.connect(zoom.update_settings)
    settings_window.close_application.connect(lambda: (zoom.quit(), app.quit()))
    
    tray_icon = QSystemTrayIcon(icon_handler.get_qicon(), app)
    tray_icon.setToolTip("Zoomify")
    
    tray_menu = QMenu()
    show_act = QAction("Settings", app); show_act.triggered.connect(settings_window.show); tray_menu.addAction(show_act)
    tray_menu.addSeparator()
    quit_act = QAction("Exit", app); quit_act.triggered.connect(lambda: (zoom.quit(), app.quit())); tray_menu.addAction(quit_act)
    
    tray_icon.setContextMenu(tray_menu)
    tray_icon.activated.connect(lambda r: settings_window.show() if r in [QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick] else None)
    tray_icon.show()
    
    spy = "ON" if config_manager.get("spyglass_enabled") else "OFF"
    
    print("=" * 50)
    print("Zoomify - Screen Zoom Tool")
    print("=" * 50)
    print(f"Toggle:       {config_manager.get('toggle_key').upper()}")
    print(f"Zoom In:      {config_manager.get('zoom_in_key').upper()}")
    print(f"Zoom Out:     {config_manager.get('zoom_out_key').upper()}")
    print(f"Spyglass:     {spy}")
    print(f"Follow Mouse: {'ON' if config_manager.get('follow_cursor') else 'OFF'}")
    print("=" * 50)
    print("Running in system tray")
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()