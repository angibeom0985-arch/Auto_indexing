# -*- coding: utf-8 -*-
"""Integrated auto indexing tool for Google and Naver."""

import json
import os
import re
import sqlite3
import sys
import time
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
from threading import Event
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from urllib.parse import unquote, urldefrag, urljoin, urlparse, urlsplit, urlunsplit

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
APP_BASE_DIR = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else SCRIPT_DIR
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)
if APP_BASE_DIR not in sys.path:
    sys.path.insert(0, APP_BASE_DIR)

SETTING_DIR = os.path.join(APP_BASE_DIR, "setting")
CONFIG_FILE = os.path.join(SETTING_DIR, "auto_indexing_config.json")
ENCRYPTED_CONFIG_FILE = os.path.join(SETTING_DIR, "auto_indexing_config.enc")
INDEXED_URLS_FILE = os.path.join(SETTING_DIR, "indexed_urls.json")
GOOGLE_QUOTA_FILE = os.path.join(SETTING_DIR, "google_quota.json")
NAVER_QUOTA_FILE = os.path.join(SETTING_DIR, "naver_quota.json")
URL_STATE_DB_FILE = os.path.join(SETTING_DIR, "indexing_state.db")
LOG_FILE = os.path.join(SETTING_DIR, "auto_indexing_log.txt")
KAKAO_CONTACT_URL = "https://open.kakao.com/me/david0985"


def _window_icon_source() -> str:
    if getattr(sys, "frozen", False):
        return sys.executable
    for p in [os.path.join(APP_BASE_DIR, "david153.ico"), os.path.join(SCRIPT_DIR, "david153.ico")]:
        if os.path.exists(p):
            return p
    return ""


def _apply_window_icon(widget: Any) -> None:
    try:
        src = _window_icon_source()
        if src and "QIcon" in globals():
            widget.setWindowIcon(QIcon(src))
    except Exception:
        pass


def _migrate_legacy_runtime_files() -> None:
    os.makedirs(SETTING_DIR, exist_ok=True)
    legacy_to_new = [
        (os.path.join(APP_BASE_DIR, "auto_indexing_config.json"), CONFIG_FILE),
        (os.path.join(APP_BASE_DIR, "auto_indexing_config.enc"), ENCRYPTED_CONFIG_FILE),
        (os.path.join(APP_BASE_DIR, "data", "indexed_urls.json"), INDEXED_URLS_FILE),
        (os.path.join(APP_BASE_DIR, "data", "google_quota.json"), GOOGLE_QUOTA_FILE),
        (os.path.join(APP_BASE_DIR, "data", "naver_quota.json"), NAVER_QUOTA_FILE),
        (os.path.join(APP_BASE_DIR, "data", "indexing_state.db"), URL_STATE_DB_FILE),
        (os.path.join(APP_BASE_DIR, "logs", "auto_indexing_log.txt"), LOG_FILE),
    ]
    for legacy, new in legacy_to_new:
        try:
            if os.path.exists(legacy) and not os.path.exists(new):
                os.replace(legacy, new)
        except Exception:
            pass


_migrate_legacy_runtime_files()


def show_unregistered_machine_dialog(machine_id: str) -> None:
    dlg = QDialog()
    dlg.setWindowTitle("프로그램 사용 권한")
    _apply_window_icon(dlg)
    dlg.setModal(True)
    dlg.setFixedSize(690, 560)
    dlg.setStyleSheet(
        """
        QDialog {
            background: #efefef;
        }
        QLabel#title {
            color: #e53935;
            font-size: 44px;
            font-weight: 800;
        }
        QLabel#icon {
            color: #f0a838;
            font-size: 54px;
        }
        QWidget#panel {
            background: #d5e5f3;
            border-radius: 16px;
        }
        QLabel#panelTitle {
            color: #1967c2;
            font-size: 24px;
            font-weight: 800;
        }
        QWidget#idCard {
            background: #f6fbff;
            border: 1px solid #9ec6ea;
            border-radius: 12px;
        }
        QLabel#idText {
            color: #1f1f1f;
            font-size: 18px;
            font-family: Consolas, "Courier New", monospace;
            font-weight: 500;
        }
        QLabel#note {
            color: #67717e;
            font-size: 14px;
        }
        QPushButton#copyBtn {
            background: #2a80d8;
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 700;
            padding: 8px 18px;
            min-width: 74px;
            min-height: 40px;
        }
        QPushButton#confirmBtn {
            background: #51b24e;
            color: white;
            border: none;
            border-radius: 10px;
            font-size: 34px;
            font-weight: 800;
            padding: 12px 30px;
            min-width: 150px;
            min-height: 70px;
        }
        """
    )

    root = QVBoxLayout(dlg)
    root.setContentsMargins(30, 24, 30, 30)
    root.setSpacing(16)

    title_row = QHBoxLayout()
    icon = QLabel("⚠")
    icon.setObjectName("icon")
    title_row.addWidget(icon, 0, Qt.AlignmentFlag.AlignVCenter)
    title = QLabel("등록되지 않은 사용자입니다.")
    title.setObjectName("title")
    title_row.addWidget(title, 1, Qt.AlignmentFlag.AlignVCenter)
    root.addLayout(title_row)

    panel = QWidget()
    panel.setObjectName("panel")
    panel_layout = QVBoxLayout(panel)
    panel_layout.setContentsMargins(12, 14, 12, 12)
    panel_layout.setSpacing(12)
    panel_title = QLabel("아래 머신 ID를 제작자에게 전달해주세요.")
    panel_title.setObjectName("panelTitle")
    panel_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
    panel_layout.addWidget(panel_title)

    id_card = QWidget()
    id_card.setObjectName("idCard")
    id_card_layout = QHBoxLayout(id_card)
    id_card_layout.setContentsMargins(16, 12, 16, 12)
    id_card_layout.setSpacing(12)
    id_label = QLabel(machine_id)
    id_label.setObjectName("idText")
    id_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    id_card_layout.addWidget(id_label, 1)
    copy_btn = QPushButton("복사")
    copy_btn.setObjectName("copyBtn")
    copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    id_card_layout.addWidget(copy_btn, 0, Qt.AlignmentFlag.AlignVCenter)
    panel_layout.addWidget(id_card)
    root.addWidget(panel)

    note = QLabel("💡 참고: 와이파이 변경, 재부팅 시에도 머신 ID는 변경되지 않습니다.")
    note.setObjectName("note")
    note.setAlignment(Qt.AlignmentFlag.AlignCenter)
    root.addWidget(note)

    bottom = QHBoxLayout()
    bottom.addStretch(1)
    ok_btn = QPushButton("확인")
    ok_btn.setObjectName("confirmBtn")
    ok_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    ok_btn.setDefault(True)
    ok_btn.setAutoDefault(True)
    bottom.addWidget(ok_btn, 0, Qt.AlignmentFlag.AlignRight)
    root.addStretch(1)
    root.addLayout(bottom)

    def on_copy() -> None:
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(machine_id)
        copy_btn.setText("복사됨")
        QTimer.singleShot(900, lambda: copy_btn.setText("복사"))

    copy_btn.clicked.connect(on_copy)
    ok_btn.clicked.connect(dlg.accept)
    dlg.setWindowModality(Qt.WindowModality.ApplicationModal)
    dlg.exec()


def show_expired_license_dialog() -> None:
    dlg = QDialog()
    dlg.setWindowTitle("프로그램 사용 권한")
    _apply_window_icon(dlg)
    dlg.setModal(True)
    dlg.setFixedSize(760, 410)
    dlg.setStyleSheet(
        """
        QDialog {
            background: #f3f3f3;
        }
        QLabel#title {
            color: #e53935;
            font-size: 24px;
            font-weight: 800;
        }
        QLabel#icon {
            color: #f0a838;
            font-size: 36px;
        }
        QWidget#panel {
            background: #efe4d1;
            border-radius: 14px;
        }
        QLabel#panelText {
            color: #1f1f1f;
            font-size: 16px;
            font-weight: 600;
        }
        QPushButton#openTalkBtn {
            background: #2a80d8;
            color: white;
            border: none;
            border-radius: 12px;
            font-size: 16px;
            font-weight: 800;
            padding: 8px 18px;
            min-height: 44px;
        }
        QPushButton#confirmBtn {
            background: #51b24e;
            color: white;
            border: none;
            border-radius: 12px;
            font-size: 16px;
            font-weight: 800;
            padding: 8px 20px;
            min-width: 110px;
            min-height: 44px;
        }
        """
    )

    root = QVBoxLayout(dlg)
    root.setContentsMargins(24, 18, 24, 16)
    root.setSpacing(12)

    title_row = QHBoxLayout()
    icon = QLabel("⚠️")
    icon.setObjectName("icon")
    title_row.addWidget(icon, 0, Qt.AlignmentFlag.AlignVCenter)
    title = QLabel("사용 기간이 만료되었습니다.")
    title.setObjectName("title")
    title_row.addWidget(title, 1, Qt.AlignmentFlag.AlignVCenter)
    root.addLayout(title_row)

    panel = QWidget()
    panel.setObjectName("panel")
    panel_layout = QVBoxLayout(panel)
    panel_layout.setContentsMargins(12, 10, 12, 10)
    panel_layout.setSpacing(8)
    panel_text = QLabel("기간 연장이 필요합니다. 아래 오픈카톡으로 문의해주세요.")
    panel_text.setObjectName("panelText")
    panel_text.setWordWrap(True)
    panel_layout.addWidget(panel_text)
    open_talk_btn = QPushButton("오픈카톡 바로가기")
    open_talk_btn.setObjectName("openTalkBtn")
    open_talk_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    panel_layout.addWidget(open_talk_btn)
    root.addWidget(panel)

    bottom = QHBoxLayout()
    bottom.addStretch(1)
    ok_btn = QPushButton("확인")
    ok_btn.setObjectName("confirmBtn")
    ok_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    ok_btn.setDefault(True)
    ok_btn.setAutoDefault(True)
    bottom.addWidget(ok_btn, 0, Qt.AlignmentFlag.AlignRight)
    root.addLayout(bottom)

    def on_open_talk() -> None:
        opened = QDesktopServices.openUrl(QUrl(KAKAO_CONTACT_URL))
        if not opened:
            QMessageBox.warning(dlg, "오류", "오픈카톡 링크를 열지 못했습니다.")

    open_talk_btn.clicked.connect(on_open_talk)
    ok_btn.clicked.connect(dlg.accept)
    dlg.setWindowModality(Qt.WindowModality.ApplicationModal)
    dlg.exec()


def show_license_failure_dialog(message: str, machine_id: str) -> None:
    dlg = QDialog()
    dlg.setWindowTitle("라이선스 인증 실패")
    _apply_window_icon(dlg)
    dlg.setModal(True)
    dlg.setFixedSize(600, 305)
    dlg.setStyleSheet(
        """
        QDialog {
            background: #efefef;
        }
        QLabel#title {
            color: #e53935;
            font-size: 16px;
            font-weight: 800;
        }
        QLabel#mainMsg {
            color: #1f1f1f;
            font-size: 15px;
            font-weight: 600;
        }
        QLabel#icon {
            color: #f0a838;
            font-size: 36px;
        }
        QWidget#panel {
            background: #d5e5f3;
            border-radius: 16px;
        }
        QWidget#idCard {
            background: #f6fbff;
            border: 1px solid #9ec6ea;
            border-radius: 12px;
        }
        QLabel#machineTitle {
            color: #1f1f1f;
            font-size: 15px;
            font-weight: 700;
        }
        QLabel#machineId {
            color: #1f1f1f;
            font-size: 14px;
            font-family: Consolas, "Courier New", monospace;
            font-weight: 500;
        }
        QPushButton#copyBtn {
            background: #2a80d8;
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 700;
            padding: 6px 14px;
            min-width: 74px;
            min-height: 32px;
        }
        QPushButton#okBtn {
            background: #51b24e;
            color: white;
            border: none;
            border-radius: 10px;
            font-size: 14px;
            font-weight: 800;
            padding: 6px 16px;
            min-width: 90px;
            min-height: 36px;
        }
        """
    )

    root = QVBoxLayout(dlg)
    root.setContentsMargins(14, 10, 14, 10)
    root.setSpacing(6)

    title_row = QHBoxLayout()
    title_row.setContentsMargins(0, 0, 0, 0)
    title_row.setSpacing(8)
    icon = QLabel("⚠")
    icon.setObjectName("icon")
    title_row.addWidget(icon, 0, Qt.AlignmentFlag.AlignVCenter)
    title = QLabel("라이선스 인증에 실패했습니다.")
    title.setObjectName("title")
    title_row.addWidget(title, 1, Qt.AlignmentFlag.AlignVCenter)
    root.addLayout(title_row)

    panel = QWidget()
    panel.setObjectName("panel")
    panel_layout = QVBoxLayout(panel)
    panel_layout.setContentsMargins(8, 6, 8, 6)
    panel_layout.setSpacing(6)

    msg = QLabel(message)
    msg.setObjectName("mainMsg")
    msg.setWordWrap(True)
    msg.setMinimumHeight(28)
    panel_layout.addWidget(msg)

    title = QLabel("현재 머신 ID:")
    title.setObjectName("machineTitle")
    panel_layout.addWidget(title)

    id_card = QWidget()
    id_card.setObjectName("idCard")
    id_layout = QHBoxLayout(id_card)
    id_layout.setContentsMargins(10, 6, 10, 6)
    id_layout.setSpacing(8)
    mid = QLabel(machine_id)
    mid.setObjectName("machineId")
    mid.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    id_layout.addWidget(mid, 1)
    copy_btn = QPushButton("복사")
    copy_btn.setObjectName("copyBtn")
    copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    id_layout.addWidget(copy_btn, 0, Qt.AlignmentFlag.AlignVCenter)
    panel_layout.addWidget(id_card)
    root.addWidget(panel)

    buttons = QHBoxLayout()
    buttons.addStretch(1)
    ok_btn = QPushButton("확인")
    ok_btn.setObjectName("okBtn")
    ok_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    ok_btn.setDefault(True)
    ok_btn.setAutoDefault(True)
    buttons.addWidget(ok_btn)
    root.addLayout(buttons)

    def on_copy() -> None:
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(machine_id)
        copy_btn.setText("복사됨")
        QTimer.singleShot(900, lambda: copy_btn.setText("복사"))

    copy_btn.clicked.connect(on_copy)
    ok_btn.clicked.connect(dlg.accept)
    dlg.setWindowModality(Qt.WindowModality.ApplicationModal)
    dlg.exec()

try:
    import requests
    from bs4 import BeautifulSoup
    HTTP_AVAILABLE = True
except (Exception, KeyboardInterrupt):
    HTTP_AVAILABLE = False

try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import BatchHttpRequest
    GOOGLE_API_AVAILABLE = True
except Exception:
    GOOGLE_API_AVAILABLE = False

# 암호화 설정(.encryption_salt) 기능은 사용하지 않음.
ENCRYPTION_AVAILABLE = False

try:
    from seo_prefilter import SEOPreFilter
    SEO_FILTER_AVAILABLE = True
except Exception:
    SEO_FILTER_AVAILABLE = False

try:
    from naver_selenium_service import NaverSeleniumService
    NAVER_SELENIUM_AVAILABLE = True
except Exception:
    NAVER_SELENIUM_AVAILABLE = False

try:
    from PyQt6.QtCore import QMetaObject, QThread, QTimer, Qt, QUrl, Q_ARG, pyqtSignal
    from PyQt6.QtGui import QDesktopServices, QFont, QIcon, QKeySequence
    from PyQt6.QtWidgets import QApplication, QCheckBox, QComboBox, QDialog, QFileDialog, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox, QProgressBar, QPushButton, QScrollArea, QTabWidget, QTextBrowser, QTextEdit, QVBoxLayout, QWidget
    GUI_AVAILABLE = True
except Exception:
    GUI_AVAILABLE = False

try:
    from password_dialog import PasswordDialog
    PASSWORD_DIALOG_AVAILABLE = True
except Exception:
    PASSWORD_DIALOG_AVAILABLE = False

try:
    from license_check import LicenseManager
    LICENSE_CHECK_AVAILABLE = True
except Exception:
    LICENSE_CHECK_AVAILABLE = False


class IndexingLogger:
    def __init__(self):
        self.gui_widgets: List[Any] = []
        self.error_callback: Optional[Callable[[str], None]] = None
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

    def set_gui_log_widget(self, widget):
        self.gui_widgets = [widget] if widget else []

    def set_error_callback(self, callback: Optional[Callable[[str], None]]) -> None:
        self.error_callback = callback

    def log(self, message: str, level: str = "INFO"):
        raw_message = str(message or "").strip()
        is_rich = "<a " in raw_message.lower()
        if is_rich:
            normalized = raw_message
        else:
            normalized = self._normalize_message(message)
            if normalized is None:
                return
        # Keep exactly one leading icon in GUI logs.
        while normalized and normalized[0] in ("ℹ", "ℹ️", "⚠", "⚠️", "❌", "✅", "🔍", "📋", "📌", "🛠", "🚀"):
            normalized = normalized[1:].lstrip("️ ").strip()
        level_text = (level or "INFO").upper()
        if level_text == "DEBUG":
            level_text = "INFO"
        icon_map = {
            "INFO": "ℹ️",
            "WARNING": "⚠️",
            "ERROR": "❌",
            "SUCCESS": "✅",
        }
        icon = icon_map.get(level_text, "ℹ️")
        line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {icon} {normalized}"
        plain_line = re.sub(r"<[^>]+>", "", line) if is_rich else line
        print(plain_line)
        if level_text == "ERROR" and callable(self.error_callback):
            try:
                self.error_callback(plain_line)
            except Exception:
                pass
        for w in self.gui_widgets:
            try:
                if GUI_AVAILABLE:
                    QMetaObject.invokeMethod(
                        w,
                        "append",
                        Qt.ConnectionType.QueuedConnection,
                        Q_ARG(str, line),
                    )
                else:
                    w.append(line)
            except Exception:
                pass
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(plain_line + "\n")
        except Exception:
            pass

    def _decode_url(self, text: str) -> Optional[str]:
        try:
            parts = urlsplit(text)
            path = unquote(parts.path, encoding="utf-8", errors="strict")
            query = unquote(parts.query, encoding="utf-8", errors="strict")
            frag = unquote(parts.fragment, encoding="utf-8", errors="strict")
            return urlunsplit((parts.scheme, parts.netloc, path, query, frag))
        except Exception:
            return None

    def _normalize_message(self, message: str) -> Optional[str]:
        raw = str(message or "")
        url_pattern = re.compile(r"https?://[^\s]+")
        out = raw
        for m in url_pattern.finditer(raw):
            original = m.group(0)
            if "%" not in original:
                continue
            decoded = self._decode_url(original)
            if decoded is None:
                return None
            out = out.replace(original, decoded)
        out = re.sub(r"\s+", " ", out).strip()
        return out if out else None


class ConfigManager:
    def __init__(self):
        self.config_file = CONFIG_FILE
        self.encrypted_config_file = ENCRYPTED_CONFIG_FILE
        self.password: Optional[str] = None
        self.encryption_manager = None
        self.default_config = {
            "google_enabled": True,
            "naver_enabled": True,
            "google_service_account_file": "service-account-key.json",
            "google_service_account_files": [],
            "google_site_urls": [],
            "google_site_items": [],
            "naver_method": "selenium",
            "indexnow_host": "",
            "indexnow_api_key": "",
            "indexnow_key_location": "",
            "naver_access_token": "",
            "naver_site_urls": [],
            "naver_site_items": [],
            "naver_username": "",
            "naver_password": "",
            "use_seo_prefilter": True,
            "use_batch_api": True,
            "daily_limit": 200,
            "submit_order": "oldest",
        }

    def _normalize(self, cfg):
        out = self.default_config.copy()
        out.update(cfg or {})
        g_files = out.get("google_service_account_files")
        if not isinstance(g_files, list):
            g_files = []
        normalized_g_files: List[str] = []
        seen_g_files: Set[str] = set()
        for p in g_files:
            s = str(p or "").strip()
            if s and s not in seen_g_files:
                seen_g_files.add(s)
                normalized_g_files.append(s)
        single_g = str(out.get("google_service_account_file", "") or "").strip()
        if single_g and single_g not in seen_g_files:
            normalized_g_files.insert(0, single_g)
        out["google_service_account_files"] = normalized_g_files
        out["google_service_account_file"] = normalized_g_files[0] if normalized_g_files else "service-account-key.json"
        default_order = str(out.get("submit_order", "oldest") or "oldest").strip().lower()
        if default_order not in ("oldest", "newest"):
            default_order = "oldest"
        out["submit_order"] = default_order

        def _normalize_items(items, urls):
            normalized = []
            seen = set()
            if isinstance(items, list):
                for it in items:
                    if not isinstance(it, dict):
                        continue
                    u = str(it.get("url", "") or "").strip()
                    if not u or u in seen:
                        continue
                    seen.add(u)
                    order = str(it.get("order", default_order) or default_order).strip().lower()
                    if order not in ("oldest", "newest"):
                        order = default_order
                    enabled = it.get("enabled", True)
                    if isinstance(enabled, str):
                        enabled = enabled.strip().lower() not in ("false", "0", "no", "off", "")
                    else:
                        enabled = bool(enabled)
                    normalized.append({"url": u, "order": order, "enabled": enabled})
            if not normalized and isinstance(urls, list):
                for raw in urls:
                    u = str(raw or "").strip()
                    if not u or u in seen:
                        continue
                    seen.add(u)
                    normalized.append({"url": u, "order": default_order, "enabled": True})
            return normalized

        out["google_site_items"] = _normalize_items(out.get("google_site_items"), out.get("google_site_urls", []))
        out["google_site_urls"] = [it["url"] for it in out["google_site_items"]]
        out["naver_site_items"] = _normalize_items(out.get("naver_site_items"), out.get("naver_site_urls", []))
        out["naver_site_urls"] = [it["url"] for it in out["naver_site_items"]]
        if out.get("naver_site_url") and not out.get("naver_site_urls"):
            out["naver_site_urls"] = [out["naver_site_url"]]
        return out

    def load_config(self, password: Optional[str] = None):
        if ENCRYPTION_AVAILABLE and self.encryption_manager and os.path.exists(self.encrypted_config_file):
            if not password:
                return None
            try:
                self.encryption_manager.set_password(password)
                cfg = self.encryption_manager.load_encrypted_config(self.encrypted_config_file)
                if cfg is None:
                    return None
                self.password = password
                return self._normalize(cfg)
            except Exception:
                return None
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    return self._normalize(json.load(f))
            except Exception:
                return self.default_config.copy()
        return self.default_config.copy()

    def save_config(self, config, password=None, encrypt=True):
        data = self._normalize(config)
        try:
            if ENCRYPTION_AVAILABLE and self.encryption_manager and encrypt and password:
                self.encryption_manager.set_password(password)
                ok = self.encryption_manager.save_encrypted_config(data, self.encrypted_config_file)
                if ok:
                    self.password = password
                return bool(ok)
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False


class URLManager:
    def __init__(self, logger: IndexingLogger):
        self.logger = logger
        self.stop_event = Event()
        os.makedirs(SETTING_DIR, exist_ok=True)

    def stop(self):
        self.stop_event.set()

    @staticmethod
    def valid(url: str) -> bool:
        try:
            p = urllib.parse.urlparse(url)
            return bool(p.scheme and p.netloc)
        except Exception:
            return False

    @staticmethod
    def _strip_fragment(url: str) -> str:
        return urldefrag(url or "")[0].strip()

    def load_indexed(self) -> Set[str]:
        if not os.path.exists(INDEXED_URLS_FILE):
            return set()
        try:
            with open(INDEXED_URLS_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            return set()

    def save_indexed(self, urls: Set[str]):
        with open(INDEXED_URLS_FILE, "w", encoding="utf-8") as f:
            json.dump(sorted(urls), f, ensure_ascii=False, indent=2)

    @staticmethod
    def _normalize_dt(value: str) -> Optional[str]:
        if not value:
            return None
        raw = value.strip()
        if not raw:
            return None
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        try:
            d = datetime.fromisoformat(raw)
            return d.isoformat(timespec="seconds")
        except Exception:
            pass
        for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
            try:
                d = datetime.strptime(raw, fmt)
                return d.isoformat(timespec="seconds")
            except Exception:
                pass
        try:
            d = parsedate_to_datetime(raw)
            return d.isoformat(timespec="seconds")
        except Exception:
            pass
        return None

    @staticmethod
    def _guess_title_from_url(url: str) -> str:
        try:
            path = urlparse(url).path.strip("/")
            if not path:
                return "홈"
            slug = path.split("/")[-1]
            title = unquote(slug, encoding="utf-8", errors="ignore").replace("-", " ").replace("_", " ").strip()
            return title if title else url
        except Exception:
            return url

    def _sitemap_urls(self, text: str) -> Tuple[Dict[str, Optional[str]], Dict[str, str]]:
        dated: Dict[str, Optional[str]] = {}
        titled: Dict[str, str] = {}
        try:
            root = ET.fromstring(text)
            for node in root.findall(".//{*}url"):
                loc = node.find("{*}loc")
                if loc is None or not loc.text:
                    continue
                u = self._strip_fragment(loc.text)
                if not u:
                    continue
                lastmod_node = node.find("{*}lastmod")
                lastmod = self._normalize_dt(lastmod_node.text if lastmod_node is not None and lastmod_node.text else "")
                dated[u] = lastmod
                titled[u] = self._guess_title_from_url(u)
        except Exception:
            pass
        return dated, titled

    def _extract_sitemap_links_from_html(self, text: str, base_url: str) -> List[str]:
        links: List[str] = []
        try:
            soup = BeautifulSoup(text, "lxml")
            table = soup.find("table", id="sitemap")
            candidates = table.find_all("a", href=True) if table else soup.find_all("a", href=True)
            for a in candidates:
                href_raw = a.get("href")
                if isinstance(href_raw, list):
                    href = (href_raw[0] if href_raw else "").strip()
                else:
                    href = (href_raw or "").strip()
                if not href:
                    continue
                u = urljoin(base_url, href)
                if u.lower().endswith(".xml"):
                    links.append(u)
        except Exception:
            pass
        uniq: List[str] = []
        seen: Set[str] = set()
        for u in links:
            if u not in seen:
                seen.add(u)
                uniq.append(u)
        return uniq

    def _extract_url_entries_from_html(self, text: str, base_url: str, host: str) -> Tuple[Dict[str, Optional[str]], Dict[str, str]]:
        dated: Dict[str, Optional[str]] = {}
        titled: Dict[str, str] = {}
        try:
            soup = BeautifulSoup(text, "lxml")
            table = soup.find("table", id="sitemap")
            if table is None:
                return dated, titled
            rows = table.select("tbody tr")
            for row in rows:
                a = row.find("a", href=True)
                if a is None:
                    continue
                href_raw = a.get("href")
                if isinstance(href_raw, list):
                    href = (href_raw[0] if href_raw else "").strip()
                else:
                    href = (href_raw or "").strip()
                if not href:
                    continue
                u = self._strip_fragment(urljoin(base_url, href))
                if not u or urlparse(u).netloc != host:
                    continue
                # 하위 sitemap 링크(xml)는 URL 엔트리가 아님
                if u.lower().endswith(".xml"):
                    continue
                cells = row.find_all("td")
                lastmod_text = ""
                if len(cells) >= 3:
                    lastmod_text = (cells[2].get_text(" ", strip=True) or "").strip()
                elif len(cells) >= 2:
                    lastmod_text = (cells[-1].get_text(" ", strip=True) or "").strip()
                dated[u] = self._normalize_dt(lastmod_text)
                titled[u] = self._guess_title_from_url(u)
        except Exception:
            pass
        return dated, titled

    def _fetch_sitemap_recursive(
        self,
        session: requests.Session,
        sitemap_url: str,
        host: str,
        visited: Set[str],
    ) -> Tuple[Dict[str, Optional[str]], Dict[str, str]]:
        dated: Dict[str, Optional[str]] = {}
        titled: Dict[str, str] = {}
        sm_url = self._strip_fragment(sitemap_url)
        if not sm_url or sm_url in visited:
            return dated, titled
        visited.add(sm_url)
        try:
            resp = session.get(sm_url, timeout=10)
        except Exception:
            return dated, titled
        if resp.status_code != 200 or not resp.text:
            return dated, titled
        text = resp.text

        try:
            root = ET.fromstring(text)
            root_tag = (root.tag.split("}")[-1] if "}" in root.tag else root.tag).lower()

            if root_tag == "sitemapindex":
                for node in root.findall(".//{*}sitemap"):
                    loc = node.find("{*}loc")
                    if loc is None or not loc.text:
                        continue
                    child_url = self._strip_fragment(urljoin(sm_url, loc.text.strip()))
                    c_dates, c_titles = self._fetch_sitemap_recursive(session, child_url, host, visited)
                    for u, dt in c_dates.items():
                        if urlparse(u).netloc != host:
                            continue
                        prev = dated.get(u)
                        if prev is None or (dt and dt < prev):
                            dated[u] = dt
                    for u, title in c_titles.items():
                        if urlparse(u).netloc == host and title:
                            titled[u] = title
                return dated, titled

            if root_tag == "urlset":
                d, t = self._sitemap_urls(text)
                for u, dt in d.items():
                    if urlparse(u).netloc != host:
                        continue
                    prev = dated.get(u)
                    if prev is None or (dt and dt < prev):
                        dated[u] = dt
                for u, title in t.items():
                    if urlparse(u).netloc == host and title:
                        titled[u] = title
                return dated, titled
        except Exception:
            pass

        # HTML 표가 "URL" 목록인 경우 (Rank Math post-sitemap 렌더링)
        html_dates, html_titles = self._extract_url_entries_from_html(text, sm_url, host)
        if html_dates:
            return html_dates, html_titles

        # Rank Math 등에서 HTML 테이블 형태로 sitemap index를 렌더링하는 경우 대응
        for child in self._extract_sitemap_links_from_html(text, sm_url):
            c_dates, c_titles = self._fetch_sitemap_recursive(session, child, host, visited)
            for u, dt in c_dates.items():
                if urlparse(u).netloc != host:
                    continue
                prev = dated.get(u)
                if prev is None or (dt and dt < prev):
                    dated[u] = dt
            for u, title in c_titles.items():
                if urlparse(u).netloc == host and title:
                    titled[u] = title
        return dated, titled

    def _rss_entries(self, base_url: str) -> Tuple[Dict[str, Optional[str]], Dict[str, str]]:
        out: Dict[str, Optional[str]] = {}
        titles: Dict[str, str] = {}
        try:
            s = requests.Session()
            s.headers.update({"User-Agent": "Mozilla/5.0"})
            for path in ["/feed", "/rss", "/rss.xml", "/atom.xml"]:
                try:
                    r = s.get(urljoin(base_url, path), timeout=8)
                except Exception:
                    continue
                if r.status_code != 200 or not r.text:
                    continue
                try:
                    root = ET.fromstring(r.text)
                except Exception:
                    continue
                # RSS item
                for item in root.findall(".//item"):
                    link_node = item.find("link")
                    if link_node is None or not link_node.text:
                        continue
                    u = self._strip_fragment(link_node.text)
                    if not u:
                        continue
                    title_node = item.find("title")
                    date_node = item.find("pubDate") or item.find("date")
                    out[u] = self._normalize_dt(date_node.text if date_node is not None and date_node.text else "")
                    titles[u] = (title_node.text or "").strip() if title_node is not None and title_node.text else self._guess_title_from_url(u)
                # Atom entry
                for entry in root.findall(".//{http://www.w3.org/2005/Atom}entry"):
                    link = entry.find("{http://www.w3.org/2005/Atom}link")
                    href = link.get("href", "") if link is not None else ""
                    if not href:
                        continue
                    u = self._strip_fragment(urljoin(base_url, href))
                    if not u:
                        continue
                    title_node = entry.find("{http://www.w3.org/2005/Atom}title")
                    date_node = entry.find("{http://www.w3.org/2005/Atom}published") or entry.find("{http://www.w3.org/2005/Atom}updated")
                    out[u] = self._normalize_dt(date_node.text if date_node is not None and date_node.text else "")
                    titles[u] = (title_node.text or "").strip() if title_node is not None and title_node.text else self._guess_title_from_url(u)
                if out:
                    break
        except Exception:
            pass
        return out, titles

    def crawl_site(
        self,
        base_url: str,
        max_urls: Optional[int] = None,
        submit_order: str = "oldest",
    ) -> Tuple[List[str], Dict[str, str], Dict[str, str]]:
        if self.stop_event.is_set() or not self.valid(base_url) or not HTTP_AVAILABLE:
            if self.valid(base_url):
                clean = self._strip_fragment(base_url)
                return ([clean] if clean else [], {}, {clean: self._guess_title_from_url(clean)} if clean else {})
            return ([], {}, {})
        s = requests.Session()
        s.headers.update({"User-Agent": "Mozilla/5.0"})
        host = urlparse(base_url).netloc
        sitemap_root = urljoin(base_url, "/sitemap.xml")
        sm_dates, sm_titles = self._fetch_sitemap_recursive(s, sitemap_root, host, set())
        found = set(sm_dates.keys())
        dated: Dict[str, str] = {u: dt for u, dt in sm_dates.items() if dt}
        titled: Dict[str, str] = {u: sm_titles.get(u, self._guess_title_from_url(u)) for u in found}
        newest_first = str(submit_order or "").strip().lower() == "newest"
        valid_urls = sorted(
            {u for u in found if self.valid(u)},
            key=lambda u: (
                1 if not (dated.get(u) or "").strip() else 0,
                (dated.get(u) or ("0000-01-01T00:00:00" if newest_first else "9999-12-31T23:59:59")),
                u,
            ),
            reverse=newest_first,
        )
        if isinstance(max_urls, int) and max_urls > 0:
            valid_urls = valid_urls[:max_urls]
        valid_set = set(valid_urls)
        valid_dated = {u: dt for u, dt in dated.items() if u in valid_set}
        valid_titles = {u: titled.get(u, self._guess_title_from_url(u)) for u in valid_set}
        return valid_urls, valid_dated, valid_titles

    def collect(self, seeds: List[str], submit_order: str = "oldest") -> Tuple[List[str], Dict[str, str], Dict[str, str]]:
        uniq, seen = [], set()
        for u in seeds:
            u = u.strip()
            if u and u not in seen:
                seen.add(u)
                uniq.append(u)
        out = set()
        dated: Dict[str, str] = {}
        titled: Dict[str, str] = {}
        for i, seed in enumerate(uniq, 1):
            if self.stop_event.is_set():
                break
            self.logger.log(f"[{i}/{len(uniq)}] {seed} 색인 자동화 시작")
            urls, dmap, tmap = self.crawl_site(seed, submit_order=submit_order)
            out.update(urls)
            for u, dt in dmap.items():
                prev = dated.get(u)
                if prev is None or dt < prev:
                    dated[u] = dt
            for u, title in tmap.items():
                if u not in titled and title:
                    titled[u] = title
        return sorted(out), dated, titled


class URLStateStore:
    def __init__(self, logger: IndexingLogger):
        self.logger = logger
        os.makedirs(SETTING_DIR, exist_ok=True)
        self.db_file = URL_STATE_DB_FILE
        self._init_db()
        self._migrate_legacy_indexed_urls()

    def _connect(self):
        c = sqlite3.connect(self.db_file)
        c.row_factory = sqlite3.Row
        return c

    def _init_db(self):
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS url_state (
                    url TEXT PRIMARY KEY,
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    published_at TEXT,
                    title TEXT,
                    google_submitted_at TEXT,
                    naver_submitted_at TEXT
                )
                """
            )
            cols = [r["name"] for r in conn.execute("PRAGMA table_info(url_state)").fetchall()]
            if "published_at" not in cols:
                conn.execute("ALTER TABLE url_state ADD COLUMN published_at TEXT")
            if "title" not in cols:
                conn.execute("ALTER TABLE url_state ADD COLUMN title TEXT")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_google_pending ON url_state(google_submitted_at, first_seen_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_naver_pending ON url_state(naver_submitted_at, first_seen_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_published_at ON url_state(published_at)")

    def _migrate_legacy_indexed_urls(self):
        if not os.path.exists(INDEXED_URLS_FILE):
            return
        try:
            with open(INDEXED_URLS_FILE, "r", encoding="utf-8") as f:
                urls = [u.strip() for u in json.load(f) if isinstance(u, str) and u.strip()]
        except Exception:
            return
        if not urls:
            return
        now = datetime.now().isoformat(timespec="seconds")
        try:
            with self._connect() as conn:
                for u in urls:
                    conn.execute(
                        """
                        INSERT INTO url_state (url, first_seen_at, last_seen_at, google_submitted_at, naver_submitted_at)
                        VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(url) DO UPDATE SET
                            last_seen_at=excluded.last_seen_at,
                            google_submitted_at=COALESCE(url_state.google_submitted_at, excluded.google_submitted_at),
                            naver_submitted_at=COALESCE(url_state.naver_submitted_at, excluded.naver_submitted_at)
                        """,
                        (u, now, now, now, now),
                    )
            bak = INDEXED_URLS_FILE + ".migrated"
            if not os.path.exists(bak):
                os.replace(INDEXED_URLS_FILE, bak)
            self.logger.log(f"Legacy indexed URL data migrated to SQLite: {len(urls)} URLs")
        except Exception as e:
            self.logger.log(f"Legacy migration failed: {e}", "WARNING")

    def upsert_seen_urls(self, urls: List[str], published_map: Optional[Dict[str, str]] = None, title_map: Optional[Dict[str, str]] = None):
        if not urls:
            return
        now = datetime.now().isoformat(timespec="seconds")
        published_map = published_map or {}
        title_map = title_map or {}
        with self._connect() as conn:
            for u in urls:
                p = published_map.get(u)
                t = (title_map.get(u) or "").strip()
                conn.execute(
                    """
                    INSERT INTO url_state (url, first_seen_at, last_seen_at, published_at, title)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(url) DO UPDATE SET
                        last_seen_at=excluded.last_seen_at,
                        published_at=CASE
                            WHEN excluded.published_at IS NULL THEN url_state.published_at
                            WHEN url_state.published_at IS NULL THEN excluded.published_at
                            WHEN excluded.published_at < url_state.published_at THEN excluded.published_at
                            ELSE url_state.published_at
                        END,
                        title=CASE
                            WHEN excluded.title IS NULL OR excluded.title = '' THEN url_state.title
                            WHEN url_state.title IS NULL OR url_state.title = '' THEN excluded.title
                            ELSE url_state.title
                        END
                    """,
                    (u, now, now, p, t),
                )

    def get_pending_urls(self, service: str, limit: int, submit_order: str = "oldest") -> List[str]:
        if limit <= 0:
            return []
        col = "google_submitted_at" if service == "google" else "naver_submitted_at"
        newest_first = str(submit_order or "").strip().lower() == "newest"
        published_order = "DESC" if newest_first else "ASC"
        first_seen_order = "DESC" if newest_first else "ASC"
        url_order = "DESC" if newest_first else "ASC"
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT url
                FROM url_state
                WHERE {col} IS NULL
                ORDER BY
                    CASE WHEN published_at IS NULL THEN 1 ELSE 0 END ASC,
                    published_at {published_order},
                    first_seen_at {first_seen_order},
                    url {url_order}
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [r["url"] for r in rows]

    def pending_count(self, service: str) -> int:
        col = "google_submitted_at" if service == "google" else "naver_submitted_at"
        with self._connect() as conn:
            row = conn.execute(f"SELECT COUNT(*) AS cnt FROM url_state WHERE {col} IS NULL").fetchone()
        return int(row["cnt"] if row else 0)

    def pending_count_for_site(self, service: str, site_url: str) -> int:
        col = "google_submitted_at" if service == "google" else "naver_submitted_at"
        prefix = (site_url or "").rstrip("/")
        if not prefix:
            return 0
        with self._connect() as conn:
            row = conn.execute(
                f"""
                SELECT COUNT(*) AS cnt
                FROM url_state
                WHERE {col} IS NULL
                  AND (url = ? OR url LIKE ?)
                """,
                (prefix, prefix + "/%"),
            ).fetchone()
        return int(row["cnt"] if row else 0)

    def get_pending_urls_for_site(
        self,
        service: str,
        site_url: str,
        limit: int,
        submit_order: str = "oldest",
    ) -> List[str]:
        if limit <= 0:
            return []
        col = "google_submitted_at" if service == "google" else "naver_submitted_at"
        prefix = (site_url or "").rstrip("/")
        if not prefix:
            return []
        newest_first = str(submit_order or "").strip().lower() == "newest"
        published_order = "DESC" if newest_first else "ASC"
        first_seen_order = "DESC" if newest_first else "ASC"
        url_order = "DESC" if newest_first else "ASC"
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT url
                FROM url_state
                WHERE {col} IS NULL
                  AND (url = ? OR url LIKE ?)
                ORDER BY
                    CASE WHEN published_at IS NULL THEN 1 ELSE 0 END ASC,
                    published_at {published_order},
                    first_seen_at {first_seen_order},
                    url {url_order}
                LIMIT ?
                """,
                (prefix, prefix + "/%", limit),
            ).fetchall()
        return [r["url"] for r in rows]

    def mark_submitted(self, service: str, urls: List[str]):
        if not urls:
            return
        now = datetime.now().isoformat(timespec="seconds")
        col = "google_submitted_at" if service == "google" else "naver_submitted_at"
        with self._connect() as conn:
            for u in urls:
                conn.execute(f"UPDATE url_state SET {col} = ? WHERE url = ?", (now, u))

    def get_url_meta(self, urls: List[str]) -> Dict[str, Dict[str, str]]:
        if not urls:
            return {}
        out: Dict[str, Dict[str, str]] = {}
        with self._connect() as conn:
            for u in urls:
                row = conn.execute("SELECT published_at, title FROM url_state WHERE url = ?", (u,)).fetchone()
                if not row:
                    continue
                out[u] = {
                    "published_at": (row["published_at"] or "").strip(),
                    "title": (row["title"] or "").strip(),
                }
        return out

class GoogleIndexingService:
    def __init__(self, logger: IndexingLogger):
        self.logger = logger
        self.service = None
        self.daily_limit = 200
        self.keep_days = 7
        os.makedirs(SETTING_DIR, exist_ok=True)

    @staticmethod
    def parse_service_account_files(raw: str) -> List[str]:
        text = str(raw or "")
        chunks = re.split(r"[;\n\r]+", text)
        out: List[str] = []
        seen: Set[str] = set()
        for c in chunks:
            p = c.strip().strip('"').strip("'")
            if p and p not in seen:
                seen.add(p)
                out.append(p)
        return out

    @staticmethod
    def _today() -> str:
        return datetime.now().strftime("%Y-%m-%d")

    @staticmethod
    def _prune_history(history: Dict[str, Any], keep_days: int) -> Dict[str, Any]:
        if not isinstance(history, dict):
            return {}
        valid_dates: List[Tuple[datetime, str]] = []
        for k in history.keys():
            try:
                valid_dates.append((datetime.strptime(k, "%Y-%m-%d"), k))
            except Exception:
                continue
        valid_dates.sort(key=lambda x: x[0], reverse=True)
        keep_keys = {k for _, k in valid_dates[: max(1, int(keep_days or 7))]}
        return {k: v for k, v in history.items() if k in keep_keys}

    def _normalize_day(self, day: Any) -> Dict[str, Any]:
        if not isinstance(day, dict):
            day = {}
        urls = day.get("urls")
        if not isinstance(urls, list):
            urls = []
        return {
            "used": int(day.get("used", 0) or 0),
            "success": int(day.get("success", 0) or 0),
            "failed": int(day.get("failed", 0) or 0),
            "urls": [u for u in urls if isinstance(u, str) and u.strip()],
        }

    def _load_quota(self):
        today = self._today()
        out: Dict[str, Any] = {"keep_days": self.keep_days, "history": {}}
        if os.path.exists(GOOGLE_QUOTA_FILE):
            try:
                with open(GOOGLE_QUOTA_FILE, "r", encoding="utf-8") as f:
                    d = json.load(f)
                if isinstance(d, dict):
                    out["keep_days"] = int(d.get("keep_days", self.keep_days) or self.keep_days)
                    hist = d.get("history")
                    if isinstance(hist, dict):
                        out["history"] = {
                            dt: self._normalize_day(val)
                            for dt, val in hist.items()
                            if isinstance(dt, str)
                        }
                    elif isinstance(d.get("date"), str):
                        # Legacy single-day format.
                        legacy_date = d.get("date", today)
                        out["history"] = {
                            legacy_date: self._normalize_day(
                                {
                                    "used": d.get("used", 0),
                                    "success": d.get("success", 0),
                                    "failed": d.get("failed", 0),
                                    "urls": d.get("urls", []),
                                }
                            )
                        }
            except Exception:
                pass
        out["history"] = self._prune_history(out.get("history", {}), out.get("keep_days", self.keep_days))
        out.setdefault("history", {})
        out["history"].setdefault(today, self._normalize_day({}))
        return out

    def _save_quota(self, d):
        d = d if isinstance(d, dict) else {}
        d["keep_days"] = int(d.get("keep_days", self.keep_days) or self.keep_days)
        d["history"] = self._prune_history(d.get("history", {}), d["keep_days"])
        with open(GOOGLE_QUOTA_FILE, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)

    def _today_entry(self, q: Dict[str, Any]) -> Dict[str, Any]:
        today = self._today()
        hist = q.setdefault("history", {})
        if today not in hist:
            hist[today] = self._normalize_day({})
        else:
            hist[today] = self._normalize_day(hist.get(today))
        return hist[today]

    def remaining(self):
        q = self._load_quota()
        st = self._today_entry(q)
        return max(0, self.daily_limit - int(st.get("used", 0) or 0))

    def initialize(self, service_account_file: str) -> bool:
        if not GOOGLE_API_AVAILABLE:
            self.logger.log("Google API library missing", "ERROR")
            return False
        if not os.path.exists(service_account_file):
            self.logger.log(f"Service account file not found: {service_account_file}", "ERROR")
            return False
        try:
            creds = service_account.Credentials.from_service_account_file(service_account_file, scopes=["https://www.googleapis.com/auth/indexing"])
            self.service = build("indexing", "v3", credentials=creds)
            self.logger.log(f"Google API initialized. Remaining quota: {self.remaining()}")
            return True
        except Exception as e:
            self.logger.log(f"Google init failed: {e}", "ERROR")
            return False

    def submit_urls(self, urls: List[str], use_batch: bool = True) -> Tuple[int, int]:
        if not self.service:
            return 0, len(urls)
        remaining = self.remaining()
        if remaining <= 0:
            return 0, len(urls)
        proc = urls[:min(len(urls), remaining)]
        quota = self._load_quota()
        today_entry = self._today_entry(quota)
        if use_batch and len(proc) > 1:
            success = 0
            failed = 0

            def cb(_id, _resp, ex):
                nonlocal success, failed
                if ex is None:
                    success += 1
                else:
                    failed += 1

            try:
                batch = BatchHttpRequest(callback=cb)
                for u in proc:
                    batch.add(self.service.urlNotifications().publish(body={"url": u, "type": "URL_UPDATED"}))
                batch.execute()
            except Exception:
                success = 0
                failed = len(proc)
        else:
            success = 0
            failed = 0
            for u in proc:
                try:
                    self.service.urlNotifications().publish(body={"url": u, "type": "URL_UPDATED"}).execute()
                    success += 1
                except Exception:
                    failed += 1
                time.sleep(0.2)
        today_entry["used"] = int(today_entry.get("used", 0) or 0) + len(proc)
        today_entry["success"] = int(today_entry.get("success", 0) or 0) + success
        today_entry["failed"] = int(today_entry.get("failed", 0) or 0) + failed
        history_urls = today_entry.get("urls", [])
        seen = set(history_urls)
        for u in proc:
            if u not in seen:
                history_urls.append(u)
                seen.add(u)
        today_entry["urls"] = history_urls
        self._save_quota(quota)
        return success, failed


class NaverIndexingService:
    def __init__(self, logger: IndexingLogger):
        self.logger = logger
        self.daily_limit = 50
        self.keep_days = 7
        os.makedirs(SETTING_DIR, exist_ok=True)

    @staticmethod
    def _today() -> str:
        return datetime.now().strftime("%Y-%m-%d")

    @staticmethod
    def _prune_history(history: Dict[str, Any], keep_days: int) -> Dict[str, Any]:
        if not isinstance(history, dict):
            return {}
        valid_dates: List[Tuple[datetime, str]] = []
        for k in history.keys():
            try:
                valid_dates.append((datetime.strptime(k, "%Y-%m-%d"), k))
            except Exception:
                continue
        valid_dates.sort(key=lambda x: x[0], reverse=True)
        keep_keys = {k for _, k in valid_dates[: max(1, int(keep_days or 7))]}
        return {k: v for k, v in history.items() if k in keep_keys}

    def _normalize_site_stats(self, site_stats: Any) -> Dict[str, Any]:
        if not isinstance(site_stats, dict):
            site_stats = {}
        urls = site_stats.get("urls")
        if not isinstance(urls, list):
            urls = []
        return {
            "used": int(site_stats.get("used", 0) or 0),
            "success": int(site_stats.get("success", 0) or 0),
            "failed": int(site_stats.get("failed", 0) or 0),
            "urls": [u for u in urls if isinstance(u, str) and u.strip()],
        }

    def _normalize_day(self, day: Any) -> Dict[str, Any]:
        if not isinstance(day, dict):
            day = {}
        sites = day.get("sites")
        if not isinstance(sites, dict):
            sites = {}
        return {
            "sites": {
                self._norm_site(k): self._normalize_site_stats(v)
                for k, v in sites.items()
                if isinstance(k, str) and self._norm_site(k)
            }
        }

    def _load_quota(self):
        today = self._today()
        out: Dict[str, Any] = {"keep_days": self.keep_days, "history": {}}
        if os.path.exists(NAVER_QUOTA_FILE):
            try:
                with open(NAVER_QUOTA_FILE, "r", encoding="utf-8") as f:
                    d = json.load(f)
                if isinstance(d, dict):
                    out["keep_days"] = int(d.get("keep_days", self.keep_days) or self.keep_days)
                    hist = d.get("history")
                    if isinstance(hist, dict):
                        out["history"] = {
                            dt: self._normalize_day(val)
                            for dt, val in hist.items()
                            if isinstance(dt, str)
                        }
                    elif isinstance(d.get("date"), str):
                        # Legacy single-day format compatibility.
                        legacy_date = d.get("date", today)
                        if "sites" in d and isinstance(d.get("sites"), dict):
                            out["history"] = {legacy_date: self._normalize_day({"sites": d.get("sites", {})})}
                        else:
                            used = int(d.get("used", 0) or 0)
                            success = int(d.get("success", 0) or 0)
                            failed = int(d.get("failed", 0) or 0)
                            out["history"] = {
                                legacy_date: self._normalize_day(
                                    {
                                        "sites": {
                                            "__legacy__": {
                                                "used": used,
                                                "success": success,
                                                "failed": failed,
                                                "urls": d.get("urls", []),
                                            }
                                        }
                                    }
                                )
                            }
            except Exception:
                pass
        out["history"] = self._prune_history(out.get("history", {}), out.get("keep_days", self.keep_days))
        out.setdefault("history", {})
        out["history"].setdefault(today, self._normalize_day({}))
        return out

    def _save_quota(self, d):
        d = d if isinstance(d, dict) else {}
        d["keep_days"] = int(d.get("keep_days", self.keep_days) or self.keep_days)
        d["history"] = self._prune_history(d.get("history", {}), d["keep_days"])
        with open(NAVER_QUOTA_FILE, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)

    @staticmethod
    def _norm_site(site_url: str) -> str:
        return (site_url or "").strip().rstrip("/").lower()

    def _today_sites(self, q: Dict[str, Any]) -> Dict[str, Any]:
        today = self._today()
        hist = q.setdefault("history", {})
        day = hist.get(today)
        day_norm = self._normalize_day(day)
        hist[today] = day_norm
        return day_norm.setdefault("sites", {})

    def remaining_for_site(self, site_url: str) -> int:
        q = self._load_quota()
        sites = self._today_sites(q)
        key = self._norm_site(site_url)
        st = sites.get(key, {})
        used = int(st.get("used", 0) or 0)
        success = int(st.get("success", 0) or 0)
        failed = int(st.get("failed", 0) or 0)
        # Recovery for older buggy runs: all attempts failed before real submit.
        if used > 0 and success == 0 and failed >= used:
            used = 0
        return max(0, self.daily_limit - used)

    def submit_indexnow(self, urls: List[str], host: str, api_key: str, key_location: str = "") -> Tuple[int, int]:
        if not HTTP_AVAILABLE or not host or not api_key:
            return 0, len(urls)
        payload = {"host": host, "key": api_key, "urlList": urls}
        if key_location:
            payload["keyLocation"] = key_location
        try:
            r = requests.post("https://api.indexnow.org/indexnow", json=payload, timeout=30)
            if r.status_code in (200, 202):
                return len(urls), 0
            return 0, len(urls)
        except Exception:
            return 0, len(urls)

    def submit_crawl_api(self, urls: List[str], token: str, site_url: str) -> Tuple[int, int]:
        if not HTTP_AVAILABLE or not token or not site_url:
            return 0, len(urls)
        success = 0
        failed = 0
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        for u in urls:
            try:
                r = requests.post("https://searchadvisor.naver.com/api/crawl-request", json={"siteUrl": site_url, "url": u}, headers=headers, timeout=20)
                if r.status_code == 200:
                    success += 1
                else:
                    failed += 1
            except Exception:
                failed += 1
            time.sleep(0.15)
        return success, failed

    def submit_selenium(
        self,
        urls: List[str],
        site_urls: List[str],
        username: str,
        password: str,
        url_meta: Optional[Dict[str, Dict[str, str]]] = None,
        stop_event: Optional[Event] = None,
        submit_order: str = "oldest",
    ) -> Tuple[int, int]:
        if not NAVER_SELENIUM_AVAILABLE or not username or not password or not site_urls:
            return 0, len(urls)
        url_meta = url_meta or {}
        grouped = {s.rstrip("/"): [] for s in site_urls}
        for u in urls:
            put = False
            for s in grouped:
                if u.startswith(s):
                    grouped[s].append(u)
                    put = True
                    break
            if not put:
                grouped[site_urls[0].rstrip("/")].append(u)
        succ = 0
        fail = 0
        quota = self._load_quota()
        sites = self._today_sites(quota)
        for site, bucket in grouped.items():
            if stop_event and stop_event.is_set():
                self.logger.log("중지 요청 감지: 네이버 작업을 중단합니다.", "WARNING")
                break
            if not bucket:
                continue
            site_key = self._norm_site(site)
            st = sites.setdefault(site_key, {"used": 0, "success": 0, "failed": 0, "urls": []})
            remaining = max(0, self.daily_limit - int(st.get("used", 0) or 0))
            if remaining <= 0:
                self.logger.log(f"네이버 quota 소진(사이트): {site}", "WARNING")
                continue
            proc_bucket = bucket[:remaining]
            try:
                with NaverSeleniumService(logger=self.logger, headless=False) as svc:
                    if not svc.login_naver(username, password):
                        fail += len(proc_bucket)
                        st["failed"] = int(st.get("failed", 0) or 0) + len(proc_bucket)
                        continue
                    if not svc.navigate_to_search_advisor(site):
                        fail += len(proc_bucket)
                        st["failed"] = int(st.get("failed", 0) or 0) + len(proc_bucket)
                        continue
                    s, f = svc.submit_urls_for_crawling(
                        proc_bucket,
                        site,
                        {u: url_meta.get(u, {}) for u in proc_bucket},
                        stop_event=stop_event,
                        submit_order=submit_order,
                        username=username,
                        password=password,
                    )
                    succ += s
                    fail += f
                    attempted = min(len(proc_bucket), max(0, s + f))
                    st["used"] = int(st.get("used", 0) or 0) + attempted
                    st["success"] = int(st.get("success", 0) or 0) + s
                    st["failed"] = int(st.get("failed", 0) or 0) + f
                    site_urls = st.get("urls", [])
                    site_seen = set(site_urls)
                    for u in proc_bucket[:attempted]:
                        if u not in site_seen:
                            site_urls.append(u)
                            site_seen.add(u)
                    st["urls"] = site_urls
            except Exception as e:
                self.logger.log(f"{site} 네이버 Selenium 처리 예외: {type(e).__name__}: {e}", "ERROR")
                fail += len(proc_bucket)
                st["failed"] = int(st.get("failed", 0) or 0) + len(proc_bucket)
        self._save_quota(quota)
        return succ, fail


class IndexingController:
    def __init__(self):
        self.logger = IndexingLogger()
        self.config_manager = ConfigManager()
        self.url_manager = URLManager(self.logger)
        self.url_state = URLStateStore(self.logger)
        self.google_service = GoogleIndexingService(self.logger)
        self.naver_service = NaverIndexingService(self.logger)
        self.stop_event = Event()

    def stop_indexing(self):
        self.stop_event.set()
        self.url_manager.stop()
        self.logger.log("중지 요청이 접수되었습니다.", "WARNING")

    @staticmethod
    def _is_indexable_content_url(url: str) -> bool:
        try:
            p = urlparse((url or "").strip())
            if not p.scheme or not p.netloc:
                return False
            path = (p.path or "").strip()
            if path in ("", "/"):
                return False
            if path.startswith("//"):
                return False
            return True
        except Exception:
            return False

    def _filter_submission_targets(self, urls: List[str], service_name: str) -> List[str]:
        out: List[str] = []
        seen: Set[str] = set()
        skipped = 0
        for u in urls:
            if u in seen:
                continue
            seen.add(u)
            if self._is_indexable_content_url(u):
                out.append(u)
            else:
                skipped += 1
        if skipped > 0:
            self.logger.log(
                f"{service_name}: 홈(/) 또는 비정상 URL {skipped}개를 제출 대상에서 제외했습니다. "
                "(기준: 스킴/도메인 없음, 경로가 '/' 또는 비어 있음, 경로가 '//'로 시작)",
                "WARNING",
            )
        return out

    @staticmethod
    def _normalize_seed_items(items: Any, fallback_urls: Optional[List[str]], default_order: str) -> List[Dict[str, str]]:
        out: List[Dict[str, str]] = []
        seen: Set[str] = set()
        if isinstance(items, list):
            for it in items:
                if not isinstance(it, dict):
                    continue
                u = str(it.get("url", "") or "").strip()
                if not u or u in seen:
                    continue
                seen.add(u)
                o = str(it.get("order", default_order) or default_order).strip().lower()
                if o not in ("oldest", "newest"):
                    o = default_order
                enabled = it.get("enabled", True)
                if isinstance(enabled, str):
                    enabled = enabled.strip().lower() not in ("false", "0", "no", "off", "")
                else:
                    enabled = bool(enabled)
                if not enabled:
                    continue
                out.append({"url": u, "order": o})
        if not out:
            for raw in (fallback_urls or []):
                u = str(raw or "").strip()
                if not u or u in seen:
                    continue
                seen.add(u)
                out.append({"url": u, "order": default_order})
        return out

    def run_indexing(self, progress_callback=None, google_urls=None, naver_urls=None, service_to_run="all"):
        self.stop_event.clear()
        self.url_manager.stop_event.clear()
        cfg = self.config_manager.load_config(self.config_manager.password) or self.config_manager.load_config()
        if cfg is None:
            return {"total": 0, "google_success": 0, "naver_success": 0, "errors": 1, "scheduled": 0}
        default_order = str(cfg.get("submit_order", "oldest") or "oldest").strip().lower()
        if default_order not in ("oldest", "newest"):
            default_order = "oldest"
        google_seed_items = self._normalize_seed_items(cfg.get("google_site_items"), google_urls or [], default_order)
        naver_seed_items = self._normalize_seed_items(cfg.get("naver_site_items"), naver_urls or [], default_order)
        google_seeds = [it["url"] for it in google_seed_items]
        naver_seeds = [it["url"] for it in naver_seed_items]
        if service_to_run == "google" and not google_seeds:
            return {"total": 0, "google_success": 0, "naver_success": 0, "errors": 1, "scheduled": 0}
        if service_to_run == "naver" and not naver_seeds:
            return {"total": 0, "google_success": 0, "naver_success": 0, "errors": 1, "scheduled": 0}
        if service_to_run == "all" and not (google_seeds or naver_seeds):
            return {"total": 0, "google_success": 0, "naver_success": 0, "errors": 1, "scheduled": 0}
        daily_limit = int(cfg.get("daily_limit", 200) or 200)
        google_targets: List[str] = []
        naver_total_targets = 0
        scheduled = 0

        if service_to_run in ("google", "all"):
            if progress_callback:
                progress_callback("입력한 사이트에서 페이지 주소를 찾는 중...", 10)
            self.google_service.daily_limit = daily_limit
            crawled_set: Set[str] = set()
            crawled_dates: Dict[str, str] = {}
            crawled_titles: Dict[str, str] = {}
            total_google_sites = len(google_seed_items)
            for i, item in enumerate(google_seed_items, 1):
                if self.stop_event.is_set():
                    break
                site = item["url"]
                order = item["order"]
                self.logger.log(f"[{i}/{total_google_sites}] {site} 색인 자동화 시작")
                urls, dmap, tmap = self.url_manager.crawl_site(site, submit_order=order)
                crawled_set.update(urls)
                for u, dt in dmap.items():
                    prev = crawled_dates.get(u)
                    if prev is None or dt < prev:
                        crawled_dates[u] = dt
                for u, title in tmap.items():
                    if u not in crawled_titles and title:
                        crawled_titles[u] = title
            crawled = sorted(crawled_set)
            crawled_dates = {u: crawled_dates[u] for u in crawled if u in crawled_dates}
            crawled_titles = {u: crawled_titles[u] for u in crawled if u in crawled_titles}
            self.url_state.upsert_seen_urls(crawled, crawled_dates, crawled_titles)
            google_pending_total = self.url_state.pending_count("google")
            google_targets = self.url_state.get_pending_urls(
                "google",
                min(daily_limit, self.google_service.remaining()),
                submit_order=default_order,
            )
            google_targets = self._filter_submission_targets(google_targets, "구글")
            scheduled += max(0, google_pending_total - len(google_targets))

        res = {
            "total": len(google_targets),
            "google_success": 0,
            "naver_success": 0,
            "errors": 0,
            "scheduled": scheduled,
        }

        if service_to_run in ("naver", "all") and cfg.get("naver_enabled", True):
            self.naver_service.daily_limit = 50
            ordered_sites: List[str] = []
            seen_sites: Set[str] = set()
            for s in naver_seeds:
                u = (s or "").strip().rstrip("/")
                if u and u not in seen_sites:
                    seen_sites.add(u)
                    ordered_sites.append(u)
            site_order_map = {it["url"].rstrip("/"): it["order"] for it in naver_seed_items}
            total_sites = len(ordered_sites)
            for idx, site in enumerate(ordered_sites, 1):
                if self.stop_event.is_set():
                    break
                self.logger.log(f"[{idx}/{total_sites}] {site} 색인 자동화 시작")
                site_remaining = self.naver_service.remaining_for_site(site)
                self.logger.log(f"{site} 오늘 남은 할당량: {site_remaining}개")
                if site_remaining <= 0:
                    self.logger.log(f"{site} 오늘 할당량 소진으로 건너뜁니다.", "WARNING")
                    continue
                if progress_callback:
                    progress_callback(f"[{idx}/{total_sites}] {site} 페이지 주소를 찾는 중...", 60)

                site_crawled, site_dates, site_titles = self.url_manager.crawl_site(
                    site,
                    submit_order=site_order_map.get(site.rstrip("/"), default_order),
                )
                if not site_crawled:
                    self.logger.log(f"{site}에서 수집된 URL이 없습니다.", "WARNING")
                    continue
                site_crawled = self._filter_submission_targets(site_crawled, "네이버")
                if not site_crawled:
                    continue
                site_dates = {u: site_dates[u] for u in site_crawled if u in site_dates}
                site_titles = {u: site_titles[u] for u in site_crawled if u in site_titles}
                self.url_state.upsert_seen_urls(site_crawled, site_dates, site_titles)

                pending_for_site = self.url_state.pending_count_for_site("naver", site)
                site_targets = self.url_state.get_pending_urls_for_site(
                    "naver",
                    site,
                    site_remaining,
                    submit_order=site_order_map.get(site.rstrip("/"), default_order),
                )
                site_targets = self._filter_submission_targets(site_targets, "네이버")
                if len(site_targets) > site_remaining:
                    site_targets = site_targets[:site_remaining]
                if not site_targets:
                    self.logger.log(f"{site} 새로 요청할 URL이 없습니다.")
                    continue
                naver_total_targets += len(site_targets)
                res["scheduled"] += max(0, pending_for_site - len(site_targets))
                if progress_callback:
                    progress_callback(f"[{idx}/{total_sites}] {site} 네이버 색인 요청 중...", 75)

                ns, nf = self.naver_service.submit_selenium(
                    site_targets,
                    [site],
                    cfg.get("naver_username", ""),
                    cfg.get("naver_password", ""),
                    self.url_state.get_url_meta(site_targets),
                    stop_event=self.stop_event,
                    submit_order=site_order_map.get(site.rstrip("/"), default_order),
                )
                res["naver_success"] += ns
                res["errors"] += nf
                if ns > 0:
                    self.url_state.mark_submitted("naver", site_targets[:ns])
                if nf > 0 and not self.stop_event.is_set():
                    retry_remaining = self.naver_service.remaining_for_site(site)
                    if retry_remaining <= 0:
                        self.logger.log(f"{site} 재시도 건너뜀: 남은 할당량이 없습니다.", "WARNING")
                    else:
                        self.logger.log(
                            f"{site} 오류 URL 재시도를 위해 URL을 다시 수집합니다. (남은 할당량 {retry_remaining}개)",
                            "WARNING",
                        )
                        retry_crawled, retry_dates, retry_titles = self.url_manager.crawl_site(
                            site,
                            submit_order=site_order_map.get(site.rstrip("/"), default_order),
                        )
                        if retry_crawled:
                            retry_crawled = self._filter_submission_targets(retry_crawled, "네이버")
                            retry_dates = {u: retry_dates[u] for u in retry_crawled if u in retry_dates}
                            retry_titles = {u: retry_titles[u] for u in retry_crawled if u in retry_titles}
                            self.url_state.upsert_seen_urls(retry_crawled, retry_dates, retry_titles)
                        retry_pending_for_site = self.url_state.pending_count_for_site("naver", site)
                        retry_targets = self.url_state.get_pending_urls_for_site(
                            "naver",
                            site,
                            retry_remaining,
                            submit_order=site_order_map.get(site.rstrip("/"), default_order),
                        )
                        retry_targets = self._filter_submission_targets(retry_targets, "네이버")
                        if len(retry_targets) > retry_remaining:
                            retry_targets = retry_targets[:retry_remaining]
                        if not retry_targets:
                            self.logger.log(f"{site} 재수집 후 재시도할 URL이 없습니다.")
                        else:
                            naver_total_targets += len(retry_targets)
                            res["scheduled"] += max(0, retry_pending_for_site - len(retry_targets))
                            if progress_callback:
                                progress_callback(f"[{idx}/{total_sites}] {site} 재수집 URL 재시도 중...", 78)
                            rns, rnf = self.naver_service.submit_selenium(
                                retry_targets,
                                [site],
                                cfg.get("naver_username", ""),
                                cfg.get("naver_password", ""),
                                self.url_state.get_url_meta(retry_targets),
                                stop_event=self.stop_event,
                                submit_order=site_order_map.get(site.rstrip("/"), default_order),
                            )
                            res["naver_success"] += rns
                            res["errors"] += rnf
                            if rns > 0:
                                self.url_state.mark_submitted("naver", retry_targets[:rns])
                            self.logger.log(
                                f"{site} 재시도 완료: 성공 {rns}개 | 실패 {rnf}개",
                                "SUCCESS" if rnf == 0 else "WARNING",
                            )

            res["total"] += naver_total_targets

        if res["total"] == 0:
            if progress_callback:
                progress_callback("새로 등록할 주소가 없습니다.", 100)
            return {"total": 0, "google_success": 0, "naver_success": 0, "errors": 0, "scheduled": 0}

        if service_to_run in ("google", "all") and cfg.get("google_enabled", True) and not self.stop_event.is_set():
            if progress_callback:
                progress_callback("구글에 검색 등록 요청 중...", 45)
            key_files = cfg.get("google_service_account_files")
            if not isinstance(key_files, list) or not key_files:
                key_files = GoogleIndexingService.parse_service_account_files(cfg.get("google_service_account_file", "service-account-key.json"))
            remaining_targets = list(google_targets)
            submitted: List[str] = []
            any_initialized = False
            for key_path in key_files:
                if self.stop_event.is_set() or not remaining_targets:
                    break
                key = str(key_path or "").strip()
                if not key:
                    continue
                if not self.google_service.initialize(key):
                    continue
                any_initialized = True
                gs, _gf = self.google_service.submit_urls(remaining_targets, use_batch=cfg.get("use_batch_api", True))
                if gs <= 0:
                    continue
                done = remaining_targets[:gs]
                submitted.extend(done)
                remaining_targets = remaining_targets[gs:]
                res["google_success"] += gs
            if submitted:
                self.url_state.mark_submitted("google", submitted)
            if not any_initialized:
                res["errors"] += len(google_targets)
            else:
                res["errors"] += len(remaining_targets)
        if progress_callback:
            progress_callback("완료", 100)
        self.logger.log(
            f"작업 완료: 전체 {res['total']}개 | 구글 성공 {res['google_success']}개 | 네이버 성공 {res['naver_success']}개 | 오류 {res['errors']}개",
            "SUCCESS",
        )
        return res

if GUI_AVAILABLE:
    WP_COLORS = {
        "primary": "#0073aa",
        "primary_hover": "#005177",
        "accent": "#00a0d2",
        "surface": "#2d2d2d",
        "surface_light": "#383838",
        "background": "#1e1e1e",
        "text": "#ffffff",
        "text_muted": "#cfd6de",
        "border": "#4a5568",
        "success": "#46b450",
        "warning": "#ffb900",
        "danger": "#dc3232",
    }

    class GlassButton(QPushButton):
        def __init__(self, text, button_type="primary", parent=None):
            super().__init__(text, parent)
            self.button_type = button_type
            self.setMinimumHeight(42)
            self.setFont(QFont("맑은 고딕", 10, QFont.Weight.Bold))
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self._update_style()

        def _update_style(self):
            color_map = {
                "primary": (WP_COLORS["primary"], WP_COLORS["primary_hover"]),
                "success": (WP_COLORS["success"], "#3d9946"),
                "warning": (WP_COLORS["warning"], "#e0a400"),
                "danger": (WP_COLORS["danger"], "#c42d2d"),
                "secondary": (WP_COLORS["surface_light"], WP_COLORS["primary"]),
                "add": ("#7C3AED", "#6D28D9"),
            }
            base, hover = color_map.get(self.button_type, color_map["primary"])
            text_color = WP_COLORS["text"]
            self.setStyleSheet(
                f"""
                QPushButton {{
                    background-color: {base};
                    color: {text_color};
                    border: none;
                    border-radius: 8px;
                    padding: 10px 16px;
                    font-weight: 700;
                }}
                QPushButton:hover {{
                    background-color: {hover};
                }}
                QPushButton:pressed {{
                    background-color: {WP_COLORS['accent']};
                }}
                QPushButton:disabled {{
                    background-color: {WP_COLORS['border']};
                    color: {WP_COLORS['text_muted']};
                }}
                """
            )

    class GlassLineEdit(QLineEdit):
        multiline_urls_pasted = pyqtSignal(str)

        def __init__(self, placeholder="", parent=None):
            super().__init__(parent)
            self.setPlaceholderText(placeholder)
            self.setMinimumHeight(36)
            self.setFont(QFont("맑은 고딕", 10))

        @staticmethod
        def _clipboard_text() -> str:
            try:
                cb = QApplication.clipboard()
                return str(cb.text() or "") if cb is not None else ""
            except Exception:
                return ""

        @staticmethod
        def _is_multiline_text(text: str) -> bool:
            return ("\n" in str(text or "")) or ("\r" in str(text or ""))

        def keyPressEvent(self, event):
            if event is not None and event.matches(QKeySequence.StandardKey.Paste):
                raw = self._clipboard_text()
                if self._is_multiline_text(raw):
                    self.multiline_urls_pasted.emit(raw)
                    return
            super().keyPressEvent(event)

        def paste(self):
            raw = self._clipboard_text()
            if self._is_multiline_text(raw):
                self.multiline_urls_pasted.emit(raw)
                return
            super().paste()

    class GlassTextEdit(QTextBrowser):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setFont(QFont("맑은 고딕", 11))
            self.setOpenExternalLinks(False)
            self.setOpenLinks(False)

    class IndexingWorker(QThread):
        progress_updated = pyqtSignal(str, str, int)
        finished = pyqtSignal(str, dict)

        def __init__(self, controller: IndexingController, urls: List[str], service_type: str):
            super().__init__()
            self.controller = controller
            self.urls = urls
            self.service_type = service_type

        def run(self):
            try:
                if self.service_type == "google":
                    r = self.controller.run_indexing(
                        progress_callback=lambda m, p: self.progress_updated.emit("google", m, p),
                        google_urls=self.urls,
                        service_to_run="google",
                    )
                    self.finished.emit("google", {"total": r.get("total", 0), "success": r.get("google_success", 0), "errors": r.get("errors", 0), "scheduled": r.get("scheduled", 0)})
                else:
                    r = self.controller.run_indexing(
                        progress_callback=lambda m, p: self.progress_updated.emit("naver", m, p),
                        naver_urls=self.urls,
                        service_to_run="naver",
                    )
                    self.finished.emit("naver", {"total": r.get("total", 0), "success": r.get("naver_success", 0), "errors": r.get("errors", 0), "scheduled": r.get("scheduled", 0)})
            except Exception as e:
                service_label = "구글" if self.service_type == "google" else "네이버"
                self.controller.logger.log(f"{service_label} 작업 중 예외가 발생했습니다: {type(e).__name__}: {e}", "ERROR")
                self.finished.emit(self.service_type, {"total": 0, "success": 0, "errors": 1, "scheduled": 0})

    class ModernIndexingGUI(QMainWindow):
        error_logged = pyqtSignal(str, str)

        def __init__(self, usage_period_text: str = "확인 필요"):
            super().__init__()
            self.controller = IndexingController()
            self.google_worker: Optional[IndexingWorker] = None
            self.naver_worker: Optional[IndexingWorker] = None
            self._active_error_details: Dict[str, List[str]] = {"google": [], "naver": []}
            self._completed_error_details: Dict[str, List[Dict[str, Any]]] = {"google": [], "naver": []}
            self.current_config = self.controller.config_manager.default_config.copy()
            self.usage_period_text = usage_period_text
            self._notice_boxes: List[QMessageBox] = []
            self.error_logged.connect(self._on_error_logged)
            self.init_ui()
            if not self.initialize_encryption_and_load_config():
                QTimer.singleShot(100, self.close)
                return
            self._show_usage_guides()
            self._setup_daily_auto_cycle_timer()

        def _setup_daily_auto_cycle_timer(self):
            self._app_started_ts = time.time()
            self._next_daily_cycle_ts = self._app_started_ts + 86400
            self._daily_cycle_pending = False
            self._daily_cycle_timer = QTimer(self)
            self._daily_cycle_timer.setInterval(10000)
            self._daily_cycle_timer.timeout.connect(self._check_daily_auto_cycle)
            self._daily_cycle_timer.start()

        def _any_worker_running(self) -> bool:
            return bool(
                (self.google_worker and self.google_worker.isRunning())
                or (self.naver_worker and self.naver_worker.isRunning())
            )

        def _check_daily_auto_cycle(self):
            now = time.time()
            should_trigger = now >= self._next_daily_cycle_ts or self._daily_cycle_pending
            if not should_trigger:
                return

            if self._any_worker_running():
                if not self._daily_cycle_pending:
                    self._daily_cycle_pending = True
                    self._append_log("google", "ℹ️ 24시간 주기 자동 실행 대기 중 (현재 작업이 끝나면 시작)")
                    self._append_log("naver", "ℹ️ 24시간 주기 자동 실행 대기 중 (현재 작업이 끝나면 시작)")
                return

            while self._next_daily_cycle_ts <= now:
                self._next_daily_cycle_ts += 86400
            self._daily_cycle_pending = False
            self._run_daily_auto_cycle()

        def _run_daily_auto_cycle(self):
            self.save_all_configs()
            self._append_log("google", "ℹ️ 24시간 경과로 자동 색인 작업을 시작합니다.")
            self._append_log("naver", "ℹ️ 24시간 경과로 자동 색인 작업을 시작합니다.")
            self.start_google_indexing(silent=True)
            self.start_naver_indexing(silent=True)

        def init_ui(self):
            self.setWindowTitle("Auto_Indexing - 구글 + 네이버 색인 자동화")
            self.setGeometry(100, 80, 1450, 920)
            _apply_window_icon(self)
            self.setStyleSheet(
                f"""
                QMainWindow {{
                    background-color: {WP_COLORS['background']};
                    color: {WP_COLORS['text']};
                }}
                QLabel {{
                    color: {WP_COLORS['text']};
                    font-size: 14px;
                }}
                QLineEdit {{
                    background-color: {WP_COLORS['surface']};
                    border: 2px solid {WP_COLORS['border']};
                    border-radius: 8px;
                    padding: 8px 12px;
                    color: {WP_COLORS['text']};
                }}
                QLineEdit:focus {{
                    border-color: {WP_COLORS['primary']};
                }}
                QTextEdit {{
                    background-color: {WP_COLORS['surface']};
                    border: 2px solid {WP_COLORS['border']};
                    border-radius: 10px;
                    padding: 8px;
                    color: {WP_COLORS['text']};
                }}
                QTextEdit:focus {{
                    border-color: {WP_COLORS['primary']};
                }}
                QProgressBar {{
                    border: 1px solid {WP_COLORS['border']};
                    border-radius: 6px;
                    background-color: {WP_COLORS['surface']};
                    color: {WP_COLORS['text']};
                    text-align: center;
                }}
                QProgressBar::chunk {{
                    border-radius: 6px;
                    background-color: {WP_COLORS['primary']};
                }}
                QTabWidget::pane {{
                    border: 1px solid {WP_COLORS['border']};
                    border-radius: 8px;
                    background-color: {WP_COLORS['surface']};
                    margin-top: 2px;
                }}
                QTabBar::tab {{
                    background-color: {WP_COLORS['surface_light']};
                    color: {WP_COLORS['text_muted']};
                    padding: 11px 22px;
                    margin-right: 2px;
                    border: 1px solid {WP_COLORS['border']};
                    border-bottom: none;
                    border-top-left-radius: 8px;
                    border-top-right-radius: 8px;
                    font-weight: 600;
                }}
                QTabBar::tab:selected {{
                    background-color: {WP_COLORS['primary']};
                    color: white;
                    border-color: {WP_COLORS['primary']};
                }}
                QTabBar::tab:hover:!selected {{
                    background-color: {WP_COLORS['primary_hover']};
                    color: white;
                }}
                QGroupBox {{
                    font-weight: 700;
                    font-size: 14px;
                    color: {WP_COLORS['text']};
                    border: 2px solid {WP_COLORS['border']};
                    border-radius: 14px;
                    margin-top: 12px;
                    padding-top: 16px;
                    background-color: {WP_COLORS['surface']};
                }}
                QGroupBox::title {{
                    subcontrol-origin: margin;
                    left: 12px;
                    padding: 0 8px;
                    color: {WP_COLORS['accent']};
                    background-color: {WP_COLORS['surface']};
                }}
                """
            )
            central = QWidget(self)
            self.setCentralWidget(central)
            main = QVBoxLayout(central)
            self.tabs = QTabWidget()
            self.usage_period_label = QLabel(f"사용 기간: {self.usage_period_text}")
            self.usage_period_label.setStyleSheet(
                f"color: {WP_COLORS['text_muted']}; font-size: 12px; padding-right: 10px;"
            )
            self.tabs.setCornerWidget(self.usage_period_label, Qt.Corner.TopRightCorner)
            main.addWidget(self.tabs, 1)
            self.tabs.addTab(self._build_google_tab(), "구글 색인 자동화")
            self.tabs.addTab(self._build_naver_tab(), "네이버 색인 자동화")
            foot = QHBoxLayout()
            self.status_label = QLabel("준비 완료")
            self.progress_bar = QProgressBar()
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)
            foot.addWidget(self.status_label, 1)
            foot.addWidget(self.progress_bar, 2)
            main.addLayout(foot)

        def _build_google_tab(self):
            tab = QWidget()
            layout = QVBoxLayout(tab)
            settings = QGroupBox("구글 연결 설정")
            grid = QGridLayout(settings)
            grid.addWidget(QLabel("JSON 파일"), 0, 0)
            self.google_service_file_input = GlassLineEdit("service-account-key.json")
            file_row = QWidget()
            file_row_layout = QHBoxLayout(file_row)
            file_row_layout.setContentsMargins(0, 0, 0, 0)
            file_row_layout.setSpacing(8)
            file_row_layout.addWidget(self.google_service_file_input, 1)
            self.google_key_upload_btn = GlassButton("업로드", "secondary")
            self.google_key_upload_btn.clicked.connect(lambda: self._run_action_with_notice(self._upload_google_key_file, "파일 업로드가 완료되었습니다."))
            self.google_key_add_btn = GlassButton("+추가", "add")
            self.google_key_add_btn.clicked.connect(lambda: self._run_action_with_notice(self._append_google_key_files, "파일 추가가 완료되었습니다."))
            self.google_key_clear_btn = GlassButton("삭제", "danger")
            self.google_key_clear_btn.clicked.connect(lambda: self._run_action_with_notice(self._clear_google_key_file, "파일 삭제가 완료되었습니다."))
            file_row_layout.addWidget(self.google_key_upload_btn, 0)
            file_row_layout.addWidget(self.google_key_add_btn, 0)
            file_row_layout.addWidget(self.google_key_clear_btn, 0)
            grid.addWidget(file_row, 0, 1)
            self.google_key_extra_widget = QWidget()
            self.google_key_extra_layout = QVBoxLayout(self.google_key_extra_widget)
            self.google_key_extra_layout.setContentsMargins(0, 6, 0, 0)
            self.google_key_extra_layout.setSpacing(6)
            self.google_key_extra_rows: List[Dict[str, Any]] = []
            grid.addWidget(self.google_key_extra_widget, 1, 1)
            layout.addWidget(settings)
            seeds = QGroupBox("색인 요청할 도메인 URL")
            s = QVBoxLayout(seeds)
            self.google_seed_rows: List[Dict[str, Any]] = []
            self.google_seed_urls_widget = QWidget()
            self.google_seed_urls_layout = QVBoxLayout(self.google_seed_urls_widget)
            self.google_seed_urls_layout.setContentsMargins(0, 0, 0, 0)
            self.google_seed_urls_layout.setSpacing(8)
            self.google_seed_urls_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
            self.google_seed_scroll = QScrollArea()
            self.google_seed_scroll.setWidgetResizable(True)
            self.google_seed_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self.google_seed_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            self.google_seed_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
            self.google_seed_scroll.setWidget(self.google_seed_urls_widget)
            self.google_seed_scroll.setMinimumHeight(240)
            seed_btn_row = QHBoxLayout()
            self.google_add_seed_btn = GlassButton("+ 추가", "add")
            self.google_add_seed_btn.clicked.connect(lambda: self._add_seed_url_input("google"))
            seed_btn_row.addWidget(self.google_add_seed_btn, 0, Qt.AlignmentFlag.AlignLeft)
            self.google_seed_count_label = QLabel("총 URL 0개")
            self.google_seed_count_label.setStyleSheet(f"color: {WP_COLORS['text_muted']}; font-size: 18px; font-weight: 700;")
            seed_btn_row.addWidget(self.google_seed_count_label, 0, Qt.AlignmentFlag.AlignLeft)
            seed_btn_row.addStretch(1)
            s.addLayout(seed_btn_row)
            s.addWidget(self.google_seed_scroll, 1)
            self._add_seed_url_input("google")
            log_group = QGroupBox("진행 현황")
            gl = QVBoxLayout(log_group)
            google_log_top = QHBoxLayout()
            google_log_top.addStretch(1)
            self.google_error_detail_btn = GlassButton("오류 상세", "secondary")
            self.google_error_detail_btn.clicked.connect(lambda: self._show_error_details_dialog("google"))
            google_log_top.addWidget(self.google_error_detail_btn, 0)
            gl.addLayout(google_log_top)
            self.google_log = GlassTextEdit()
            self.google_log.setReadOnly(True)
            self.google_log.textChanged.connect(lambda: self._scroll_log_to_bottom(self.google_log))
            self.google_log.anchorClicked.connect(self._handle_log_link_clicked)
            gl.addWidget(self.google_log)
            split_row = QHBoxLayout()
            split_row.setSpacing(12)
            split_row.addWidget(seeds, 1)
            split_row.addWidget(log_group, 1)
            layout.addLayout(split_row, 1)
            row = QHBoxLayout()
            self.google_start_btn = GlassButton("▶ 구글 등록 시작", "primary")
            self.google_stop_btn = GlassButton("⏹ 중지", "danger")
            for b in [self.google_start_btn, self.google_stop_btn]:
                row.addWidget(b)
            layout.addLayout(row)
            self.google_start_btn.clicked.connect(self.start_google_indexing)
            self.google_stop_btn.clicked.connect(lambda: self._run_action_with_notice(lambda: self.stop_indexing("google"), "중지 요청이 완료되었습니다."))
            return tab

        def _build_naver_tab(self):
            tab = QWidget()
            layout = QVBoxLayout(tab)
            settings = QGroupBox("네이버 계정 설정")
            row = QHBoxLayout(settings)
            self.naver_username_input = GlassLineEdit()
            self.naver_password_input = GlassLineEdit()
            self.naver_password_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.naver_password_input.returnPressed.connect(self._save_from_password_enter)
            row.addWidget(QLabel("네이버 로그인 아이디"))
            row.addWidget(self.naver_username_input, 2)
            row.addWidget(QLabel("네이버 비밀번호"))
            row.addWidget(self.naver_password_input, 2)
            self.naver_password_toggle_btn = GlassButton("공개", "secondary")
            self.naver_password_toggle_btn.clicked.connect(lambda: self._run_action_with_notice(self._toggle_naver_password_visibility, "비밀번호 표시 설정이 완료되었습니다."))
            row.addWidget(self.naver_password_toggle_btn)
            self.naver_settings_save_btn = GlassButton("저장", "success")
            self.naver_settings_save_btn.clicked.connect(lambda: self._run_action_with_notice(self.save_all_configs, "저장이 완료되었습니다."))
            row.addWidget(self.naver_settings_save_btn)
            layout.addWidget(settings)
            seed_group = QGroupBox("색인 요청할 도메인 URL")
            sd = QVBoxLayout(seed_group)
            self.naver_seed_rows: List[Dict[str, Any]] = []
            self.naver_seed_urls_widget = QWidget()
            self.naver_seed_urls_layout = QVBoxLayout(self.naver_seed_urls_widget)
            self.naver_seed_urls_layout.setContentsMargins(0, 0, 0, 0)
            self.naver_seed_urls_layout.setSpacing(8)
            self.naver_seed_urls_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
            self.naver_seed_scroll = QScrollArea()
            self.naver_seed_scroll.setWidgetResizable(True)
            self.naver_seed_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self.naver_seed_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            self.naver_seed_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
            self.naver_seed_scroll.setWidget(self.naver_seed_urls_widget)
            self.naver_seed_scroll.setMinimumHeight(240)
            seed_btn_row = QHBoxLayout()
            self.naver_add_seed_btn = GlassButton("+ 추가", "add")
            self.naver_add_seed_btn.clicked.connect(lambda: self._add_seed_url_input("naver"))
            seed_btn_row.addWidget(self.naver_add_seed_btn, 0, Qt.AlignmentFlag.AlignLeft)
            self.naver_seed_count_label = QLabel("총 URL 0개")
            self.naver_seed_count_label.setStyleSheet(f"color: {WP_COLORS['text_muted']}; font-size: 18px; font-weight: 700;")
            seed_btn_row.addWidget(self.naver_seed_count_label, 0, Qt.AlignmentFlag.AlignLeft)
            seed_btn_row.addStretch(1)
            sd.addLayout(seed_btn_row)
            sd.addWidget(self.naver_seed_scroll, 1)
            self._add_seed_url_input("naver")
            log_group = QGroupBox("진행 현황")
            nl = QVBoxLayout(log_group)
            naver_log_top = QHBoxLayout()
            naver_log_top.addStretch(1)
            self.naver_error_detail_btn = GlassButton("오류 상세", "secondary")
            self.naver_error_detail_btn.clicked.connect(lambda: self._show_error_details_dialog("naver"))
            naver_log_top.addWidget(self.naver_error_detail_btn, 0)
            nl.addLayout(naver_log_top)
            self.naver_log = GlassTextEdit()
            self.naver_log.setReadOnly(True)
            self.naver_log.textChanged.connect(lambda: self._scroll_log_to_bottom(self.naver_log))
            self.naver_log.anchorClicked.connect(self._handle_log_link_clicked)
            nl.addWidget(self.naver_log)
            split_row = QHBoxLayout()
            split_row.setSpacing(12)
            split_row.addWidget(seed_group, 1)
            split_row.addWidget(log_group, 1)
            layout.addLayout(split_row, 1)
            row = QHBoxLayout()
            self.naver_start_btn = GlassButton("▶ 네이버 색인 요청", "primary")
            self.naver_stop_btn = GlassButton("⏹ 중지", "danger")
            for b in [self.naver_start_btn, self.naver_stop_btn]:
                row.addWidget(b)
            layout.addLayout(row)
            self.naver_start_btn.clicked.connect(self.start_naver_indexing)
            self.naver_stop_btn.clicked.connect(lambda: self._run_action_with_notice(lambda: self.stop_indexing("naver"), "중지 요청이 완료되었습니다."))
            return tab

        @staticmethod
        def _lines(text: str) -> List[str]:
            seen, out = set(), []
            for ln in text.splitlines():
                u = ln.strip()
                if u and not u.startswith("#") and u not in seen:
                    seen.add(u)
                    out.append(u)
            return out

        @staticmethod
        def _normalize_order_value(value: str) -> str:
            v = str(value or "").strip().lower()
            return v if v in ("oldest", "newest") else "oldest"

        @staticmethod
        def _order_label(value: str) -> str:
            return "가장 최신 글부터" if value == "newest" else "가장 오래된 글부터"

        def _add_seed_url_input(self, service: str, value: str = "", order: str = "oldest", enabled: bool = True):
            order = self._normalize_order_value(order)
            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(8)
            inp = GlassLineEdit("https://example.com")
            inp.setText((value or "").strip())
            inp.returnPressed.connect(self._save_from_seed_enter)
            inp.textChanged.connect(lambda _t, svc=service: self._refresh_seed_url_count_label(svc))
            order_combo = QComboBox()
            order_combo.addItem("가장 오래된 글부터", "oldest")
            order_combo.addItem("가장 최신 글부터", "newest")
            order_combo.setCurrentIndex(1 if order == "newest" else 0)
            order_combo.setMinimumWidth(170)
            enabled_chk = QCheckBox("활성화")
            enabled_chk.setChecked(bool(enabled))
            enabled_chk.stateChanged.connect(lambda _s, svc=service: self._refresh_seed_url_count_label(svc))
            inp.multiline_urls_pasted.connect(
                lambda raw, svc=service, target_inp=inp, target_order=order_combo, target_enabled=enabled_chk: self._handle_seed_multiline_paste(
                    svc, target_inp, target_order, target_enabled, raw
                )
            )
            row_layout.addWidget(inp, 1)
            row_layout.addWidget(enabled_chk, 0)
            row_layout.addWidget(order_combo, 0)
            if service == "google":
                self.google_seed_rows.append({"widget": row_widget, "input": inp, "enabled": enabled_chk, "order": order_combo})
                self.google_seed_urls_layout.addWidget(row_widget)
                QTimer.singleShot(0, lambda: self._scroll_seed_to_bottom("google"))
            else:
                self.naver_seed_rows.append({"widget": row_widget, "input": inp, "enabled": enabled_chk, "order": order_combo})
                self.naver_seed_urls_layout.addWidget(row_widget)
                QTimer.singleShot(0, lambda: self._scroll_seed_to_bottom("naver"))
            self._refresh_seed_url_count_label(service)

        def _handle_seed_multiline_paste(self, service: str, target_inp: QLineEdit, target_order: QComboBox, target_enabled: QCheckBox, raw_text: str):
            urls = self._lines(str(raw_text or "").replace("\r", "\n"))
            if not urls:
                return
            current_order = self._normalize_order_value(str(target_order.currentData() or "oldest"))
            current_enabled = bool(target_enabled.isChecked())
            target_inp.setText(urls[0])
            for u in urls[1:]:
                self._add_seed_url_input(service, u, current_order, current_enabled)
            self._refresh_seed_url_count_label(service)

        def _refresh_seed_url_count_label(self, service: str):
            count = len(self._collect_seed_items(service))
            if service == "google":
                if hasattr(self, "google_seed_count_label") and self.google_seed_count_label is not None:
                    self.google_seed_count_label.setText(f"총 URL {count}개")
            else:
                if hasattr(self, "naver_seed_count_label") and self.naver_seed_count_label is not None:
                    self.naver_seed_count_label.setText(f"총 URL {count}개")

        def _scroll_seed_to_bottom(self, service: str):
            scroll = self.google_seed_scroll if service == "google" else self.naver_seed_scroll
            sb = getattr(scroll, "verticalScrollBar", None)
            if callable(sb):
                bar = sb()
                if bar is not None:
                    maximum_fn = getattr(bar, "maximum", None)
                    set_value_fn = getattr(bar, "setValue", None)
                    if callable(maximum_fn) and callable(set_value_fn):
                        set_value_fn(maximum_fn())

        def _set_seed_items(self, service: str, items: List[Dict[str, Any]]):
            rows = self.google_seed_rows if service == "google" else self.naver_seed_rows
            while rows:
                r = rows.pop()
                w = r.get("widget")
                if w is not None:
                    w.deleteLater()
            if items:
                for it in items:
                    self._add_seed_url_input(
                        service,
                        it.get("url", ""),
                        it.get("order", "oldest"),
                        bool(it.get("enabled", True)),
                    )
            else:
                self._add_seed_url_input(service)
            self._refresh_seed_url_count_label(service)

        def _collect_seed_urls(self, service: str) -> List[str]:
            return [it["url"] for it in self._collect_seed_items(service, only_enabled=True)]

        def _collect_seed_items(self, service: str, only_enabled: bool = False) -> List[Dict[str, Any]]:
            seen, out = set(), []
            rows = self.google_seed_rows if service == "google" else self.naver_seed_rows
            for row in rows:
                inp = row.get("input")
                enabled_chk = row.get("enabled")
                cb = row.get("order")
                if inp is None or enabled_chk is None or cb is None:
                    continue
                u = inp.text().strip()
                enabled = bool(enabled_chk.isChecked())
                if u and u not in seen:
                    seen.add(u)
                    if only_enabled and not enabled:
                        continue
                    out.append(
                        {
                            "url": u,
                            "enabled": enabled,
                            "order": self._normalize_order_value(str(cb.currentData() or "oldest")),
                        }
                    )
            return out

        def _append_log(self, service: str, message: str):
            target = self.google_log if service == "google" else self.naver_log
            target.append(message)
            self._scroll_log_to_bottom(target)

        def _service_label(self, service: str) -> str:
            return "구글" if service == "google" else "네이버"

        def _strip_error_line(self, message: str) -> str:
            text = str(message or "").strip()
            text = re.sub(r"^\[[^\]]+\]\s*", "", text)
            text = re.sub(r"^[❌⚠️ℹ️✅\s]+", "", text)
            return text or "오류 메시지를 확인할 수 없습니다."

        def _resolve_troubleshooting_tip(self, service: str, error_text: str) -> str:
            low = error_text.lower()
            if "service account file not found" in low or ("json" in low and "not found" in low):
                return "JSON 키 파일 경로를 다시 확인하고 파일이 실제로 존재하는지 점검하세요."
            if "google api library missing" in low:
                return "환경에 google-api-python-client, google-auth를 설치한 뒤 프로그램을 재실행하세요."
            if "quota" in low or "할당량" in error_text:
                return "오늘 할당량을 확인하고, 남은 할당량이 없으면 다음 주기까지 대기하거나 계정을 추가하세요."
            if service == "naver" and ("login" in low or "로그인" in error_text):
                return "네이버 아이디/비밀번호와 서치어드바이저 등록 계정 일치 여부를 확인하고, 브라우저 추가 인증 여부를 점검하세요."
            if "403" in low or "permission" in low or "권한" in error_text:
                return "권한 설정을 점검하세요. 구글은 Search Console 사용자/권한 연결 상태를 확인하는 것이 우선입니다."
            return "로그의 오류 원문을 확인한 뒤 설정 저장 후 재시도하세요. 동일하면 아래 메시지를 데이비에게 전달하세요."

        def _build_david_message(self, service: str, error_text: str, tip: str) -> str:
            return (
                "[Auto_Indexing 오류 전달]\n"
                f"- 발생 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"- 서비스: {self._service_label(service)}\n"
                f"- 오류 내용: {error_text}\n"
                f"- 1차 해결 방법: {tip}\n"
                f"- 로그 파일 위치: {LOG_FILE}\n"
                "- 위 내용 확인 부탁드립니다."
            )

        def _on_error_logged(self, service: str, message: str):
            # Keep a per-run error snapshot and show an actionable contact dialog on error.
            self._ensure_error_visible_in_progress(service, message)
            self._record_active_error_detail(service, message)
            self._show_error_contact_dialog(service, message)

        def _ensure_error_visible_in_progress(self, service: str, message: str):
            target = self.google_log if service == "google" else self.naver_log
            line = str(message or "").strip()
            if not line or target is None:
                return
            lines = [ln.strip() for ln in target.toPlainText().splitlines() if ln.strip()]
            if not lines or lines[-1] != line:
                self._append_log(service, line)

        def _show_error_contact_dialog(self, service: str, message: str):
            service_label = self._service_label(service)
            error_text = self._strip_error_line(message)
            tip = self._resolve_troubleshooting_tip(service, error_text)
            payload = self._build_david_message(service, error_text, tip)

            dlg = QDialog(self)
            dlg.setWindowTitle(f"{service_label} 오류 안내")
            dlg.resize(760, 460)
            layout = QVBoxLayout(dlg)

            title = QLabel("오류가 발생했습니다. 아래 내용을 복사해 전달해주세요.")
            title.setWordWrap(True)
            layout.addWidget(title, 0)

            message_box = GlassTextEdit(dlg)
            message_box.setPlainText(payload)
            message_box.setReadOnly(True)
            layout.addWidget(message_box, 1)

            btn_row = QHBoxLayout()
            btn_row.addStretch(1)
            copy_btn = GlassButton("복사", "secondary")
            close_btn = GlassButton("확인", "primary")
            btn_row.addWidget(copy_btn)
            btn_row.addWidget(close_btn)
            layout.addLayout(btn_row)

            def _copy_payload():
                cb = QApplication.clipboard()
                if cb is not None:
                    cb.setText(payload)
                copy_btn.setText("복사됨")
                QTimer.singleShot(900, lambda: copy_btn.setText("복사"))

            copy_btn.clicked.connect(_copy_payload)
            close_btn.clicked.connect(dlg.accept)
            dlg.exec()

        @staticmethod
        def _unique_preserve_order(lines: List[str]) -> List[str]:
            seen: Set[str] = set()
            out: List[str] = []
            for line in lines:
                text = str(line or "").strip()
                if not text or text in seen:
                    continue
                seen.add(text)
                out.append(text)
            return out

        def _reset_active_error_details(self, service: str):
            self._active_error_details[service] = []

        def _record_active_error_detail(self, service: str, message: str):
            text = str(message or "").strip()
            if not text:
                return
            bag = self._active_error_details.setdefault(service, [])
            if text not in bag:
                bag.append(text)

        def _latest_service_summary_line(self, service: str) -> str:
            target = self.google_log if service == "google" else self.naver_log
            lines = [ln.strip() for ln in target.toPlainText().splitlines() if ln.strip()]
            for ln in reversed(lines):
                if "작업 완료: 전체 " in ln:
                    return ln
            return ""

        def _snapshot_completed_error_details(self, service: str, total_errors: int):
            details = self._unique_preserve_order(self._active_error_details.get(service, []))
            snapshot = {
                "summary": self._latest_service_summary_line(service),
                "total_errors": int(total_errors or 0),
                "details": details,
            }
            history = self._completed_error_details.setdefault(service, [])
            history.append(snapshot)
            if len(history) > 30:
                del history[:-30]
            self._reset_active_error_details(service)

        def _resolve_snapshot_details(self, service: str, summary: str) -> List[str]:
            history = self._completed_error_details.get(service, [])
            if not history:
                return []
            for snap in reversed(history):
                if str(snap.get("summary", "") or "").strip() == summary.strip():
                    details = snap.get("details", [])
                    return details if isinstance(details, list) else []
            latest = history[-1]
            details = latest.get("details", [])
            return details if isinstance(details, list) else []

        def _extract_last_run_error_details(self, service: str) -> Dict[str, Any]:
            target = self.google_log if service == "google" else self.naver_log
            lines = [ln.strip() for ln in target.toPlainText().splitlines() if ln.strip()]
            completed_indexes = [i for i, ln in enumerate(lines) if "작업 완료: 전체 " in ln]
            if not completed_indexes:
                return {"ok": False, "message": "아직 완료된 작업 로그가 없습니다."}
            last_idx = completed_indexes[-1]
            prev_idx = completed_indexes[-2] if len(completed_indexes) >= 2 else -1
            run_lines = lines[prev_idx + 1 : last_idx + 1]
            summary_line = lines[last_idx]
            m = re.search(r"오류\s+(\d+)개", summary_line)
            total_errors = int(m.group(1)) if m else 0
            hard_errors = [ln for ln in run_lines if "❌" in ln]
            submit_failures = [ln for ln in run_lines if "요청 내역 반영 확인 실패:" in ln]
            details = self._unique_preserve_order(hard_errors + submit_failures)
            if total_errors > 0:
                details = self._unique_preserve_order(details + self._resolve_snapshot_details(service, summary_line))
            return {
                "ok": True,
                "summary": summary_line,
                "total_errors": total_errors,
                "details": details,
            }

        def _show_error_details_dialog(self, service: str):
            payload = self._extract_last_run_error_details(service)
            service_label = self._service_label(service)
            if not payload.get("ok"):
                QMessageBox.information(self, f"{service_label} 오류 상세", str(payload.get("message", "오류 상세가 없습니다.")))
                return
            summary = str(payload.get("summary", "") or "")
            total_errors = int(payload.get("total_errors", 0) or 0)
            details = payload.get("details", []) or []
            if not isinstance(details, list):
                details = []

            dlg = QDialog(self)
            dlg.setWindowTitle(f"{service_label} 오류 상세")
            dlg.resize(920, 620)
            layout = QVBoxLayout(dlg)

            summary_label = QLabel(f"마지막 완료 요약\n{summary}")
            summary_label.setWordWrap(True)
            layout.addWidget(summary_label, 0)

            browser = QTextBrowser(dlg)
            browser.setOpenExternalLinks(False)
            browser.setOpenLinks(False)
            if total_errors <= 0:
                browser.setPlainText("마지막 완료 작업의 오류 수가 0개입니다.")
            elif details:
                rendered = [f"[{i}] {ln}" for i, ln in enumerate(details, 1)]
                browser.setPlainText("\n".join(rendered))
            else:
                browser.setPlainText(
                    "오류 개수는 집계됐지만 화면용 오류 원문을 찾지 못했습니다.\n"
                    "다음 실행부터는 원문이 자동 수집되어 이 창에 바로 표시됩니다."
                )
            layout.addWidget(browser, 1)

            btn_row = QHBoxLayout()
            btn_row.addStretch(1)
            close_btn = GlassButton("닫기", "secondary")
            close_btn.clicked.connect(dlg.accept)
            btn_row.addWidget(close_btn)
            layout.addLayout(btn_row)
            dlg.exec()

        def _handle_log_link_clicked(self, url: QUrl):
            u = (url.toString() or "").strip()
            if u == "help://google-key":
                self._show_google_key_guide_dialog()
                return
            if u:
                QDesktopServices.openUrl(url)

        def _show_google_key_guide_dialog(self):
            dlg = QDialog(self)
            dlg.setWindowTitle("구글 인증 키 발급 방법")
            dlg.resize(860, 700)
            layout = QVBoxLayout(dlg)
            guide = QTextBrowser(dlg)
            guide.setOpenExternalLinks(True)
            guide.setHtml(
                """
                <div style="font-size:14px; line-height:1.8; color:#f1f5f9;">
                  <h2 style="margin:0 0 10px 0;">구글 인증 키(JSON) 발급 방법</h2>
                  <p style="margin:0 0 12px 0;">처음 사용자 기준으로, 아래 순서대로 진행하면 됩니다.</p>
                  <h3 style="margin:14px 0 6px 0;">1) Google Cloud 프로젝트 만들기</h3>
                  <p style="margin:0 0 8px 0;">
                    - <a href="https://console.cloud.google.com/" style="color:#38bdf8;">Google Cloud Console 열기</a><br>
                    - 상단 프로젝트 선택 메뉴에서 <b>새 프로젝트</b> 생성
                  </p>
                  <h3 style="margin:14px 0 6px 0;">2) Indexing API 사용 설정</h3>
                  <p style="margin:0 0 8px 0;">
                    - 좌측 메뉴 <b>API 및 서비스 → 라이브러리</b><br>
                    - 검색창에 <b>indexing api</b> 입력<br>
                    - 결과가 여러 개 나오면 <b>Web Search Indexing API (Google)</b>를 클릭<br>
                    - 선택한 <b>Web Search Indexing API</b> 화면에서 <b>사용</b> 클릭
                  </p>
                  <h3 style="margin:14px 0 6px 0;">3) 서비스 계정 만들기</h3>
                  <p style="margin:0 0 8px 0;">
                    - <b>API 및 서비스 → 사용자 인증 정보</b> 이동<br>
                    - <b>사용자 인증 정보 만들기 → 서비스 계정</b> 선택<br>
                    - 이름 입력 후 생성
                  </p>
                  <h3 style="margin:14px 0 6px 0;">4) JSON 키 발급</h3>
                  <p style="margin:0 0 8px 0;">
                    - 방금 만든 서비스 계정 클릭<br>
                    - <b>키</b> 탭 → <b>키 추가</b> → <b>새 키 만들기</b><br>
                    - 유형 <b>JSON</b> 선택 후 생성<br>
                    - JSON 파일이 PC에 다운로드됨
                  </p>
                  <h3 style="margin:14px 0 6px 0;">5) Search Console 권한 연결</h3>
                  <p style="margin:0 0 8px 0;">
                    - JSON 파일 안의 <b>client_email</b> 값을 복사<br>
                    - <a href="https://search.google.com/search-console" style="color:#38bdf8;">Google Search Console</a> 접속<br>
                    - 내 사이트의 <b>설정 → 사용자 및 권한</b>에서 해당 이메일을 <b>소유자/전체 권한</b>으로 추가
                  </p>
                  <h3 style="margin:14px 0 6px 0;">6) 프로그램에 등록</h3>
                  <p style="margin:0 0 8px 0;">
                    - 프로그램의 <b>JSON 파일</b> 칸에서 경로를 직접 입력하거나<br>
                    - 옆의 <b>업로드</b> 버튼으로 JSON 파일을 선택<br>
                    - 파일을 더 붙일 때는 <b>+추가</b> 사용
                  </p>
                  <p style="margin:16px 0 0 0; color:#ef4444; font-weight:700;">
                    주의: 사이트 권한 연결(Search Console 사용자 추가)을 하지 않으면 색인 요청이 실패할 수 있습니다.
                  </p>
                </div>
                """
            )
            layout.addWidget(guide, 1)
            btn_row = QHBoxLayout()
            btn_row.addStretch(1)
            close_btn = GlassButton("닫기", "secondary")
            close_btn.clicked.connect(dlg.accept)
            btn_row.addWidget(close_btn)
            layout.addLayout(btn_row)
            dlg.exec()

        @staticmethod
        def _scroll_log_to_bottom(widget: QTextEdit):
            try:
                sb = widget.verticalScrollBar()
                if sb is not None:
                    sb.setValue(sb.maximum())
            except Exception:
                pass

        def _show_brief_notice(self, text: str):
            box = QMessageBox(self)
            box.setWindowTitle("안내")
            box.setText(text)
            box.setIcon(QMessageBox.Icon.NoIcon)
            box.setStandardButtons(QMessageBox.StandardButton.NoButton)
            box.setModal(False)
            box.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
            self._notice_boxes.append(box)

            def _remove_box():
                if box in self._notice_boxes:
                    self._notice_boxes.remove(box)

            box.finished.connect(lambda _r: _remove_box())

            timer = QTimer(box)
            timer.setSingleShot(True)
            timer.timeout.connect(box.accept)
            timer.start(1000)
            box.open()

        def _run_action_with_notice(self, action, text: str):
            result = action()
            if result is not False:
                self._show_brief_notice(text)

        def _save_from_password_enter(self):
            self._run_action_with_notice(self.save_all_configs, "저장이 완료되었습니다.")

        def _save_from_seed_enter(self):
            self._run_action_with_notice(self.save_all_configs, "저장이 완료되었습니다.")

        def _add_google_key_upload_row(self, value: str = ""):
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(8)

            key_input = GlassLineEdit("추가 JSON 파일 경로")
            key_input.returnPressed.connect(self._save_from_seed_enter)
            if value:
                key_input.setText(str(value).strip())
            upload_btn = GlassButton("업로드", "secondary")
            remove_btn = GlassButton("삭제", "danger")

            def _upload_to_this():
                path, _ = QFileDialog.getOpenFileName(self, "JSON 파일 선택", SCRIPT_DIR, "JSON files (*.json);;All files (*.*)")
                if path:
                    key_input.setText(str(path).strip())
                    self.save_all_configs()

            def _remove_this():
                if row in [r.get("row") for r in self.google_key_extra_rows]:
                    self.google_key_extra_layout.removeWidget(row)
                    row.deleteLater()
                    self.google_key_extra_rows = [r for r in self.google_key_extra_rows if r.get("row") is not row]
                    self.save_all_configs()

            upload_btn.clicked.connect(_upload_to_this)
            remove_btn.clicked.connect(_remove_this)
            row_layout.addWidget(key_input, 1)
            row_layout.addWidget(upload_btn, 0)
            row_layout.addWidget(remove_btn, 0)

            self.google_key_extra_layout.addWidget(row)
            self.google_key_extra_rows.append({"row": row, "input": key_input, "upload": upload_btn, "remove": remove_btn})
            return True

        def _collect_google_key_files(self) -> List[str]:
            files: List[str] = []
            main_input = getattr(self, "google_service_file_input", None)
            main_text_fn = getattr(main_input, "text", None)
            if callable(main_text_fn):
                for p in GoogleIndexingService.parse_service_account_files(str(main_text_fn() or "")):
                    if p and p not in files:
                        files.append(p)
            for row in self.google_key_extra_rows:
                inp = row.get("input")
                text_fn = getattr(inp, "text", None)
                if callable(text_fn):
                    for p in GoogleIndexingService.parse_service_account_files(str(text_fn() or "")):
                        if p and p not in files:
                            files.append(p)
            return files

        def _set_google_key_files(self, files: List[str]):
            for row in self.google_key_extra_rows:
                widget = row.get("row")
                if widget is not None:
                    self.google_key_extra_layout.removeWidget(widget)
                    widget.deleteLater()
            self.google_key_extra_rows = []

            normalized: List[str] = []
            for p in files:
                s = str(p or "").strip()
                if s and s not in normalized:
                    normalized.append(s)

            self.google_service_file_input.setText(normalized[0] if normalized else "")
            for p in normalized[1:]:
                self._add_google_key_upload_row(p)

        def _upload_google_key_file(self):
            paths, _ = QFileDialog.getOpenFileNames(self, "JSON 파일 선택(최대 2개)", SCRIPT_DIR, "JSON files (*.json);;All files (*.*)")
            if paths:
                selected = [str(p or "").strip() for p in paths if str(p or "").strip()]
                if len(selected) > 2:
                    selected = selected[:2]
                self._set_google_key_files(selected)
                self.save_all_configs()
                return True
            return False

        def _append_google_key_files(self):
            paths, _ = QFileDialog.getOpenFileNames(self, "JSON 파일 추가(복수 선택 가능)", SCRIPT_DIR, "JSON files (*.json);;All files (*.*)")
            if paths:
                merged = self._collect_google_key_files()
                for p in paths:
                    s = str(p or "").strip()
                    if s and s not in merged:
                        merged.append(s)
                self._set_google_key_files(merged)
                self.save_all_configs()
                return True
            return False

        def _clear_google_key_file(self):
            if not self._collect_google_key_files():
                return False
            self._set_google_key_files([])
            self.save_all_configs()
            return True

        def _toggle_naver_password_visibility(self):
            if self.naver_password_input.echoMode() == QLineEdit.EchoMode.Password:
                self.naver_password_input.setEchoMode(QLineEdit.EchoMode.Normal)
                self.naver_password_toggle_btn.setText("비공개")
            else:
                self.naver_password_input.setEchoMode(QLineEdit.EchoMode.Password)
                self.naver_password_toggle_btn.setText("공개")

        def _show_usage_guides(self):
            self.google_log.setHtml(
                """
                <div style="font-size:15px; line-height:2.05;">
                  <h2 style="font-size:20px; margin:0 0 2px 0; line-height:1.25;">구글 색인 자동화 사용 방법</h2>
                  <p style="margin:0 0 10px 0; color:#cbd5e1;">처음 사용하는 분도 그대로 따라 할 수 있게, 입력 칸 기준으로 설명합니다.</p>
                  <h3 style="font-size:17px; margin:0 0 10px 0;">[JSON 파일]</h3>
                  <p style="margin:0 0 7px 0;">- 이 칸에는 <b>서비스 계정 JSON 파일</b>을 등록합니다.</p>
                  <p style="margin:0 0 7px 0;">- <b>업로드</b>: 지금 선택한 파일들로 목록을 새로 바꿉니다.</p>
                  <p style="margin:0 0 7px 0;">- <b>+추가</b>: 이미 등록된 목록에 JSON 파일을 더 붙입니다.</p>
                  <p style="margin:0 0 7px 0;">- <b>삭제</b>: 등록된 JSON 목록을 비웁니다.</p>
                  <p style="margin:0 0 14px 0;">- 발급이 어려우면 <a href="help://google-key" style="color:#38bdf8; text-decoration:underline;"><b>구글 인증 키 발급 방법</b></a>을 눌러 상세 안내를 보세요.</p>
                  <h3 style="font-size:17px; margin:0 0 10px 0;">[색인 요청할 도메인 URL]</h3>
                  <p style="margin:0 0 7px 0;">- 색인할 사이트의 <b>도메인 URL</b>을 입력합니다. 예) https://example.com</p>
                  <p style="margin:0 0 7px 0;">- 사이트가 여러 개면 <b>+ 추가</b>로 칸을 늘려 각각 입력합니다.</p>
                  <p style="margin:0 0 7px 0;">- URL 입력칸 1개만 있어도, 여러 URL을 줄바꿈한 뒤 <b>붙여넣기(Ctrl+V)</b>하면 칸이 자동으로 추가되어 한 번에 등록됩니다.</p>
                  <p style="margin:0 0 14px 0;">- 각 URL 오른쪽에서 사이트별로 <b>요청 순서</b>를 고를 수 있습니다.<br>(가장 오래된 글부터 / 가장 최신 글부터)</p>
                  <h3 style="font-size:17px; margin:0 0 10px 0;">[버튼 사용 순서]</h3>
                  <p style="margin:0 0 7px 0;">1. JSON 파일과 사이트 URL을 입력합니다.</p>
                  <p style="margin:0 0 7px 0;">2. <b>저장</b> 버튼으로 현재 입력값을 저장합니다.</p>
                  <p style="margin:0 0 7px 0;">3. <b>▶ 구글 등록 시작</b> 버튼을 누르면 자동으로 색인 요청을 진행합니다.</p>
                  <p style="margin:0 0 7px 0;">4. JSON이 여러 개면 키를 순서대로 사용해 남은 URL을 계속 처리합니다.</p>
                  <p style="margin:0 0 7px 0;">5. 구글/네이버는 각각 독립 실행이라, 필요하면 두 탭을 함께 실행할 수 있습니다.</p>
                  <p style="margin:12px 0 0 0; color:#cbd5e1;">구글 설정이 어렵다면 구글 기능은 생략하고 네이버만 사용해도 됩니다.</p>
                </div>
                """
            )
            self.naver_log.setHtml(
                """
                <div style="font-size:15px; line-height:2.05;">
                  <h2 style="font-size:20px; margin:0 0 2px 0; line-height:1.25;">네이버 색인 자동화 사용 방법</h2>
                  <p style="margin:0 0 10px 0; color:#cbd5e1;">입력 칸 이름 그대로 따라 입력하면 바로 사용할 수 있습니다.</p>
                  <div style="margin-bottom:10px; padding:10px 12px; border:1px solid #dc3232; border-radius:8px; color:#ffd7d7;">
                    <b>중요:</b> 네이버 계정은 <b>서치어드바이저에 사이트를 등록한 계정</b>이어야 합니다.
                  </div>
                  <div style="margin-bottom:12px; padding:10px 12px; border:1px solid #dc3232; border-radius:8px; color:#ffd7d7;">
                    <b>필수 조건:</b> 네이버 기능은 <b>Rank Math 플러그인을 사용하는 워드프레스 사이트</b>만 지원합니다.
                  </div>
                  <h3 style="font-size:17px; margin:0 0 10px 0;">[네이버 계정 설정]</h3>
                  <p style="margin:0 0 7px 0;">- <b>네이버 로그인 아이디</b>: 사이트를 등록한 네이버 계정 아이디</p>
                  <p style="margin:0 0 14px 0;">- <b>네이버 비밀번호</b>: 해당 계정 비밀번호 (공개/비공개 버튼 지원)</p>
                  <h3 style="font-size:17px; margin:0 0 10px 0;">[색인 요청할 도메인 URL]</h3>
                  <p style="margin:0 0 7px 0;">- 색인할 사이트의 <b>도메인 URL</b>을 입력합니다. 예) https://example.com</p>
                  <p style="margin:0 0 7px 0;">- 여러 사이트를 쓰면 <b>+ 추가</b>로 칸을 늘려 입력합니다.</p>
                  <p style="margin:0 0 7px 0;">- URL 입력칸 1개만 있어도, 여러 URL을 줄바꿈한 뒤 <b>붙여넣기(Ctrl+V)</b>하면 칸이 자동으로 추가되어 한 번에 등록됩니다.</p>
                  <p style="margin:0 0 14px 0;">- 각 URL 오른쪽에서 사이트별로 <b>요청 순서</b>를 고를 수 있습니다.<br>(가장 오래된 글부터 / 가장 최신 글부터)</p>
                  <h3 style="font-size:17px; margin:0 0 10px 0;">[버튼 사용 순서]</h3>
                  <p style="margin:0 0 7px 0;">1. 네이버 계정과 사이트 URL을 입력합니다.</p>
                  <p style="margin:0 0 7px 0;">2. <b>저장</b> 버튼으로 현재 입력값을 저장합니다.</p>
                  <p style="margin:0 0 7px 0;">3. <b>▶ 네이버 색인 요청</b> 버튼을 누르면 자동으로 진행됩니다.</p>
                  <p style="margin:0 0 7px 0;">4. 사이트를 하나씩 처리하며, 사이트별 오늘 남은 할당량만큼만 요청합니다.</p>
                  <p style="margin:0 0 7px 0;">5. 크롬 로그인 상태를 유지해 다음 실행 시 재로그인 부담을 줄입니다.</p>
                  <p style="margin:0;">6. 구글/네이버는 각각 독립 실행이라, 필요하면 두 탭을 함께 실행할 수 있습니다.</p>
                </div>
                """
            )

        def _on_naver_method_changed(self, method: str):
            # Selenium-only mode; kept for compatibility.
            self.naver_username_input.setEnabled(True)
            self.naver_password_input.setEnabled(True)
            self.naver_password_toggle_btn.setEnabled(True)

        def _gather_config(self):
            google_seed_items = self._collect_seed_items("google")
            naver_seed_items = self._collect_seed_items("naver")
            google_key_files = self._collect_google_key_files()
            return {
                "google_enabled": True,
                "naver_enabled": True,
                "google_service_account_file": (google_key_files[0] if google_key_files else self.google_service_file_input.text().strip()),
                "google_service_account_files": google_key_files,
                "google_site_items": google_seed_items,
                "google_site_urls": [it["url"] for it in google_seed_items],
                "naver_method": "selenium",
                "naver_site_items": naver_seed_items,
                "naver_site_urls": [it["url"] for it in naver_seed_items],
                "naver_username": self.naver_username_input.text().strip(),
                "naver_password": self.naver_password_input.text(),
                "use_seo_prefilter": True,
                "use_batch_api": True,
                "submit_order": "oldest",
            }

        def _apply_config(self, c):
            g_files = c.get("google_service_account_files")
            if isinstance(g_files, list) and g_files:
                self._set_google_key_files([str(x).strip() for x in g_files if str(x).strip()])
            else:
                self._set_google_key_files(GoogleIndexingService.parse_service_account_files(c.get("google_service_account_file", "service-account-key.json")))
            self.naver_username_input.setText(c.get("naver_username", ""))
            self.naver_password_input.setText(c.get("naver_password", ""))
            global_order = self._normalize_order_value(c.get("submit_order", "oldest"))
            google_items = c.get("google_site_items")
            if not isinstance(google_items, list):
                google_items = [{"url": u, "order": global_order, "enabled": True} for u in (c.get("google_site_urls") or []) if str(u or "").strip()]
            naver_items = c.get("naver_site_items")
            if not isinstance(naver_items, list):
                naver_urls = c.get("naver_site_urls") or ([c.get("naver_site_url")] if c.get("naver_site_url") else [])
                naver_items = [{"url": u, "order": global_order, "enabled": True} for u in naver_urls if str(u or "").strip()]
            self._set_seed_items("google", google_items)
            self._set_seed_items("naver", naver_items)
            self._on_naver_method_changed("selenium")

        def initialize_encryption_and_load_config(self):
            # 암호화 설정 기능을 사용하지 않으므로 일반 설정만 로드한다.
            self.load_all_configs()
            return True

        def load_all_configs(self):
            cm = self.controller.config_manager
            cfg = cm.load_config(cm.password) if cm.password else None
            if cfg is None:
                cfg = cm.load_config()
            if cfg is None:
                cfg = cm.default_config.copy()
            self.current_config = cfg
            self._apply_config(cfg)
            self.status_label.setText("설정 불러오기 완료")
            self._show_usage_guides()

        def save_all_configs(self):
            base = self.controller.config_manager.default_config.copy()
            base.update(self.current_config or {})
            base.update(self._gather_config())
            cm = self.controller.config_manager
            ok = cm.save_config(base, password=cm.password, encrypt=bool(cm.password and ENCRYPTION_AVAILABLE))
            if ok:
                self.current_config = base
                self.status_label.setText("설정 저장 완료")
            else:
                QMessageBox.warning(self, "오류", "설정 저장에 실패했습니다.")

        def _set_service_running(self, service: str, running: bool):
            if service == "google":
                self.google_start_btn.setEnabled(not running)
                self.google_stop_btn.setEnabled(running)
            else:
                self.naver_start_btn.setEnabled(not running)
                self.naver_stop_btn.setEnabled(running)

        def _new_runtime_controller(self, service: str) -> IndexingController:
            c = IndexingController()
            c.logger.set_gui_log_widget(self.google_log if service == "google" else self.naver_log)
            c.logger.set_error_callback(lambda msg, svc=service: self.error_logged.emit(svc, msg))
            return c

        def start_google_indexing(self, silent: bool = False):
            if self.google_worker and self.google_worker.isRunning():
                if not silent:
                    QMessageBox.information(self, "실행 중", "구글 작업이 이미 실행 중입니다.")
                return
            seeds = self._collect_seed_urls("google")
            if not seeds:
                if silent:
                    self._append_log("google", "ℹ️ 자동 실행 건너뜀: 구글 사이트 URL이 없습니다.")
                else:
                    QMessageBox.warning(self, "입력 필요", "구글 탭에 사이트 주소를 1개 이상 입력하세요.")
                return
            self.save_all_configs()
            worker_controller = self._new_runtime_controller("google")
            self._reset_active_error_details("google")
            self.google_worker = IndexingWorker(worker_controller, seeds, "google")
            self.google_worker.progress_updated.connect(self.on_progress)
            self.google_worker.finished.connect(self.on_finished)
            self._set_service_running("google", True)
            self.status_label.setText("구글 등록 작업 실행 중...")
            self.progress_bar.setValue(0)
            self.google_worker.start()

        def start_naver_indexing(self, silent: bool = False):
            if self.naver_worker and self.naver_worker.isRunning():
                if not silent:
                    QMessageBox.information(self, "실행 중", "네이버 작업이 이미 실행 중입니다.")
                return
            seeds = self._collect_seed_urls("naver")
            if not seeds:
                if silent:
                    self._append_log("naver", "ℹ️ 자동 실행 건너뜀: 네이버 사이트 URL이 없습니다.")
                else:
                    QMessageBox.warning(self, "입력 필요", "네이버 탭에 사이트 주소를 1개 이상 입력하세요.")
                return
            self.save_all_configs()
            worker_controller = self._new_runtime_controller("naver")
            self._reset_active_error_details("naver")
            self.naver_worker = IndexingWorker(worker_controller, seeds, "naver")
            self.naver_worker.progress_updated.connect(self.on_progress)
            self.naver_worker.finished.connect(self.on_finished)
            self._set_service_running("naver", True)
            self.status_label.setText("네이버 색인 요청 실행 중...")
            self.progress_bar.setValue(0)
            self.naver_worker.start()

        def stop_indexing(self, service: str):
            worker = self.google_worker if service == "google" else self.naver_worker
            if worker and worker.isRunning():
                worker.controller.stop_indexing()
                self.status_label.setText(f"{'구글' if service == 'google' else '네이버'} 중지 요청 중...")
            else:
                self.status_label.setText("실행 중인 작업이 없습니다.")

        def on_progress(self, service: str, message: str, progress: int):
            prefix = "구글" if service == "google" else "네이버"
            self.status_label.setText(f"[{prefix}] {message}")
            self.progress_bar.setValue(max(0, min(100, progress)))
            self._append_log(service, message)

        def on_finished(self, service: str, result: Dict[str, int]):
            self._set_service_running(service, False)
            self.progress_bar.setValue(100)
            self.status_label.setText("완료")
            service_label = "구글" if service == "google" else "네이버"
            errors = int(result.get("errors", 0) or 0)
            self._snapshot_completed_error_details(service, errors)
            if errors > 0:
                self._append_log(service, f"ℹ️ 오류 {errors}개 상세는 '오류 상세' 버튼에서 확인하세요.")
            self._show_brief_notice(f"{service_label} 작업이 완료되었습니다.")
            if service == "google":
                self.google_worker = None
            else:
                self.naver_worker = None


def run_gui() -> int:
    if not GUI_AVAILABLE:
        print("PyQt6 is not installed. Run: pip install PyQt6")
        return 1
    app = QApplication(sys.argv)
    src = _window_icon_source()
    if src:
        app.setWindowIcon(QIcon(src))
    startup_dialog = QDialog()
    startup_dialog.setWindowTitle("안내")
    _apply_window_icon(startup_dialog)
    startup_dialog.setModal(False)
    startup_dialog.setFixedSize(360, 130)
    startup_layout = QVBoxLayout(startup_dialog)
    startup_layout.setContentsMargins(18, 16, 18, 16)
    startup_label = QLabel("프로그램 실행 중입니다.\n잠시만 기다려 주세요.")
    startup_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    startup_layout.addWidget(startup_label)
    startup_dialog.show()
    QApplication.processEvents()
    if not LICENSE_CHECK_AVAILABLE:
        startup_dialog.close()
        QMessageBox.critical(
            None,
            "필수 모듈 누락",
            "license_check.py 모듈을 불러오지 못했습니다.\n머신 ID 검증 없이 실행할 수 없습니다.",
        )
        return 1
    try:
        lm = LicenseManager()
        ok, msg = lm.verify_license()
        if not ok:
            startup_dialog.close()
            machine_id = lm.get_machine_id()
            full_message = f"{msg}\n\n현재 머신 ID:\n{machine_id}"
            if "등록되지 않은 컴퓨터" in msg:
                show_unregistered_machine_dialog(machine_id)
            elif "만료" in msg:
                show_expired_license_dialog()
            else:
                show_license_failure_dialog(msg, machine_id)
            return 1
        usage_period_text = "확인 필요"
        try:
            lic_info = lm.get_license_info()
            usage_period_text = str(lic_info.get("expire_date", "확인 필요"))
        except Exception:
            usage_period_text = "확인 필요"
    except Exception as e:
        startup_dialog.close()
        QMessageBox.critical(None, "라이선스 오류", f"라이선스 확인 중 오류가 발생했습니다.\n{e}")
        return 1
    startup_dialog.close()
    w = ModernIndexingGUI(usage_period_text=usage_period_text)
    w.showMaximized()
    try:
        return app.exec()
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    try:
        sys.exit(run_gui())
    except KeyboardInterrupt:
        sys.exit(0)

