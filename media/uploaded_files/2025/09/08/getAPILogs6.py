from selenium import webdriver
from selenium.webdriver.common.by import By

from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

import time

import pandas as pd

import requests
from datetime import datetime


list_codes = []
def get_initials(text):
    words = text.split()
    if len(words) == 1:
        return words[0][0].upper()
    elif len(words) > 1:
        return words[0][0].upper() + words[1][0].upper()
    return ""

def get_api_logs(
    email: str,
    password: str,
    response_codes: list[int] = [400, 401, 429],

):
    driver = webdriver.Chrome()
    driver.get("https://xbotic.cbots.live/admin/login")
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.NAME, "email")))

    try:
        username_field = driver.find_element(By.NAME, "email")
        password_field = driver.find_element(By.NAME, "password")
        username_field.send_keys(email)
        password_field.send_keys(password)

        login_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        login_button.click()

        try:
            WebDriverWait(driver, 10).until(EC.presence_of_all_elements_located((By.ID, "addBotButton")))
            print("Login successful")
        except TimeoutException:
            print("Login unsuccessful")
            driver.quit()
            return
        
        bot_cards = driver.find_elements(By.XPATH, "//section[@data-baseweb='card' and @data-qa='bot-card']")

        for card in bot_cards:
            card.click()

            integrations_button = driver.find_element(By.ID, "integrations-icon")
            integrations_button.click()

            WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, "/html/body/div[1]/div[1]/div/div[2]/div/div[2]/div/div[2]/a[3]/div/span")))
            apiLogs_button = driver.find_element(By.XPATH, "/html/body/div[1]/div[1]/div/div[2]/div/div[2]/div/div[2]/a[3]/div/span")
            apiLogs_button.click()
            

            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "[title='Filter']")))
            filter_button = driver.find_element(By.CSS_SELECTOR, "[title='Filter']")
            filter_button.click()

            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, "//span[text()='Response Code']")))
            response_code_input = driver.find_element(By.XPATH, "//span[text()='Response Code']")
            response_code_input.click()

            for code in response_codes:

                WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, "/html/body/div[1]/div[2]/div/div[2]/div/div/div/div[2]/ul/li[3]/div[2]/div/div/div/div[2]")))
                dropdown_option = driver.find_element(By.XPATH, "/html/body/div[1]/div[2]/div/div[2]/div/div/div/div[2]/ul/li[3]/div[2]/div/div/div/div[2]")
                dropdown_option.click()

                WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, "//div[text()='"+ str(code) +"']")))
                code_button = driver.find_element(By.XPATH, "//div[text()='"+ str(code) +"']")
                driver.execute_script("arguments[0].scrollIntoView();", code_button)
                code_button.click()


            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, "//button[text()='Apply']")))
            apply_button = driver.find_element(By.XPATH, "//button[text()='Apply']")
            apply_button.click()

            # log_entries = driver.find_elements(By.XPATH, "/html/body/div[1]/div[1]/div/div[2]/div/div[3]/div/div[2]/div/div[1]/div/div[2]/div/div[2]/ul[1]/li/div[2]/div")
            codes = []
            # print(f"Found {len(log_entries)} log entries")
            for i in range(30):
                try:
                    path = f"/html/body/div[1]/div[1]/div/div[2]/div/div[3]/div/div[2]/div/div[1]/div/div[2]/div/div[2]/ul[1]/li/div[2]/div[{i+1}]/div/div[1]/span"
                    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, path)))
                    span = driver.find_element(By.XPATH, path)
                    text = span.text.strip()
                    if text:
                        codes.append(text)
                except Exception as e:
                    print(f"Could not extract span from entry")
                    break

            print(f"Found codes: {codes}")
            

            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, "//span[text()='Bots']")))
            back_button = driver.find_element(By.XPATH, "//span[text()='Bots']")
            back_button.click()

            

        # time.sleep(10)  

        account_text = driver.find_element(By.XPATH, "/html/body/div[1]/div[1]/div/div[2]/div/div/div/div/section/div/div[2]/div[2]/div/div[1]/h1").text

        WebDriverWait(driver, 10).until(EC.presence_of_all_elements_located((By.XPATH, "//div[text()='" + get_initials(account_text) +"']")))
        profile_button = driver.find_element(By.XPATH, "//div[text()='" + get_initials(account_text) +"']")
        profile_button.click()

        WebDriverWait(driver, 10).until(EC.presence_of_all_elements_located((By.XPATH, "//span[text()='Logout']")))
        logout_button = driver.find_element(By.XPATH, "//span[text()='Logout']")
        logout_button.click()

        print("Logout successful")

        driver.delete_all_cookies()   

        driver.quit()
        return codes
    except Exception as e:
        print(f"An error occurred: {e}")
        driver.delete_all_cookies()
        driver.quit()
        return
    
def get_logs_from_accounts(accounts: list[dict]):
    
    for account in accounts:
        email = account.get("email")
        password = account.get("password")
        response_codes = account.get("response_codes")
        
        if not email or not password:
            print(f"Skipping account due to missing credentials: {account}")
            continue
         
        print(f"[*] Processing account: {email}")

        try:
            codes = get_api_logs(email, password, response_codes)
            temp = []
            for code in codes:
                if code not in temp:
                    temp.append(code)
            codes = temp
            if codes is None:
                codes = []
            list_codes.append(codes)

        except Exception as e:
            print(f"Error processing account {email}: {e}")
            continue
        
        

sheet_url = "https://docs.google.com/spreadsheets/d/1uscEauMUEwlYTaYHukdgtUWeuplpsZ27kSBlNaQzlKY/export?format=csv"
df = pd.read_csv(sheet_url)
df = df.dropna(subset=["ID", "Password"])

accounts_list = []
for _, row in df.iterrows():
    accounts_list.append({
        "email": row["ID"],
        "password": row["Password"],
        "response_codes": [400, 401, 429]
    })

get_logs_from_accounts(accounts_list)


output_column = [", ".join(codes) for codes in list_codes]
output_column += [""] * (len(df) - len(output_column))  # pad with blanks

apps_script_url = "https://script.google.com/macros/s/AKfycbxKB0ApxseZn65gWpRDBMN_bP8y-KMfFChJVzAtmnlvzN1W_NHZiiVPH2vKPt9PXAetBw/exec"
payload = {
    "responses": output_column
}

print(payload)

try:
    res = requests.post(apps_script_url, json=payload)
    # print(res.text)
    print("Status code:", res.status_code)

except Exception as e:
    print("Failed to send data:")