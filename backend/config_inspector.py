#!/usr/bin/env python3
"""
Parses backend/config.py's own source file into a grouped, explained view
for the admin panel's Configuration section - every tunable constant, its
resolved value, and its file comment, extracted mechanically so it never drifts from the file.
"""

import ast
import io
import re
import tokenize

# Raw config.py section name -> display group. Order here is NOT the
# display order - see DISPLAY_GROUP_ORDER below for that.
_SECTION_TO_GROUP = {
    'COMPOSITE_INDEX': 'Composite Index',
    'GEMS': 'Hidden Gems',
    'MONEYBALL': 'Moneyball',
    'CONTRACT_URGENCY': 'Moneyball',  # contract_opportunity_breakdown is moneyball's own contract-weighted component
    'MARKET_VALUE_HEURISTIC': 'Market Value',
    'GBM_HYPERPARAMS': 'Market Value',  # train_mv_models' own hyperparameters - still Market Value, just a later section in the file
    'SQUAD_PROFILE': 'Squad Profiling',
    'PLAYER_RISK': 'Squad Profiling',  # split further per-constant below - only the two sell-high thresholds move to Sell-High Risk
    'SELL_HIGH_ML': 'Sell-High Risk',
    'IMPACT_SCORE': 'Impact Score',
    'STYLE_CLUSTERING': 'Style Clustering',
}

# Per-constant overrides on top of _SECTION_TO_GROUP, for names whose
# natural home differs from the rest of their raw section - the sell-high
# pair belongs alongside ml.sell_high_risk's own thresholds.
_CONSTANT_GROUP_OVERRIDES = {
    'RISK_SELL_HIGH_DETERIORATION_PROB_THRESHOLD': 'Sell-High Risk',
    'RISK_SELL_HIGH_PEAK_RATIO': 'Sell-High Risk',
}

# Every area the admin panel shows, in display order - "Similarity" has
# zero tunable constants currently but is kept as an explicit empty
# section rather than silently omitted.
DISPLAY_GROUP_ORDER = [
    'Composite Index', 'Similarity', 'Hidden Gems', 'Moneyball', 'Market Value',
    'Sell-High Risk', 'Style Clustering', 'Squad Profiling', 'Impact Score',
]

_DIVIDER_RE = re.compile(r'=+')


def _jsonify(value):
    """Recursively coerce a live config value into something JSON-safe.
    `range` shows as its resolved list; tuples become lists; dicts/lists
    recurse so nested structures round-trip correctly."""
    if isinstance(value, range):
        return list(value)
    if isinstance(value, dict):
        return {str(k): _jsonify(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonify(v) for v in value]
    return value


def _find_sections(comments_by_line):
    """Every `# ====...====` / `# TITLE (...)` / `# ====...====` triple, as
    (title, description, header_end_line). `title` is the header's first
    token; `description` is the rest, joined across wrapped lines."""
    divider_lines = sorted(
        ln for ln, text in comments_by_line.items() if _DIVIDER_RE.fullmatch(text.strip())
    )
    sections = []
    i = 0
    while i + 1 < len(divider_lines):
        open_ln, close_candidates = divider_lines[i], divider_lines[i + 1:]
        # The header text is every comment line strictly between this
        # divider and the NEXT divider line.
        next_divider = close_candidates[0]
        header_lines = [
            comments_by_line[ln] for ln in range(open_ln + 1, next_divider)
            if ln in comments_by_line
        ]
        if not header_lines:
            i += 1
            continue
        full_header = ' '.join(header_lines)
        title = re.split(r'[\s(]', full_header, maxsplit=1)[0]
        description = full_header[len(title):].strip()
        if description.startswith('('):
            description = description.rstrip(')').lstrip('(').strip()
        sections.append({'title': title, 'description': description, 'header_end_line': next_divider})
        i += 2  # skip past this section's closing divider to the next section's opening one
    return sections


def _section_for_line(sections, lineno):
    """Which section (by header_end_line ordering) a given assignment's
    line falls under - the LAST section whose header ends at or before
    this line."""
    best = None
    for s in sections:
        if s['header_end_line'] <= lineno:
            best = s
        else:
            break
    return best['title'] if best else None


def _explanation_for(comments_by_line, code_lines, start_lineno, end_lineno):
    """A constant's explanation: a contiguous block of comment-only lines
    immediately above its assignment, plus its own inline trailing comment
    - concatenated block-first, then inline. None if it has neither."""
    inline = comments_by_line.get(end_lineno)
    block = []
    ln = start_lineno - 1
    while ln in comments_by_line and ln not in code_lines:
        text = comments_by_line[ln]
        if _DIVIDER_RE.fullmatch(text.strip()):
            break
        block.append(text)
        ln -= 1
    block.reverse()
    parts = []
    if block:
        parts.append(' '.join(block))
    if inline:
        parts.append(inline)
    return ' '.join(parts) if parts else None


def get_config_groups(config_module):
    """The full grouped, explained view of config_module's tunable
    constants - a list of {group, entries: [...]} dicts, in
    DISPLAY_GROUP_ORDER. Built fresh from the file on every call, never cached."""
    with open(config_module.__file__) as f:
        source = f.read()
    tree = ast.parse(source)

    comments_by_line = {}
    code_lines = set()
    _NON_CODE_TOKENS = (
        tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT,
        tokenize.ENCODING, tokenize.ENDMARKER,
    )
    for tok in tokenize.generate_tokens(io.StringIO(source).readline):
        if tok.type == tokenize.COMMENT:
            comments_by_line[tok.start[0]] = tok.string.lstrip('#').strip()
        elif tok.type not in _NON_CODE_TOKENS and tok.string.strip():
            code_lines.add(tok.start[0])

    sections = _find_sections(comments_by_line)

    groups = {g: [] for g in DISPLAY_GROUP_ORDER}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
            continue
        name = node.targets[0].id
        if not name.isupper() or not hasattr(config_module, name):
            continue

        lineno = node.lineno
        end_lineno = getattr(node, 'end_lineno', lineno)
        section = _section_for_line(sections, lineno)
        group = _CONSTANT_GROUP_OVERRIDES.get(name) or _SECTION_TO_GROUP.get(section)
        if group is None:
            continue  # a top-level UPPERCASE constant outside any known section - shouldn't happen, skip rather than guess

        groups[group].append({
            'name': name,
            'value': _jsonify(getattr(config_module, name)),
            'section': section,
            'explanation': _explanation_for(comments_by_line, code_lines, lineno, end_lineno),
            'line': lineno,
        })

    return [{'group': g, 'entries': groups[g]} for g in DISPLAY_GROUP_ORDER]
