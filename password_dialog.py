"""
🔑 비밀번호 다이얼로그 (Password Dialog)
마스터 비밀번호 입력 및 설정을 위한 PyQt6 다이얼로그

주요 기능:
- 최초 실행 시 비밀번호 설정 다이얼로그
- 비밀번호 강도 표시 (약함/보통/강함/매우 강함)
- 비밀번호 변경 다이얼로그
- 비밀번호 가시성 토글
"""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                              QLineEdit, QPushButton, QProgressBar, QMessageBox)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont


class PasswordDialog(QDialog):
    """마스터 비밀번호 입력 다이얼로그"""
    
    def __init__(self, mode='login', parent=None):
        """
        비밀번호 다이얼로그 초기화
        
        Args:
            mode: 'login' (로그인) 또는 'setup' (최초 설정) 또는 'change' (변경)
            parent: 부모 위젯
        """
        super().__init__(parent)
        self.mode = mode
        self.password = None
        self.new_password = None
        self.init_ui()
    
    def init_ui(self):
        """UI 초기화"""
        if self.mode == 'login':
            self.setWindowTitle("🔐 마스터 비밀번호")
            title_text = "설정 파일 복호화를 위해\n마스터 비밀번호를 입력하세요"
        elif self.mode == 'setup':
            self.setWindowTitle("🆕 마스터 비밀번호 설정")
            title_text = "설정 파일 암호화를 위한\n마스터 비밀번호를 생성하세요"
        else:  # change
            self.setWindowTitle("🔄 비밀번호 변경")
            title_text = "마스터 비밀번호를 변경합니다"
        
        self.setModal(True)
        self.setFixedSize(400, 350 if self.mode == 'setup' else 250)
        
        # 다크 테마
        self.setStyleSheet("""
            QDialog {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgb(25, 35, 65), stop:1 rgb(35, 45, 85));
            }
            QLabel {
                color: rgba(255, 255, 255, 0.9);
            }
            QLineEdit {
                background: rgba(255, 255, 255, 0.1);
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 8px;
                color: rgba(255, 255, 255, 0.9);
                padding: 10px;
                font-size: 12px;
            }
            QLineEdit:focus {
                background: rgba(255, 255, 255, 0.15);
                border: 1px solid rgba(255, 255, 255, 0.4);
            }
            QPushButton {
                background: rgba(255, 255, 255, 0.15);
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 8px;
                color: rgba(255, 255, 255, 0.9);
                padding: 10px 20px;
                font-weight: 500;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.25);
            }
            QPushButton:pressed {
                background: rgba(255, 255, 255, 0.1);
            }
            QProgressBar {
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 4px;
                text-align: center;
                color: white;
                background: rgba(0, 0, 0, 0.3);
            }
            QProgressBar::chunk {
                border-radius: 3px;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(30, 30, 30, 30)
        
        # 제목
        title = QLabel(title_text)
        title.setFont(QFont("Consolas", 11, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("margin-bottom: 10px;")
        layout.addWidget(title)
        
        # Change 모드일 경우 기존 비밀번호 입력
        if self.mode == 'change':
            old_pwd_label = QLabel("현재 비밀번호:")
            old_pwd_label.setFont(QFont("Consolas", 9))
            layout.addWidget(old_pwd_label)
            
            self.old_password_input = QLineEdit()
            self.old_password_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.old_password_input.setPlaceholderText("현재 비밀번호를 입력하세요...")
            layout.addWidget(self.old_password_input)
        
        # 비밀번호 입력
        pwd_label = QLabel("새 비밀번호:" if self.mode == 'change' else "비밀번호:")
        pwd_label.setFont(QFont("Consolas", 9))
        layout.addWidget(pwd_label)
        
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText("최소 8자 이상, 영문/숫자/특수문자 포함...")
        
        if self.mode == 'setup':
            self.password_input.textChanged.connect(self.update_strength)
        
        layout.addWidget(self.password_input)
        
        # Setup 모드일 경우 비밀번호 강도 표시
        if self.mode == 'setup':
            self.strength_bar = QProgressBar()
            self.strength_bar.setMaximum(100)
            self.strength_bar.setValue(0)
            self.strength_bar.setFormat("비밀번호 강도: %p%")
            layout.addWidget(self.strength_bar)
            
            self.strength_label = QLabel("강도: -")
            self.strength_label.setFont(QFont("Consolas", 9))
            self.strength_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(self.strength_label)
            
            # 비밀번호 확인 입력
            confirm_label = QLabel("비밀번호 확인:")
            confirm_label.setFont(QFont("Consolas", 9))
            layout.addWidget(confirm_label)
            
            self.confirm_input = QLineEdit()
            self.confirm_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.confirm_input.setPlaceholderText("비밀번호를 다시 입력하세요...")
            layout.addWidget(self.confirm_input)
        
        # 버튼들
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        self.cancel_btn = QPushButton("취소")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)
        
        ok_text = "설정" if self.mode == 'setup' else "확인"
        self.ok_btn = QPushButton(ok_text)
        self.ok_btn.clicked.connect(self.validate_and_accept)
        self.ok_btn.setDefault(True)
        button_layout.addWidget(self.ok_btn)
        
        layout.addLayout(button_layout)
    
    def update_strength(self, password: str):
        """
        비밀번호 강도 업데이트
        
        Args:
            password: 검사할 비밀번호
        """
        if not password:
            self.strength_bar.setValue(0)
            self.strength_label.setText("강도: -")
            return
        
        # 간단한 강도 계산
        score = 0
        
        # 길이
        length = len(password)
        if length >= 8:
            score += 20
        if length >= 12:
            score += 10
        if length >= 16:
            score += 10
        
        # 문자 종류
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
        
        # 다양성
        variety = sum([has_lower, has_upper, has_digit, has_special])
        if variety >= 3:
            score += 10
        if variety == 4:
            score += 10
        
        # 강도 레벨
        if score < 40:
            level = "약함"
            color = "#F44336"
        elif score < 60:
            level = "보통"
            color = "#FF9800"
        elif score < 80:
            level = "강함"
            color = "#4CAF50"
        else:
            level = "매우 강함"
            color = "#2196F3"
        
        self.strength_bar.setValue(score)
        self.strength_bar.setStyleSheet(f"QProgressBar::chunk {{ background: {color}; }}")
        self.strength_label.setText(f"강도: {level} ({score}점)")
    
    def validate_and_accept(self):
        """비밀번호 검증 및 다이얼로그 승인"""
        password = self.password_input.text()
        
        # 기본 검증
        if not password:
            QMessageBox.warning(self, "오류", "비밀번호를 입력하세요!")
            return
        
        if self.mode == 'setup':
            # Setup 모드 검증
            confirm = self.confirm_input.text()
            
            if password != confirm:
                QMessageBox.warning(self, "오류", "비밀번호가 일치하지 않습니다!")
                return
            
            if len(password) < 8:
                QMessageBox.warning(self, "오류", "비밀번호는 최소 8자 이상이어야 합니다!")
                return
        
        elif self.mode == 'change':
            # Change 모드 검증
            old_password = self.old_password_input.text()
            
            if not old_password:
                QMessageBox.warning(self, "오류", "현재 비밀번호를 입력하세요!")
                return
            
            self.password = old_password  # 기존 비밀번호 저장
            self.new_password = password  # 새 비밀번호 저장
        
        if self.mode != 'change':
            self.password = password
        
        self.accept()
    
    def get_password(self) -> str:
        """입력된 비밀번호 반환"""
        return self.password
    
    def get_new_password(self) -> str:
        """새 비밀번호 반환 (change 모드용)"""
        return self.new_password


def test_password_dialog():
    """비밀번호 다이얼로그 테스트"""
    from PyQt6.QtWidgets import QApplication
    import sys
    
    app = QApplication(sys.argv)
    
    # 1. Setup 모드 테스트
    print("1. Setup 모드 테스트...")
    dialog = PasswordDialog(mode='setup')
    if dialog.exec() == QDialog.DialogCode.Accepted:
        print(f"✅ 설정된 비밀번호: {dialog.get_password()}")
    else:
        print("❌ 취소됨")
    
    # 2. Login 모드 테스트
    print("\n2. Login 모드 테스트...")
    dialog = PasswordDialog(mode='login')
    if dialog.exec() == QDialog.DialogCode.Accepted:
        print(f"✅ 입력된 비밀번호: {dialog.get_password()}")
    else:
        print("❌ 취소됨")
    
    # 3. Change 모드 테스트
    print("\n3. Change 모드 테스트...")
    dialog = PasswordDialog(mode='change')
    if dialog.exec() == QDialog.DialogCode.Accepted:
        print(f"✅ 기존 비밀번호: {dialog.get_password()}")
        print(f"✅ 새 비밀번호: {dialog.get_new_password()}")
    else:
        print("❌ 취소됨")


if __name__ == '__main__':
    test_password_dialog()
