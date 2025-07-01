from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

def get_et_links(search_term):
    options = Options()
    options.add_argument('--headless')  # Uncomment for headless mode
    options.add_argument('--start-maximized')
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    links = []
    try:
        driver.get("https://economictimes.indiatimes.com/")
        time.sleep(3)

        # Wait for the search bar to be present and interactable
        search_input = WebDriverWait(driver, 12).until(
            EC.element_to_be_clickable((By.XPATH, '//*[@id="ticker_newsearch"]'))
        )
        search_input.clear()
        search_input.send_keys(search_term)
        search_input.send_keys(Keys.RETURN)
        time.sleep(5)

        # Locate the specific div using XPath
        categorywise_top_div = driver.find_element(By.XPATH, '//*[@id="categorywiseTop"]')

        # Parse only the HTML of that div
        soup = BeautifulSoup(categorywise_top_div.get_attribute('innerHTML'), 'html.parser')
        result_links = soup.find_all('a', href=True)

        count = 0
        for link in result_links:
            href = link['href']
            if "/news/" in href or href.startswith("https://economictimes.indiatimes.com"):
                if not href.startswith("http"):
                    href = "https://economictimes.indiatimes.com" + href
                links.append(href)
                print(href)
                count += 1
                if count == 3:
                    break

    except Exception as e:
        print(f"❌ Error occurred: {e}")
    finally:
        driver.quit()
    return links
