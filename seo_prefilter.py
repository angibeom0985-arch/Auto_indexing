"""
🔍 SEO 프리필터링 시스템 (SEO Pre-Filter)
색인 요청 전 URL의 SEO 적격성을 검사하여 할당량 낭비를 방지

주요 기능:
- HTTP 상태 코드 검증 (200 OK 확인)
- robots meta 태그 분석 (noindex, nofollow 감지)
- Canonical URL 일치 여부 확인
- SSL 인증서 검증
- 부적격 URL 필터링 및 상세 보고
"""

import requests
from bs4 import BeautifulSoup
from typing import List, Tuple, Dict
from urllib.parse import urlparse, urljoin, urlunparse
import time
import re


class SEOPreFilter:
    """SEO 프리필터링 클래스"""
    
    def __init__(self, logger=None):
        """
        SEO 프리필터 초기화
        
        Args:
            logger: 로깅 객체 (선택적)
        """
        self.logger = logger
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
        })
        
        # 통계
        self.stats = {
            'total_checked': 0,
            'passed': 0,
            'failed_http': 0,
            'failed_robots': 0,
            'failed_canonical': 0,
            'failed_ssl': 0,
            'failed_timeout': 0
        }
    
    def log(self, message: str, level: str = "INFO"):
        """로그 메시지 출력"""
        if self.logger:
            self.logger.log(message, level)
        else:
            print(f"[{level}] {message}")
    
    def check_http_status(self, url: str, timeout: int = 10) -> Tuple[bool, int, str]:
        """
        HTTP 상태 코드 검사
        
        Args:
            url: 검사할 URL
            timeout: 타임아웃 (초)
            
        Returns:
            Tuple[bool, int, str]: (통과 여부, 상태 코드, 메시지)
        """
        try:
            response = self.session.head(url, timeout=timeout, allow_redirects=True)
            status_code = response.status_code
            
            # 200-299 범위는 성공
            if 200 <= status_code < 300:
                return True, status_code, f"HTTP {status_code} OK"
            else:
                return False, status_code, f"HTTP {status_code} 오류"
                
        except requests.exceptions.Timeout:
            self.stats['failed_timeout'] += 1
            return False, 0, f"타임아웃 ({timeout}초 초과)"
            
        except requests.exceptions.SSLError:
            self.stats['failed_ssl'] += 1
            return False, 0, "SSL 인증서 오류"
            
        except requests.exceptions.ConnectionError:
            return False, 0, "연결 실패"
            
        except Exception as e:
            return False, 0, f"검사 실패: {type(e).__name__}"
    
    def check_robots_meta(self, url: str, timeout: int = 10) -> Tuple[bool, str]:
        """
        robots meta 태그 검사
        
        <meta name="robots" content="noindex"> 등의 태그를 확인합니다.
        
        Args:
            url: 검사할 URL
            timeout: 타임아웃 (초)
            
        Returns:
            Tuple[bool, str]: (통과 여부, 메시지)
        """
        try:
            response = self.session.get(url, timeout=timeout)
            
            if response.status_code != 200:
                return False, f"HTTP {response.status_code}"
            
            # HTML 파싱
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # robots meta 태그 찾기
            robots_meta = soup.find('meta', attrs={'name': lambda x: x and x.lower() == 'robots'})
            
            if robots_meta:
                content = robots_meta.get('content', '').lower()
                
                # noindex 또는 none이 포함되어 있으면 색인 불가
                if 'noindex' in content or 'none' in content:
                    return False, f"robots meta: {content}"
            
            # X-Robots-Tag HTTP 헤더도 확인
            x_robots = response.headers.get('X-Robots-Tag', '').lower()
            if 'noindex' in x_robots or 'none' in x_robots:
                return False, f"X-Robots-Tag: {x_robots}"
            
            return True, "robots 검사 통과"
            
        except Exception as e:
            # robots 검사 실패는 통과로 처리 (보수적 접근)
            return True, f"robots 검사 실패 (통과 처리): {type(e).__name__}"
    
    def check_canonical_url(self, url: str, timeout: int = 10) -> Tuple[bool, str]:
        """
        Canonical URL 일치 여부 확인
        
        <link rel="canonical" href="..."> 태그의 URL이
        현재 URL과 일치하는지 확인합니다.
        
        Args:
            url: 검사할 URL
            timeout: 타임아웃 (초)
            
        Returns:
            Tuple[bool, str]: (통과 여부, 메시지)
        """
        try:
            response = self.session.get(url, timeout=timeout)
            
            if response.status_code != 200:
                return False, f"HTTP {response.status_code}"
            
            # HTML 파싱
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # canonical 링크 찾기
            canonical_link = soup.find('link', attrs={'rel': lambda x: x and 'canonical' in x.lower()})
            
            if canonical_link:
                canonical_url = canonical_link.get('href', '')
                
                # 상대 URL을 절대 URL로 변환
                canonical_url = urljoin(url, canonical_url)
                
                # URL 정규화 (trailing slash, 프로토콜 등 정리)
                url_normalized = self._normalize_url(url)
                canonical_normalized = self._normalize_url(canonical_url)
                
                if url_normalized != canonical_normalized:
                    return False, f"canonical 불일치: {canonical_url}"
            
            # canonical 태그가 없거나 일치하면 통과
            return True, "canonical 검사 통과"
            
        except Exception as e:
            # canonical 검사 실패는 통과로 처리
            return True, f"canonical 검사 실패 (통과 처리): {type(e).__name__}"
    
    def _normalize_url(self, url: str) -> str:
        """
        URL 정규화 (비교를 위한 표준화)
        
        Args:
            url: 정규화할 URL
            
        Returns:
            str: 정규화된 URL
        """
        parsed = urlparse(url)

        # 스킴/호스트 소문자, fragment 제거
        scheme = (parsed.scheme or "https").lower()
        netloc = parsed.netloc.lower()
        if (scheme == "http" and netloc.endswith(":80")) or (scheme == "https" and netloc.endswith(":443")):
            netloc = netloc.rsplit(":", 1)[0]

        # 퍼센트 인코딩 대소문자 통일(%EA == %ea)
        def _normalize_percent_case(text: str) -> str:
            return re.sub(r"%[0-9a-fA-F]{2}", lambda m: m.group(0).upper(), text or "")

        path = _normalize_percent_case(parsed.path or "")
        if path != "/":
            path = path.rstrip("/")

        query = _normalize_percent_case(parsed.query or "")

        return urlunparse((scheme, netloc, path, "", query, ""))
    
    def validate_url(self, url: str) -> Tuple[bool, str]:
        """
        URL 종합 검증 (모든 검사 통합)
        
        Args:
            url: 검사할 URL
            
        Returns:
            Tuple[bool, str]: (통과 여부, 실패 사유)
        """
        self.stats['total_checked'] += 1
        
        # 1. HTTP 상태 코드 검사
        http_passed, status_code, http_msg = self.check_http_status(url)
        if not http_passed:
            self.stats['failed_http'] += 1
            return False, http_msg
        
        # 2. robots meta 검사
        robots_passed, robots_msg = self.check_robots_meta(url)
        if not robots_passed:
            self.stats['failed_robots'] += 1
            return False, robots_msg
        
        # 3. canonical URL 검사
        canonical_passed, canonical_msg = self.check_canonical_url(url)
        if not canonical_passed:
            self.stats['failed_canonical'] += 1
            return False, canonical_msg
        
        # 모든 검사 통과
        self.stats['passed'] += 1
        return True, "모든 SEO 검사 통과"
    
    def filter_urls(self, urls: List[str], delay: float = 0.5) -> Tuple[List[str], List[Tuple[str, str]]]:
        """
        URL 리스트 필터링
        
        Args:
            urls: 검사할 URL 리스트
            delay: 각 요청 간 지연 시간 (초, 서버 부하 방지)
            
        Returns:
            Tuple[List[str], List[Tuple[str, str]]]: (적격 URL 리스트, 부적격 URL 및 사유 리스트)
        """
        self.log(f"🔍 SEO 프리필터링 시작: {len(urls)}개 URL 검사...")
        
        passed_urls = []
        failed_urls = []
        
        for i, url in enumerate(urls, 1):
            # 진행 상황 표시
            if i % 10 == 0 or i == len(urls):
                self.log(f"  진행: {i}/{len(urls)} ({i*100//len(urls)}%)")
            
            # URL 검증
            is_valid, reason = self.validate_url(url)
            
            if is_valid:
                passed_urls.append(url)
                self.log(f"  ✅ [{i}] {url}", "DEBUG")
            else:
                failed_urls.append((url, reason))
                self.log(f"  ❌ [{i}] {url} - {reason}", "WARNING")
            
            # 요청 간 지연 (서버 부하 방지)
            if i < len(urls):
                time.sleep(delay)
        
        # 결과 요약
        self.log("=" * 60)
        self.log(f"📊 SEO 프리필터링 완료!")
        self.log(f"  총 검사: {self.stats['total_checked']}개")
        self.log(f"  ✅ 적격: {self.stats['passed']}개")
        self.log(f"  ❌ 부적격: {len(failed_urls)}개")
        
        if failed_urls:
            self.log(f"\n❌ 부적격 URL 상세:")
            self.log(f"  - HTTP 오류: {self.stats['failed_http']}개")
            self.log(f"  - robots noindex: {self.stats['failed_robots']}개")
            self.log(f"  - canonical 불일치: {self.stats['failed_canonical']}개")
            self.log(f"  - SSL 오류: {self.stats['failed_ssl']}개")
            self.log(f"  - 타임아웃: {self.stats['failed_timeout']}개")
            
            # 부적격 URL 목록 (최대 10개만 표시)
            self.log(f"\n📋 부적격 URL 목록 (최대 10개):")
            for i, (url, reason) in enumerate(failed_urls[:10], 1):
                self.log(f"  {i}. {url}")
                self.log(f"     사유: {reason}")
            
            if len(failed_urls) > 10:
                self.log(f"  ... 외 {len(failed_urls) - 10}개 더")
        
        self.log("=" * 60)
        
        return passed_urls, failed_urls
    
    def get_stats(self) -> Dict:
        """
        통계 정보 반환
        
        Returns:
            Dict: 통계 딕셔너리
        """
        return self.stats.copy()
    
    def reset_stats(self):
        """통계 초기화"""
        for key in self.stats:
            self.stats[key] = 0


def test_seo_prefilter():
    """SEO 프리필터 테스트 함수"""
    print("🔍 SEO 프리필터 테스트 시작...\n")
    
    # 테스트 URL 목록
    test_urls = [
        "https://www.google.com",  # 정상
        "https://httpbin.org/status/404",  # 404 오류
        "https://httpbin.org/robots.txt",  # 정상 (robots.txt)
        "https://example.com",  # 정상
        "https://nonexistent-domain-12345.com",  # 연결 실패
    ]
    
    # 프리필터 초기화
    prefilter = SEOPreFilter()
    
    # URL 필터링
    passed, failed = prefilter.filter_urls(test_urls, delay=0.5)
    
    # 결과 출력
    print(f"\n✅ 적격 URL ({len(passed)}개):")
    for url in passed:
        print(f"  - {url}")
    
    print(f"\n❌ 부적격 URL ({len(failed)}개):")
    for url, reason in failed:
        print(f"  - {url}")
        print(f"    사유: {reason}")
    
    # 통계
    stats = prefilter.get_stats()
    print(f"\n📊 통계:")
    for key, value in stats.items():
        print(f"  - {key}: {value}")


if __name__ == '__main__':
    test_seo_prefilter()
