from __future__ import annotations

from pathlib import Path


def _find_matching_paren(text: str, start_idx: int) -> int:
    """
    Returns index of the matching ')' for the '(' at start_idx.
    Ignores parentheses inside quoted strings.
    """
    depth = 0
    in_string = False
    escape = False
    for i in range(start_idx, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
            continue
        if ch == "(":
            depth += 1
            continue
        if ch == ")":
            depth -= 1
            if depth == 0:
                return i
    return -1


from typing import Optional


def _extract_field(block: str, key: str) -> Optional[str]:
    import re

    m = re.search(rf'\(\s*{re.escape(key)}\s+"([^"]*)"\s*\)', block)
    if not m:
        return None
    return m.group(1)


def _extract_comments(block: str) -> dict[int, str]:
    import re

    out: dict[int, str] = {}
    for m in re.finditer(r'\(\s*comment\s+(\d+)\s+"([^"]*)"\s*\)', block):
        try:
            idx = int(m.group(1))
        except Exception:
            continue
        if 1 <= idx <= 9:
            out[idx] = m.group(2)
    return out


def _canonical_title_block(*, title: str, date: str, rev: str, company: str, comments: dict[int, str]) -> str:
    def c(i: int) -> str:
        return comments.get(i, "")

    return (
        "  (title_block\n"
        f'    (title "{title}")\n'
        f'    (date "{date}")\n'
        f'    (rev "{rev}")\n'
        f'    (company "{company}")\n'
        f'    (comment 1 "{c(1)}")\n'
        f'    (comment 2 "{c(2)}")\n'
        f'    (comment 3 "{c(3)}")\n'
        f'    (comment 4 "{c(4)}")\n'
        "  )\n"
    )


def set_title_block_revision(schematic_file: str, revision: str) -> bool:
    """
    Updates the schematic title block (rev field) in a *.kicad_sch file.
    Returns True if file content changed.
    """
    rev = (revision or "").strip()
    if not rev:
        return False

    path = Path(schematic_file)
    if not path.exists():
        return False

    text = path.read_text(encoding="utf-8", errors="replace")

    start = text.find("(title_block")
    if start < 0:
        # Insert a canonical title_block near the header, ideally after (paper ...).
        insert_at = -1
        for anchor in ("(paper", "(uuid", "(generator_version", "(generator", "(version"):
            pos = text.find(anchor)
            if pos >= 0:
                # Insert right after the end of that S-expression line.
                nl = text.find("\n", pos)
                insert_at = nl + 1 if nl >= 0 else len(text)
                break
        if insert_at < 0:
            nl = text.find("\n")
            insert_at = nl + 1 if nl >= 0 else len(text)

        block = _canonical_title_block(title="", date="", rev=rev, company="", comments={})
        new_text = text[:insert_at] + block + text[insert_at:]
        if new_text != text:
            path.write_text(new_text, encoding="utf-8")
            return True
        return False

    # Find full title_block expression boundaries.
    open_paren = text.rfind("(", 0, start + 1)
    if open_paren < 0:
        return False
    end = _find_matching_paren(text, open_paren)
    if end < 0:
        return False

    block = text[open_paren : end + 1]

    # Rewrite the full title_block in a canonical multi-line format to satisfy KiCad's parser.
    title = _extract_field(block, "title") or ""
    date = _extract_field(block, "date") or ""
    company = _extract_field(block, "company") or ""
    comments = _extract_comments(block)
    new_block = _canonical_title_block(title=title, date=date, rev=rev, company=company, comments=comments).rstrip("\n")

    if new_block == block:
        return False

    new_text = text[:open_paren] + new_block + text[end + 1 :]
    path.write_text(new_text, encoding="utf-8")
    return True
