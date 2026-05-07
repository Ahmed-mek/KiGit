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
        # Insert a minimal title_block after the first line (usually `(kicad_sch ...)`)
        nl = text.find("\n")
        insert_at = nl + 1 if nl >= 0 else len(text)
        block = f'  (title_block (rev "{rev}"))\n'
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

    # Replace existing (rev "...") if present, else insert one right after title_block.
    import re

    if re.search(r'\(\s*rev\s+"[^"]*"\s*\)', block):
        new_block = re.sub(r'\(\s*rev\s+"[^"]*"\s*\)', f'(rev "{rev}")', block, count=1)
    else:
        # Insert after "(title_block"
        new_block = re.sub(r"\(title_block\b", f'(title_block (rev "{rev}")', block, count=1)

    if new_block == block:
        return False

    new_text = text[:open_paren] + new_block + text[end + 1 :]
    path.write_text(new_text, encoding="utf-8")
    return True

