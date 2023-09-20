import datetime
import logging
from pathlib import Path
from typing import List

from bs4 import BeautifulSoup, Tag, PageElement

from ee_patch_notes.scraper import PatchNote


logger = logging.getLogger("ee.export")


class FormattingException(Exception):
    pass


def get_html(patch_note: PatchNote) -> PageElement:
    if patch_note.content is None:
        raise FormattingException(f"Patch note {patch_note} does not have any content")
    soup = BeautifulSoup(patch_note.content, "html.parser")
    for span_tag in soup.find_all("span"):  # type: Tag
        if "color" not in span_tag.get("style", default=""):
            span_tag.unwrap()

    # noinspection PyTypeChecker
    tag = soup.contents[0]  # type: Tag
    tag["class"] = "patch-note"
    tag["id"] = "patch-note-" + patch_note.time.isoformat()
    tag.find("div", class_="title")["class"] = "patch-title"
    tag.find("div", class_="artCon")["class"] = "patch-content"
    return tag


def export_html(patch_notes: List[PatchNote], path: str):
    logger.info("Loading html template")
    file_path = (Path(__file__) / Path("../../resources/patch_notes_template.html")).resolve()
    with open(file_path, "r", encoding="utf-8") as file:
        template_raw = file.read()
    template = BeautifulSoup(template_raw, "html.parser")
    # template = template.replace("{time_updated}", datetime.datetime.now().isoformat(sep=" ", timespec="minutes"))
    # template = template.replace("{patch_notes}", html_str)

    tag_time = template.find("br", id="timestamp", recursive=True)
    tag_time.replaceWith(datetime.datetime.now().isoformat(sep=" ", timespec="minutes"))
    div_patch_notes = template.find("div", id="patch-notes", recursive=True)

    num_notes = len(patch_notes)
    logger.info("Inserting %s patch notes", num_notes)
    for i, patch_note in enumerate(sorted(patch_notes, key=lambda p: p.time, reverse=True)):
        div_patch_notes.append(get_html(patch_note))
        if (i + 1) % 20 == 0:
            logger.info("Inserted %s/%s", i + 1, num_notes)

    logger.info("Generating final html")
    html = template.prettify(encoding="utf-8")
    logger.info("Saving to %s", path)
    with open(path, "wb") as file:
        file.write(html)
