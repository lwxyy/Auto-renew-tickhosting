from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from datetime import datetime
import time
from dateutil import parser
import os
import requests
import re

# ===================== 环境变量 =====================
SESSION_COOKIE = os.getenv("PTERODACTYL_SESSION", "")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# ===================== 浏览器 =====================
def setup_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    return webdriver.Chrome(options=options)

# ===================== Cookie 登录 =====================
def login_with_cookie(driver):
    if not SESSION_COOKIE:
        raise Exception("PTERODACTYL_SESSION not set")

    print("Logging in with cookie...")

    driver.get("https://tickhosting.com/auth/login")
    time.sleep(3)

    driver.delete_all_cookies()

    driver.add_cookie({
        "name": "pterodactyl_session",
        "value": SESSION_COOKIE,
        "domain": "tickhosting.com",
        "path": "/",
        "secure": True,
        "httpOnly": True
    })

    driver.get("https://tickhosting.com/")
    time.sleep(5)

    print("URL:", driver.current_url)
    print("Title:", driver.title)

    if "Dashboard" in driver.title or "/dashboard" in driver.current_url:
        print("✅ Cookie login success")
        return True

    driver.save_screenshot("cookie_login_failed.png")
    print(driver.page_source[:2000])
    return False

# ===================== Telegram =====================
def send_telegram_message(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    requests.post(url, json={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message
    })

# ===================== 到期时间 =====================
def get_expiration_time(driver):
    try:
        el = driver.find_elements(By.CSS_SELECTOR, ".RenewBox___StyledP-sc-1inh2rq-4")
        if not el:
            return None

        text = el[0].text.replace("EXPIRED:", "").strip()
        print("Expiration text:", text)
        return text
    except:
        return None

# ===================== 主逻辑 =====================
def main():
    driver = None
    try:
        driver = setup_driver()
        driver.set_page_load_timeout(30)

        if not login_with_cookie(driver):
            raise Exception("Cookie login failed")

        # 等页面完全加载
        time.sleep(5)
        driver.save_screenshot("dashboard.png")

        print("Looking for server card...")
        server_cards = driver.find_elements(By.CSS_SELECTOR, ".server-card")
        if not server_cards:
            raise Exception("No server card found")

        server_cards[0].click()
        time.sleep(6)

        print("Server URL:", driver.current_url)
        driver.save_screenshot("server_page.png")

        server_id_match = re.search(r'/server/([a-f0-9]+)', driver.current_url)
        server_id = server_id_match.group(1) if server_id_match else "Unknown"

        initial_time = get_expiration_time(driver)

        print("Looking for renew button...")
        renew_buttons = driver.find_elements(
            By.XPATH,
            "//button[.//span[contains(text(), 'ADD')]]"
        )

        if not renew_buttons:
            raise Exception("Renew button not found")

        renew_buttons[0].click()
        print("Renew button clicked")

        time.sleep(70)
        driver.refresh()
        time.sleep(8)

        new_time = get_expiration_time(driver)

        if initial_time and new_time:
            old = parser.parse(initial_time)
            new = parser.parse(new_time)

            if new > old:
                msg = (
                    f"✅ Tickhosting 自动续期成功\n"
                    f"Server: {server_id}\n"
                    f"旧时间: {initial_time}\n"
                    f"新时间: {new_time}"
                )
                print(msg)
                send_telegram_message(msg)
            else:
                raise Exception("Time not extended")
        else:
            raise Exception("Could not read expiration time")

    except Exception as e:
        print("❌ Error:", e)
        if driver:
            driver.save_screenshot("error.png")
        send_telegram_message(f"❌ Tickhosting 自动续期失败\n{e}")

    finally:
        if driver:
            driver.quit()

# ===================== 入口 =====================
if __name__ == "__main__":
    main()
