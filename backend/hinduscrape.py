from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import time
from news_topic import NEWS_TOPIC

# ---- Setup WebDriver ----
options = Options()
# options.add_argument('--headless')  # Optional: Run in headless mode
options.add_argument('--start-maximized')

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

try:
    # ---- Step 1: Open The Hindu Website ----
    driver.get("https://www.thehindu.com/")
    time.sleep(3)

    # ---- Step 2: Click Search Icon ----
    search_icon = driver.find_element(By.XPATH, "//header//div[contains(@class, 'container')]//div[contains(@class, 'hamburger-search')]/a")
    search_icon.click()
    print("✅ Search icon clicked.")
    time.sleep(2)

    # ---- Step 3: Enter Search Keywords in Search Bar ----
    search_input = driver.find_element(By.XPATH, '//*[@id="gsc-i-id1"]')
    search_term = NEWS_TOPIC

    # Filter top keywords
    stopwords = {"the", "is", "in", "at", "of", "on", "and", "a", "to", "after", "has", "with", "for", "by", "an", "as", "it", "from", "this", "that", "be", "are", "was", "were", "or", "but", "not", "which", "have", "had", "will", "would", "can", "could", "should", "may", "might", "do", "does", "did", "so", "such", "if", "then", "than", "also", "their", "its", "about", "into", "more", "other", "some", "any", "all", "no", "only", "over", "out", "up", "down", "off", "just", "now", "like", "because", "how", "when", "where", "who", "what", "why"}
    keywords = [word for word in search_term.split() if word.lower() not in stopwords]
    keyword_query = " ".join(keywords[:10])  # Use top 10 keywords

    search_input.send_keys(keyword_query)
    search_input.send_keys(Keys.RETURN)
    print(f"🔍 Searched for: {keyword_query}")
    time.sleep(5)  # Let results load

    # ---- Step 4: Scrape Result Links from Results Section ----
    soup = BeautifulSoup(driver.page_source, "html.parser")
    results_div = soup.select_one('#___gcse_0 div div div div:nth-of-type(5)')  # Results section

    print("\n🔗 Top 3 Search Result Links:")
    count = 0
    if results_div:
        for a_tag in results_div.find_all("a", href=True):
            href = a_tag["href"]
            text = a_tag.get_text(strip=True)
            if text and href.startswith("https://www.thehindu.com"):
                count += 1
                print(f"{count}. {text[:80]} ➜ {href}")
                if count == 3:
                    break
    else:
        print("❌ Could not find results section.")

    if count == 0:
        print("❌ No valid news article links found.")

except Exception as e:
    print(f"❌ Error: {e}")

finally:
    driver.quit()
