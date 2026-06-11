from han_auto.formatter import MarkdownHwpFormatter
from han_auto.models import InlineText, ListItem, MarkdownBlock, StyleMapping


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def put_field_text(self, field_name: str, text: str) -> None:
        self.calls.append(("put_field", f"{field_name}={text}"))

    def move_to_field(self, field_name: str) -> None:
        self.calls.append(("move", field_name))

    def insert_text(self, text: str) -> None:
        self.calls.append(("insert", text))

    def run_action(self, action_name: str) -> None:
        self.calls.append(("action", action_name))


def _blocks() -> list[MarkdownBlock]:
    return [
        MarkdownBlock(type="heading", level=1, text="Title", runs=[InlineText(text="Title")]),
        MarkdownBlock(
            type="paragraph",
            text="Body with bold",
            runs=[InlineText(text="Body with "), InlineText(text="bold", bold=True)],
        ),
        MarkdownBlock(
            type="list",
            ordered=True,
            items=[
                ListItem(text="first", runs=[InlineText(text="first")]),
                ListItem(text="second", runs=[InlineText(text="second")]),
            ],
        ),
    ]


def test_plain_text_renders_all_block_types() -> None:
    text = MarkdownHwpFormatter().plain_text(_blocks())

    assert "Title" in text
    assert "Body with bold" in text
    assert "1. first" in text
    assert "2. second" in text


def test_insert_body_clears_field_then_inserts_in_order() -> None:
    client = FakeClient()
    styles = StyleMapping(heading={1: "HeadingAction"}, bold="CharShapeBold")

    MarkdownHwpFormatter().insert_body(client, "body", _blocks(), styles)

    assert client.calls[0] == ("put_field", "body=")
    assert client.calls[1] == ("move", "body")
    assert ("action", "HeadingAction") in client.calls
    inserted = "".join(text for kind, text in client.calls if kind == "insert")
    assert "Title" in inserted
    assert "1. first" in inserted
    assert "2. second" in inserted


def test_insert_body_toggles_bold_around_bold_runs() -> None:
    client = FakeClient()
    styles = StyleMapping(bold="CharShapeBold")
    blocks = [
        MarkdownBlock(
            type="paragraph",
            text="a b",
            runs=[InlineText(text="a "), InlineText(text="b", bold=True)],
        )
    ]

    MarkdownHwpFormatter().insert_body(client, "body", blocks, styles)

    bold_indexes = [i for i, call in enumerate(client.calls) if call == ("action", "CharShapeBold")]
    assert len(bold_indexes) == 2
    assert client.calls[bold_indexes[0] + 1] == ("insert", "b")
    assert bold_indexes[1] == bold_indexes[0] + 2


def test_insert_body_skips_bold_action_when_unmapped() -> None:
    client = FakeClient()
    styles = StyleMapping(bold=None)
    blocks = [
        MarkdownBlock(type="paragraph", text="b", runs=[InlineText(text="b", bold=True)])
    ]

    MarkdownHwpFormatter().insert_body(client, "body", blocks, styles)

    assert all(kind != "action" for kind, _ in client.calls)
    assert ("insert", "b") in client.calls
