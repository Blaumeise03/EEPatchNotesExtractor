import unittest
from typing import List

from bs4 import BeautifulSoup, Tag, NavigableString

from ee_patch_notes import formatter


class SectionHeadingTest(unittest.TestCase):
    def assertHTMLEquals(self, expected: List[str], root_tag: Tag):
        tag = root_tag.contents[0]
        for i, expected in enumerate(expected):
            while isinstance(tag, NavigableString) and len(tag.text.strip(" \n")) == 0:
                tag = tag.next_sibling
            self.assertIsNotNone(tag, f"Did not found tag {expected} at pos {i}")
            self.assertEqual(expected, tag.name, f"Tag at position {i} is not correct")
            tag = tag.next_sibling
        while isinstance(tag, NavigableString) and len(tag.text.strip(" \n")) == 0:
            tag = tag.next_sibling
        self.assertIsNone(tag, "There are more tags than expected")

    def assertFormatsCorrect(self, html: str, expected_result: List[str]):
        soup = BeautifulSoup(markup=html, features="html.parser")
        tag = soup.find("span")
        formatter.replace_section_heading(tag, soup)
        self.assertHTMLEquals(expected_result, soup.find("p"))

    def test_special_case(self):
        self.assertFormatsCorrect(
            html="<p><span style=\"color:#FF8C00;\">"
                 "  <strong>"
                 "    New Content"
                 "  </strong>"
                 "  <br>"
                 "  Structure: Asteroid Detection Array"
                 "</span></p>",
            expected_result=["h3", "h4"]
        )

    def test_major_headings(self):
        self.assertFormatsCorrect(
            html="<p>"
                 " <span style=\"color:#FF8C00;\"> "
                 "  <strong>"
                 "    New Content"
                 "  </strong> "
                 " </span> "
                 "</p> ",
            expected_result=["h3"])
        self.assertFormatsCorrect(
            html="<p> "
                 " <span style=\"color:#FF8C00;\"> "
                 "  <strong> "
                 "   <em>New Content</em>"
                 "  </strong> "
                 " </span></br> "
                 " "
                 "</p> ",
            expected_result=["h3"])
        self.assertFormatsCorrect(
            html="<p>"
                 " <strong>"
                 "  <span style=\"color:#FF8C00;\"> "
                 "   <em>New Content</em></br> "
                 "  </span>"
                 " </strong>"
                 "</p>",
            expected_result=["h3"])

    def test_minor_headings(self):
        self.assertFormatsCorrect(
            html="<p>"
                 " <em>"
                 "  <span style=\"color:#FF8C00;\"> "
                 "   New Content"
                 "  </span>"
                 " </em>"
                 "</p>",
            expected_result=["h4"])
        self.assertFormatsCorrect(
            html="<p>"
                 " <span style=\"color:#FF8C00;\"> "
                 "  <em>New Content</em> "
                 " </span>"
                 "</p>",
            expected_result=["h4"])
        self.assertFormatsCorrect(
            html="<p>"
                 " <span style=\"color:#FF8C00;\"> "
                 "  New Content "
                 " </span>"
                 "</p>",
            expected_result=["h4"])

    def test_malformed_html(self):
        self.assertFormatsCorrect(
            html="<p>"
                 " <span style=\"color:#FF8C00;\">New Content</em></span>"
                 " <br>"
                 "</p>",
            expected_result=["h4"])

    def test_linebreaks(self):
        self.assertFormatsCorrect(
            html="<p>"
                 " <span style=\"color:#FF8C00;\">New Content</span>"
                 " </br>"
                 "</p>",
            expected_result=["h4"])


if __name__ == '__main__':
    unittest.main()
