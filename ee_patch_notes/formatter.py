import datetime
import logging
from pathlib import Path
from typing import List, Union, Optional

from bs4 import BeautifulSoup, Tag, PageElement, NavigableString

from ee_patch_notes.scraper import PatchNote


logger = logging.getLogger("ee.export")
TEXT_TAGS = ["span", "em", "strong"]


class FormattingException(Exception):
    pass


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

    def _is_end_of_paragraph(obj: Tag | NavigableString):
        sibling = _get_first_real_element(element=obj)
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


def remove_div(div: Tag, soup: BeautifulSoup):
    len_content = 0
    child = None
    for c in div.contents:
        if isinstance(c, NavigableString) and len(c.text.strip(" \n")) == 0:
            continue
        len_content += 1
        if child is None:
            child = c
    if len_content < 1:
        div.decompose()
    elif len_content == 1:
        if child.name == "div":
            div.unwrap()
            remove_div(child, soup=soup)
        elif isinstance(child, NavigableString) or child.name in TEXT_TAGS:
            repl = soup.new_tag("p")
            repl.insert(0, child.extract())
            div.insert_after(repl)
            div.decompose()
        else:
            logger.warning("Unknown div child %s", child)
    else:
        div.unwrap()


def replace_with_ul(tag: Tag, soup: BeautifulSoup):
    ul = soup.new_tag("ul", style="list-style-type: square;")
    tag.insert_before(ul)
    p = tag
    i = 0
    while p.name == "p" and "margin-left: 40px" in p.get("style", ""):
        n = p.next_sibling
        li = soup.new_tag("li")
        ul.insert(i, li)
        li.insert(0, p)
        p.unwrap()
        i += 1
        p = n


def extract_heading(heading: Tag, soup: BeautifulSoup):
    prev_p = heading.parent
    next_p = soup.new_tag("p")
    i = 0
    tag = heading.next_sibling
    while tag is not None:
        next_p.insert(i, tag)
        tag = tag.next_sibling
        i += 1
    prev_p.insert_after(heading)
    heading.insert_after(next_p)
    if len(prev_p.contents) == 0 or _get_first_real_element(contents=prev_p.contents) is None:
        prev_p.decompose()
    if len(next_p.contents) == 0 or _get_first_real_element(contents=next_p.contents) is None:
        next_p.decompose()


def get_html(patch_note: PatchNote) -> PageElement:
    if patch_note.content is None:
        raise FormattingException(f"Patch note {patch_note} does not have any content")
    soup = BeautifulSoup(patch_note.content.replace(" ", " "), "html.parser")  # .replace(" ", " ")
    # soup2 = BeautifulSoup(patch_note.content.replace(" ", " "), "html.parser")

    # Delete all images (older patch notes did contain <img> tags)
    for img_tag in soup.find_all("img"):  # type: Tag
        img_tag.replaceWith("")

    # Basic setup
    # noinspection PyTypeChecker
    tag = soup.contents[0]  # type: Tag
    tag["class"] = "patch-note"
    tag["id"] = "patch-note-" + patch_note.time.isoformat()
    tag.find("div", class_="title")["class"] = "patch-title"
    content = tag.find("div", class_="artCon")
    content["class"] = "patch-content"

    # Remove unnecessary spans
    for span_tag in soup.find_all("span"):  # type: Tag
        # There is also one patch note that is using #FFA500 as color
        if "color" not in span_tag.get("style", default="") or "#FF8C00" not in span_tag.get("style"):
            span_tag.unwrap()
        if span_tag.get("class") is not None:
            del span_tag["class"]

    # Replace/remove divs
    for div_tag in content.find_all("div", recursive=False):
        remove_div(div_tag, soup)

    for p_tag in soup.find_all("p"):  # type: Tag
        if p_tag.get("style") is not None:
            if p_tag.decomposed:
                continue
            if "margin-left: 40px" in p_tag.get("style"):
                replace_with_ul(p_tag, soup)
            del p_tag["style"]
        if p_tag.get("class") is not None and len(p_tag["class"]) != 1 and p_tag["class"][0] != "date":
            del p_tag["class"]
        if p_tag.get("align") is not None:
            del p_tag["align"]
    for tag in soup.find_all("b"):
        tag.name = "strong"

    # Find subheadings
    for span_tag in soup.find_all("span"):  # type: Tag
        if "color" not in span_tag.get("style", default=""):
            continue
        # ToDo: Maybe handle pre-2021-10-11 patch notes (uncolored headings)
        replace_section_heading(span_tag, soup)
    # ToDo: Cleanup Headings and divs, see 2022-04-02
    for p_tag in soup.find_all("p"):
        for heading in p_tag.find_all(["h3", "h4"], recursive=False):
            extract_heading(heading, soup)
    return soup.contents[0]


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
