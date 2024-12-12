import os
import time
import traceback
import hashlib
from celery import shared_task
from django.conf import settings
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common import TimeoutException
from django.utils import timezone
from .models import PDFFile, ParserConfiguration

DOWNLOAD_FOLDER = "downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)


@shared_task
def run_parser():
    config = ParserConfiguration.objects.first()
    if not config:
        # If no config yet, create default one
        config = ParserConfiguration.objects.create(interval_minutes=60)

    options = webdriver.ChromeOptions()
    prefs = {
        "download.default_directory": os.path.abspath(DOWNLOAD_FOLDER),
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True,
    }
    options.add_experimental_option("prefs", prefs)
    driver = None
    try:
        driver = webdriver.Chrome(options=options)
        driver.get(
            "https://gisp.gov.ru/nmp/main/?recommended=0&search_terms=&search_terms=&search_terms=&search_terms=&event=&search_terms=&search_terms=&search_terms=&search_terms=&search_terms=&measureActive=1&searchstr=&csrftoken=1809ba1086ebed6939c64a68812d4a676b4f06aef49a6bf91c361e661bcaf32f5b54d4342bda65a1")
        wait = WebDriverWait(driver, 10)

        while True:
            project_links = driver.find_elements(By.CSS_SELECTOR, ".catalog__list-info a")

            for project in project_links:
                project_url = project.get_attribute("href")
                # Open in new tab
                driver.execute_script("window.open(arguments[0], '_blank');", project_url)
                driver.switch_to.window(driver.window_handles[-1])

                # Attempt to download the file
                try:
                    download_button = wait.until(EC.element_to_be_clickable((By.LINK_TEXT, "Скачать условия")))
                    download_button.click()
                    time.sleep(2)  # wait for download

                    # Identify the latest downloaded file
                    downloaded_files = os.listdir(DOWNLOAD_FOLDER)
                    pdf_files = [f for f in downloaded_files if f.endswith('.pdf')]
                    pdf_files = sorted(pdf_files, key=lambda x: os.path.getmtime(os.path.join(DOWNLOAD_FOLDER, x)),
                                       reverse=True)

                    if pdf_files:
                        latest_file = pdf_files[0]
                        file_path = os.path.join(DOWNLOAD_FOLDER, latest_file)

                        # Compute hash
                        with open(file_path, 'rb') as f:
                            file_data = f.read()
                            file_md5 = hashlib.md5(file_data).hexdigest()

                        # Check if this file (by hash) already exists in DB
                        if PDFFile.objects.filter(file_hash=file_md5).exists():
                            # Duplicate by hash, delete newly downloaded file
                            os.remove(file_path)
                        else:
                            # Not a duplicate by hash
                            # Check if filename contains '(1).pdf'
                            if ' (1).pdf' in latest_file:
                                original_name = latest_file.replace(' (1)', '')
                                original_path = os.path.join(DOWNLOAD_FOLDER, original_name)

                                # If you prefer to always delete files with (1):
                                # os.remove(file_path)
                                # continue

                                # Otherwise, try renaming it:
                                if os.path.exists(original_path):
                                    # If original_path already exists, then we have a duplicate scenario.
                                    # Since by hash it's unique, this means original is different.
                                    # You can decide to just keep the (1) version or delete it.
                                    # Let's delete to avoid confusion:
                                    os.remove(file_path)
                                else:
                                    # Rename to the original name
                                    os.rename(file_path, original_path)
                                    PDFFile.objects.create(
                                        name=original_name,
                                        file_path=original_path,
                                        file_hash=file_md5
                                    )
                            else:
                                # Normal filename, just create a record
                                PDFFile.objects.create(
                                    name=latest_file,
                                    file_path=file_path,
                                    file_hash=file_md5
                                )

                except Exception as e:
                    # log error but continue
                    pass
                finally:
                    driver.close()
                    driver.switch_to.window(driver.window_handles[0])

            # Check if next page exists
            try:
                next_button = driver.find_elements(By.CSS_SELECTOR, "a[href*='/nmp/main/'] svg use")
                if len(next_button) == 1:
                    next_link = next_button[0].find_element(By.XPATH, "..")
                    next_link.click()
                    time.sleep(5)
                elif len(next_button) > 1:
                    next_link = next_button[1].find_element(By.XPATH, "..")
                    next_link.click()
                    time.sleep(5)
                else:
                    # No next button found
                    break
            except:
                break

        config.last_run = timezone.now()
        config.last_error = ""
        config.save()
    except Exception as e:
        # Save the error in config
        if config:
            config.last_error = traceback.format_exc()
            config.save()
    finally:
        if driver:
            driver.quit()


@shared_task
def check_and_run_parser():
    config = ParserConfiguration.objects.first()
    if not config:
        config = ParserConfiguration.objects.create(interval_minutes=60)

    now = timezone.now()
    if not config.last_run or (now - config.last_run).total_seconds() >= config.interval_minutes * 60:
        # Time to run parser
        run_parser.delay()
