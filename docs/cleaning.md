# Chapter Cleaning

## Purpose

A downloaded web page is not automatically a clean ebook chapter.

Websites often place navigation, advertisements, reader controls, social links, watermarks, and other interface elements around the actual prose. The cleaning stage removes those unwanted parts while keeping the chapter text.

The important design choice is that downloading and cleaning are separate operations.

```text
Raw chapter
    ↓
Cleaning rules
    ↓
Normalized XHTML
```

The raw download remains available for inspection if a cleaning rule needs to be changed later.

---

## General cleanup

The cleaning pipeline can remove or normalize common web-page artifacts, including:

- unwanted HTML elements;
- scripts and styles that do not belong in the chapter;
- common notices and announcements;
- social/support links;
- repeated chapter titles;
- duplicate paragraphs;
- unnecessary attributes;
- empty wrappers left after other elements are removed.

The exact cleanup depends on the cleaner mode and the source.

---

## Lumo-specific cleanup

Lumo's reader can place interface elements inside the same DOM area as the chapter prose.

Known artifacts include examples such as:

```text
svg0
svg0 (icon)
0
Read on Lumo Stories. Unauthorized reproduction prohibited.
```

The cleaner uses targeted rules for known artifacts rather than blindly deleting every element containing words such as `svg` or `icon`.

It can also remove reader controls such as:

- buttons;
- input controls;
- select controls;
- decorative SVG elements;
- horizontal separators associated with controls;
- empty wrappers left after removal.

---

## Why cleanup is separate

Separating the stages makes troubleshooting easier.

If the raw file contains the correct chapter text but the cleaned file does not, the problem is in the cleaning rules.

If the raw file already lacks the chapter text, the problem is earlier in the download/extraction stage.

This distinction prevents scraper problems and cleaning problems from being confused with each other.

---

## Safe maintenance

Cleaning rules should be narrow whenever possible.

For example, a rule that removes a known Lumo reproduction notice is safer than a rule that removes every paragraph containing the word `reproduction`.

Before changing a cleanup rule:

1. save an example of the unwanted element;
2. identify what makes it unique;
3. create the smallest selector or text rule that removes it;
4. verify that normal prose is not affected;
5. run the cleaner against several chapters.
