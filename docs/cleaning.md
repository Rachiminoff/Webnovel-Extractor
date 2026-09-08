# Chapter Cleaning

## Purpose

The downloader captures what the browser exposes. That can include reader-interface artifacts that are not part of the chapter itself. The cleaner transforms raw chapter files into cleaner XHTML suitable for compilation.

## Generic cleanup

The cleaning pipeline can remove or normalize:

- Unwanted HTML tags.
- Common notices and announcements.
- Social and support links.
- Duplicate paragraphs.
- Repeated chapter titles.
- Excess attributes.

## Lumo Stories cleanup

Lumo chapters may contain reader artifacts such as:

```text
svg0
svg0 (icon)

Read on Lumo Stories. Unauthorized reproduction prohibited.
```

The cleaner removes these using targeted rules rather than broadly deleting any text containing words such as `svg` or `read`.

It also removes decorative `<svg>` elements before text serialization when appropriate.

### Example

Before:

```text
# A machine without emotions.

svg0

Night had fallen over the city.

Read on Lumo Stories. Unauthorized reproduction prohibited.

svg0 (icon)

After finishing her third cup of coffee...
```

After:

```text
# A machine without emotions.

Night had fallen over the city.

After finishing her third cup of coffee...
```

## Why site-specific rules are useful

A watermark or UI artifact may be unique to one website. A targeted cleanup rule reduces the risk of accidentally removing legitimate prose from chapters downloaded from another source.

## Lumo reader-control artifacts

Some Lumo chapters include reader-interface elements inside the same DOM container as the prose. After decorative SVG elements are removed, their wrappers may still render as tiny controls, counters such as `0`, or horizontal separators.

The cleaner now performs an additional DOM-level pass that removes reader controls (`button`, `input`, `select`, and related SVG elements), standalone icon/counter remnants such as `0`, `svg0`, and `svg0 (icon)`, horizontal separators associated with those controls, and empty wrappers left behind after removal. A defensive version of the same cleanup also runs when Lumo HTML is initially downloaded.
