from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import time

# ------ Setup Selenium WebDriver ------
options = Options()
#options.add_argument('--headless')  # Uncomment for headless mode
options.add_argument('--start-maximized')
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

# ------ Open Economic Times ------
driver.get("https://economictimes.indiatimes.com/")

# ------ Wait for the search bar to be interactable ------
time.sleep(3)

# ------ Find search bar and enter query ------
search_input = driver.find_element(By.XPATH, '//*[@id="ticker_newsearch"]')
search_input.send_keys("inflation trends")  # 🔍 <-- Your query here
search_input.send_keys(Keys.RETURN)

# ------ Wait for results to load ------
time.sleep(5)

# ------ Get page source and parse with BeautifulSoup ------
soup = BeautifulSoup(driver.page_source, 'html.parser')

# ------ Extract links from search results ------
results_section = soup.find_all('a', href=True)

# ------ Filter and print top 3 article links ------
print("🔗 Top 3 Article Links:")
count = 0
for link in results_section:
    href = link['href']
    if "/news/" in href or href.startswith("https://economictimes.indiatimes.com"):
        if not href.startswith("http"):
            href = "https://economictimes.indiatimes.com" + href
        print(href)
        count += 1
        if count == 3:
            break

# ------ Quit driver ------
driver.quit()

def get_et_links(search_term):
    options = Options()
    #options.add_argument('--headless')  # Uncomment for headless mode
    options.add_argument('--start-maximized')
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    links = []
    try:
        driver.get("https://economictimes.indiatimes.com/")
        time.sleep(3)
        search_input = driver.find_element(By.XPATH, '//*[@id="ticker_newsearch"]')
        search_input.send_keys(search_term)
        search_input.send_keys(Keys.RETURN)
        time.sleep(5)
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        results_section = soup.find_all('a', href=True)
        count = 0
        for link in results_section:
            href = link['href']
            if "/news/" in href or href.startswith("https://economictimes.indiatimes.com"):
                if not href.startswith("http"):
                    href = "https://economictimes.indiatimes.com" + href
                links.append(href)
                count += 1
                if count == 3:
                    break
    except Exception as e:
        print(f"❌ Error occurred: {e}")
    finally:
        driver.quit()
    return links


