import datetime
import logging
from pathlib import Path
from typing import List, Union, Optional

from bs4 import BeautifulSoup, Tag, PageElement, NavigableString

from ee_patch_notes.scraper import PatchNote


logger = logging.getLogger("ee.export")


class FormattingException(Exception):
    pass


# noinspection PyTypeChecker,PyUnresolvedReferences
def replace_section_heading(tag: Tag, soup: BeautifulSoup):
    # The heading scheme is inconsistent, there are these variations:
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
    def _is_heading_tag(obj: Tag):
        return isinstance(obj, Tag) and (obj.name == "em" or obj.name == "strong")

    def _get_first_real_element(
            contents: Optional[List[Union[Tag, NavigableString]]] = None,
            element: Union[Tag, NavigableString] = None):
        if contents is None and element is None:
            raise TypeError("Either a list of elements or an element must be given")
        if contents is not None and element is not None:
            raise TypeError("Only may parameter be given")
        if element is not None:
            el = element.next_sibling
            if isinstance(el, NavigableString) and len(el.text.strip(" \n")) == 0:
                if el.next_sibling is None:
                    return None
                # noinspection PyTypeChecker
                return _get_first_real_element(element=el)
            return el
        # noinspection PyTypeChecker
        for el in contents:
            if isinstance(el, NavigableString) and len(el.text.strip(" \n")) == 0:
                continue
            return el
        return None

    def _is_end_of_paragraph(obj: Tag | NavigableString):
        sibling = _get_first_real_element(element=tag)
        if sibling is not None and sibling.name == "br":
            return True
        elif sibling is None:
            return obj.parent.name == "p"
        if isinstance(obj.next_sibling, NavigableString):
            _str = obj.next_sibling
            if _str.next_sibling is not None and _str.next_sibling.name == "br":
                _str.extract()
        return False

    outer_tag = None  # type: Tag
    middle_tag = None  # type: Tag
    inner_tag = None  # type: Tag
    major = None  # type: NavigableString
    minor = None  # type: NavigableString
    num_contents = 0
    for t in tag.contents:
        if isinstance(t, NavigableString) and len(t.text.strip(" \n")) == 0:
            continue
        num_contents += 1

    # Check special case where there are two headings in one <span>
    if num_contents > 1:
        outer_tag = tag
        for t in tag.contents:
            if isinstance(t, Tag) and t.name == "strong":
                inner_tag = t
            if isinstance(t, NavigableString):
                minor = t
    else:
        t = _get_first_real_element(tag.contents)
        outer_tag = tag
        # Check children of span
        if isinstance(t, Tag) and _is_heading_tag(t):
            inner_tag = t
            t = _get_first_real_element(t.contents)
            # <span><strong>???</strong><span>
            # outer  inner   t
            if isinstance(t, Tag) and _is_heading_tag(t):
                # <span><strong><em>Text</em></strong><span>
                # outer  middle  t
                middle_tag = inner_tag
                inner_tag = t
            elif isinstance(t, NavigableString):
                # <span><strong>Text</strong><span>
                # outer  inner   t
                pass
        elif isinstance(t, NavigableString):
            # <span>Text<span>
            # inner   t
            inner_tag = t.parent
        # Check parents
        t = outer_tag.parent
        if _is_heading_tag(t):
            # <em><span>???<span></em>
            #  t  outer inner?
            middle_tag = outer_tag
            outer_tag = t
            t = outer_tag.parent
            if _is_heading_tag(t):
                # <strong><em><span>Text<span></em></strong>
                # outer  middle inner
                middle_tag = outer_tag
                outer_tag = t

    if outer_tag is None or not _is_end_of_paragraph(outer_tag):
        return
    if inner_tag.name == "strong" or (middle_tag and middle_tag.name == "strong") or outer_tag.name == "strong":
        major = inner_tag.contents[0]
    else:
        minor = inner_tag.contents[0]

    major_heading = None
    last_el = None
    if major:
        major_heading = soup.new_tag("h3")
        major_heading.insert(0, major)
        outer_tag.insert_after(major_heading)
        last_el = major_heading
    if minor:
        minor_heading = soup.new_tag("h4")
        minor_heading.insert(0, minor)
        if major_heading is not None:
            major_heading.insert_after(minor_heading)
        else:
            outer_tag.insert_after(minor_heading)
        last_el = minor_heading
    next_el = _get_first_real_element(element=last_el)
    if next_el is not None and next_el.name == "br":
        next_el.decompose()
    outer_tag.decompose()


def get_html(patch_note: PatchNote) -> PageElement:
    if patch_note.content is None:
        raise FormattingException(f"Patch note {patch_note} does not have any content")
    soup = BeautifulSoup(patch_note.content.replace(" ", " "), "html.parser")  # .replace(" ", " ")
    # soup2 = BeautifulSoup(patch_note.content.replace(" ", " "), "html.parser")

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
    for tag in soup.find_all("b"):
        tag.name = "strong"

    # Delete all images (older patch notes did contain <img> tags)
    for img_tag in soup.find_all("img"):  # type: Tag
        img_tag.replaceWith("")

    # Find subheadings
    for span_tag in soup.find_all("span"):  # type: Tag
        if "color" not in span_tag.get("style", default=""):
            continue
        # ToDo: Maybe handle pre-2021-10-11 patch notes (uncolored headings)
        replace_section_heading(span_tag, soup)
    # ToDo: Cleanup Headings and divs, see 2022-04-02 or 2022-05-31, especially 2022-06-08
    # ToDo: Divide <p> tags at headings (there are now h3 and h4 inside <p> tags)
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
