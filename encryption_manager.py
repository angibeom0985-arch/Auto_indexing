"""
🔐 암호화 관리 모듈 (Encryption Manager)
API 키와 토큰을 안전하게 암호화/복호화하는 엔터프라이즈급 보안 레이어

주요 기능:
- Fernet 대칭키 암호화 (AES-256 기반)
- PBKDF2 기반 마스터 비밀번호 키 생성
- 설정 파일 자동 암호화/복호화
- 비밀번호 변경 및 키 회전 지원
"""

import os
import json
import base64
import hashlib
from typing import Dict, Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class EncryptionManager:
    """설정 파일 암호화 관리 클래스"""
    
    def __init__(self, salt_file: str = '.encryption_salt'):
        """
        암호화 관리자 초기화
        
        Args:
            salt_file: Salt 값을 저장할 파일 경로
        """
        self.salt_file = salt_file
        self.salt = self._load_or_create_salt()
        self.fernet = None  # 비밀번호 설정 전까지 None
        
    def _load_or_create_salt(self) -> bytes:
        """
        Salt 값 로드 또는 새로 생성
        
        Salt는 비밀번호 해싱 시 보안성을 높이기 위한 랜덤 값입니다.
        같은 비밀번호라도 다른 Salt를 사용하면 다른 키가 생성됩니다.
        
        Returns:
            bytes: 32바이트 Salt 값
        """
        if os.path.exists(self.salt_file):
            try:
                with open(self.salt_file, 'rb') as f:
                    salt = f.read()
                    if len(salt) == 32:
                        return salt
            except Exception:
                pass
        
        # 새로운 Salt 생성 (32바이트 = 256비트)
        salt = os.urandom(32)
        try:
            with open(self.salt_file, 'wb') as f:
                f.write(salt)
        except Exception as e:
            print(f"⚠️ Salt 파일 저장 실패: {e}")
        
        return salt
    
    def generate_key(self, password: str) -> bytes:
        """
        비밀번호로부터 암호화 키 생성
        
        PBKDF2 (Password-Based Key Derivation Function 2)를 사용하여
        사용자 비밀번호를 Fernet 암호화 키로 변환합니다.
        
        Args:
            password: 마스터 비밀번호
            
        Returns:
            bytes: Base64 인코딩된 Fernet 키
        """
        # PBKDF2 설정: 600,000 반복 (OWASP 권장)
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,  # 256비트 키
            salt=self.salt,
            iterations=600000,  # 브루트포스 공격 방어
        )
        
        # 비밀번호를 바이트로 변환 후 키 생성
        password_bytes = password.encode('utf-8')
        key = base64.urlsafe_b64encode(kdf.derive(password_bytes))
        
        return key
    
    def set_password(self, password: str) -> bool:
        """
        마스터 비밀번호 설정
        
        Args:
            password: 설정할 비밀번호
            
        Returns:
            bool: 설정 성공 여부
        """
        try:
            key = self.generate_key(password)
            self.fernet = Fernet(key)
            return True
        except Exception as e:
            print(f"❌ 비밀번호 설정 실패: {e}")
            return False
    
    def encrypt_config(self, config: Dict) -> bytes:
        """
        설정 딕셔너리 암호화
        
        Args:
            config: 암호화할 설정 딕셔너리
            
        Returns:
            bytes: 암호화된 데이터
            
        Raises:
            ValueError: Fernet 객체가 초기화되지 않은 경우
        """
        if self.fernet is None:
            raise ValueError("비밀번호가 설정되지 않았습니다. set_password()를 먼저 호출하세요.")
        
        # 딕셔너리를 JSON 문자열로 변환
        json_str = json.dumps(config, ensure_ascii=False, indent=2)
        json_bytes = json_str.encode('utf-8')
        
        # Fernet 암호화
        encrypted_data = self.fernet.encrypt(json_bytes)
        
        return encrypted_data
    
    def decrypt_config(self, encrypted_data: bytes) -> Dict:
        """
        암호화된 데이터 복호화
        
        Args:
            encrypted_data: 암호화된 바이트 데이터
            
        Returns:
            Dict: 복호화된 설정 딕셔너리
            
        Raises:
            ValueError: Fernet 객체가 초기화되지 않은 경우
            cryptography.fernet.InvalidToken: 잘못된 비밀번호 또는 손상된 데이터
        """
        if self.fernet is None:
            raise ValueError("비밀번호가 설정되지 않았습니다. set_password()를 먼저 호출하세요.")
        
        # Fernet 복호화
        decrypted_bytes = self.fernet.decrypt(encrypted_data)
        json_str = decrypted_bytes.decode('utf-8')
        
        # JSON 파싱
        config = json.loads(json_str)
        
        return config
    
    def save_encrypted_config(self, config: Dict, filepath: str) -> bool:
        """
        암호화된 설정 파일 저장
        
        Args:
            config: 저장할 설정 딕셔너리
            filepath: 저장할 파일 경로
            
        Returns:
            bool: 저장 성공 여부
        """
        try:
            encrypted_data = self.encrypt_config(config)
            
            with open(filepath, 'wb') as f:
                f.write(encrypted_data)
            
            return True
            
        except Exception as e:
            print(f"❌ 암호화된 설정 저장 실패: {e}")
            return False
    
    def load_encrypted_config(self, filepath: str) -> Optional[Dict]:
        """
        암호화된 설정 파일 로드
        
        Args:
            filepath: 로드할 파일 경로
            
        Returns:
            Dict or None: 복호화된 설정 딕셔너리 (실패 시 None)
        """
        try:
            if not os.path.exists(filepath):
                return None
            
            with open(filepath, 'rb') as f:
                encrypted_data = f.read()
            
            config = self.decrypt_config(encrypted_data)
            
            return config
            
        except Exception as e:
            print(f"❌ 암호화된 설정 로드 실패: {e}")
            return None
    
    def change_password(self, old_password: str, new_password: str, config_file: str) -> bool:
        """
        마스터 비밀번호 변경 (키 회전)
        
        기존 비밀번호로 설정을 복호화한 후,
        새 비밀번호로 재암호화하여 저장합니다.
        
        Args:
            old_password: 현재 비밀번호
            new_password: 새 비밀번호
            config_file: 설정 파일 경로
            
        Returns:
            bool: 변경 성공 여부
        """
        try:
            # 1. 기존 비밀번호로 설정 로드
            self.set_password(old_password)
            config = self.load_encrypted_config(config_file)
            
            if config is None:
                print("❌ 기존 설정을 복호화할 수 없습니다. 비밀번호를 확인하세요.")
                return False
            
            # 2. 새 비밀번호로 Fernet 재초기화
            self.set_password(new_password)
            
            # 3. 새 비밀번호로 재암호화하여 저장
            success = self.save_encrypted_config(config, config_file)
            
            if success:
                print("✅ 비밀번호가 성공적으로 변경되었습니다.")
            
            return success
            
        except Exception as e:
            print(f"❌ 비밀번호 변경 실패: {e}")
            return False
    
    def check_password_strength(self, password: str) -> tuple[str, int]:
        """
        비밀번호 강도 검사
        
        Args:
            password: 검사할 비밀번호
            
        Returns:
            tuple: (강도 레벨, 점수)
                - 강도 레벨: '약함', '보통', '강함', '매우 강함'
                - 점수: 0-100
        """
        score = 0
        
        # 길이 체크
        length = len(password)
        if length >= 8:
            score += 20
        if length >= 12:
            score += 10
        if length >= 16:
            score += 10
        
        # 문자 종류 체크
        has_lower = any(c.islower() for c in password)
        has_upper = any(c.isupper() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_special = any(not c.isalnum() for c in password)
        
        if has_lower:
            score += 10
        if has_upper:
            score += 10
        if has_digit:
            score += 15
        if has_special:
            score += 15
        
        # 다양성 보너스
        variety = sum([has_lower, has_upper, has_digit, has_special])
        if variety >= 3:
            score += 10
        if variety == 4:
            score += 10
        
        # 강도 레벨 결정
        if score < 40:
            level = '약함'
        elif score < 60:
            level = '보통'
        elif score < 80:
            level = '강함'
        else:
            level = '매우 강함'
        
        return level, score


def test_encryption():
    """암호화 관리자 테스트 함수"""
    print("🔐 암호화 관리자 테스트 시작...")
    
    # 1. 초기화
    manager = EncryptionManager()
    password = "test_password_123!@#"
    manager.set_password(password)
    
    # 2. 테스트 설정
    test_config = {
        'google_service_account_file': 'my-secret-key.json',
        'google_api_key': 'AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXX',
        'naver_access_token': 'Bearer abc123def456ghi789',
        'indexnow_api_key': 'secret-indexnow-key-12345'
    }
    
    # 3. 암호화 및 저장
    print("📝 설정 암호화 중...")
    success = manager.save_encrypted_config(test_config, 'test_config.enc')
    print(f"{'✅' if success else '❌'} 암호화 저장: {success}")
    
    # 4. 복호화 및 로드
    print("📂 설정 복호화 중...")
    loaded_config = manager.load_encrypted_config('test_config.enc')
    
    if loaded_config == test_config:
        print("✅ 암호화/복호화 성공!")
        print(f"원본: {test_config}")
        print(f"복호화: {loaded_config}")
    else:
        print("❌ 데이터 불일치!")
    
    # 5. 비밀번호 강도 테스트
    print("\n🔒 비밀번호 강도 테스트:")
    test_passwords = [
        "123456",
        "password",
        "Password123",
        "P@ssw0rd!2024"
    ]
    
    for pwd in test_passwords:
        level, score = manager.check_password_strength(pwd)
        print(f"  '{pwd}': {level} (점수: {score})")
    
    # 6 정리
    try:
        os.remove('test_config.enc')
        os.remove('.encryption_salt')
        print("\n🧹 테스트 파일 정리 완료")
    except:
        pass


if __name__ == '__main__':
    test_encryption()
