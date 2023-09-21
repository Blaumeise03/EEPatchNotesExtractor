import datetime
import logging
from pathlib import Path
from typing import List

from bs4 import BeautifulSoup, Tag, PageElement, NavigableString

from ee_patch_notes.scraper import PatchNote


logger = logging.getLogger("ee.export")


class FormattingException(Exception):
    pass


# noinspection PyTypeChecker,PyUnresolvedReferences
def _replace_section_heading(tag: Tag, soup: BeautifulSoup):
    # The heading scheme is incosistent, there are these variations:
    # <span style="color:#FF8C00;">
    #  <strong>Major Heading</strong>
    #  <br>
    #  Minor Heading
    # </span>
    # <br>
    #
    # <span style="color:#FF8C00;">Minor Heading</span>
    # <br>
    #
    # <span style="color:#FF8C00;">
    #  <strong>Major Heading</strong>
    # </span>
    # <br>
    #
    # <span style="color:#FF8C00;">
    #  <em><strong>Major Heading</strong></em>
    # </span>
    # <br>
    #
    # <strong>
    #  <span style="color:#FF8C00;">
    #   Major Heading
    #  </span>
    # </strong>
    #
    def _is_br_sibling(obj: Tag | NavigableString):
        if obj.next_sibling is not None and obj.next_sibling.name == "br":
            return True
        if obj.next_sibling is None:
            return False
        if isinstance(obj.next_sibling, NavigableString):
            _str = obj.next_sibling
            if _str.next_sibling is not None and _str.next_sibling.name == "br":
                _str.extract()
        return False
    span = None
    strong = None
    em = None
    minor = None

    if tag.name != "span":
        return
    span = tag
    em = span.find("em")  # type: Tag | None
    # ToDo: Handle headings without <strong> (only <em>), see 2021-12-01
    if len(span.contents) == 0:
        return
    if len(span.contents) > 1:
        for t in span.contents:
            if isinstance(t, Tag) and t.name == "strong":
                strong = t
            if isinstance(t, NavigableString):
                minor = t
    else:
        if isinstance(span.contents[0], NavigableString):
            minor = span.contents[0]
        elif em is not None and em.contents[0].name == "strong":
            strong = em.contents[0]
        elif isinstance(span.contents[0], Tag) and span.contents[0].name == "strong":
            strong = span.contents[0]

    if not _is_br_sibling(span):
        # Check if <span> and <strong> are switched
        if span.parent.name == "strong":
            strong = span
            span = span.parent
            if span.parent.name == "em":
                span = span.parent
            # (Those tags get deleted anyway, so it doesn't matter that the span tag is now saved in `strong`
        elif span.parent.name == "em":
            # Can also happen with an <em> between <strong> and <span>
            em = span.parent
            if em.parent.name == "strong":
                strong = span
                span = em.parent
        # ToDo: Find better way, also possible is <em><span><strong>Heading..., see 2022-10-26

    if not _is_br_sibling(span):
        # Check if the heading is the sole content of a <p> tag, for example
        # <p><span style...>Heading</span></p>
        # In this case there is now br tag required
        # ToDo: It is also possible that span is the last content of a <p>-tag, see 2022-08-17
        # ToDo: Also possible that instead of p-tag they use a div-tag, see 2022-08-10
        if span.parent.name != "p" or len(span.parent.contents) != 1:
            return
    else:
        # Delete the <br> tag
        span.next_sibling.decompose()

    major_heading = None
    if strong:
        if _is_br_sibling(strong):
            strong.next_sibling.decompose()
        major_heading = soup.new_tag("h3")
        major_heading.insert(0, strong.contents[0])
        tag.insert_after(major_heading)
    if minor:
        minor_heading = soup.new_tag("h4")
        minor_heading.insert(0, minor)
        if major_heading is not None:
            major_heading.insert_after(minor_heading)
        else:
            tag.insert_after(minor_heading)

    tag.decompose()


def get_html(patch_note: PatchNote) -> PageElement:
    if patch_note.content is None:
        raise FormattingException(f"Patch note {patch_note} does not have any content")
    soup = BeautifulSoup(patch_note.content, "html.parser")

    # Remove unnecessary spans
    for span_tag in soup.find_all("span"):  # type: Tag
        # There is also one patch note that is using #FFA500 as color
        if "color" not in span_tag.get("style", default="") or "#FF8C00" not in span_tag.get("style"):
            span_tag.unwrap()
        if span_tag.get("class") is not None:
            del span_tag["class"]
    for p_tag in soup.find_all("p"):  # type: Tag
        # ToDo: Convert p with style="margin-left" to <ul>-lists, see 2022-04-02
        if p_tag.get("style") is not None:
            del p_tag["style"]
        if p_tag.get("class") is not None and len(p_tag["class"]) != 1 and p_tag["class"][0] != "date":
            del p_tag["class"]

    # Delete all images (older patch notes did contain <img> tags)
    for img_tag in soup.find_all("img"):  # type: Tag
        img_tag.replaceWith("")

    # Find subheadings
    for span_tag in soup.find_all("span"):  # type: Tag
        if "color" not in span_tag.get("style", default=""):
            continue
        # ToDo: Maybe handle pre-2021-10-11 patch notes (uncolored headings)
        _replace_section_heading(span_tag, soup)
    # ToDo: Cleanup Headings and divs, see 2022-04-02 or 2022-05-31, especially 2022-06-08
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
