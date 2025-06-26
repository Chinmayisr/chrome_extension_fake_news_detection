from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import time
from news_topic import NEWS_TOPIC

def get_bbc_links():
    options = Options()
    # options.add_argument('--headless')  # Uncomment for headless mode
    options.add_argument('--start-maximized')
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    links = []
    try:
        # ---- Step 1: Open BBC News ----
        driver.get("https://www.bbc.com/news")
        time.sleep(2)

        # ---- Step 2: Click on Search Icon's Parent Button ----
        search_icon_button = driver.find_element(By.XPATH, '//*[@id="__next"]/div/header/div/div[1]/button')
        search_icon_button.click()
        print("✅ Search icon clicked.")
        time.sleep(2)

        # ---- Step 3: Enter Search Term in Search Bar ----
        search_input = driver.find_element(By.XPATH, '//*[@id="__next"]/div/div[5]/div/div[1]/div/input')
        search_term = NEWS_TOPIC
        # Extract main keywords (remove common stopwords)
        stopwords = {"the", "is", "in", "at", "of", "on", "and", "a", "to", "after", "has", "with", "for", "by", "an", "as", "it", "from", "this", "that", "be", "are", "was", "were", "or", "but", "not", "which", "have", "had", "will", "would", "can", "could", "should", "may", "might", "do", "does", "did", "so", "such", "if", "then", "than", "also", "their", "its", "about", "into", "more", "other", "some", "any", "all", "no", "only", "over", "out", "up", "down", "off", "just", "now", "like", "because", "how", "when", "where", "who", "what", "why"}
        keywords = [word for word in search_term.split() if word.lower() not in stopwords]
        # Use only the first 3 keywords for the search
        top_n = 10
        selected_keywords = keywords[:top_n]
        keyword_query = " ".join(selected_keywords)
        search_input.send_keys(keyword_query)
        search_input.send_keys(Keys.RETURN)
        print(f"🔍 Searched for top {top_n} main keywords: {keyword_query}")
        time.sleep(5)  # Wait for results to load

        # ---- Step 4: Scrape Result Links Only from Search Results Section ----
        soup = BeautifulSoup(driver.page_source, "html.parser")
        search_results_div = soup.find("div", {"data-testid": "new-jersey-grid"})

        print("\n🔗 Top 3 Search Result Links:")
        count = 0
        if search_results_div:
            for link in search_results_div.find_all("a", href=True):
                href = link["href"]
                text = link.get_text(strip=True)
                if text and ("/news" in href or href.startswith("https://www.bbc.com/news")):
                    count += 1
                    full_url = href if href.startswith("http") else "https://www.bbc.com" + href
                    links.append(full_url)
                    print(f"{count}. {text[:80]} ➜ {full_url}")
                    if count == 3:
                        break
        else:
            print("❌ Could not find search results section.")

        if count == 0:
            print("❌ No valid news article links found in search results.")

    except Exception as e:
        print(f"❌ Error occurred: {e}")

    finally:
        driver.quit()
    return links

if __name__ == "__main__":
    bbc_links = get_bbc_links()
    print(bbc_links)
