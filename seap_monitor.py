
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import json
import time
import os
import requests

CONFIG_PATH = "config.json"
LAST_IDS_PATH = "last_seen_ids.txt"
TELEGRAM_TOKEN = "8156868565:AAFbuMiXP8PnonxKfv-54RXhULxRtNIyRAQ"
TELEGRAM_CHAT_ID = "7111990152"
SEAP_URL = "https://www.e-licitatie.ro/pub/adv-notices/list/1"
DEBUG = True

def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def load_last_seen_ids():
    if os.path.exists(LAST_IDS_PATH):
        with open(LAST_IDS_PATH, "r") as f:
            return set(line.strip() for line in f.readlines())
    return set()

def save_last_seen_ids(ids):
    existing = load_last_seen_ids()
    all_ids = existing.union(ids)
    with open(LAST_IDS_PATH, "w") as f:
        f.write("\n".join(sorted(all_ids)))

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
    requests.post(url, data=data)

def extract_current_notice_ids(driver):
    ids = set()
    blocks = driver.find_elements(By.CSS_SELECTOR, "div.col-md-4")
    for block in blocks:
        if "Numar anunt:" in block.text:
            try:
                ids.add(block.find_element(By.TAG_NAME, "strong").text.strip())
            except:
                continue
    return ids

def process_results(driver, last_seen_ids, current_ids, found_new, ignored_initial=None):
    blocks = driver.find_elements(By.CSS_SELECTOR, "div.col-md-4")

    for block in blocks:
        try:
            if "Numar anunt:" not in block.text:
                continue

            notice_number = block.find_element(By.TAG_NAME, "strong").text.strip()

            if not notice_number.startswith("ADV"):
                continue
            if notice_number in last_seen_ids:
                if DEBUG:
                    print(f"⛔ Ignorat (deja notificat): {notice_number}")
                continue
            if ignored_initial and notice_number in ignored_initial:
                if DEBUG:
                    print(f"⚪ Ignorat (vizibil la încărcare): {notice_number}")
                continue

            found_new[0] = True
            current_ids.add(notice_number)

            message = f"🔔 <b>Anunț nou detectat</b>\n<b>Număr anunț:</b> {notice_number}"
            send_telegram_message(message)

            if DEBUG:
                print(f"✅ Notificat: {notice_number}")

        except Exception as e:
            if DEBUG:
                print(f"⚠️ Eroare la extragerea numărului anunțului: {e}")
            continue

def perform_search(driver, input_selector, text, wait_time, is_institution=False):
    try:
        input_elem = driver.find_element(By.CSS_SELECTOR, input_selector)
        input_elem.clear()
        input_elem.send_keys(text)
        time.sleep(2)

        if is_institution:
            try:
                first_option = WebDriverWait(driver, 10).until(
                    EC.visibility_of_element_located((By.CSS_SELECTOR, "#filterCaDdl_listbox li"))
                )
                first_option.click()
                time.sleep(1)
            except Exception as e:
                print(f"⚠️ Nu s-a putut selecta instituția din dropdown: {e}")
                return

        input_elem.send_keys(Keys.ENTER)
        time.sleep(wait_time)

    except Exception as e:
        print(f"Eroare la căutarea: {text} -> {e}")

def clear_input(driver, input_selector):
    try:
        input_elem = driver.find_element(By.CSS_SELECTOR, input_selector)
        input_elem.clear()
        input_elem.send_keys(Keys.BACKSPACE * 10)
        time.sleep(1)
        input_elem.send_keys(Keys.ENTER)
        time.sleep(2)
    except Exception as e:
        print(f"Eroare la golirea câmpului: {e}")

def main():
    config = load_config()
    last_seen_ids = load_last_seen_ids()
    current_ids = set()
    found_new = [False]
    institutions = config["institutions"]
    keywords = config["keywords"]

    options = Options()
    options.headless = True
    driver = webdriver.Firefox(options=options)

    try:
        driver.get(SEAP_URL)
        time.sleep(10)

        # extrage anunțuri vizibile la încărcare (fără căutare)
        ignored_initial = extract_current_notice_ids(driver)

        for institution in institutions:
            perform_search(driver, "input[aria-owns='filterCaDdl_listbox']", institution, wait_time=7, is_institution=True)
            process_results(driver, last_seen_ids, current_ids, found_new)

        clear_input(driver, "input[aria-owns='filterCaDdl_listbox']")

        for keyword in keywords:
            perform_search(driver, "input[ng-model='vm.filter.contractObject']", keyword, wait_time=5)
            process_results(driver, last_seen_ids, current_ids, found_new, ignored_initial=ignored_initial)

        if not found_new[0]:
            send_telegram_message("📭 Niciun anunț nou găsit după filtrele setate.")
        save_last_seen_ids(current_ids)

    finally:
        driver.quit()

if __name__ == "__main__":
    main()
