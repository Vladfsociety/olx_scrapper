import sys
import logging
import logging.config
import pandas as pd
from time import sleep
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

MAIN_URL = "https://www.olx.ua/uk/nedvizhimost/kvartiry/dolgosrochnaya-arenda-kvartir/"
LISTING_URL_PATTERN = "https://www.olx.ua/uk/nedvizhimost/kvartiry/dolgosrochnaya-arenda-kvartir/?page="
ANNOUNCEMENT_URL_PATTERN = "https://www.olx.ua/"
TIMEOUT_BETWEEN_REQUESTS = 1
TIMEOUT_FOR_REQUESTS = {
    'pages_count': 5,
    'listing': 10,
    'announcement': 3,
}
ANNOUNCEMENT_PRIMARY_FEATURES = [
    "Ціна",
    "Локація (Місто, Район)",
]
ANNOUNCEMENT_SECONDARY_FEATURES = [
    "Поверх",
    "Поверховість",
    "Загальна площа",
    "Площа кухні",
    "Кількість кімнат",
    "Меблювання",
    "Ремонт",
    "Домашні улюбленці",
    "Автономність при блекауті",
]


def request(url, page_type="pages_count"):
    sleep(TIMEOUT_BETWEEN_REQUESTS)
    chrome_options = Options()
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    if page_type == 'announcement':
        chrome_options.add_experimental_option("prefs", {
            "profile.managed_default_content_settings.javascript": 2
        })
    else:
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    driver = webdriver.Chrome(options=chrome_options)
    driver.get(url)
    # delay for js execute
    sleep(TIMEOUT_FOR_REQUESTS[page_type])
    response = driver.page_source
    driver.quit()
    return BeautifulSoup(response, "lxml")


def get_pages_count():
    pages_count = ''
    main_content = request(MAIN_URL)
    pagination = main_content.find_all('a', class_="css-1mi714g")

    if pagination:
        pages_count = pagination[-1].string

    return int(pages_count)


def get_primary_announcements_data(page):
    announcements_data = {}
    listing_content = request(LISTING_URL_PATTERN + str(page), page_type="listing")
    announcements = (listing_content
                     .find('div', {"data-testid": "listing-grid"})
                     .find_all('div', {"class": "css-qfzx1y"}))

    if announcements:
        for announcement in announcements:
            logging.info("announcement: %s", announcement)
            # url example: /d/uk/obyavlenie/orenda-kvartiri-vul-bratv-mhnovskih-IDWyoN4.html
            url = announcement.find('a').get('href')
            price = announcement.find('p', {"data-testid": "ad-price"}).decode_contents()
            location = announcement.find('p', {"data-testid": "location-date"}).decode_contents()
            announcements_data[url] = {
                "Ціна": price,
                "Локація (Місто, Район)": location,
            }
            announcements_data[url].update({feature: "" for feature in ANNOUNCEMENT_SECONDARY_FEATURES})

    if not announcements_data:
        logging.info("Empty announcements_data list. Announcements object: %s", announcements)
        raise Exception("Empty announcements_data list")

    return announcements_data


def get_announcement_secondary_data(announcement_url):
    secondary_data = {}
    announcement = request(ANNOUNCEMENT_URL_PATTERN + announcement_url, page_type="announcement")
    announcement_tags = announcement.find('ul', class_="css-px7scb").find_all('p', class_="css-b5m1rv")

    for announcement_tag in announcement_tags:
        tag_split = announcement_tag.string.split(': ')
        tag_label = tag_split[0]
        tag_value = tag_split[1] if len(tag_split) > 1 else ""
        if tag_label in ANNOUNCEMENT_SECONDARY_FEATURES:
            secondary_data[tag_label] = tag_value

    return secondary_data


def main():
    logging.config.fileConfig('logging.conf')
    logging.info('------Script start------')

    try:
        pages_count = get_pages_count()
    except Exception as e:
        pages_count = None
        logging.error('Cannot get pages count. Reason: %s', repr(e))

    if not pages_count:
        logging.info('Page count is None.')
        sys.exit(1)

    data = []

    for page in range(1, pages_count + 1):
        try:
            announcements_data = get_primary_announcements_data(page)
        except Exception as e:
            logging.error('Cannot get primary announcements data for page %s. Reason: %s' % (page, repr(e)))
            continue

        for announcement_url in announcements_data.keys():
            try:
                announcements_data[announcement_url].update(get_announcement_secondary_data(announcement_url))
            except Exception as e:
                logging.error('Cannot get secondary announcement data. Reason: %s', repr(e))
                continue

        data.extend(list(announcements_data.values()))

    if data:
        df = pd.DataFrame(data, columns=ANNOUNCEMENT_PRIMARY_FEATURES + ANNOUNCEMENT_SECONDARY_FEATURES)
        df.to_csv('result.csv')

    logging.info('------Script end------')


if __name__ == '__main__':
    main()
