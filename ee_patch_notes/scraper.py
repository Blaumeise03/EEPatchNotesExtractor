import json
import logging
import os.path
import random
import re
from datetime import datetime, date
from time import sleep
from typing import Optional, List, Dict

import requests
from bs4 import BeautifulSoup, Tag
from requests import Response

logger = logging.getLogger("ee.web")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/117.0"
}
RATE_LIMIT_SECONDS = 1
RATE_LIMIT_RAND_FAC = 1
last_request = None  # type: datetime | None
DOWNLOAD_PATH = "data/patch_notes"
CACHE_PATH = f"{DOWNLOAD_PATH}/cache.json"
session = requests.Session()


def mk_dirs():
    if not os.path.exists(DOWNLOAD_PATH):
        os.makedirs(DOWNLOAD_PATH)


class WebScrapeException(Exception):
    pass


class PatchNote:
    date_pattern = re.compile(r"updata/(\d+)/")

    def __init__(self, url: str, time: Optional[date] = None):
        self.url = url
        if not url.startswith("http"):
            if url.startswith("//"):
                self.url = f"https:{url}"
            elif url.startswith("www"):
                self.url = f"https://{url}"
            else:
                raise WebScrapeException("Invalid url " + url)
        self.time = time
        self.content = None  # type: str | None
        if self.time is None:
            self.extract_date_from_url()

    def extract_date_from_url(self) -> None:
        match = PatchNote.date_pattern.search(self.url)
        if match is None:
            logger.error("Failed to extract patch note release date from url %s", self.url)
            raise WebScrapeException("Can't extract patch note time from url " + self.url)
        raw = match.group(1)
        self.time = date(year=int(raw[:4]), month=int(raw[4:6]), day=int(raw[6:]))

    def save_content(self, file_path: str) -> None:
        if self.content is None:
            raise WebScrapeException("Can't save patch notes %s (%s) to file %s as there is no content loaded",
                                     self.time, self.url, file_path)
        with open(file_path, "w", encoding="utf-8") as file:
            file.write(self.content)

    def to_meta_dict(self) -> Dict[str, Optional[str]]:
        return {
            "url": self.url,
            "time": self.time.isoformat()
        }

    def __repr__(self):
        return f"PatchNote({self.time})" if self.time is not None else f"PatchNote({self.url})"

    @staticmethod
    def from_meta_dict(raw: Dict[str, Optional[str]]) -> "PatchNote":
        return PatchNote(
            url=raw["url"],
            time=date.fromisoformat(raw["time"]) if raw["time"] is not None else None
        )


def save_patch_note_cache(patch_notes: List[PatchNote]) -> None:
    result = []
    for patch_note in patch_notes:
        result.append(patch_note.to_meta_dict())
    with open(CACHE_PATH, "w", encoding="utf-8") as file:
        json.dump(result, file)
    logger.info("Dumped patch note metadata to %s", CACHE_PATH)


def load_patch_notes_from_cache(file_path: str = CACHE_PATH) -> List[PatchNote]:
    with open(file_path, "r", encoding="utf-8") as file:
        raw = json.load(file)
    patch_notes = []
    for raw_p in raw:
        patch_notes.append(PatchNote.from_meta_dict(raw_p))
    return patch_notes


def rate_limit():
    global last_request
    if last_request is None:
        last_request = datetime.now()
        return
    diff = (datetime.now() - last_request).total_seconds()
    if diff < RATE_LIMIT_SECONDS:
        delay = RATE_LIMIT_SECONDS - diff + RATE_LIMIT_RAND_FAC * random.random()
        sleep(delay)
    last_request = datetime.now()


def fetch_page(url: str) -> Response:
    rate_limit()
    logger.info("Fetching page %s", url)
    return session.get(url, headers=HEADERS)


def load_page_range(home_url: str) -> int:
    page = fetch_page(home_url)

    # Find the div for the pagination
    soup = BeautifulSoup(page.content, "html.parser")
    try:
        data_pager = soup.find("div", class_="wrap").find("div", "pageBox").find("div", "pager")
    except TypeError as e:
        raise WebScrapeException("Failed to process news page format") from e

    # Find the url from the link to the "Last" page
    data_controllers = data_pager.find_all("a", class_="next")
    last_page_url = None
    for link in data_controllers:  # type: Tag
        data_span = link.find("span")
        if data_span is not None and len(data_span.contents) == 1 and data_span.contents[0] == "Last":
            last_page_url = link.get("href")
    if last_page_url is None:
        logger.error("Failed to find the last page url")
        raise WebScrapeException("Unable to find last patch notes page url")
    logger.info("Found last page url: %s", last_page_url)

    # Find the number of the last page
    re_link = re.compile(r"updata/index_(\d+).html")
    match = re_link.search(last_page_url)
    if match is None:
        logger.error("Failed to detect the patch notes url range")
        raise WebScrapeException("Invalid url pattern")
    last_page = int(match.group(1))
    logger.info("Last patch notes page has id %s", last_page)
    return last_page


def extract_patch_notes_urls(url: str) -> List[PatchNote]:
    page = fetch_page(url)

    soup = BeautifulSoup(page.content, "html.parser")
    try:
        data_list = soup.find("div", class_="wrap").find("ul", "newList")
    except TypeError as e:
        logger.error("Failed to parse patch notes list from page %s", url)
        raise WebScrapeException("Failed parse patch notes list") from e
    patch_urls = []  # type: List[PatchNote]
    logger.info("Searching patch notes urls")
    for item in data_list.find_all("li", class_="item"):
        link_tag = item.find("a")  # type: Tag
        if link_tag is None:
            continue
        date_tag = link_tag.find("p", class_="newDate", recursive=True)
        link = link_tag.get(key="href")
        date_str = date_tag.contents[0].getText() if len(date_tag.contents) == 1 else None
        if link is None:
            logger.warning("Tag didn't contains a patch notes link: %s", link)
            continue
        if date_str is None:
            logger.warning("Did not found a date for patch notes %s", link)
            release_date = None
        else:
            release_date = date.fromisoformat(date_str)
        patch_urls.append(PatchNote(url=link, time=release_date))
    logger.info("Found %s patch note urls in %s", len(patch_urls), url)
    return patch_urls


def find_all_patch_notes_urls(base_url: str, max_index: int, min_index: int = 1) -> List[PatchNote]:
    patch_notes = []
    for i in range(min_index, max_index + 1):
        logger.info("Loading patch note urls %s/%s", i, max_index)
        index = f"_{i}"
        if i == 1:
            index = ""
        new_notes = extract_patch_notes_urls(base_url.format(index=index))
        patch_notes.extend(new_notes)
    logger.info("Loaded a total of %s patch note urls", len(patch_notes))
    save_patch_note_cache(patch_notes)
    return patch_notes


def download_patch_note(patch_note: PatchNote, save_path: str) -> None:
    page = fetch_page(patch_note.url)

    # with open(save_path, "w", encoding="utf-8") as file:
    #     file.write(page.content.decode(encoding="utf-8"))

    soup = BeautifulSoup(page.content, "html.parser")

    try:
        data_patch_notes = soup.find("div", class_="wrap").find("div", "newDetail")
    except TypeError as e:
        logger.error("Failed to parse patch notes %s", patch_note.url)
        raise WebScrapeException("Failed parse patch notes") from e

    data_content = data_patch_notes.find("div", class_="artCon")
    data_title = data_patch_notes.find("div", class_="title")
    if data_content is None:
        logger.error("Did not found patch note content for %s", patch_note.url)
        raise WebScrapeException("Failed parse patch note content")
    if data_title is None:
        logger.error("Did not found patch note title for %s", patch_note.url)
        raise WebScrapeException("Failed parse patch note title")

    patch_note.content = data_patch_notes.decode()
    patch_note.save_content(save_path)
    logger.debug("Saved patch notes %s to %s", patch_note.url, save_path)


def download_all_patch_notes(patch_notes: List[PatchNote], skip_existing=True) -> None:
    length = len(patch_notes)
    for i, patch_note in enumerate(patch_notes):
        save_path = f"{DOWNLOAD_PATH}/patch_notes_{patch_note.time.isoformat()}.html"
        if skip_existing and os.path.exists(save_path):
            logger.info("Processing %s [%s/%s]: File exists - skipping",
                        patch_note.time.isoformat(), i + 1, length)
            continue
        logger.info("Processing %s [%s/%s]: Downloading %s",
                    patch_note.time.isoformat(), i + 1, length, patch_note.url)
        download_patch_note(patch_note, save_path)


def has_missing_notes(patch_notes: List[PatchNote]) -> bool:
    for patch_note in patch_notes:
        save_path = f"{DOWNLOAD_PATH}/patch_notes_{patch_note.time.isoformat()}.html"
        if not os.path.exists(save_path):
            return True
    return False


def download_new_patch_notes(base_url: str, stop_at=4) -> None:
    logger.info("Loading missing patch notes")
    for i in range(1, stop_at + 1):
        patch_notes = find_all_patch_notes_urls(base_url=base_url, max_index=i, min_index=i)
        if not has_missing_notes(patch_notes):
            logger.info("Page %s has no new patch notes, stopping search", i)
            break
        download_all_patch_notes(patch_notes)
