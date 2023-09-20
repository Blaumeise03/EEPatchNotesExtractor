import logging
import sys
import http.client

import requests

from ee_patch_notes import scraper

logger = logging.getLogger()

formatter = logging.Formatter(fmt="[%(asctime)s][%(levelname)s][%(name)s]: %(message)s")

console = logging.StreamHandler(sys.stdout)
console.setLevel(logging.DEBUG)
console.setFormatter(formatter)
logger.addHandler(console)
logger.setLevel(logging.DEBUG)

# Requests logging
# requests_log = logging.getLogger("requests.packages.urllib3")
# requests_log.setLevel(logging.DEBUG)
# requests_log.propagate = True
# http.client.HTTPConnection.debuglevel = 1


if __name__ == '__main__':
    last_page = scraper.load_page_range("https://www.eveechoes.com/news/updata/")
    patch_notes = scraper.find_all_patch_notes_urls(
        base_url="https://www.eveechoes.com/news/updata/index{index}.html",
        max_index=last_page)
    # patch_notes = scraper.load_patch_notes_from_cache()
    scraper.download_all_patch_notes(patch_notes, skip_existing=True)
