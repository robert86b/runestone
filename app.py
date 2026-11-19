from flask import (
    Flask, render_template, request, redirect,
    url_for, jsonify, send_from_directory
)
from pathlib import Path
from datetime import datetime
from urllib.parse import quote
import html
import os
import re

app = Flask(__name__)

NOTES_DIR = Path(os.environ.get("RUNESTONE_NOTES_DIR", "/data/notes")).resolve()
NOTES_DIR.mkdir(parents=True, exist_ok=True)


def safe_name(name):
    name = re.sub(r'[^\w\s\-]', '', name).strip()
    return re.sub(r'\s+', ' ', name) or "Untitled"


def note_path(filename):
    path = (NOTES_DIR / filename).resolve()

    if NOTES_DIR not in path.parents or path.suffix != ".md":
        raise ValueError("Invalid note path")

    return path


def list_notes():
    notes = []

    for path in NOTES_DIR.rglob("*.md"):
        stat = path.stat()

        notes.append({
            "name": path.stem,
            "file": str(path.relative_to(NOTES_DIR)),
            "modified": datetime.fromtimestamp(
                stat.st_mtime
            ).strftime("%Y-%m-%d %H:%M")
        })

    return sorted(
        notes,
        key=lambda x: x["modified"],
        reverse=True
    )


def find_note_by_title(title):
    wanted = title.strip().lower()

    for note in list_notes():
        if note["name"].lower() == wanted:
            return note

    return None


def backlinks_for(filename):
    try:
        current = note_path(filename)
    except ValueError:
        return []

    title = current.stem.lower()
    backlinks = []

    for note in list_notes():
        if note["file"] == filename:
            continue

        try:
            content = note_path(note["file"]).read_text(
                encoding="utf-8",
                errors="ignore"
            )

            links = re.findall(
                r'\[\[([^\]]+)\]\]',
                content
            )

            if any(
                link.strip().lower() == title
                for link in links
            ):
                backlinks.append(note)

        except Exception:
            pass

    return backlinks


def inline_markdown(text):
    text = html.escape(text)

    # Wiki links
    def wiki(match):
        title = html.unescape(match.group(1)).strip()
        found = find_note_by_title(title)

        if found:
            href = "/note/" + quote(
                found["file"],
                safe="/"
            )
            return (
                f'<a class="wiki" href="{href}">'
                f'{html.escape(title)}</a>'
            )

        return (
            '<span class="wiki missing">'
            + html.escape(title)
            + '</span>'
        )

    text = re.sub(
        r'\[\[([^\]]+)\]\]',
        wiki,
        text
    )

    text = re.sub(
        r'\*\*(.+?)\*\*',
        r'<strong>\1</strong>',
        text
    )

    text = re.sub(
        r'(?<!\*)\*([^*]+?)\*(?!\*)',
        r'<em>\1</em>',
        text
    )

    text = re.sub(
        r'`([^`]+)`',
        r'<code>\1</code>',
        text
    )

    return text


def render_markdown(content):
    lines = content.splitlines()
    output = []
    in_ul = False

    def close_ul():
        nonlocal in_ul
        if in_ul:
            output.append("</ul>")
            in_ul = False

    for raw in lines:
        line = raw.rstrip()

        if not line:
            close_ul()
            output.append('<div class="spacer"></div>')
            continue

        if line.startswith("### "):
            close_ul()
            output.append(
                "<h3>" +
                inline_markdown(line[4:]) +
                "</h3>"
            )

        elif line.startswith("## "):
            close_ul()
            output.append(
                "<h2>" +
                inline_markdown(line[3:]) +
                "</h2>"
            )

        elif line.startswith("# "):
            close_ul()
            output.append(
                "<h1>" +
                inline_markdown(line[2:]) +
                "</h1>"
            )

        elif re.match(r'^- \[[ xX]\] ', line):
            close_ul()

            checked = line[3].lower() == "x"
            text = line[6:]

            output.append(
                '<div class="task">'
                f'<span class="box {"checked" if checked else ""}">'
                f'{"✓" if checked else ""}'
                '</span>'
                f'<span>{inline_markdown(text)}</span>'
                '</div>'
            )

        elif line.startswith("- "):
            if not in_ul:
                output.append("<ul>")
                in_ul = True

            output.append(
                "<li>" +
                inline_markdown(line[2:]) +
                "</li>"
            )

        elif line.startswith("> "):
            close_ul()
            output.append(
                "<blockquote>" +
                inline_markdown(line[2:]) +
                "</blockquote>"
            )

        else:
            close_ul()
            output.append(
                "<p>" +
                inline_markdown(line) +
                "</p>"
            )

    close_ul()

    return "\n".join(output)


@app.route("/")
def index():
    return render_template(
        "index.html",
        notes=list_notes(),
        search=None
    )


@app.route("/note/<path:filename>")
def note(filename):
    try:
        path = note_path(filename)
    except ValueError:
        return "Invalid note", 400

    if not path.exists():
        return "Note not found", 404

    content = path.read_text(
        encoding="utf-8",
        errors="ignore"
    )

    return render_template(
        "editor.html",
        filename=filename,
        title=path.stem,
        content=content,
        rendered=render_markdown(content),
        notes=list_notes(),
        backlinks=backlinks_for(filename)
    )


@app.route("/new", methods=["POST"])
def new_note():
    title = safe_name(
        request.form.get(
            "title",
            "Untitled"
        )
    )

    path = NOTES_DIR / f"{title}.md"

    counter = 2
    original = path

    while path.exists():
        path = (
            NOTES_DIR /
            f"{original.stem} {counter}.md"
        )
        counter += 1

    path.write_text(
        f"# {path.stem}\n\n",
        encoding="utf-8"
    )

    return redirect(
        url_for(
            "note",
            filename=path.name
        )
    )


@app.route(
    "/save/<path:filename>",
    methods=["POST"]
)
def save(filename):
    try:
        path = note_path(filename)
    except ValueError:
        return jsonify({
            "saved": False,
            "error": "Invalid note"
        }), 400

    data = request.get_json(
        silent=True
    ) or {}

    content = data.get(
        "content",
        ""
    )

    path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    path.write_text(
        content,
        encoding="utf-8"
    )

    return jsonify({
        "saved": True,
        "filename": filename
    })


@app.route(
    "/delete/<path:filename>",
    methods=["POST"]
)
def delete(filename):
    try:
        path = note_path(filename)
    except ValueError:
        return "Invalid note", 400

    if path.exists():
        path.unlink()

    return redirect(
        url_for("index")
    )


@app.route("/search")
def search():
    q = request.args.get(
        "q",
        ""
    ).lower().strip()

    if not q:
        return redirect(
            url_for("index")
        )

    results = []

    for note in list_notes():
        try:
            content = note_path(
                note["file"]
            ).read_text(
                encoding="utf-8",
                errors="ignore"
            ).lower()

            if (
                q in note["name"].lower()
                or q in content
            ):
                results.append(note)

        except Exception:
            pass

    return render_template(
        "index.html",
        notes=results,
        search=q
    )


@app.route("/sw.js")
def service_worker():
    response = send_from_directory(
        "static",
        "sw.js",
        mimetype="application/javascript"
    )

    response.headers[
        "Service-Worker-Allowed"
    ] = "/"

    response.headers[
        "Cache-Control"
    ] = "no-cache"

    return response


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "app": "Runestone",
        "version": "2.0"
    })


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=8096
    )
