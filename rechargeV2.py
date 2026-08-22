import os
import auth
import traceback
import time
import base64
from typing import List, Optional
from selenium.webdriver.remote.webelement import WebElement

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException

import requests
import json
import random

class RechargeV2:
    def __init__(self, *, wait_timeout_seconds: Optional[int] = None, headless: Optional[bool] = None):
        """
        초기 설정을 구성합니다.

        - wait_timeout_seconds: WebDriverWait 타임아웃을 설정합니다. 미지정 시 환경변수 WAIT_TIMEOUT_SECONDS(기본 30)를 사용합니다.
        - headless: 헤드리스 모드 여부. 미지정 시 환경변수 HEADLESS(기본 true)를 사용합니다.
        """
        self._wait_timeout_seconds = (
            int(wait_timeout_seconds)
            if wait_timeout_seconds is not None
            else int(os.environ.get("WAIT_TIMEOUT_SECONDS", "30") or 30)
        )
        if headless is None:
            headless_env = os.environ.get("HEADLESS", "true").lower()
            self._headless = headless_env not in ("0", "false", "no")
        else:
            self._headless = bool(headless)

    def _create_driver(self) -> webdriver.Chrome:
        """Chrome WebDriver를 생성하고 공통 옵션을 적용합니다."""
        chrome_options = Options()
        if self._headless:
            chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        return webdriver.Chrome(options=chrome_options)

    def _login(self, wait: WebDriverWait, username: str, password: str) -> None:
        """로그인 페이지로 이동하고 ID/PW 입력 후 로그인 버튼을 클릭합니다."""
        id_input = wait.until(EC.presence_of_element_located((By.ID, "inpUserId")))
        id_input.send_keys(username)
        pw_input = wait.until(EC.presence_of_element_located((By.ID, "inpUserPswdEncn")))
        pw_input.send_keys(password)
        login_button = wait.until(EC.element_to_be_clickable((By.ID, "btnLogin")))
        login_button.click()

    def _select_amount(self, wait: WebDriverWait, amount: int) -> None:
        """
        허용된 금액 중 유효한 값을 선택 요소에 반영합니다.

        허용 범위를 벗어나면 기본값 10000원을 선택합니다.
        """
        allowed_values = {"5000", "10000", "20000", "30000", "50000", "100000", "150000"}
        desired_value = str(amount)
        if desired_value not in allowed_values:
            desired_value = "10000"
        select_el = wait.until(
            EC.element_to_be_clickable((By.ID, "EcAmt"))
        )
        # select_el = wait.until(EC.presence_of_element_located((By.ID, "EcAmt")))
        Select(select_el).select_by_value(desired_value)

    def _dismiss_overlays(self, driver: webdriver.Chrome) -> None:
        """화면을 가리는 팝업이나 오버레이를 제거합니다."""
        try:
            # 일반적인 알림/공지 팝업 닫기 시도
            close_selectors = [
                "button.btn-close",
                "a.btn-close",
                ".popup-close",
                ".layer-close",
                "button[onclick*='close']",
            ]
            for selector in close_selectors:
                try:
                    close_btns = driver.find_elements(By.CSS_SELECTOR, selector)
                    for btn in close_btns:
                        if btn.is_displayed():
                            print(f"[Recharge] Dismissing overlay via selector: {selector}")
                            btn.click()
                            time.sleep(0.3)
                except Exception:
                    pass
        except Exception as e:
            print(f"[Recharge] Overlay dismissal check failed (non-critical): {e}")

    def _click_payment_button(self, wait: WebDriverWait) -> None:
        """결제 버튼을 클릭합니다. 오버레이 회피 로직을 포함합니다."""
        driver = wait._driver
        btn = None
        
        # 버튼 찾기: CSS 우선, 실패 시 XPATH 폴백
        try:
            btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "#con1 > div > div.btn-wrap02.mt-30.easyAfter > button")))
        except TimeoutException:
            btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[@id='con1']/div/div[3]/button")))
        
        if not btn:
            raise TimeoutException("Payment button not found")
        
        # 버튼을 화면에 보이도록 스크롤
        try:
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
            time.sleep(0.5)
        except Exception as e:
            print(f"[Recharge] Scroll into view failed (non-critical): {e}")
        
        # 오버레이 제거 시도
        self._dismiss_overlays(driver)
        
        # 일반 클릭 시도 (최대 3회 재시도)
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                btn.click()
                print("[Recharge] Payment button clicked successfully")
                return
            except ElementClickInterceptedException as e:
                print(f"[Recharge] Click intercepted (attempt {attempt}/{max_retries}): {e}")
                if attempt < max_retries:
                    self._dismiss_overlays(driver)
                    time.sleep(0.5)
                else:
                    # 최종 폴백: JavaScript 클릭
                    print("[Recharge] Falling back to JavaScript click")
                    try:
                        driver.execute_script("arguments[0].click();", btn)
                        print("[Recharge] JavaScript click succeeded")
                        return
                    except Exception as js_err:
                        print(f"[Recharge] JavaScript click also failed: {js_err}")
                        raise ElementClickInterceptedException(
                            f"Payment button not clickable after {max_retries} retries and JS fallback"
                        ) from e

    def _switch_to_ecaccount_popup(self, driver: webdriver.Chrome, timeout_seconds: float = 10) -> None:
        """URL에 ecAccount.do가 포함된 팝업으로 전환합니다. 없으면 기존 창을 유지합니다."""
        target_substr = "dhlottery.co.kr/ecAccount.do"
        original_handle = getattr(driver, "current_window_handle", None)
        start_ts = time.time()
        logged_handles = None

        while time.time() - start_ts < timeout_seconds:
            handles = driver.window_handles
            handles_snapshot = tuple(handles)
            if handles_snapshot != logged_handles:
                print(f"[Recharge] Window handles after payment click: {handles}")
                logged_handles = handles_snapshot
            for handle in handles:
                try:
                    driver.switch_to.window(handle)
                    current_url = driver.current_url or ""
                    print(f"[Recharge] Inspecting window handle={handle} url={current_url}")
                    if target_substr in current_url:
                        print(f"[Recharge] Switched to target popup: {current_url}")
                        return
                except Exception:
                    continue
            time.sleep(0.2)

        if original_handle:
            try:
                driver.switch_to.window(original_handle)
            except Exception:
                pass
        print("[Recharge] Target popup (ecAccount.do) not found; staying in current window")

    def _infer_keypad_layout_via_openrouter(self, layout_img_src: str) -> Optional[List[int]]:
        """
        키패드 프롬프트 이미지를 기반으로 0~9의 배열 순서를 OpenRouter로부터 추론합니다.

        실패(네트워크/HTTP/파싱/스키마) 시 None을 반환합니다.
        """
        print(f"[Recharge] Inferring keypad layout via OpenRouter: {layout_img_src}")
        api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
        # 하드코딩된 모델 목록 (필요 시 이 배열만 수정하세요)
        models: List[str] = [
            # "x-ai/grok-4.1-fast",
            "openrouter/healer-alpha",
            # "google/gemini-2.0-flash-exp:free",
            # "nvidia/nemotron-nano-12b-v2-vl:free",
            "mistralai/mistral-small-3.1-24b-instruct:free",
            "google/gemma-3-4b-it:free",
            "google/gemma-3-12b-it:free",
            "google/gemma-3-27b-it:free",
        ]

        if not api_key:
            print("[Recharge] OPENROUTER_API_KEY not set; skipping keypad layout inference")
            return None

        timeout_seconds = int(os.environ.get("OPENROUTER_TIMEOUT", "15") or 15)
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        # 모델 목록을 무작위로 섞은 뒤 순차 시도
        models_to_try = list(models)
        random.shuffle(models_to_try)

        for model_name in models_to_try:
            print("--------------------------------")
            print(f"[Recharge] Trying OpenRouter model: {model_name}")
            payload = {
                "model": model_name,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "You are an expert at image-based data extraction. \
Analyze the given image, which contains a blue keypad with numbers and buttons labeled in Korean. \
The image always shows two identical keypads side by side, each containing digits (0-9) randomly placed in a 3x4 grid. \
The bottom row includes Korean text “전체삭제” (which means \"clear all\") and a backspace icon — ignore these elements completely. \
Your task: \
1. Focus only on the left keypad. \
2. Identify and extract only the 10 digits (0-9) visible inside the left keypad area. \
3. Read the digits in the left keypad in row-major order (left to right, top to bottom). \
4. Return the result as a numeric array containing exactly 10 numbers. \
Example output: { \"keypad_layout\": [6, 7, 8, 3, 9, 5, 4, 1, 0, 2] } \
Output only the numeric array, nothing else — no explanations or text."},
                            {"type": "image_url", "image_url": {"url": layout_img_src}},
                        ],
                    }
                ],
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "keypad",
                        "strict": True,
                        "schema": {
                            "type": "object",
                            "properties": {
                                "keypad_layout": {
                                    "type": "array",
                                    "description": "A layout of a keypad with a length of 10 with one number from 0 to 9.",
                                    "items": {"type": "number", "description": "keypad number"},
                                }
                            },
                            "required": ["keypad_layout"],
                            "additionalProperties": False,
                        },
                    },
                },
            }

            try:
                response = requests.post(
                    url="https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    data=json.dumps(payload),
                    timeout=timeout_seconds,
                )
            except Exception as e:
                print(f"[Recharge] OpenRouter request failed (model={model_name}): {e}")
                continue

            if not getattr(response, "status_code", 0) or response.status_code >= 400:
                status_code = getattr(response, "status_code", "?")
                reason = getattr(response, "reason", "")
                body_text = ""
                try:
                    body_text = response.text or ""
                except Exception:
                    body_text = ""
                err_message = ""
                try:
                    j = response.json()
                    if isinstance(j, dict):
                        if "error" in j:
                            err_val = j["error"]
                            if isinstance(err_val, dict):
                                err_message = str(err_val.get("message") or err_val.get("error") or "")
                            else:
                                err_message = str(err_val)
                        elif "message" in j:
                            err_message = str(j.get("message") or "")
                except Exception:
                    pass
                print(f"[Recharge] OpenRouter HTTP error (model={model_name}): status={status_code} reason={reason} message={err_message} body={body_text[:500]}")
                continue

            try:
                json_data = response.json()
                print("[Recharge] OpenRouter response (formatted):")
                print(json.dumps(json_data, ensure_ascii=False, indent=2))

                content_text = json_data["choices"][0]["message"]["content"]
                content_json = json.loads(content_text)
                keypad_layout_data = content_json if isinstance(content_json, list) else content_json["keypad_layout"]
            except Exception as e:
                print(f"[Recharge] OpenRouter response parsing failed (model={model_name}): {e}")
                continue

            # 아래 정규화/검증 로직은 성공 시에만 반환하며, 실패 시 다음 모델로 시도합니다.
            if len(keypad_layout_data) == 20:
                keypad_layout: List[int] = []
                seen = set()
                for x in keypad_layout_data:
                    if x not in seen:
                        keypad_layout.append(x)
                        seen.add(x)
            elif len(keypad_layout_data) == 9:
                keypad_layout = list(keypad_layout_data)
                missing = None
                for num in range(10):
                    if num not in keypad_layout_data:
                        missing = num
                        break
                if missing is not None:
                    keypad_layout.append(missing)
            elif len(keypad_layout_data) == 18:
                keypad_layout = []
                seen = set()
                for x in keypad_layout_data:
                    if x not in seen:
                        keypad_layout.append(x)
                        seen.add(x)
                missing = None
                for num in range(10):
                    if num not in keypad_layout_data:
                        missing = num
                        break
                if missing is not None:
                    keypad_layout.append(missing)
            elif len(keypad_layout_data) == 10:
                keypad_layout = list(keypad_layout_data)
            else:
                print(f"[Recharge] Keypad layout data length is not 9, 10, 18 or 20: {len(keypad_layout_data)} (model={model_name})")
                continue

            if len(keypad_layout) != 10:
                continue
            if any(type(x) != int for x in keypad_layout):
                continue
            if set(keypad_layout) != set(range(10)):
                continue
            if keypad_layout == [1, 2, 3, 4, 5, 6, 7, 8, 9, 0]:
                continue
            if keypad_layout == [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]:
                continue
            return keypad_layout

        print("[Recharge] All models failed to produce a valid keypad layout")
        return None

    def _find_keypad_element(self, wait: WebDriverWait) -> WebElement:
        """키패드 루트 요소를 탐색합니다. 우선 id, 실패 시 일반 클래스 선택자로 재시도."""
        try:
            return wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#nppfs-keypad-ecpassword")))
        except Exception:
            return wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.nppfs-keypad")))

    def _extract_layout_image_as_base64(self, driver: webdriver.Chrome, keypad: WebElement, max_retries: int = 5) -> str:
        """
        키패드 내 레이아웃 가이드 이미지를 JavaScript를 통해 base64 문자열로 반환합니다.
        
        반환 형식: data:image/png;base64,iVBORw0KGgoAAAANS...
        오류 발생 시 최대 max_retries회 재시도하며, 최종 실패 시 빈 문자열을 반환합니다.
        """
        for attempt in range(1, max_retries + 1):
            try:
                key_layout_img = keypad.find_element(By.CSS_SELECTOR, "img.kpd-image-button")
                
                base64_data = driver.execute_script("""
                    const img = arguments[0];
                    if (!img.complete || img.naturalWidth === 0) {
                        return "ERROR: Image not loaded";
                    }
                    const naturalWidth = img.naturalWidth || img.width;
                    const naturalHeight = img.naturalHeight || img.height;
                    
                    const canvas = document.createElement('canvas');
                    canvas.width = naturalWidth / 2;
                    canvas.height = naturalHeight;
                    
                    const ctx = canvas.getContext('2d');
                    ctx.drawImage(
                        img, 
                        naturalWidth / 2, 0, naturalWidth / 2, naturalHeight,
                        0, 0, naturalWidth / 2, naturalHeight
                    );
                    return canvas.toDataURL('image/png');
                """, key_layout_img)
                
                if not base64_data or not base64_data.startswith('data:'):
                    print(f"[Recharge] Failed to convert image to base64 (attempt {attempt}/{max_retries}): {base64_data}")
                    if attempt < max_retries:
                        time.sleep(1)
                        continue
                    return ""
                
                print(f"[Recharge] Base64 data: {base64_data}")
                return base64_data
            except Exception as e:
                print(f"[Recharge] Failed to extract image as base64 (attempt {attempt}/{max_retries}): {e}")
                traceback.print_exc()
                if attempt < max_retries:
                    time.sleep(1)
                    continue
                return ""
        return ""

    def _parse_coords(self, el: WebElement) -> tuple:
        """키 이미지의 data-coords(y/x)를 파싱해 정렬 키로 사용합니다. 실패 시 큰 값 반환."""
        try:
            c = (el.get_attribute("data-coords") or "0,0,0,0").split(",")
            x1, y1 = int(c[0]), int(c[1])
            return (y1, x1)
        except Exception:
            return (9999, 9999)

    def _get_sorted_key_images(self, keypad: WebElement) -> List[WebElement]:
        """키패드의 키 이미지 목록을 좌표 기준으로 정렬하여 반환합니다."""
        key_imgs = keypad.find_elements(By.CSS_SELECTOR, "img.kpd-data[data-action^='data:'][data-coords]")
        print(f"[Recharge] Found {len(key_imgs)} key images")
        return sorted(key_imgs, key=self._parse_coords)

    def _click_password_sequence(self, wait: WebDriverWait, key_imgs_sorted: List[WebElement], keypad_layout: List[int], account_password: str) -> None:
        """키패드 레이아웃과 계좌 비밀번호를 이용해 숫자 키를 순서대로 클릭합니다."""
        for num in list(account_password):
            # keypad_layout에서 password의 숫자 index 찾기
            index = keypad_layout.index(int(num))
            # 찾은 index로 key_imgs_sorted에서 해당 요소 찾기
            el = key_imgs_sorted[index]
            coords = el.get_attribute("data-coords") or "?"
            action = el.get_attribute("data-action") or "?"
            try:
                wait.until(EC.element_to_be_clickable(el))
                el.click()
                # print(f"[Recharge] Clicked number: {num} (Index: {index}, Coords: {coords})")
            except Exception as _e:
                print(f"[Recharge] Keypad click failed index={num} coords={coords} action={action}: {_e}")
                traceback.print_exc()
            time.sleep(1)

    def recharge(self, username: str, password: str, amount: int) -> dict:
        """
        예치금 충전 시도를 수행합니다.

        매개변수:
          - username: 사용자 아이디
          - password: 사용자 비밀번호
          - amount: 충전 금액 (예: 10000)

        반환:
          - {"status": "success", "amount": amount} 성공 시도
          - {"status": "error", "error": "..."} 에러 발생 시
        """
        assert type(amount) == int and amount > 0

        account_password = os.environ.get("ACCOUNT_PASSWORD", "")

        if not account_password:
            print("[Recharge] Missing environment: ACCOUNT_PASSWORD")
            return {
                "status": "error",
                "error": "Missing ACCOUNT_PASSWORD in environment",
            }

        driver = None
        try:
            try:
                driver = self._create_driver()
            except Exception as e:
                print(f"[Recharge] Failed to initialize ChromeDriver: {e}")
                traceback.print_exc()
                return {"status": "error", "error": f"driver_init: {e}"}

            wait = WebDriverWait(driver, self._wait_timeout_seconds)

            # 로그인 페이지로 이동
            driver.get("https://www.dhlottery.co.kr/login")

            # 로그인
            self._login(wait, username, password)
            
            # 충전 페이지로 이동
            driver.get("https://www.dhlottery.co.kr/mypage/mndpChrg")

            # 충전 금액 선택 (외부 입력값, 기본 10000원)
            try:
                self._select_amount(wait, amount)
            except Exception as e:
                print(f"[Recharge] Failed to select amount: {e}")
                traceback.print_exc()

            # 충전 팝업 열기
            try:
                self._click_payment_button(wait)
            except ElementClickInterceptedException as e:
                print(f"[Recharge] Payment button click intercepted: {e}")
                traceback.print_exc()
                return {"status": "error", "error": f"payment button click intercepted: {e}"}
            self._switch_to_ecaccount_popup(driver)

            # 직접 클릭: 키패드 찾기 → 레이아웃 이미지 추출 → 키패드 배열 추론 → 키 이미지 정렬 → 비밀번호 클릭
            try:
                keypad = self._find_keypad_element(wait)
                layout_img_src = self._extract_layout_image_as_base64(driver, keypad)
                if not layout_img_src:
                    print("[Recharge] Skipping keypad layout inference: layout image extraction failed after all retries")
                    return {"status": "error", "error": "layout image extraction failed"}
                keypad_layout = self._infer_keypad_layout_via_openrouter(layout_img_src)
                if keypad_layout is None:
                    print("[Recharge] Skipping keypad clicking due to missing or invalid keypad layout")
                    return {"status": "error", "error": "missing or invalid keypad layout"}
                key_imgs_sorted = self._get_sorted_key_images(keypad)
                self._click_password_sequence(wait, key_imgs_sorted, keypad_layout, account_password)
            except Exception as e:
                print(f"[Recharge] Keypad clicking failed: {e}")
                traceback.print_exc()
                return {"status": "error", "error": f"keypad clicking failed: {e}"}

            # 충전 성공 확인
            current_url = driver.current_url if driver else None
            print(f"[Recharge] Current page URL: {current_url}")
            
            try:
                alert_body = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#msgPop_1 > div.pop-up > div > div.pop-body")))
                alert_text = alert_body.text
                print(f"[Recharge] Alert text: {alert_text}")
            except TimeoutException:
                print("[Recharge] Timeout waiting for alert popup")
                return {"status": "error", "error": "timeout waiting for alert popup"}

            if current_url and "/mypage/mndpChrg" in current_url:
                print("[Recharge] Detected /mypage/mndpChrg domain in URL.")
                if "예치금 충전이 완료되었습니다." in alert_text:
                    print("[Recharge] Recharge successful")
                    return {"status": "success", "amount": amount}
                else:
                    print(f"[Recharge] Recharge failed: {alert_text}")
                    return {"status": "error", "error": alert_text}
            else:
                print(f"[Recharge] Unexpected URL: {current_url}")
                print(f"[Recharge] Recharge failed: {alert_text}")
                return {"status": "error", "error": alert_text}
            
        except Exception as e:
            print(f"[Recharge] Exception during recharge flow: {e}")
            traceback.print_exc()
            return {"status": "error", "error": str(e)}
        finally:
            if driver:
                try:
                    driver.quit()
                except Exception as e:
                    print(f"[Recharge] Failed to quit driver: {e}")
                    traceback.print_exc()