import requests
import os
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
import PyPDF2
import pandas as pd
from urllib.parse import urljoin, urlparse
import logging
import re
from io import BytesIO
from difflib import SequenceMatcher

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SEBINewsTopicScraperHeadless:
    def __init__(self, download_folder="./sebi_pdfs", news_topic=None):
        self.download_folder = download_folder
        self.base_url = "https://www.sebi.gov.in"
        self.press_release_url = "https://www.sebi.gov.in/sebiweb/home/HomeAction.do?doListing=yes&sid=6&ssid=23&smid=0"
        self.driver = None
        self.scraped_data = []
        
        # News topic to search for
        self.news_topic = news_topic or "securities market"
        
        # Extract key terms from the news topic for better matching
        self.key_terms = self.extract_key_terms(self.news_topic)
        
        # Create download folder if it doesn't exist
        os.makedirs(self.download_folder, exist_ok=True)
        
        logger.info(f"Initialized SEBI news topic scraper for: '{self.news_topic[:100]}...'")
        logger.info(f"Key terms extracted: {', '.join(self.key_terms[:10])}")  # Show first 10 terms
    
    def extract_key_terms(self, news_topic):
        """Extract key terms from the news topic for better matching"""
        # Remove common stop words and extract meaningful terms
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'while', 'from', 'about', 'over', 'their', 'various', 'amid', 'also'}
        
        # Clean and split the topic
        words = re.findall(r'\b\w+\b', news_topic.lower())
        key_terms = [word for word in words if word not in stop_words and len(word) > 2]
        
        # Also include important phrases (2-3 words)
        sentences = re.split(r'[.!?]+', news_topic.lower())
        for sentence in sentences:
            words_in_sentence = re.findall(r'\b\w+\b', sentence.strip())
            if len(words_in_sentence) >= 2:
                # Add 2-word phrases
                for i in range(len(words_in_sentence) - 1):
                    phrase = f"{words_in_sentence[i]} {words_in_sentence[i+1]}"
                    if all(word not in stop_words for word in words_in_sentence[i:i+2]):
                        key_terms.append(phrase)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_terms = []
        for term in key_terms:
            if term not in seen:
                seen.add(term)
                unique_terms.append(term)
        
        return unique_terms
    
    def setup_headless_chrome_driver(self):
        """Setup headless Chrome driver with optimized options"""
        chrome_options = Options()
        
        # HEADLESS MODE - This is the key!
        chrome_options.add_argument('--headless')  # Run in background
        chrome_options.add_argument('--headless=new')  # Use new headless mode (Chrome 109+)
        
        # Performance optimizations
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--disable-web-security')
        chrome_options.add_argument('--disable-features=VizDisplayCompositor')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--disable-plugins')
        chrome_options.add_argument('--disable-images')  # Don't load images for faster browsing
        chrome_options.add_argument('--disable-javascript-harmony-shipping')
        chrome_options.add_argument('--disable-background-timer-throttling')
        chrome_options.add_argument('--disable-renderer-backgrounding')
        chrome_options.add_argument('--disable-backgrounding-occluded-windows')
        chrome_options.add_argument('--disable-ipc-flooding-protection')
        
        # Memory optimizations
        chrome_options.add_argument('--memory-pressure-off')
        chrome_options.add_argument('--max_old_space_size=4096')
        
        # Anti-detection
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # Set download preferences (though we'll mostly use in-memory processing)
        prefs = {
            "download.default_directory": os.path.abspath(self.download_folder),
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "plugins.always_open_pdf_externally": True,
            "profile.default_content_settings.popups": 0,
            "profile.default_content_setting_values.notifications": 2
        }
        chrome_options.add_experimental_option("prefs", prefs)
        
        try:
            # You can specify chromedriver path if needed
            # service = Service('/path/to/chromedriver')  # Uncomment and modify if needed
            # self.driver = webdriver.Chrome(service=service, options=chrome_options)
            
            self.driver = webdriver.Chrome(options=chrome_options)
            
            # Remove webdriver property to avoid detection
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            # Set user agent
            self.driver.execute_cdp_cmd('Network.setUserAgentOverride', {
                "userAgent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            })
            
            logger.info("Headless Chrome driver initialized successfully")
            logger.info(f"Browser version: {self.driver.capabilities['browserVersion']}")
            
        except Exception as e:
            logger.error(f"Failed to initialize headless Chrome driver: {e}")
            raise
    
    def calculate_text_similarity(self, text1, text2):
        """Calculate similarity between two text strings"""
        return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()
    
    def is_news_topic_related(self, text, similarity_threshold=0.3):
        """Check if text is related to the news topic"""
        if not text:
            return False, 0, []
        
        text_lower = text.lower()
        found_terms = []
        max_similarity = 0
        
        # Check for key terms presence
        for term in self.key_terms:
            if term in text_lower:
                found_terms.append(term)
        
        # Calculate similarity with the original news topic
        similarity = self.calculate_text_similarity(text, self.news_topic)
        max_similarity = max(max_similarity, similarity)
        
        # Check for partial matches with key terms
        for term in self.key_terms:
            term_similarity = self.calculate_text_similarity(text, term)
            max_similarity = max(max_similarity, term_similarity)
        
        # Consider it related if we have term matches OR high similarity
        is_related = len(found_terms) > 0 or max_similarity >= similarity_threshold
        
        return is_related, max_similarity, found_terms
    
    def get_press_releases_headless(self, max_pages=5):
        """Scrape SEBI press release links using headless browser"""
        press_releases = []
        
        try:
            logger.info("Navigating to SEBI press releases page (headless)...")
            self.driver.get(self.press_release_url)
            
            wait = WebDriverWait(self.driver, 20)
            
            for page in range(max_pages):
                logger.info(f"Scraping SEBI page {page + 1} (headless)")
                
                wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                time.sleep(3)  # Wait for dynamic content to load
                
                # Look for press release links in SEBI's structure
                # Try multiple selectors as SEBI's structure might vary
                press_release_links = []
                
                # Try different possible selectors for SEBI press releases
                selectors = [
                    "//a[contains(@href, 'press') or contains(@href, 'Press')]",
                    "//a[contains(@href, '.pdf') or contains(@href, '.PDF')]",
                    "//table//a[contains(@href, 'pdf')]",
                    "//td//a[contains(@href, 'pdf')]",
                    "//div[@class='press-release']//a",
                    "//div[contains(@class, 'press')]//a",
                    "//tr//a[contains(@href, 'pdf')]"
                ]
                
                for selector in selectors:
                    try:
                        links = self.driver.find_elements(By.XPATH, selector)
                        if links:
                            press_release_links.extend(links)
                            logger.info(f"Found {len(links)} links with selector: {selector}")
                    except:
                        continue
                
                # Remove duplicates based on href
                unique_links = []
                seen_hrefs = set()
                for link in press_release_links:
                    try:
                        href = link.get_attribute('href')
                        if href and href not in seen_hrefs and ('.pdf' in href.lower() or 'press' in href.lower()):
                            seen_hrefs.add(href)
                            unique_links.append(link)
                    except:
                        continue
                
                press_release_links = unique_links
                logger.info(f"Found {len(press_release_links)} unique press release links on page {page + 1}")
                
                for link in press_release_links:
                    try:
                        title = link.text.strip()
                        if not title:
                            # Try to get title from parent element or nearby text
                            try:
                                parent = link.find_element(By.XPATH, "./..")
                                title = parent.text.strip()
                            except:
                                title = "SEBI Press Release"
                        
                        if not title or len(title) < 5:
                            continue
                        
                        # Check if title is related to our news topic
                        is_related, similarity, found_terms = self.is_news_topic_related(title)
                        
                        href = link.get_attribute('href')
                        
                        # Handle relative URLs
                        if href.startswith('/'):
                            pdf_url = self.base_url + href
                        elif href.startswith('../'):
                            pdf_url = urljoin(self.base_url, href)
                        elif not href.startswith('http'):
                            pdf_url = urljoin(self.base_url, href)
                        else:
                            pdf_url = href
                        
                        # Try to extract date from surrounding elements
                        date = "N/A"
                        try:
                            # Look for date in parent row or nearby elements
                            parent_row = link.find_element(By.XPATH, "./ancestor::tr[1]")
                            date_cells = parent_row.find_elements(By.TAG_NAME, "td")
                            for cell in date_cells:
                                cell_text = cell.text.strip()
                                if re.search(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}', cell_text):
                                    date = cell_text
                                    break
                        except:
                            # Try alternative date extraction
                            try:
                                parent_div = link.find_element(By.XPATH, "./ancestor::div[contains(@class, 'date') or contains(text(), '20')]")
                                date_text = parent_div.text.strip()
                                date_match = re.search(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}', date_text)
                                if date_match:
                                    date = date_match.group()
                            except:
                                pass
                        
                        press_releases.append({
                            'date': date,
                            'title': title,
                            'pdf_url': pdf_url,
                            'detail_url': href,
                            'title_is_related': is_related,
                            'title_similarity': similarity,
                            'title_found_terms': found_terms
                        })
                        
                        if is_related:
                            logger.info(f"Related SEBI title found: {title[:50]}... (Similarity: {similarity:.2f}, Terms: {len(found_terms)})")
                        else:
                            logger.debug(f"SEBI title added for content check: {title[:50]}... (Similarity: {similarity:.2f})")
                
                    except Exception as e:
                        logger.warning(f"Error processing SEBI link: {e}")
                        continue
                
                # Try to navigate to next page (if pagination exists)
                try:
                    # Look for next page button - common patterns in SEBI site
                    next_buttons = self.driver.find_elements(By.XPATH, 
                        "//a[contains(text(), 'Next') or contains(text(), '»') or contains(@title, 'Next')]")
                    
                    if next_buttons and page < max_pages - 1:
                        next_button = next_buttons[0]
                        if next_button.is_enabled():
                            self.driver.execute_script("arguments[0].click();", next_button)
                            time.sleep(3)
                            continue
                    else:
                        logger.info("No more pages or reached max pages limit")
                        break
                except:
                    logger.info("Could not find next page button, stopping pagination")
                    break
        
        except Exception as e:
            logger.error(f"Error scraping SEBI press releases: {e}")
        
        logger.info(f"Found {len(press_releases)} SEBI press releases with PDFs")
        return press_releases
    
    def download_pdf_to_memory(self, pdf_url):
        """Download PDF to memory for content checking"""
        try:
            # Add headers to mimic browser request
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'application/pdf,application/octet-stream,*/*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
            
            response = requests.get(pdf_url, stream=True, timeout=30, headers=headers)
            response.raise_for_status()
            return BytesIO(response.content)
        except Exception as e:
            logger.error(f"Error downloading PDF to memory from {pdf_url}: {e}")
            return None
    
    def download_pdf_using_selenium(self, pdf_url):
        """Alternative: Download PDF using Selenium (if direct requests fail)"""
        try:
            logger.info(f"Downloading SEBI PDF using headless browser: {pdf_url}")
            self.driver.get(pdf_url)
            time.sleep(5)  # Wait for download to complete
            
            # Get current URL (might redirect to actual PDF)
            current_url = self.driver.current_url
            if current_url.endswith('.pdf') and current_url != pdf_url:
                return self.download_pdf_to_memory(current_url)
            
            # If we're on a PDF page, try to get the content
            if 'pdf' in current_url.lower():
                return self.download_pdf_to_memory(current_url)
            
            return None
        except Exception as e:
            logger.error(f"Error downloading SEBI PDF using Selenium: {e}")
            return None
    
    def extract_text_from_pdf_memory(self, pdf_stream):
        """Extract text content from PDF in memory"""
        try:
            pdf_reader = PyPDF2.PdfReader(pdf_stream)
            text = ""
            
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
            
            return text.strip()
        except Exception as e:
            logger.error(f"Error extracting text from PDF in memory: {e}")
            return None
    
    def process_press_releases_headless(self, press_releases, max_pdfs=10, save_matching_pdfs=False, similarity_threshold=0.3):
        """Process SEBI PDFs with headless browser support"""
        processed_count = 0
        topic_matches = 0
        
        # Sort by title similarity first (prioritize likely matches)
        press_releases_sorted = sorted(press_releases, key=lambda x: x['title_similarity'], reverse=True)
        
        for release in press_releases_sorted:
            if processed_count >= max_pdfs:
                break
            
            try:
                logger.info(f"Processing SEBI release (headless): {release['title'][:50]}...")
                
                # Try direct download first (faster)
                pdf_stream = self.download_pdf_to_memory(release['pdf_url'])
                
                # If direct download fails, try using headless browser
                if not pdf_stream:
                    pdf_stream = self.download_pdf_using_selenium(release['pdf_url'])
                
                if pdf_stream:
                    pdf_text = self.extract_text_from_pdf_memory(pdf_stream)
                    
                    if pdf_text:
                        # Check for news topic relevance in both title and content
                        title_is_related, title_similarity, title_terms = self.is_news_topic_related(release['title'], similarity_threshold)
                        content_is_related, content_similarity, content_terms = self.is_news_topic_related(pdf_text, similarity_threshold)
                        
                        # Combine all found terms
                        all_terms = list(set(title_terms + content_terms))
                        is_overall_related = title_is_related or content_is_related
                        max_similarity = max(title_similarity, content_similarity)
                        
                        if is_overall_related:
                            topic_matches += 1
                            logger.info(f"✓ SEBI topic match found: Similarity {max_similarity:.2f}, Terms: {len(all_terms)}")
                            
                            # Create safe filename for potential saving
                            safe_filename = "".join(c for c in release['title'][:50] if c.isalnum() or c in (' ', '-', '_')).rstrip()
                            safe_filename = safe_filename.replace(' ', '_') + '.pdf'
                            
                            # Optionally save the PDF file if it's related to the topic
                            pdf_file_path = None
                            if save_matching_pdfs:
                                pdf_file_path = self.save_pdf_from_memory(pdf_stream, safe_filename)
                            
                            # Store the data
                            self.scraped_data.append({
                                'date': release['date'],
                                'title': release['title'],
                                'pdf_url': release['pdf_url'],
                                'pdf_filename': safe_filename if save_matching_pdfs else 'not_saved',
                                'pdf_saved': save_matching_pdfs,
                                'content': pdf_text,
                                'content_length': len(pdf_text),
                                'news_topic': self.news_topic[:100] + "..." if len(self.news_topic) > 100 else self.news_topic,
                                'title_is_related': title_is_related,
                                'title_similarity': title_similarity,
                                'title_found_terms': ', '.join(title_terms),
                                'content_is_related': content_is_related,
                                'content_similarity': content_similarity,
                                'content_found_terms': ', '.join(content_terms),
                                'max_similarity': max_similarity,
                                'all_found_terms': ', '.join(all_terms),
                                'terms_count': len(all_terms)
                            })
                            
                            logger.info(f"✓ Processed SEBI: {release['title'][:50]}... (Similarity: {max_similarity:.2f})")
                        else:
                            logger.info(f"✗ Not related to topic, skipping SEBI: {release['title'][:50]}... (Similarity: {max_similarity:.2f})")
                        
                        processed_count += 1
                        time.sleep(0.5)  # Reduced delay for headless mode
                    else:
                        logger.warning(f"Could not extract text from SEBI PDF: {release['title'][:50]}...")
                else:
                    logger.warning(f"Could not download SEBI PDF: {release['title'][:50]}...")
                
            except Exception as e:
                logger.error(f"Error processing SEBI release '{release['title'][:50]}...': {e}")
                continue
        
        logger.info(f"Processed {processed_count} SEBI PDFs (headless), {topic_matches} related to topic")
        if save_matching_pdfs:
            logger.info(f"Saved {topic_matches} matching SEBI PDFs to disk")
        else:
            logger.info("No SEBI PDFs were saved to disk (memory-only processing)")
    
    def save_pdf_from_memory(self, pdf_stream, filename):
        """Save PDF from memory stream to file"""
        try:
            filepath = os.path.join(self.download_folder, filename)
            pdf_stream.seek(0)  # Reset stream position
            
            with open(filepath, 'wb') as f:
                f.write(pdf_stream.read())
            
            logger.info(f"Saved SEBI PDF: {filename}")
            return filepath
        except Exception as e:
            logger.error(f"Error saving SEBI PDF {filename}: {e}")
            return None
    
    def save_to_csv(self, filename=None):
        """Save scraped data to CSV"""
        if not self.scraped_data:
            logger.warning("No SEBI data to save")
            return
        
        if filename is None:
            # Create filename based on news topic
            safe_topic = "".join(c for c in self.news_topic[:50] if c.isalnum() or c in (' ', '-', '_')).rstrip()
            safe_topic = safe_topic.replace(' ', '_')[:30]  # Limit length
            filename = f"sebi_news_topic_{safe_topic}.csv"
        
        df = pd.DataFrame(self.scraped_data)
        df.to_csv(filename, index=False, encoding='utf-8')
        logger.info(f"SEBI data saved to {filename}")
        
        # Save summary
        summary_df = df[['date', 'title', 'content_length', 'max_similarity', 'terms_count', 'all_found_terms']].copy()
        summary_filename = filename.replace('.csv', '_summary.csv')
        summary_df.to_csv(summary_filename, index=False, encoding='utf-8')
        logger.info(f"SEBI summary saved to {summary_filename}")
    
    def analyze_content(self):
        """Analyze scraped SEBI content"""
        if not self.scraped_data:
            logger.warning("No SEBI data to analyze")
            return
        
        logger.info("=== SEBI News Topic Content Analysis ===")
        logger.info(f"News Topic: '{self.news_topic[:100]}...'")
        logger.info(f"Total SEBI documents processed: {len(self.scraped_data)}")
        
        # Similarity statistics
        title_matches = sum(1 for item in self.scraped_data if item['title_is_related'])
        content_matches = sum(1 for item in self.scraped_data if item['content_is_related'])
        
        logger.info(f"SEBI documents with topic match in title: {title_matches}")
        logger.info(f"SEBI documents with topic match in content: {content_matches}")
        
        # Average similarity
        avg_similarity = sum(item['max_similarity'] for item in self.scraped_data) / len(self.scraped_data)
        logger.info(f"Average similarity score: {avg_similarity:.3f}")
        
        # Top matches
        sorted_data = sorted(self.scraped_data, key=lambda x: x['max_similarity'], reverse=True)
        logger.info("\nTop 3 most relevant SEBI documents:")
        for i, item in enumerate(sorted_data[:3]):
            logger.info(f"{i+1}. {item['title'][:60]}... (Similarity: {item['max_similarity']:.3f})")
    
    def cleanup(self):
        """Close headless browser and cleanup"""
        if self.driver:
            self.driver.quit()
            logger.info("Headless browser closed")
    
    def run_news_topic_scraping(self, max_pages=3, max_pdfs=10, save_matching_pdfs=False, similarity_threshold=0.3):
        """Run the complete SEBI news topic scraping process"""
        try:
            logger.info("Starting SEBI News Topic headless scraping...")
            logger.info(f"Target news topic: '{self.news_topic[:100]}...'")
            logger.info(f"Key terms: {', '.join(self.key_terms[:10])}...")  # Show first 10 terms
            logger.info(f"Similarity threshold: {similarity_threshold}")
            logger.info(f"Save matching PDFs: {save_matching_pdfs}")
            
            # Setup headless browser
            self.setup_headless_chrome_driver()
            
            # Get press release links
            press_releases = self.get_press_releases_headless(max_pages=max_pages)
            
            if not press_releases:
                logger.error("No SEBI press releases found")
                return
            
            # Process PDFs
            self.process_press_releases_headless(
                press_releases, 
                max_pdfs=max_pdfs, 
                save_matching_pdfs=save_matching_pdfs,
                similarity_threshold=similarity_threshold
            )
            
            # Save data
            self.save_to_csv()
            
            # Analyze content
            self.analyze_content()
            
            logger.info("SEBI news topic scraping completed successfully!")
            
        except Exception as e:
            logger.error(f"Error during SEBI news topic scraping: {e}")
        
        finally:
            self.cleanup()