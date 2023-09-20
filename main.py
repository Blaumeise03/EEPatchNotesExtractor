import argparse
import logging
import sys
import http.client
from typing import Literal

import requests

from ee_patch_notes import scraper, formatter

logger = logging.getLogger()

log_format = logging.Formatter(fmt="[%(asctime)s][%(levelname)s][%(name)s]: %(message)s")

console = logging.StreamHandler(sys.stdout)
console.setLevel(logging.DEBUG)
console.setFormatter(log_format)
logger.addHandler(console)
logger.setLevel(logging.INFO)

# Requests logging
# requests_log = logging.getLogger("requests.packages.urllib3")
# requests_log.setLevel(logging.DEBUG)
# requests_log.propagate = True
# http.client.HTTPConnection.debuglevel = 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Patch notes scrapper for the game Eve Echoes")
    parser.add_argument("mode",
                        type=str, choices=["load_all", "load_new", "create_html"],
                        help="Select the mode, must be load_all, load_new or create_html")
    parser.add_argument("output_path",
                        type=str, help="The output directory")
    parser.add_argument("-c", "--cache",
                        help="Use the cached patch note urls (new patch notes will be missing), only effective for load_all",
                        action="store_true")
    parser.add_argument("-f", "--force_reload",
                        help="Reload and overwrite already (locally) saved patch notes, only effective for load_all",
                        action="store_true")
    parser.add_argument("-url",
                        help="The url for the patch notes, should contain {index} for the page number",
                        default="https://www.eveechoes.com/news/updata/index{index}.html")
    parser.add_argument("-r", "--ratelimit",
                        help="The delay between http requests in seconds",
                        default=1, type=float)
    parser.add_argument("--ratelimit_rnd_fac", type=float, default=2,
                        help="A factor that gets multiplied with a random number between 0 and 1, the result will get "
                             "added to the rate limit (will be random for every request)")

    args = parser.parse_args()
    scraper.DOWNLOAD_PATH = f"{args.output_path}/patch_notes"
    scraper.CACHE_PATH = f"{scraper.DOWNLOAD_PATH}/cache.json"
    scraper.RATE_LIMIT_SECONDS = args.ratelimit
    scraper.RATE_LIMIT_RAND_FAC = args.ratelimit_rnd_fac
    base_url = args.url

    if args.mode == "load_all":
        last_page = scraper.load_page_range(home_url=base_url.format(index=""))
        if args.cache:
            patch_notes = scraper.load_patch_notes_from_cache()
        else:
            patch_notes = scraper.find_all_patch_notes_urls(
               base_url=base_url,
               max_index=last_page)
        scraper.download_all_patch_notes(patch_notes, skip_existing=not args.force_reload)
    elif args.mode == "load_new":
        last_page = scraper.load_page_range(home_url=base_url.format(index=""))
        scraper.download_new_patch_notes(base_url=base_url, stop_at=last_page)
    elif args.mode == "create_html":
        patch_notes = scraper.load_patch_notes_from_cache()
        scraper.load_patch_notes_content(patch_notes)
        formatter.export_html(patch_notes, f"{args.output_path}/patch_notes.html")
