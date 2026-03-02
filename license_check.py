# -*- coding: utf-8 -*-
"""
라이선스 및 머신 ID 검증 모듈 (Google Spreadsheet 연동)
"""

import socket
import hashlib
import json
import os
import sys
from datetime import datetime
import uuid
import subprocess
import platform
import re


class LicenseManager:
    MACHINE_ID_PREFIX = "Indexing-"
    MACHINE_ID_VERSION = "v2"
    MACHINE_ID_PEPPER = "AutoIndexing-MID-2026-03"
    FORCE_ROTATE_MACHINE_ID_ONCE = True
    FORBIDDEN_MACHINE_ID_FILENAME = "machine_id.txt"
    """라이선스 관리자 클래스 - Google Spreadsheet 연동"""

    # Google Spreadsheet ID
    SPREADSHEET_ID = "1wFMyEe1DZjiqjE3rf8H0NbC9610ZxdnIxvEMfrJrtdY"
    SHEET_NAME = "시트1"

    def __init__(self):
        self.base_dir = self._get_base_dir()
        self.state_dir = self._get_state_dir()
        self.license_file = os.path.join(self.state_dir, "license.json")
        self.rotation_marker_file = os.path.join(self.state_dir, f"machine_id_rotated_{self.MACHINE_ID_VERSION}.flag")
        self._enforce_no_machine_id_txt()
        self._cleanup_legacy_machine_id_files()
        self.license_data = self.load_license()

    def _get_base_dir(self):
        """Auto_indexing 기준 경로 반환 (EXE/PY 모두 지원)"""
        if getattr(sys, "frozen", False):
            return os.path.dirname(sys.executable)
        return os.path.dirname(os.path.abspath(__file__))

    def _get_state_dir(self):
        """버전/빌드와 무관하게 유지되는 상태 저장 경로"""
        if platform.system() == "Windows":
            candidates = [
                os.getenv("APPDATA", "").strip(),
                os.getenv("LOCALAPPDATA", "").strip(),
                os.getenv("PROGRAMDATA", "").strip(),
                os.path.expanduser("~"),
            ]
            for root in candidates:
                if root:
                    try:
                        path = os.path.join(root, "Auto_indexing")
                        os.makedirs(path, exist_ok=True)
                        return path
                    except Exception:
                        continue
        return os.path.join(self.base_dir, "setting")

    def _legacy_machine_id_paths(self):
        paths = [
            os.path.join(self.base_dir, "setting", self.FORBIDDEN_MACHINE_ID_FILENAME),
            os.path.join(self.state_dir, self.FORBIDDEN_MACHINE_ID_FILENAME),
        ]
        if platform.system() == "Windows":
            programdata = os.getenv("PROGRAMDATA", "").strip()
            if programdata:
                paths.append(os.path.join(programdata, "Auto_indexing", self.FORBIDDEN_MACHINE_ID_FILENAME))
        # 중복 제거
        deduped = []
        seen = set()
        for p in paths:
            key = os.path.normcase(os.path.abspath(p))
            if key in seen:
                continue
            seen.add(key)
            deduped.append(p)
        return deduped

    def _cleanup_legacy_machine_id_files(self):
        """더 이상 사용하지 않는 machine_id.txt 정리"""
        for path in self._legacy_machine_id_paths():
            try:
                if os.path.isfile(path):
                    os.remove(path)
            except Exception:
                pass

    def _enforce_no_machine_id_txt(self):
        """정책: machine_id.txt 파일은 생성/사용하지 않고 발견 즉시 삭제"""
        self._cleanup_legacy_machine_id_files()

    def _normalize_identifier(self, value):
        """식별자 정규화: 영숫자만 소문자로 유지"""
        if not value:
            return ""
        return "".join(ch.lower() for ch in str(value) if ch.isalnum())

    def _get_stable_uuid_node(self):
        """uuid.getnode() 값 중 랜덤 가능성이 낮은 값만 반환"""
        try:
            node = uuid.getnode()
            # 로컬 관리 비트가 켜져 있으면 랜덤/가상 값일 수 있어 제외
            if ((node >> 40) & 0x02) != 0:
                return ""
            normalized = self._normalize_identifier(f"{node:012x}")
            if not normalized or normalized == "000000000000":
                return ""
            return normalized
        except Exception:
            return ""

    def get_local_ip(self):
        """로컬 IP 주소 가져오기 (참고용)"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def get_mac_address(self):
        """MAC 주소 가져오기"""
        try:
            node = uuid.getnode()
            mac = ':'.join(['{:02x}'.format((node >> elements) & 0xff)
                            for elements in range(0, 8 * 6, 8)][::-1])
            return mac
        except Exception:
            return "00:00:00:00:00:00"

    def _get_stable_mac_identifier(self):
        """랜덤/가상 MAC 가능성이 높은 값은 제외한 식별자"""
        try:
            node = uuid.getnode()
            # 로컬 관리 비트(두 번째 최하위 비트)가 켜진 MAC은 랜덤일 수 있어 제외
            if ((node >> 40) & 0x02) != 0:
                return ""
            mac = self._normalize_identifier(self.get_mac_address())
            if not mac or mac == "000000000000":
                return ""
            return mac
        except Exception:
            return ""

    def get_windows_machine_id(self):
        """Windows SMBIOS UUID 기반 식별자"""
        invalid_values = {
            "",
            "none",
            "null",
            "tobefilledbyoeme",
            "ffffffffffffffffffffffffffffffff",
            "00000000000000000000000000000000",
        }
        try:
            if platform.system() == "Windows":
                try:
                    result = subprocess.check_output(
                        ["powershell", "-Command", "(Get-CimInstance -Class Win32_ComputerSystemProduct).UUID"],
                        shell=False,
                        stderr=subprocess.DEVNULL,
                    )
                    uuid_str = self._normalize_identifier(result.decode(errors="ignore"))
                    if uuid_str and len(uuid_str) > 10 and uuid_str not in invalid_values:
                        return uuid_str
                except Exception:
                    pass

                try:
                    result = subprocess.check_output(
                        "wmic csproduct get uuid", shell=True, stderr=subprocess.DEVNULL
                    )
                    parts = result.decode(errors="ignore").split("\n")
                    raw_uuid = parts[1].strip() if len(parts) > 1 else ""
                    uuid_str = self._normalize_identifier(raw_uuid)
                    if uuid_str and len(uuid_str) > 10 and uuid_str not in invalid_values:
                        return uuid_str
                except Exception:
                    pass

            return self._get_stable_uuid_node()
        except Exception:
            return self._get_stable_uuid_node()

    def _read_machine_id_from_registry(self):
        """Windows 레지스트리(HKCU)에서 저장된 머신 ID 조회"""
        if platform.system() != "Windows":
            return ""
        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Auto_indexing",
                0,
                winreg.KEY_READ,
            ) as key:
                value, _ = winreg.QueryValueEx(key, "MachineId")
                return self._normalize_machine_id(value)
        except Exception:
            return ""

    def _persist_machine_id_to_registry(self, machine_id):
        """Windows 레지스트리(HKCU)에 머신 ID 저장"""
        if platform.system() != "Windows":
            return
        try:
            import winreg

            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Auto_indexing") as key:
                winreg.SetValueEx(key, "MachineId", 0, winreg.REG_SZ, machine_id)
        except Exception:
            pass

    def get_windows_machine_guid(self):
        """Windows 레지스트리 MachineGuid 기반 식별자"""
        if platform.system() != "Windows":
            return ""
        try:
            import winreg

            access = winreg.KEY_READ
            if hasattr(winreg, "KEY_WOW64_64KEY"):
                access |= winreg.KEY_WOW64_64KEY

            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Cryptography",
                0,
                access,
            ) as key:
                value, _ = winreg.QueryValueEx(key, "MachineGuid")
                return self._normalize_identifier(value)
        except Exception:
            return ""

    def _get_windows_system_drive_serial(self):
        """Windows 시스템 드라이브 볼륨 시리얼 추출"""
        if platform.system() != "Windows":
            return ""
        try:
            cmd = "(Get-CimInstance -Class Win32_LogicalDisk -Filter \"DeviceID='C:'\").VolumeSerialNumber"
            result = subprocess.check_output(
                ["powershell", "-Command", cmd],
                shell=False,
                stderr=subprocess.DEVNULL,
            )
            serial = self._normalize_identifier(result.decode(errors="ignore"))
            return serial if serial else ""
        except Exception:
            return ""

    def _is_valid_machine_id(self, value):
        return bool(self._normalize_machine_id(value))

    def _normalize_machine_id(self, value):
        """머신 ID를 Indexing-+32hex 표준 포맷으로 정규화"""
        raw = (value or "").strip()
        if not raw:
            return ""

        lower = raw.lower()
        prefix_lower = self.MACHINE_ID_PREFIX.lower()
        if lower.startswith(prefix_lower):
            hex_part = lower[len(prefix_lower):]
        elif lower.startswith("indexing"):
            # 하위 호환: Indexingxxxxxxxx... 형태를 Indexing-xxxxxxxx...로 승격
            hex_part = lower[len("indexing"):].lstrip("-")
        elif lower.startswith("naver"):
            # 하위 호환: NAVER-/NAVER 접두사도 허용 후 Indexing-로 통일
            hex_part = lower[len("naver"):].lstrip("-")
        else:
            return ""

        if not re.fullmatch(r"[0-9a-f]{32}", hex_part):
            return ""

        return f"{self.MACHINE_ID_PREFIX}{hex_part}"

    def _read_first_saved_machine_id(self):
        """저장된 머신 ID 재사용 (레지스트리만 사용)"""
        registry_saved = self._read_machine_id_from_registry()
        if registry_saved:
            return registry_saved
        return ""

    def _persist_machine_id(self, machine_id):
        """머신 ID 저장 (레지스트리만 사용)"""
        self._persist_machine_id_to_registry(machine_id)

    def _should_force_rotate_machine_id(self):
        if not self.FORCE_ROTATE_MACHINE_ID_ONCE:
            return False
        return not os.path.exists(self.rotation_marker_file)

    def _mark_machine_id_rotation_done(self):
        try:
            os.makedirs(os.path.dirname(self.rotation_marker_file), exist_ok=True)
            with open(self.rotation_marker_file, "w", encoding="utf-8") as f:
                f.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        except Exception:
            pass

    def _generate_machine_id(self):
        """고정 규칙 기반 머신 ID 생성"""
        # 우선순위: MachineGuid > SMBIOS UUID > MAC 기반 UUID 노드
        machine_guid = self.get_windows_machine_guid()
        win_id = self.get_windows_machine_id()
        node_id = self._get_stable_uuid_node()
        source = machine_guid or win_id or node_id
        if not source:
            source = self._normalize_identifier(platform.node()) or "unknown"

        payload = f"{self.MACHINE_ID_VERSION}|{self.MACHINE_ID_PEPPER}|{source}"
        return f"{self.MACHINE_ID_PREFIX}{hashlib.sha256(payload.encode('utf-8')).hexdigest()[:32]}"

    def get_machine_id(self):
        """머신 고유 ID 생성/로드 (고정 알고리즘 + 최초 생성 후 고정)"""
        # 0) 기존 값 무시 후 1회 강제 교체
        if self._should_force_rotate_machine_id():
            machine_id = self._generate_machine_id()
            try:
                self._persist_machine_id(machine_id)
            except Exception:
                pass
            try:
                keep_key = str(self.license_data.get("license_key", "SPREADSHEET_VERIFIED")) if isinstance(self.license_data, dict) else "SPREADSHEET_VERIFIED"
                self.save_license(keep_key, machine_id)
            except Exception:
                pass
            self._mark_machine_id_rotation_done()
            return machine_id

        # 0) 기존 license.json의 등록값이 유효하면 우선 재사용 (업데이트 시 마이그레이션)
        try:
            registered_raw = self.license_data.get("registered_machine_id", "") if isinstance(self.license_data, dict) else ""
            registered = self._normalize_machine_id(registered_raw)
            if registered:
                self._persist_machine_id(registered)
                return registered
        except Exception:
            pass

        # 1) 저장된 머신 ID 재사용 (업데이트/재빌드 후에도 동일 유지)
        saved = self._read_first_saved_machine_id()
        if saved:
            return saved

        # 2) 새 머신 ID 생성 (고정 규칙)
        machine_id = self._generate_machine_id()

        # 3) 새 ID 저장
        try:
            self._persist_machine_id(machine_id)
        except Exception as e:
            print(f"머신 ID 저장 실패: {e}")

        return machine_id

    def load_license(self):
        """라이선스 파일 로드"""
        try:
            paths = [
                self.license_file,
                os.path.join(self.base_dir, "setting", "license.json"),  # 레거시 경로 호환
            ]
            for path in paths:
                if os.path.exists(path):
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, dict):
                        return data
            return {}
        except Exception:
            return {}

    def save_license(self, license_key, machine_id):
        """라이선스 정보 저장"""
        try:
            os.makedirs(os.path.join(self.base_dir, "setting"), exist_ok=True)

            license_data = {
                "license_key": license_key,
                "registered_machine_id": machine_id,
                "mac_address": self.get_mac_address(),
                "windows_id": self.get_windows_machine_id(),
                "local_ip": self.get_local_ip(),
                "registered_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "status": "active",
            }

            with open(self.license_file, "w", encoding="utf-8") as f:
                json.dump(license_data, f, ensure_ascii=False, indent=4)

            self.license_data = license_data
            return True
        except Exception as e:
            print(f"라이선스 저장 오류: {e}")
            return False

    def fetch_buyers_from_sheet(self):
        """Google Spreadsheet에서 구매자 정보 가져오기"""
        try:
            url = (
                f"https://docs.google.com/spreadsheets/d/{self.SPREADSHEET_ID}"
                f"/gviz/tq?tqx=out:csv&sheet={self.SHEET_NAME}"
            )

            import requests

            response = requests.get(url, timeout=10)
            response.encoding = "utf-8"

            if response.status_code == 200:
                lines = response.text.strip().split("\n")
                buyers = {}

                for line in lines[1:]:
                    try:
                        parts = line.replace('"', "").split(",")
                        if len(parts) >= 4:
                            name = parts[0].strip()
                            email = parts[1].strip()
                            machine_id = self._normalize_machine_id(parts[2].strip())
                            date = parts[3].strip()

                            if machine_id and name:
                                buyers[machine_id] = {
                                    "name": name,
                                    "email": email,
                                    "machine_id": machine_id,
                                    "expire_date": date,
                                }
                    except Exception:
                        continue

                return buyers
            else:
                print(f"스프레드시트 접근 실패: {response.status_code}")
                return {}
        except Exception as e:
            print(f"스프레드시트 로드 오류: {e}")
            return {}

    def check_machine_in_spreadsheet(self, current_machine_id):
        """스프레드시트에서 현재 머신 ID 확인"""
        buyers = self.fetch_buyers_from_sheet()

        if not buyers:
            return False, "구매자 정보를 불러올 수 없습니다. 현재 머신 ID를 데이비에게 전달해주세요."

        current_machine_id = self._normalize_machine_id(current_machine_id)
        if not current_machine_id:
            return False, "머신 ID 형식이 올바르지 않습니다."
        if current_machine_id in buyers:
            buyer_info = buyers[current_machine_id]
            expire_date = buyer_info.get("expire_date", "")

            try:
                if expire_date:
                    expire_dt = datetime.strptime(expire_date, "%Y-%m-%d")
                    if datetime.now() > expire_dt:
                        return (
                            False,
                            f"라이선스가 만료되었습니다.\n구매자: {buyer_info['name']}\n만료일: {expire_date}",
                        )
            except Exception:
                pass

            return True, f"인증 성공\n구매자: {buyer_info['name']}\n머신 ID: {current_machine_id[:16]}..."

        return (
            False,
            f"등록되지 않은 컴퓨터입니다.\n현재 머신 ID: {current_machine_id}\n\n구매 후 머신 ID를 등록해주세요.",
        )

    def verify_license(self):
        """라이선스 검증 - Google Spreadsheet 기반"""
        current_machine_id = self.get_machine_id()
        is_valid, message = self.check_machine_in_spreadsheet(current_machine_id)

        if not is_valid:
            return False, message

        if not self.license_data or self.license_data.get("registered_machine_id") != current_machine_id:
            self.save_license("SPREADSHEET_VERIFIED", current_machine_id)

        return True, message

    def get_license_info(self):
        """라이선스 정보 반환"""
        current_machine_id = self.get_machine_id()
        buyers = self.fetch_buyers_from_sheet()

        if current_machine_id in buyers:
            buyer = buyers[current_machine_id]
            return {
                "status": "등록됨",
                "name": buyer.get("name", "N/A"),
                "email": buyer.get("email", "N/A"),
                "machine_id": current_machine_id,
                "mac_address": self.get_mac_address(),
                "local_ip": self.get_local_ip(),
                "expire_date": buyer.get("expire_date", "N/A"),
            }

        return {
            "status": "미등록",
            "name": "N/A",
            "email": "N/A",
            "machine_id": current_machine_id,
            "mac_address": self.get_mac_address(),
            "local_ip": self.get_local_ip(),
            "expire_date": "N/A",
        }
