from han_auto.parser import parse_markdown_text


def test_parse_yaml_front_matter_and_markdown_blocks() -> None:
    document = parse_markdown_text(
        """---
recipient: Office
title: Notice
fields:
  sender: Team
---

# Heading

Paragraph with **bold** text.

- First
- **Second**
"""
    )

    assert document.recipient == "Office"
    assert document.title == "Notice"
    assert document.fields == {"sender": "Team"}
    assert document.blocks[0].type == "heading"
    assert document.blocks[1].runs[1].bold is True
    assert document.blocks[2].type == "list"
    assert document.blocks[2].items[1].runs[0].bold is True


def test_plain_body_preserves_heading_paragraph_and_list_text() -> None:
    document = parse_markdown_text(
        """---
recipient: Office
title: Notice
---

# Heading

Body.

1. One
2. Two
"""
    )

    assert document.plain_body() == "Heading\n\nBody.\n\n1. One\n2. Two"
