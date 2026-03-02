# -*- coding: utf-8 -*-
"""Naver Search Advisor Selenium service."""

import time
import os
import sys
import html
from threading import Event
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import parse_qs, unquote, urlsplit

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


class NaverSeleniumService:
    def __init__(self, logger=None, headless: bool = False):
        self.logger = logger
        self.headless = headless
        self.driver: Optional[WebDriver] = None
        self.wait: Optional[WebDriverWait] = None
        self.submit_interval_seconds = 0.0
        self.history_confirm_timeout_seconds = 25.0
        self.daily_quota_reached = False
        self.session_disconnected = False
        script_dir = os.path.dirname(os.path.abspath(__file__))
        app_base_dir = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else script_dir
        setting_dir = os.path.join(app_base_dir, "setting")
        os.makedirs(setting_dir, exist_ok=True)
        self.chrome_profile_dir = os.path.join(setting_dir, "naver_chrome_profile")
        legacy_profile_dir = os.path.join(app_base_dir, "data", "naver_chrome_profile")
        if not os.path.exists(self.chrome_profile_dir) and os.path.exists(legacy_profile_dir):
            try:
                os.replace(legacy_profile_dir, self.chrome_profile_dir)
            except Exception:
                pass

    @staticmethod
    def _sleep_interruptible(seconds: float, stop_event: Optional[Event]) -> bool:
        if seconds <= 0:
            return bool(stop_event and stop_event.is_set())
        end_at = time.time() + seconds
        while time.time() < end_at:
            if stop_event and stop_event.is_set():
                return True
            time.sleep(0.1)
        return bool(stop_event and stop_event.is_set())

    @staticmethod
    def _normalize_history_token(value: str) -> str:
        raw = (value or "").strip()
        if not raw:
            return ""
        if raw.startswith("http://") or raw.startswith("https://"):
            parts = urlsplit(raw)
            raw = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
        else:
            raw = raw.split("#", 1)[0].strip()
        if not raw:
            return "/"
        if not raw.startswith("/"):
            raw = "/" + raw
        decoded = unquote(raw)
        if decoded != "/" and decoded.endswith("/"):
            decoded = decoded.rstrip("/")
        return decoded

    @staticmethod
    def _display_date_only(value: str) -> str:
        raw = (value or "").strip()
        if not raw:
            return "날짜없음"
        if len(raw) >= 10 and raw[4:5] == "-" and raw[7:8] == "-":
            return raw[:10]
        if "T" in raw:
            head = raw.split("T", 1)[0].strip()
            if len(head) == 10 and head[4:5] == "-" and head[7:8] == "-":
                return head
        return raw

    def wait_until_history_contains(
        self,
        submitted_url: str,
        timeout_seconds: float,
        before_count: int = 0,
        before_tokens: Optional[Set[str]] = None,
        stop_event: Optional[Event] = None,
    ) -> bool:
        expected = self._normalize_history_token(submitted_url)
        end_at = time.time() + max(0.0, timeout_seconds)
        drv = self._driver()
        before_tokens = before_tokens or set()
        while time.time() <= end_at:
            if stop_event and stop_event.is_set():
                return False
            try:
                links = drv.find_elements(By.CSS_SELECTOR, "tbody tr td a.api_link")
                if before_count > 0 and len(links) > before_count:
                    return True
                for link in links:
                    text_token = self._normalize_history_token((link.text or "").strip())
                    href_token = self._normalize_history_token((link.get_attribute("href") or "").strip())
                    if text_token == expected or href_token == expected:
                        return True
                    if text_token and text_token not in before_tokens:
                        return True
                    if href_token and href_token not in before_tokens:
                        return True
            except Exception:
                pass
            time.sleep(0.35)
        return False

    def _get_history_snapshot(self) -> Tuple[int, Set[str]]:
        drv = self._driver()
        tokens: Set[str] = set()
        links = drv.find_elements(By.CSS_SELECTOR, "tbody tr td a.api_link")
        for link in links:
            text_token = self._normalize_history_token((link.text or "").strip())
            href_token = self._normalize_history_token((link.get_attribute("href") or "").strip())
            if text_token:
                tokens.add(text_token)
            if href_token:
                tokens.add(href_token)
        return len(links), tokens

    def log(self, message: str, level: str = "INFO"):
        if self.logger:
            self.logger.log(message, level)
        else:
            print(f"[{level}] {message}")

    def _driver(self) -> WebDriver:
        if self.driver is None:
            raise RuntimeError("WebDriver not initialized")
        return self.driver

    def _wait(self) -> WebDriverWait:
        if self.wait is None:
            raise RuntimeError("WebDriverWait not initialized")
        return self.wait

    def setup_driver(self) -> bool:
        try:
            self.log("크롬 브라우저 실행을 시작합니다.", "INFO")
            os.makedirs(self.chrome_profile_dir, exist_ok=True)
            options = Options()
            if self.headless:
                options.add_argument("--headless=new")
            options.add_argument(f"--user-data-dir={self.chrome_profile_dir}")
            options.add_argument("--profile-directory=Default")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument("--start-maximized")
            options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
            options.add_experimental_option("useAutomationExtension", False)
            options.add_argument(
                "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )

            try:
                from webdriver_manager.chrome import ChromeDriverManager

                self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
            except Exception:
                self.driver = webdriver.Chrome(options=options)

            drv = self._driver()
            self.wait = WebDriverWait(drv, 12)
            try:
                drv.maximize_window()
            except Exception:
                drv.set_window_size(1920, 1080)
            self.log("크롬 브라우저 실행 완료", "SUCCESS")
            return True
        except Exception as e:
            self.log(f"크롬 드라이버 준비 실패: {e}", "ERROR")
            return False

    def login_naver(self, username: str, password: str) -> bool:
        try:
            drv = self._driver()
            wait = self._wait()
            self.log("네이버 서치어드바이저 보드로 이동합니다.", "INFO")
            drv.get("https://searchadvisor.naver.com/console/board")
            time.sleep(1.2)

            # 濡쒓렇???섏씠吏濡??대룞??寃쎌슦 ?먮룞 ?낅젰
            if "nid.naver.com" in (drv.current_url or ""):
                self.log("로그인 화면 감지: 아이디/비밀번호를 입력합니다.", "INFO")
                id_input = wait.until(EC.element_to_be_clickable((By.ID, "id")))
                id_input.click()
                id_input.clear()
                id_input.send_keys(username)

                pw_input = wait.until(EC.element_to_be_clickable((By.ID, "pw")))
                pw_input.click()
                pw_input.clear()
                pw_input.send_keys(password)

                login_btn = wait.until(EC.element_to_be_clickable((By.ID, "log.login")))
                login_btn.click()
                time.sleep(1.5)
                self.log("로그인 버튼 클릭 완료", "INFO")

                # 2차 인증/리다이렉트 대기
                for _ in range(45):
                    if "searchadvisor.naver.com" in (drv.current_url or ""):
                        break
                    time.sleep(1)

            drv.get("https://searchadvisor.naver.com/console/board")
            time.sleep(1.2)
            ok = "searchadvisor.naver.com" in (drv.current_url or "")
            if ok:
                self.log("네이버 로그인 완료", "SUCCESS")
            return ok
        except Exception as e:
            self.log(f"네이버 로그인 실패: {e}", "ERROR")
            return False

    @staticmethod
    def _norm_site(url: str) -> str:
        return (url or "").strip().rstrip("/").replace("http://", "https://")

    @staticmethod
    def _site_key(url: str) -> str:
        raw = (url or "").strip().lower().rstrip("/")
        if raw.startswith("https://"):
            raw = raw[len("https://") :]
        elif raw.startswith("http://"):
            raw = raw[len("http://") :]
        return raw

    @staticmethod
    def _extract_site_from_href(href: str) -> str:
        val = (href or "").strip()
        if not val:
            return ""
        try:
            q = parse_qs(urlsplit(val).query or "")
            site = (q.get("site") or [""])[0]
            return site.strip()
        except Exception:
            return ""

    def _find_link_by_target_url(self, target_site_url: str):
        drv = self._driver()
        target_key = self._site_key(self._norm_site(target_site_url))
        js = """
        const target = arguments[0];
        const anchors = Array.from(document.querySelectorAll("a[href], a"));
        const normalize = (v) => {
          let s = (v || "").trim().toLowerCase();
          s = s.replace(/^https?:\\/\\//, "").replace(/\\/$/, "");
          return s;
        };
        for (const a of anchors) {
          const txt = normalize(a.textContent || "");
          const href = a.getAttribute("href") || "";
          let site = "";
          try {
            const u = new URL(href, location.origin);
            site = normalize(u.searchParams.get("site") || "");
          } catch (_) {}
          const hrefNorm = normalize(href);
          if (txt === target || site === target || hrefNorm.includes(target)) {
            return a;
          }
        }
        return null;
        """
        try:
            return drv.execute_script(js, target_key)
        except Exception:
            return None

    def select_site_from_list(self, target_site_url: str) -> bool:
        try:
            drv = self._driver()
            target = self._norm_site(target_site_url)
            target_key = self._site_key(target)
            self.log(f"대상 사이트 선택 시도: {target}", "INFO")
            css_candidates = [
                "a[href*='/console/site/dashboard?site=']",
                "a[href*='/console/site/request/crawl?site=']",
                "a.api_link",
                "a[href*='site=']",
            ]
            end_at = time.time() + 12.0
            links = []
            while time.time() < end_at:
                merged = []
                seen = set()
                for css in css_candidates:
                    try:
                        for el in drv.find_elements(By.CSS_SELECTOR, css):
                            key = el.id
                            if key not in seen:
                                merged.append(el)
                                seen.add(key)
                    except Exception:
                        continue
                if merged:
                    links = merged
                    break
                time.sleep(0.35)

            if not links:
                self.log("사이트 목록 링크를 찾지 못했습니다. 보드 DOM 구조 변경 가능성이 있습니다.", "ERROR")
                return False

            for link in links:
                text_site = self._norm_site((link.text or ""))
                href_site = self._norm_site(self._extract_site_from_href(link.get_attribute("href") or ""))
                if target_key in {self._site_key(text_site), self._site_key(href_site)}:
                    drv.execute_script("arguments[0].scrollIntoView({block:'center'});", link)
                    time.sleep(0.1)
                    drv.execute_script("arguments[0].click();", link)
                    time.sleep(1.0)
                    self.log(f"대상 사이트 선택 완료: {target}", "SUCCESS")
                    return True

            # Fallback: scan entire DOM for an anchor that matches user-entered URL.
            dom_link = self._find_link_by_target_url(target)
            if dom_link is not None:
                drv.execute_script("arguments[0].scrollIntoView({block:'center'});", dom_link)
                time.sleep(0.1)
                drv.execute_script("arguments[0].click();", dom_link)
                time.sleep(1.0)
                self.log(f"대상 사이트 선택 완료(DOM 검색): {target}", "SUCCESS")
                return True

            preview = []
            for link in links[:5]:
                txt = (link.text or "").strip()
                href_site = self._extract_site_from_href(link.get_attribute("href") or "")
                if txt or href_site:
                    preview.append(f"text='{txt}' site='{href_site}'")
            if preview:
                self.log("감지된 사이트 후보(일부): " + " | ".join(preview), "WARNING")
            return False
        except Exception as e:
            self.log(f"사이트 선택 실패 ({type(e).__name__}): {e!r}", "ERROR")
            return False

    def navigate_to_search_advisor(self, site_url: str) -> bool:
        try:
            self.log("사이트 목록 화면으로 이동합니다.", "INFO")
            self._driver().get("https://searchadvisor.naver.com/console/board")
            time.sleep(1.0)
            return self.select_site_from_list(site_url)
        except Exception as e:
            self.log(f"보드 이동 실패: {e}", "ERROR")
            return False

    def navigate_to_crawl_request_page(self) -> bool:
        try:
            drv = self._driver()
            wait = self._wait()
            self.log("요청 > 웹 페이지 수집 메뉴로 이동합니다.", "INFO")

            request_candidates = [
                "//div[contains(@class,'item_title_P3-BA') and contains(normalize-space(.), '요청')]",
                "//div[contains(normalize-space(.), '요청')]",
            ]
            request_menu = None
            for xp in request_candidates:
                try:
                    request_menu = wait.until(EC.element_to_be_clickable((By.XPATH, xp)))
                    if request_menu is not None:
                        break
                except Exception:
                    continue
            if request_menu is None:
                return False
            drv.execute_script("arguments[0].click();", request_menu)
            time.sleep(0.6)

            crawl_menu = None
            css_candidates = [
                "a[href*='/console/site/request/crawl?site=']",
                "a[aria-current='page'][href*='/request/crawl']",
            ]
            for css in css_candidates:
                try:
                    crawl_menu = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, css)))
                    if crawl_menu is not None:
                        break
                except Exception:
                    continue
            if crawl_menu is None:
                crawl_candidates = [
                    "//a[contains(@href,'/console/site/request/crawl') and .//div[contains(normalize-space(.), '웹 페이지 수집')]]",
                    "//div[contains(@class,'item_title_P3-BA') and contains(normalize-space(.), '웹 페이지 수집')]",
                    "//div[contains(normalize-space(.), '웹 페이지 수집')]",
                ]
                for xp in crawl_candidates:
                    try:
                        crawl_menu = wait.until(EC.element_to_be_clickable((By.XPATH, xp)))
                        if crawl_menu is not None:
                            break
                    except Exception:
                        continue
            if crawl_menu is None:
                return False
            drv.execute_script("arguments[0].click();", crawl_menu)
            time.sleep(1.0)
            self.log("웹 페이지 수집 화면 진입 완료", "SUCCESS")
            return True
        except Exception as e:
            self.log(f"요청 화면 이동 실패: {e}", "ERROR")
            return False

    def get_already_submitted_urls(self) -> Set[str]:
        out: Set[str] = set()
        try:
            for cell in self._driver().find_elements(By.CSS_SELECTOR, "td.url_pGZas"):
                u = (cell.text or "").strip()
                if u:
                    out.add(u)
        except Exception:
            pass
        return out

    def submit_single_url(self, url: str, stop_event: Optional[Event] = None) -> bool:
        try:
            self.session_disconnected = False
            drv = self._driver()
            wait = self._wait()
            self.log(f"색인 요청 URL 입력: {url}", "INFO")
            before_count, before_tokens = self._get_history_snapshot()
            inp = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[maxlength='2048'][type='text']"))
            )
            inp.click()
            inp.send_keys(Keys.CONTROL, "a")
            inp.send_keys(Keys.BACKSPACE)
            time.sleep(0.1)
            inp.clear()
            inp.send_keys(url)

            confirm_btn = wait.until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//button[contains(@class,'accent')]//span[contains(normalize-space(.), '확인')]")
                )
            )
            drv.execute_script("arguments[0].click();", confirm_btn)

            # Search Advisor often uses browser native JS alerts (not DOM modal).
            # Handle alert text first because CSS selectors cannot detect this popup.
            try:
                WebDriverWait(drv, 2).until(EC.alert_is_present())
                alert_obj = drv.switch_to.alert
                alert_text = (alert_obj.text or "").strip()
                alert_obj.accept()
                low = alert_text.lower()
                if alert_text:
                    self.log(f"안내창: {alert_text}", "WARNING")
                if any(k in alert_text for k in ("초과", "할당", "요청 가능", "한도")):
                    self.daily_quota_reached = True
                    self.log("오늘 할당량 초과로 추가 요청을 중단합니다.", "WARNING")
                    return False
                if "이미 요청된" in alert_text or "이미 등록" in alert_text or "already" in low:
                    self.log("이미 요청된 URL로 판단되어 건너뜁니다.", "INFO")
                    return True
                return False
            except Exception:
                pass

            if self.wait_until_history_contains(
                url,
                self.history_confirm_timeout_seconds,
                before_count=before_count,
                before_tokens=before_tokens,
                stop_event=stop_event,
            ):
                self.log("수집 요청 내역 반영 확인 완료", "SUCCESS")
                return True
            self.log(f"요청 내역 반영 확인 실패: {url}", "WARNING")
            return False
        except Exception as e:
            low = str(e).lower()
            if (
                "httpconnectionpool(host='localhost'" in low
                or "max retries exceeded with url: /session/" in low
                or "failed to establish a new connection" in low
                or "connection refused" in low
                or "winerror 10061" in low
                or "invalid session id" in low
                or "webdriver not initialized" in low
            ):
                self.session_disconnected = True
            self.log(f"단일 URL 제출 실패: {e}", "ERROR")
            return False

    def _recover_disconnected_session(self, username: str, password: str, site_url: str) -> bool:
        self.log("브라우저 세션이 끊겨 자동 복구를 시도합니다.", "WARNING")
        try:
            self.cleanup()
        except Exception:
            pass
        self.driver = None
        self.wait = None
        self.session_disconnected = False

        if not self.setup_driver():
            self.log("세션 자동 복구 실패: 드라이버 재시작 실패", "ERROR")
            return False
        if not self.login_naver(username, password):
            self.log("세션 자동 복구 실패: 로그인 실패", "ERROR")
            return False
        if not self.navigate_to_search_advisor(site_url):
            self.log("세션 자동 복구 실패: 사이트 선택 실패", "ERROR")
            return False
        if not self.navigate_to_crawl_request_page():
            self.log("세션 자동 복구 실패: 웹 페이지 수집 화면 진입 실패", "ERROR")
            return False

        self.log("세션 자동 복구 완료", "SUCCESS")
        return True

    def submit_urls_for_crawling(
        self,
        urls: List[str],
        site_url: Optional[str] = None,
        url_meta: Optional[Dict[str, Dict[str, str]]] = None,
        stop_event: Optional[Event] = None,
        submit_order: str = "oldest",
        username: str = "",
        password: str = "",
    ) -> Tuple[int, int]:
        success = 0
        failed = 0
        skipped = 0
        try:
            if not self.navigate_to_crawl_request_page():
                return 0, len(urls)

            already = self.get_already_submitted_urls()
            meta = url_meta or {}

            # ?ㅻ옒??湲 ?곗꽑
            newest_first = str(submit_order or "").strip().lower() == "newest"
            ordered = sorted(
                urls,
                key=lambda u: (
                    1 if not (meta.get(u, {}).get("published_at", "").strip()) else 0,
                    meta.get(u, {}).get("published_at", "").strip() or ("0000-01-01T00:00:00" if newest_first else "9999-12-31T23:59:59"),
                    u,
                ),
                reverse=newest_first,
            )

            for i, u in enumerate(ordered, 1):
                if stop_event and stop_event.is_set():
                    self.log("중지 요청 감지: 네이버 제출을 중단합니다.", "WARNING")
                    break
                if self.daily_quota_reached:
                    self.log("할당량 도달로 남은 URL 제출을 중단합니다.", "WARNING")
                    break
                if self._normalize_history_token(u) == "/":
                    skipped += 1
                    continue
                m = meta.get(u, {}) or {}
                pub = self._display_date_only((m.get("published_at") or "").strip())
                title = (m.get("title") or "").strip() or "제목없음"
                safe_title = html.escape(title)
                safe_url = html.escape(u, quote=True)
                self.log(f"{pub} | <a href=\"{safe_url}\">{safe_title}</a>", "INFO")
                if u in already:
                    skipped += 1
                    continue
                if self.submit_single_url(u, stop_event=stop_event):
                    success += 1
                    already.add(u)
                    if i < len(ordered) and self.submit_interval_seconds > 0:
                        if self._sleep_interruptible(self.submit_interval_seconds, stop_event):
                            self.log("중지 요청 감지: 대기 중 네이버 제출을 중단합니다.", "WARNING")
                            break
                else:
                    if self.daily_quota_reached:
                        break
                    recovered = False
                    if (
                        self.session_disconnected
                        and site_url
                        and username
                        and password
                        and not (stop_event and stop_event.is_set())
                    ):
                        recovered = self._recover_disconnected_session(username, password, site_url)
                        if recovered and self.submit_single_url(u, stop_event=stop_event):
                            success += 1
                            already.add(u)
                            continue
                    if self.session_disconnected and not recovered:
                        self.log("세션 복구 실패로 현재 URL을 실패 처리합니다.", "ERROR")
                        failed += 1
                        self.log("세션이 비정상 상태여서 남은 URL 제출을 중단합니다. 다음 실행에서 이어서 재시도하세요.", "WARNING")
                        break
                    failed += 1

            self.log(f"네이버 제출 완료: 성공 {success}개 | 실패 {failed}개 | 건너뜀 {skipped}개", "SUCCESS")
            return success, failed
        except Exception as e:
            self.log(f"URL 제출 처리 실패: {e}", "ERROR")
            return success, max(0, len(urls) - success)

    def cleanup(self):
        try:
            if self.driver is not None:
                self.driver.quit()
        except Exception:
            pass

    def __enter__(self):
        if not self.setup_driver():
            raise RuntimeError("WebDriver setup failed")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()

