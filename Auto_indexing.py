# -*- coding: utf-8 -*-
"""Integrated auto indexing tool for Google and Naver."""

import json
import os
import re
import sqlite3
import subprocess
import sys
import time
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
from threading import Event, Thread
from typing import Any, Dict, List, Optional, Set, Tuple
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
except Exception:
    HTTP_AVAILABLE = False

try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import BatchHttpRequest
    GOOGLE_API_AVAILABLE = True
except Exception:
    GOOGLE_API_AVAILABLE = False

try:
    from encryption_manager import EncryptionManager
    ENCRYPTION_AVAILABLE = True
except Exception:
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
    from PyQt6.QtGui import QDesktopServices, QFont, QIcon
    from PyQt6.QtWidgets import QApplication, QComboBox, QDialog, QFileDialog, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox, QProgressBar, QPushButton, QTabWidget, QTextBrowser, QTextEdit, QVBoxLayout, QWidget
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
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

    def set_gui_log_widget(self, widget):
        self.gui_widgets = [widget] if widget else []

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
        self.encryption_manager = EncryptionManager() if ENCRYPTION_AVAILABLE else None
        self.default_config = {
            "google_enabled": True,
            "naver_enabled": True,
            "google_service_account_file": "service-account-key.json",
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
                    normalized.append({"url": u, "order": order})
            if not normalized and isinstance(urls, list):
                for raw in urls:
                    u = str(raw or "").strip()
                    if not u or u in seen:
                        continue
                    seen.add(u)
                    normalized.append({"url": u, "order": default_order})
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
            except Exception:
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
            self.logger.log(f"{service_name}: 홈(/) 또는 비정상 URL {skipped}개를 제출 대상에서 제외했습니다.", "WARNING")
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
                    max_urls=site_remaining,
                    submit_order=site_order_map.get(site.rstrip("/"), default_order),
                )
                if not site_crawled:
                    self.logger.log(f"{site}에서 수집된 URL이 없습니다.", "WARNING")
                    continue
                site_crawled = self._filter_submission_targets(site_crawled, "네이버")
                if not site_crawled:
                    continue
                if len(site_crawled) > site_remaining:
                    site_crawled = site_crawled[:site_remaining]
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

            res["total"] += naver_total_targets

        if res["total"] == 0:
            if progress_callback:
                progress_callback("새로 등록할 주소가 없습니다.", 100)
            return {"total": 0, "google_success": 0, "naver_success": 0, "errors": 0, "scheduled": 0}

        if service_to_run in ("google", "all") and cfg.get("google_enabled", True) and not self.stop_event.is_set():
            if progress_callback:
                progress_callback("구글에 검색 등록 요청 중...", 45)
            if self.google_service.initialize(cfg.get("google_service_account_file", "service-account-key.json")):
                gs, gf = self.google_service.submit_urls(google_targets, use_batch=cfg.get("use_batch_api", True))
                res["google_success"] = gs
                res["errors"] += gf
                if gs > 0:
                    self.url_state.mark_submitted("google", google_targets[:gs])
            else:
                res["errors"] += len(google_targets)
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
                "add": ("#14B8A6", "#0F766E"),
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
        def __init__(self, placeholder="", parent=None):
            super().__init__(parent)
            self.setPlaceholderText(placeholder)
            self.setMinimumHeight(36)
            self.setFont(QFont("맑은 고딕", 10))

    class GlassTextEdit(QTextBrowser):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setFont(QFont("맑은 고딕", 11))
            self.setOpenExternalLinks(True)

    class IndexingWorker(QThread):
        progress_updated = pyqtSignal(str, int)
        finished = pyqtSignal(dict)

        def __init__(self, controller: IndexingController, urls: List[str], service_type: str):
            super().__init__()
            self.controller = controller
            self.urls = urls
            self.service_type = service_type

        def run(self):
            if self.service_type == "google":
                r = self.controller.run_indexing(progress_callback=lambda m, p: self.progress_updated.emit(m, p), google_urls=self.urls, service_to_run="google")
                self.finished.emit({"total": r.get("total", 0), "success": r.get("google_success", 0), "errors": r.get("errors", 0), "scheduled": r.get("scheduled", 0)})
            else:
                r = self.controller.run_indexing(progress_callback=lambda m, p: self.progress_updated.emit(m, p), naver_urls=self.urls, service_to_run="naver")
                self.finished.emit({"total": r.get("total", 0), "success": r.get("naver_success", 0), "errors": r.get("errors", 0), "scheduled": r.get("scheduled", 0)})

    class ModernIndexingGUI(QMainWindow):
        def __init__(self, usage_period_text: str = "확인 필요"):
            super().__init__()
            self.controller = IndexingController()
            self.worker: Optional[IndexingWorker] = None
            self.current_service_type = "google"
            self.current_config = self.controller.config_manager.default_config.copy()
            self.usage_period_text = usage_period_text
            self._notice_boxes: List[QMessageBox] = []
            self.init_ui()
            if not self.initialize_encryption_and_load_config():
                QTimer.singleShot(100, self.close)
                return
            self._show_usage_guides()

        def init_ui(self):
            self.setWindowTitle("Auto_Indexing - 구글 + 네이버 색인 자동화")
            self.setGeometry(100, 80, 1450, 920)
            icon_path = os.path.join(SCRIPT_DIR, "david153.ico")
            if os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
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
            grid.addWidget(QLabel("구글 인증 키 파일"), 0, 0)
            self.google_service_file_input = GlassLineEdit("service-account-key.json")
            file_row = QWidget()
            file_row_layout = QHBoxLayout(file_row)
            file_row_layout.setContentsMargins(0, 0, 0, 0)
            file_row_layout.setSpacing(8)
            file_row_layout.addWidget(self.google_service_file_input, 1)
            self.google_key_upload_btn = GlassButton("업로드", "secondary")
            self.google_key_upload_btn.clicked.connect(lambda: self._run_action_with_notice(self._upload_google_key_file, "파일 업로드가 완료되었습니다."))
            self.google_key_clear_btn = GlassButton("삭제", "danger")
            self.google_key_clear_btn.clicked.connect(lambda: self._run_action_with_notice(self._clear_google_key_file, "파일 삭제가 완료되었습니다."))
            file_row_layout.addWidget(self.google_key_upload_btn, 0)
            file_row_layout.addWidget(self.google_key_clear_btn, 0)
            grid.addWidget(file_row, 0, 1)
            layout.addWidget(settings)
            seeds = QGroupBox("색인 요청할 사이트 URL")
            s = QVBoxLayout(seeds)
            self.google_seed_rows: List[Dict[str, Any]] = []
            self.google_seed_urls_widget = QWidget()
            self.google_seed_urls_layout = QVBoxLayout(self.google_seed_urls_widget)
            self.google_seed_urls_layout.setContentsMargins(0, 0, 0, 0)
            self.google_seed_urls_layout.setSpacing(8)
            self.google_seed_urls_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
            seed_btn_row = QHBoxLayout()
            self.google_add_seed_btn = GlassButton("+ 추가", "add")
            self.google_add_seed_btn.clicked.connect(lambda: self._add_seed_url_input("google"))
            self.google_seed_save_btn = GlassButton("저장", "success")
            self.google_seed_save_btn.clicked.connect(lambda: self._run_action_with_notice(self.save_all_configs, "저장이 완료되었습니다."))
            seed_btn_row.addWidget(self.google_add_seed_btn, 0, Qt.AlignmentFlag.AlignLeft)
            seed_btn_row.addWidget(self.google_seed_save_btn, 0, Qt.AlignmentFlag.AlignLeft)
            seed_btn_row.addStretch(1)
            s.addLayout(seed_btn_row)
            s.addWidget(self.google_seed_urls_widget)
            s.addStretch(1)
            self._add_seed_url_input("google")
            log_group = QGroupBox("로그 메시지")
            gl = QVBoxLayout(log_group)
            self.google_log = GlassTextEdit()
            self.google_log.setReadOnly(True)
            self.google_log.textChanged.connect(lambda: self._scroll_log_to_bottom(self.google_log))
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
            self.google_stop_btn.clicked.connect(lambda: self._run_action_with_notice(self.stop_indexing, "중지 요청이 완료되었습니다."))
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
            seed_group = QGroupBox("색인 요청할 사이트 URL")
            sd = QVBoxLayout(seed_group)
            self.naver_seed_rows: List[Dict[str, Any]] = []
            self.naver_seed_urls_widget = QWidget()
            self.naver_seed_urls_layout = QVBoxLayout(self.naver_seed_urls_widget)
            self.naver_seed_urls_layout.setContentsMargins(0, 0, 0, 0)
            self.naver_seed_urls_layout.setSpacing(8)
            self.naver_seed_urls_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
            seed_btn_row = QHBoxLayout()
            self.naver_add_seed_btn = GlassButton("+ 추가", "add")
            self.naver_add_seed_btn.clicked.connect(lambda: self._add_seed_url_input("naver"))
            self.naver_seed_save_btn = GlassButton("저장", "success")
            self.naver_seed_save_btn.clicked.connect(lambda: self._run_action_with_notice(self.save_all_configs, "저장이 완료되었습니다."))
            seed_btn_row.addWidget(self.naver_add_seed_btn, 0, Qt.AlignmentFlag.AlignLeft)
            seed_btn_row.addWidget(self.naver_seed_save_btn, 0, Qt.AlignmentFlag.AlignLeft)
            seed_btn_row.addStretch(1)
            sd.addLayout(seed_btn_row)
            sd.addWidget(self.naver_seed_urls_widget)
            sd.addStretch(1)
            self._add_seed_url_input("naver")
            log_group = QGroupBox("로그 메시지")
            nl = QVBoxLayout(log_group)
            self.naver_log = GlassTextEdit()
            self.naver_log.setReadOnly(True)
            self.naver_log.textChanged.connect(lambda: self._scroll_log_to_bottom(self.naver_log))
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
            self.naver_stop_btn.clicked.connect(lambda: self._run_action_with_notice(self.stop_indexing, "중지 요청이 완료되었습니다."))
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

        def _add_seed_url_input(self, service: str, value: str = "", order: str = "oldest"):
            order = self._normalize_order_value(order)
            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(8)
            inp = GlassLineEdit("https://example.com")
            inp.setText((value or "").strip())
            inp.returnPressed.connect(self._save_from_seed_enter)
            order_combo = QComboBox()
            order_combo.addItem("가장 오래된 글부터", "oldest")
            order_combo.addItem("가장 최신 글부터", "newest")
            order_combo.setCurrentIndex(1 if order == "newest" else 0)
            order_combo.setMinimumWidth(170)
            row_layout.addWidget(inp, 1)
            row_layout.addWidget(order_combo, 0)
            if service == "google":
                self.google_seed_rows.append({"widget": row_widget, "input": inp, "order": order_combo})
                self.google_seed_urls_layout.addWidget(row_widget)
            else:
                self.naver_seed_rows.append({"widget": row_widget, "input": inp, "order": order_combo})
                self.naver_seed_urls_layout.addWidget(row_widget)

        def _set_seed_items(self, service: str, items: List[Dict[str, str]]):
            rows = self.google_seed_rows if service == "google" else self.naver_seed_rows
            while rows:
                r = rows.pop()
                w = r.get("widget")
                if w is not None:
                    w.deleteLater()
            if items:
                for it in items:
                    self._add_seed_url_input(service, it.get("url", ""), it.get("order", "oldest"))
            else:
                self._add_seed_url_input(service)

        def _collect_seed_urls(self, service: str) -> List[str]:
            return [it["url"] for it in self._collect_seed_items(service)]

        def _collect_seed_items(self, service: str) -> List[Dict[str, str]]:
            seen, out = set(), []
            rows = self.google_seed_rows if service == "google" else self.naver_seed_rows
            for row in rows:
                inp = row.get("input")
                cb = row.get("order")
                if inp is None or cb is None:
                    continue
                u = inp.text().strip()
                if u and u not in seen:
                    seen.add(u)
                    out.append(
                        {
                            "url": u,
                            "order": self._normalize_order_value(str(cb.currentData() or "oldest")),
                        }
                    )
            return out

        def _append_log(self, service: str, message: str):
            target = self.google_log if service == "google" else self.naver_log
            target.append(message)
            self._scroll_log_to_bottom(target)

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

        def _upload_google_key_file(self):
            path, _ = QFileDialog.getOpenFileName(self, "구글 인증 키 파일 선택", SCRIPT_DIR, "JSON files (*.json);;All files (*.*)")
            if path:
                self.google_service_file_input.setText(path)
                self.save_all_configs()
                return True
            return False

        def _clear_google_key_file(self):
            if not self.google_service_file_input.text().strip():
                return False
            self.google_service_file_input.clear()
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
                  <h3 style="font-size:17px; margin:0 0 12px 0;">[구글 인증 키 파일]</h3>
                  <p style="margin:0 0 8px 0;">- 여기에 <b>서비스 계정 JSON 파일 경로</b>를 입력합니다.<br>(업로드 버튼 사용 가능)</p>
                  <p style="margin:0 0 16px 0;">- 아직 파일이 없으면 Google Cloud에서<br>Indexing API용 서비스 계정 키(JSON)를 먼저 발급해야 합니다.</p>
                  <h3 style="font-size:17px; margin:0 0 12px 0;">[색인 요청할 사이트 URL]</h3>
                  <p style="margin:0 0 8px 0;">- 색인할 사이트의 <b>도메인 URL</b>을 입력합니다.<br>예) https://example.com</p>
                  <p style="margin:0 0 16px 0;">- 사이트가 여러 개면 <b>+ 추가</b>로 입력칸을 늘려서 각각 입력합니다.</p>
                  <h3 style="font-size:17px; margin:0 0 12px 0;">[버튼 사용 순서]</h3>
                  <p style="margin:0 0 8px 0;">1. 필요한 항목을 입력합니다.</p>
                  <p style="margin:0 0 8px 0;">2. <b>저장</b> 버튼을 눌러 설정을 저장합니다.</p>
                  <p style="margin:0;">3. <b>구글 등록 시작</b> 버튼을 누르면 자동으로 색인 요청을 진행합니다.</p>
                  <p style="margin:12px 0 0 0; letter-spacing:1px;">=================================</p>
                </div>
                """
            )
            self.naver_log.setHtml(
                """
                <div style="font-size:15px; line-height:2.05;">
                  <h2 style="font-size:20px; margin:0 0 2px 0; line-height:1.25;">네이버 색인 자동화 사용 방법</h2>
                  <div style="margin-bottom:12px; padding:10px 12px; border:1px solid #dc3232; border-radius:8px; color:#ffd7d7;">
                    <b>중요:</b> 네이버 계정은 <b>서치어드바이저에 사이트를 등록한 계정</b>이어야 합니다.
                  </div>
                  <div style="margin-bottom:12px; padding:10px 12px; border:1px solid #dc3232; border-radius:8px; color:#ffd7d7;">
                    <b>필수 조건:</b> 네이버 기능은 <b>Rank Math 플러그인을 사용하는 워드프레스 사이트</b>만 지원합니다.
                  </div>
                  <h3 style="font-size:17px; margin:0 0 12px 0;">[네이버 계정 설정]</h3>
                  <p style="margin:0 0 8px 0;">- <b>네이버 로그인 아이디</b>: 서치어드바이저에 사이트를 등록한 계정 아이디</p>
                  <p style="margin:0 0 16px 0;">- <b>네이버 비밀번호</b>: 해당 계정 비밀번호<br>(공개/비공개 버튼으로 확인 가능)</p>
                  <h3 style="font-size:17px; margin:0 0 12px 0;">[색인 요청할 사이트 URL]</h3>
                  <p style="margin:0 0 8px 0;">- 색인할 사이트의 <b>도메인 URL</b>을 입력합니다.<br>예) https://example.com</p>
                  <p style="margin:0 0 16px 0;">- 여러 사이트를 쓰면 <b>+ 추가</b>로 칸을 늘려 입력합니다.</p>
                  <h3 style="font-size:17px; margin:0 0 12px 0;">[버튼 사용 순서]</h3>
                  <p style="margin:0 0 8px 0;">1. 위 항목을 입력합니다.</p>
                  <p style="margin:0 0 8px 0;">2. <b>저장</b> 버튼을 눌러 설정을 저장합니다.</p>
                  <p style="margin:0;">3. <b>네이버 색인 요청</b> 버튼을 누르면 자동으로 진행됩니다.</p>
                  <p style="margin:12px 0 0 0; letter-spacing:1px;">=================================</p>
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
            return {
                "google_enabled": True,
                "naver_enabled": True,
                "google_service_account_file": self.google_service_file_input.text().strip(),
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
            self.google_service_file_input.setText(c.get("google_service_account_file", "service-account-key.json"))
            self.naver_username_input.setText(c.get("naver_username", ""))
            self.naver_password_input.setText(c.get("naver_password", ""))
            global_order = self._normalize_order_value(c.get("submit_order", "oldest"))
            google_items = c.get("google_site_items")
            if not isinstance(google_items, list):
                google_items = [{"url": u, "order": global_order} for u in (c.get("google_site_urls") or []) if str(u or "").strip()]
            naver_items = c.get("naver_site_items")
            if not isinstance(naver_items, list):
                naver_urls = c.get("naver_site_urls") or ([c.get("naver_site_url")] if c.get("naver_site_url") else [])
                naver_items = [{"url": u, "order": global_order} for u in naver_urls if str(u or "").strip()]
            self._set_seed_items("google", google_items)
            self._set_seed_items("naver", naver_items)
            self._on_naver_method_changed("selenium")

        def initialize_encryption_and_load_config(self):
            cm = self.controller.config_manager
            if os.path.exists(cm.encrypted_config_file):
                if not PASSWORD_DIALOG_AVAILABLE:
                    QMessageBox.warning(self, "비밀번호 필요", "암호화 설정 파일이 있지만 비밀번호 창을 사용할 수 없습니다.")
                    return False
                while True:
                    dlg = PasswordDialog(mode="login", parent=self)
                    if dlg.exec() != QDialog.DialogCode.Accepted:
                        return False
                    cfg = cm.load_config(dlg.get_password())
                    if cfg is not None:
                        self.current_config = cfg
                        self._apply_config(cfg)
                        return True
                    QMessageBox.warning(self, "오류", "비밀번호가 올바르지 않거나 복호화에 실패했습니다.")
            if not os.path.exists(cm.config_file) and ENCRYPTION_AVAILABLE and PASSWORD_DIALOG_AVAILABLE:
                dlg = PasswordDialog(mode="setup", parent=self)
                if dlg.exec() == QDialog.DialogCode.Accepted:
                    cm.password = dlg.get_password()
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

        def _set_running(self, running: bool):
            for b in [
                self.google_start_btn,
                self.naver_start_btn,
                self.naver_settings_save_btn,
                self.naver_password_toggle_btn,
                self.google_seed_save_btn,
                self.naver_seed_save_btn,
                self.google_key_upload_btn,
                self.google_key_clear_btn,
            ]:
                b.setEnabled(not running)
            for b in [self.google_stop_btn, self.naver_stop_btn]:
                b.setEnabled(running)

        def start_google_indexing(self):
            if self.worker and self.worker.isRunning():
                QMessageBox.information(self, "실행 중", "이미 작업이 실행 중입니다.")
                return
            seeds = self._collect_seed_urls("google")
            if not seeds:
                QMessageBox.warning(self, "입력 필요", "구글 탭에 사이트 주소를 1개 이상 입력하세요.")
                return
            self.save_all_configs()
            self.current_service_type = "google"
            self.controller.logger.set_gui_log_widget(self.google_log)
            self.worker = IndexingWorker(self.controller, seeds, "google")
            self.worker.progress_updated.connect(self.on_progress)
            self.worker.finished.connect(self.on_finished)
            self._set_running(True)
            self.status_label.setText("구글 등록 작업 실행 중...")
            self.progress_bar.setValue(0)
            self.worker.start()

        def start_naver_indexing(self):
            if self.worker and self.worker.isRunning():
                QMessageBox.information(self, "실행 중", "이미 작업이 실행 중입니다.")
                return
            seeds = self._collect_seed_urls("naver")
            if not seeds:
                QMessageBox.warning(self, "입력 필요", "네이버 탭에 사이트 주소를 1개 이상 입력하세요.")
                return
            self.save_all_configs()
            self.current_service_type = "naver"
            self.controller.logger.set_gui_log_widget(self.naver_log)
            self.worker = IndexingWorker(self.controller, seeds, "naver")
            self.worker.progress_updated.connect(self.on_progress)
            self.worker.finished.connect(self.on_finished)
            self._set_running(True)
            self.status_label.setText("네이버 색인 요청 실행 중...")
            self.progress_bar.setValue(0)
            self.worker.start()

        def stop_indexing(self):
            if self.worker and self.worker.isRunning():
                self.controller.stop_indexing()
                self.status_label.setText("중지 요청 중...")
            else:
                self.status_label.setText("실행 중인 작업이 없습니다.")

        def on_progress(self, message: str, progress: int):
            self.status_label.setText(message)
            self.progress_bar.setValue(max(0, min(100, progress)))
            self._append_log(self.current_service_type, message)

        def on_finished(self, result: Dict[str, int]):
            self._set_running(False)
            self.progress_bar.setValue(100)
            self.status_label.setText("완료")
            self._auto_commit_async(result)
            service_label = "구글" if self.current_service_type == "google" else "네이버"
            self._show_brief_notice(f"{service_label} 작업이 완료되었습니다.")
            self.worker = None

        @staticmethod
        def _run_git(cwd: str, args: List[str], timeout: int = 45) -> subprocess.CompletedProcess:
            return subprocess.run(
                ["git"] + args,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )

        def _find_git_repo_dir(self) -> Optional[str]:
            for base in [APP_BASE_DIR, SCRIPT_DIR, os.path.dirname(APP_BASE_DIR), os.path.dirname(SCRIPT_DIR)]:
                if base and os.path.isdir(os.path.join(base, ".git")):
                    return base
            return None

        def _auto_commit_async(self, result: Dict[str, int]):
            Thread(target=self._auto_commit_worker, args=(result,), daemon=True).start()

        def _auto_commit_worker(self, result: Dict[str, int]):
            repo_dir = self._find_git_repo_dir()
            if not repo_dir:
                return
            try:
                add = self._run_git(repo_dir, ["add", "-A"])
                if add.returncode != 0:
                    self.controller.logger.log(f"자동 Git add 실패: {(add.stderr or add.stdout).strip()}", "ERROR")
                    return

                staged = self._run_git(repo_dir, ["diff", "--cached", "--name-only"])
                if staged.returncode != 0:
                    self.controller.logger.log(f"자동 Git 변경 확인 실패: {(staged.stderr or staged.stdout).strip()}", "ERROR")
                    return
                changed_files = [ln.strip() for ln in (staged.stdout or "").splitlines() if ln.strip()]
                if not changed_files:
                    return

                commit_msg = (
                    f"auto: 작업 완료 ({self.current_service_type}) "
                    f"total={result.get('total', 0)} success={result.get('success', 0)} "
                    f"errors={result.get('errors', 0)} scheduled={result.get('scheduled', 0)} "
                    f"at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )
                commit = self._run_git(repo_dir, ["commit", "-m", commit_msg], timeout=90)
                if commit.returncode != 0:
                    out = (commit.stderr or commit.stdout or "").strip()
                    if "nothing to commit" in out.lower():
                        return
                    self.controller.logger.log(f"자동 Git commit 실패: {out}", "ERROR")
                    return
                self.controller.logger.log("자동 Git 커밋 완료", "SUCCESS")
            except Exception as e:
                self.controller.logger.log(f"자동 Git 처리 실패: {e}", "ERROR")


def run_gui() -> int:
    if not GUI_AVAILABLE:
        print("PyQt6 is not installed. Run: pip install PyQt6")
        return 1
    if not LICENSE_CHECK_AVAILABLE:
        print("license_check module is missing. Cannot start without machine ID license verification.")
        return 1
    app = QApplication(sys.argv)
    icon_path = os.path.join(SCRIPT_DIR, "david153.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    try:
        lm = LicenseManager()
        ok, msg = lm.verify_license()
        if not ok:
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
        QMessageBox.critical(None, "라이선스 오류", f"라이선스 확인 중 오류가 발생했습니다.\n{e}")
        return 1
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
