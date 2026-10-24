#!/usr/bin/env python3
"""SpecNovelist helper for spec-driven novel writing in a git repository.

A novel project is organized in layers, from upstream (source of truth) to downstream (derived):

  story/       Human-owned inputs: synopsis.md (seed), brief.md (interview results), style.md
               (the binding writing-style guide).
  kb/          Knowledge base: characters, places, organizations, objects, plot elements, themes,
               world rules, timeline events, researched facts, sources and research questions.
  outline/     The skeleton of the novel in reading order: parts > chapters > scenes.
  abridged/    Derived: condensed novel (all plot + key dialogue), one file per chapter.
  manuscript/  Derived: final prose rendered from abridged/ + kb/ + story/style.md.

Every catalogued item is defined by a Markdown heading that starts with a permanent ID
(``PREFIX-NNN: Title``, e.g. ``# CHR-001: Elena Voss``) and is cross-referenced elsewhere with
wiki-style links (``[[CHR-001]]`` or ``[[CHR-001|Elena]]``).

Sync BASELINES are commits carrying a ``Novel-Sync: <stages>`` trailer (created by ``accept``).
Stages are ``plan`` (story/kb/outline reviewed), ``abridged`` and ``manuscript``. Change impact for
a derived layer is computed by diffing upstream layers between that layer's baseline and the
working tree, then mapping changed IDs to the scenes that reference them.

Standard library only; Python 3.8+.

Usage:
    python specnovel.py init
    python specnovel.py status [--json]
    python specnovel.py check [--require abridged|manuscript] [--json]
    python specnovel.py dag [--mermaid] [--json]
    python specnovel.py next-id CHR
    python specnovel.py trace CHR-001 [--json]
    python specnovel.py delta [--stage plan|abridged|manuscript] [--json]
    python specnovel.py impact --stage abridged|manuscript [--json]
    python specnovel.py accept --stage plan|abridged|manuscript|all -m "message" [--force]
    python specnovel.py index
    python specnovel.py stats [--scenes] [--json]
    python specnovel.py compile [--layer manuscript|abridged] [--format md|docx|epub|odt|pdf]
    python specnovel.py log
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

# ------------------------------------------------------------------ configuration
ID_PATTERN = r"[A-Z][A-Z0-9]*-\d{3,}"
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
ID_HEADING_RE = re.compile(rf"^(?P<id>{ID_PATTERN})\s*[:.\-\u2013\u2014]\s*(?P<title>.+)$")
REF_RE = re.compile(rf"\[\[\s*(?P<id>{ID_PATTERN})\s*(?:\|[^\]]*)?\]\]")
REF_ALIAS_RE = re.compile(rf"\[\[\s*{ID_PATTERN}\s*\|\s*([^\]]+?)\s*\]\]")
REF_BARE_RE = re.compile(rf"\[\[\s*({ID_PATTERN})\s*\]\]")
FENCE_RE = re.compile(r"^\s*(```|~~~)")
COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
FRONT_RE = re.compile(r"\A---\s*\r?\n(.*?)\r?\n---\s*(\r?\n|\Z)", re.S)
TARGET_RE = re.compile(r"target(?:[ _-]?length|[ _-]?words)?\**\s*:\**\s*~?\s*([\d][\d,]*)", re.I)
FIELD_RE = r"^\s*[-*]?\s*\**{name}\**\s*:\**"
WORD_RE = re.compile(r"[^\W_]+(?:['\u2019\-][^\W_]+)*")
BRACKET_PLACEHOLDER_RE = re.compile(r'(?<![!\[\]])\[(?![\[\^ ])([^\]\n]+)\](?!\([^\)]*\)|\[[^\]]*\])')
ANGLE_PLACEHOLDER_RE = re.compile(r'<(?!https?://|[a-zA-Z0-9._%+-]+@|(?:br|hr|div|span|p|b|i|strong|em|sub|sup|table|tr|td|th|ul|ol|li)\b|/)([^>\n]+)>', re.I)
TODO_PLACEHOLDER_RE = re.compile(r'\b(?:TODO|TBD|FIXME):\s*([^\n]+)', re.I)

@dataclass
class PlaceholderOccurrence:
    file: str
    line: int
    section_id: Optional[str]
    context: str

@dataclass
class PlaceholderItem:
    raw: str
    text: str
    kind: str
    occurrences: List[PlaceholderOccurrence] = field(default_factory=list)
    tracked_by: Optional[str] = None

TRAILER = "Novel-Sync"
STORY, KB, OUTLINE, GRAPHICS, ABRIDGED, MANUSCRIPT, BUILD = "story", "kb", "outline", "graphics", "abridged", "manuscript", "build"
PLAN_DIRS = (STORY, KB, OUTLINE)
ALL_DIRS = (STORY, KB, OUTLINE, GRAPHICS, ABRIDGED, MANUSCRIPT)
LAYERS = {"abridged": ABRIDGED, "manuscript": MANUSCRIPT}
SYNOPSIS_FILE, BRIEF_FILE, STYLE_FILE = "story/synopsis.md", "story/brief.md", "story/style.md"
CONFIG_FILE = "story/config.md"
ACKNOWLEDGEMENTS_FILE = "story/acknowledgements.md"
MIN_STYLE_WORDS = 400

SPEC_STAGES = ("brief", "research", "bible", "outline")
ASSET_STAGES = ("graphics",)
DERIVED_STAGES = ("abridged", "manuscript")
STAGES = SPEC_STAGES + ASSET_STAGES + DERIVED_STAGES
STAGE_DIRS: Dict[str, Tuple[str, ...]] = {
    "brief": (SYNOPSIS_FILE, BRIEF_FILE, CONFIG_FILE, ACKNOWLEDGEMENTS_FILE),
    "research": ("kb/research", "kb/sources", "kb/facts"),
    "bible": ("kb/characters", "kb/places", "kb/organizations", "kb/objects",
              "kb/plot", "kb/themes", "kb/world", "kb/timeline", "kb/glossary"),
    "outline": (OUTLINE,),
    "graphics": (GRAPHICS, "kb/graphics"),
    "abridged": (ABRIDGED,),
    "manuscript": (MANUSCRIPT, STYLE_FILE, "story/editorial"),
}
GENERATED = {"kb/INDEX.md"}
KB_FOLDERS = ("characters", "places", "organizations", "objects", "plot", "themes", "world",
              "timeline", "facts", "sources", "research", "graphics", "glossary")

TYPES: "OrderedDict[str, str]" = OrderedDict([
    ("CHR", "character"), ("PLC", "place"), ("ORG", "organization"), ("OBJ", "object"),
    ("PLT", "plot element"), ("THM", "theme"), ("WLD", "world rule"), ("TML", "timeline event"),
    ("FCT", "fact"), ("SRC", "source"), ("RQ", "research question"), ("STY", "style rule"),
    ("GFX", "graphic"),
    ("GLS", "glossary entry"),
    ("EDT", "editorial directive"),
    ("PRT", "part"), ("CHP", "chapter"), ("SCN", "scene"),
])
# KB item types that are expected to be referenced from the outline (unused ones are reported).
STORY_TYPES = {"CHR", "PLC", "ORG", "OBJ", "PLT", "THM", "WLD", "TML", "FCT", "GFX", "GLS"}


class NovelError(Exception):
    pass


# ------------------------------------------------------------------ git
class Git:
    def __init__(self, cwd: Path):
        self.root = cwd
        top = self.run("rev-parse", "--show-toplevel", allow_fail=True)
        if top is None:
            raise NovelError(f"Not inside a git repository: {cwd} (run 'init' first)")
        self.root = Path(top.strip())

    def run(self, *args: str, allow_fail: bool = False) -> Optional[str]:
        try:
            proc = subprocess.run(["git", "-c", "core.quotepath=off", *args], cwd=self.root,
                                  capture_output=True, text=True, encoding="utf-8", errors="replace")
        except FileNotFoundError:
            raise NovelError("git is not installed or not on PATH.")
        if proc.returncode != 0:
            if allow_fail:
                return None
            raise NovelError(f"git {' '.join(args)} failed:\n{proc.stderr.strip()}")
        return proc.stdout

    def lines(self, *args: str) -> List[str]:
        return [l for l in (self.run(*args) or "").splitlines() if l]

    def has_commits(self) -> bool:
        return self.run("rev-parse", "--verify", "--quiet", "HEAD", allow_fail=True) is not None

    def baseline(self, stage: str) -> Optional[str]:
        """Most recent commit reachable from HEAD whose Novel-Sync trailer lists ``stage``."""
        if not self.has_commits():
            return None
        if stage in SPEC_STAGES:
            pattern = rf"({re.escape(stage)}|plan|all)"
        elif stage in DERIVED_STAGES or stage in ASSET_STAGES:
            pattern = rf"({re.escape(stage)}|all)"
        elif stage == "plan":
            pattern = r"(plan|all)"
        elif stage == "all":
            pattern = r"all"
        else:
            pattern = re.escape(stage)
        out = self.lines("log", "-1", "--format=%H", "--extended-regexp",
                         f"--grep=^{TRAILER}:.*{pattern}", "HEAD")
        return out[0].strip() if out else None

    def gfx_baseline(self, gfx_id: str) -> Optional[str]:
        """Most recent commit reachable from HEAD with Novel-GFX-Sync trailer containing ``gfx_id``."""
        if not self.has_commits():
            return None
        pattern = rf"\b{re.escape(gfx_id)}\b"
        out = self.lines("log", "-1", "--format=%H", "--extended-regexp",
                         f"--grep=^Novel-GFX-Sync:.*{pattern}", "HEAD")
        return out[0].strip() if out else None

    def commits_behind(self, sha: Optional[str]) -> int:
        """Number of commits between sha and HEAD."""
        if not sha or not self.has_commits():
            return 0
        out = self.run("rev-list", "--count", f"{sha}..HEAD", allow_fail=True)
        return int(out.strip()) if out and out.strip().isdigit() else 0

    def commit_info(self, sha: Optional[str]) -> Optional[dict]:
        if not sha:
            return None
        short, date, subject = (self.run("log", "-1", "--format=%h%x09%cI%x09%s", sha) or "").rstrip("\n").split("\t", 2)
        return {"sha": sha, "short": short, "date": date, "subject": subject}

    def working_files(self, *folders: str) -> List[str]:
        files = set(self.lines("ls-files", "--cached", "--others", "--exclude-standard", "--", *folders))
        return sorted(f for f in files if (self.root / f).is_file())

    def working_md(self, *folders: str) -> Dict[str, str]:
        return {f: (self.root / f).read_text(encoding="utf-8", errors="replace")
                for f in self.working_files(*folders) if f.endswith(".md")}

    def commit_md(self, sha: Optional[str], *folders: str) -> Dict[str, str]:
        if not sha:
            return {}
        files = [f for f in self.lines("ls-tree", "-r", "--name-only", sha, "--", *folders) if f.endswith(".md")]
        return {f: self.run("show", f"{sha}:{f}") or "" for f in files}

    def changed_since(self, sha: Optional[str], *folders: str) -> List[dict]:
        if not sha:
            return []
        out = []
        for l in self.lines("diff", "--name-status", sha, "--", *folders):
            parts = l.split("\t")
            out.append({"change": parts[0], "file": parts[-1]})
        for f in self.lines("ls-files", "--others", "--exclude-standard", "--", *folders):
            out.append({"change": "??", "file": f})
        return out


# ------------------------------------------------------------------ markdown model
@dataclass
class Section:
    file: str
    line: int
    level: int
    heading: str
    path: str
    id: Optional[str] = None
    title: str = ""
    parent: Optional[str] = None           # nearest enclosing ID section (e.g. a scene's chapter)
    raw: List[Tuple[int, str, bool]] = field(default_factory=list)  # (line no, text, in_fence)
    lines: List[str] = field(default_factory=list)
    refs: List[Tuple[str, int]] = field(default_factory=list)       # ([[ID]], line no)
    digest: str = ""
    key: str = ""

    @property
    def prefix(self) -> str:
        return self.id.split("-", 1)[0] if self.id else ""

    @property
    def location(self) -> str:
        return f"{self.file}:{self.line}"

    @property
    def body(self) -> List[str]:
        return self.lines[1:] if self.heading else self.lines

    @property
    def text(self) -> str:
        return "\n".join(self.lines)

    def has_field(self, name: str) -> bool:
        return re.search(FIELD_RE.format(name=name), self.text, re.I | re.M) is not None

    def field_value(self, *names: str) -> Optional[str]:
        """Extract the text value of a named field (e.g. 'time', 'place', 'pays_off')."""
        for name in names:
            pattern = re.sub(r"[-_\s]+", r"[-_\\s]+", re.escape(name))
            m = re.search(r"^\s*[-*]?\s*\**" + pattern + r"\**\s*:\**\s*(.*)$", self.text, re.I | re.M)
            if m:
                val = COMMENT_RE.sub("", m.group(1)).strip()
                if val:
                    return val
                # Check for subsequent indented list or continuation lines
                lines_after: List[str] = []
                in_field = False
                for line in self.lines:
                    if re.match(r"^\s*[-*]?\s*\**" + pattern + r"\**\s*:\**", line, re.I):
                        in_field = True
                        continue
                    if in_field:
                        clean_line = COMMENT_RE.sub("", line).strip()
                        if re.match(r"^\s+[-*]\s+", line) or (line.startswith(" ") and clean_line):
                            lines_after.append(clean_line)
                        elif re.match(r"^\s*[-*]?\s*\**[a-zA-Z0-9_-]+\**\s*:\**", line) or re.match(r"^#{1,6}\s+", line):
                            break
                if lines_after:
                    return " ".join(lines_after).strip()
        return None

    def ref_ids(self) -> Set[str]:
        return {r for r, _ in self.refs}

    def ref_ids_for_field(self, *names: str) -> Set[str]:
        """Extract all [[ID]] references declared under specific named fields."""
        ids: Set[str] = set()
        val = self.field_value(*names)
        if val:
            for ref_match in REF_RE.finditer(val):
                ids.add(ref_match.group("id"))
        return ids

    def prereq_ids(self) -> Set[str]:
        """Extract prerequisite IDs declared in this section."""
        ids: Set[str] = set()
        in_prereq_block = False
        for line in self.lines:
            m = re.match(r"^\s*[-*]?\s*\**prerequisites?\**\s*:\**\s*(.*)$", line, re.I)
            if not m:
                m = re.match(r"^\s*[-*]?\s*\**requires?\**\s*:\**\s*(.*)$", line, re.I)
            if not m:
                m = re.match(r"^\s*[-*]?\s*\**prereqs?\**\s*:\**\s*(.*)$", line, re.I)

            if m:
                content = m.group(1).strip()
                if content and not content.lower().startswith("none"):
                    for ref_match in REF_RE.finditer(content):
                        ids.add(ref_match.group("id"))
                in_prereq_block = True
                continue

            if in_prereq_block:
                if re.match(r"^\s+[-*]\s+.*$", line):
                    for ref_match in REF_RE.finditer(line):
                        ids.add(ref_match.group("id"))
                else:
                    in_prereq_block = False
        return ids

    @property
    def is_denouement(self) -> bool:
        """Whether this section is designated as the novel's final denouement."""
        return re.search(r"^\s*[-*]?\s*\**(?:denouement|root)\**\s*:\**\s*(?:true|yes|1)\b", self.text, re.I | re.M) is not None


def normalize(lines: Sequence[str]) -> List[str]:
    """Trim trailing whitespace, collapse blank runs, drop leading/trailing blanks."""
    out: List[str] = []
    prev_blank = True
    for raw in lines:
        t = raw.rstrip()
        if not t:
            if not prev_blank:
                out.append("")
            prev_blank = True
        else:
            out.append(t)
            prev_blank = False
    while out and not out[-1]:
        out.pop()
    return out


def parse_markdown(text: str, rel: str) -> List[Section]:
    """Split Markdown into sections.

    An ID section (heading ``ID: title``) absorbs deeper non-ID sub-headings, but ends at the next
    heading of the same or higher level, or at any other ID heading (so a chapter's own section
    stops where its first scene begins). Headings inside code fences are ignored.
    """
    sections: List[Section] = []
    path_stack: Dict[int, str] = {}
    id_stack: List[Tuple[int, str]] = []
    in_fence = False
    cur = Section(rel, 1, 0, "", "(preamble)", title="(preamble)")
    for i, line in enumerate(text.splitlines(), 1):
        if FENCE_RE.match(line):
            in_fence = not in_fence
            cur.raw.append((i, line, True))
            continue
        m = None if in_fence else HEADING_RE.match(line)
        if not m:
            cur.raw.append((i, line, in_fence))
            continue
        level, htext = len(m.group(1)), m.group(2).strip()
        rm = ID_HEADING_RE.match(htext)
        if cur.id and level > cur.level and not rm:
            cur.raw.append((i, line, False))
            continue
        sections.append(cur)
        for k in [k for k in path_stack if k >= level]:
            del path_stack[k]
        path_stack[level] = htext
        while id_stack and id_stack[-1][0] >= level:
            id_stack.pop()
        cur = Section(rel, i, level, line, " > ".join(path_stack[k] for k in sorted(path_stack)),
                      id=rm.group("id") if rm else None,
                      title=(rm.group("title") if rm else htext).strip(),
                      parent=id_stack[-1][1] if id_stack else None)
        if rm:
            id_stack.append((level, cur.id))
    sections.append(cur)

    result = []
    for s in sections:
        s.lines = normalize(([s.heading] if s.heading else []) + [t for _, t, _ in s.raw])
        if not s.lines:
            continue
        s.refs = [(m.group("id"), n) for n, t, fenced in s.raw if not fenced for m in REF_RE.finditer(t)]
        s.digest = hashlib.sha256("\n".join(s.lines).encode("utf-8")).hexdigest()
        result.append(s)
    return result


@dataclass
class Model:
    defs: "OrderedDict[str, Section]" = field(default_factory=OrderedDict)
    contexts: "OrderedDict[str, Section]" = field(default_factory=OrderedDict)
    duplicates: List[dict] = field(default_factory=list)

    def sections(self) -> List[Section]:
        return list(self.defs.values()) + list(self.contexts.values())

    def of_type(self, prefix: str) -> List[Section]:
        return [s for s in self.defs.values() if s.prefix == prefix]


def build_model(sources: Dict[str, str]) -> Model:
    model = Model()
    for rel in sorted(sources):
        if rel in GENERATED:
            continue
        if rel.startswith("story/scenarios/") or rel.startswith("story/takes/") or "/takes/" in rel or ".take-" in rel:
            continue
        for s in parse_markdown(sources[rel], rel):
            if s.id:
                if s.id in model.defs:
                    model.duplicates.append({"id": s.id, "first": model.defs[s.id].location, "second": s.location})
                    continue
                s.key = s.id
                model.defs[s.id] = s
            else:
                key = f"{rel}::{s.path}"
                n = 2
                while key in model.contexts:
                    key = f"{rel}::{s.path}#{n}"
                    n += 1
                s.key = key
                model.contexts[key] = s
    return model


@dataclass
class Outline:
    parts: List[str] = field(default_factory=list)
    chapters: List[str] = field(default_factory=list)
    scenes: List[str] = field(default_factory=list)
    chapter_of: Dict[str, str] = field(default_factory=dict)
    part_of: Dict[str, Optional[str]] = field(default_factory=dict)
    by_chapter: "OrderedDict[str, List[str]]" = field(default_factory=OrderedDict)
    problems: List[str] = field(default_factory=list)


def outline_of(model: Model) -> Outline:
    o = Outline()
    for sid, s in model.defs.items():
        in_outline = s.file.startswith(OUTLINE + "/")
        if s.prefix in ("PRT", "CHP", "SCN") and not in_outline:
            o.problems.append(f"{sid} is defined outside outline/ ({s.location})")
            continue
        if not in_outline:
            continue
        if s.prefix == "PRT":
            o.parts.append(sid)
        elif s.prefix == "CHP":
            o.chapters.append(sid)
            o.by_chapter[sid] = []
            o.part_of[sid] = s.parent if s.parent and s.parent.startswith("PRT-") else None
        elif s.prefix == "SCN":
            if s.parent and s.parent.startswith("CHP-"):
                o.scenes.append(sid)
                o.chapter_of[sid] = s.parent
                o.by_chapter[s.parent].append(sid)
            else:
                o.problems.append(f"scene {sid} is not nested under a chapter heading ({s.location})")
    return o


@dataclass
class Derived:
    model: Model
    scenes: "OrderedDict[str, Section]" = field(default_factory=OrderedDict)
    chapters: "OrderedDict[str, Section]" = field(default_factory=OrderedDict)
    chapter_of: Dict[str, Optional[str]] = field(default_factory=dict)


def derived_of(model: Model) -> Derived:
    d = Derived(model)
    for sid, s in model.defs.items():
        if s.prefix == "SCN":
            d.scenes[sid] = s
            d.chapter_of[sid] = s.parent if s.parent and s.parent.startswith("CHP-") else None
        elif s.prefix == "CHP":
            d.chapters[sid] = s
    return d


def ancestors(model: Model, sid: str) -> List[Section]:
    out, cur = [], model.defs.get(sid)
    while cur is not None:
        out.append(cur)
        cur = model.defs.get(cur.parent) if cur.parent else None
    return out


def word_count(lines: Sequence[str]) -> int:
    text = COMMENT_RE.sub("", "\n".join(l for l in lines if not HEADING_RE.match(l)))
    text = REF_ALIAS_RE.sub(r"\1", text)
    return len(WORD_RE.findall(text))


def target_words(section: Optional[Section]) -> int:
    if section is None:
        return 0
    m = TARGET_RE.search(section.text)
    return int(m.group(1).replace(",", "")) if m else 0


def front_matter(text: str) -> Dict[str, str]:
    m = FRONT_RE.match(text)
    out: Dict[str, str] = {}
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                out[k.strip().lower()] = v.strip().strip("\"'")
    return out


def parse_config_markdown(text: str) -> dict:
    """Parse Markdown-based project configuration (story/config.md)."""
    field_re = re.compile(r"^\s*[-*]\s+\*\*([A-Za-z0-9_\s-]+):\*\*\s*(.*)$")
    list_item_re = re.compile(r"^\s*[-*]\s+([^*].*)$")

    def clean_val(v_str: str):
        v_str = v_str.strip()
        if (v_str.startswith('"') and v_str.endswith('"')) or (v_str.startswith("'") and v_str.endswith("'")):
            v_str = v_str[1:-1].strip()
        v_lower = v_str.lower()
        if v_lower in ("true", "yes"):
            return True
        if v_lower in ("false", "no"):
            return False
        if v_lower in ("null", "none", "~", ""):
            return None
        if re.match(r"^-?\d+$", v_str):
            return int(v_str)
        return v_str

    raw: dict = {}
    current_sec: Optional[str] = None
    current_subsec: Optional[str] = None
    current_list_key: Optional[str] = None

    for line in text.splitlines():
        line_str = line.strip()
        if not line_str or line_str.startswith("<!--"):
            continue

        if line_str.startswith("# "):
            current_sec = "top"
            current_subsec = None
            current_list_key = None
            continue
        elif line_str.startswith("## "):
            sec_title = line_str[3:].strip().lower().replace(" ", "_").replace("-", "_")
            current_sec = sec_title
            current_subsec = None
            current_list_key = None
            if current_sec not in raw:
                raw[current_sec] = {} if current_sec != "contributors" else []
            continue
        elif line_str.startswith("### "):
            subsec_title = line_str[4:].strip()
            current_subsec = subsec_title
            current_list_key = None
            if current_sec == "locales":
                if not isinstance(raw.get("locales"), dict):
                    raw["locales"] = {}
                raw["locales"][current_subsec] = {}
            elif current_sec == "contributors":
                if not isinstance(raw.get("contributors"), list):
                    raw["contributors"] = []
                raw["contributors"].append({"name": subsec_title})
            continue

        m = field_re.match(line)
        if m:
            k = m.group(1).strip().lower().replace(" ", "_").replace("-", "_")
            v_str = m.group(2).strip()
            v = clean_val(v_str)

            if k in ("targets", "target_languages"):
                current_list_key = k
                if v is None:
                    v = []
                elif isinstance(v, str):
                    v = [x.strip() for x in v.split(",") if x.strip()]
            else:
                current_list_key = None

            if current_sec == "top" or current_sec is None:
                raw[k] = v
            elif current_sec == "locales" and current_subsec:
                raw["locales"][current_subsec][k] = v
            elif current_sec == "contributors" and isinstance(raw.get("contributors"), list) and raw["contributors"]:
                raw["contributors"][-1][k] = v
            elif isinstance(raw.get(current_sec), dict):
                raw[current_sec][k] = v
            continue

        lm = list_item_re.match(line)
        if lm:
            item_val = lm.group(1).strip()
            if (cleaned := clean_val(item_val)) is not None:
                item_val = str(cleaned) if not isinstance(cleaned, (int, float, bool)) else cleaned
            if current_sec == "languages" and current_list_key in ("targets", "target_languages"):
                if isinstance(raw.get("languages", {}).get(current_list_key), list):
                    raw["languages"][current_list_key].append(item_val)
            elif current_sec == "contributors":
                if isinstance(raw.get("contributors"), list):
                    raw["contributors"].append({"name": item_val})

    return raw


CONFIG_ALLOWED_TOP_KEYS = {
    "schema_version", "project", "author", "languages",
    "front_matter", "back_matter", "compilation", "contributors", "publication",
    "budget", "locales", "authoring"
}

CONFIG_ALLOWED_PROJECT_KEYS = {
    "title", "subtitle", "edition", "copyright_year", "license", "working_title", "genre"
}
CONFIG_ALLOWED_AUTHOR_KEYS = {
    "name", "legal_name", "email", "url"
}
CONFIG_ALLOWED_LANGUAGES_KEYS = {
    "primary", "targets", "target_languages"
}
CONFIG_ALLOWED_FRONT_KEYS = {
    "foreword", "foreword_file", "dedication", "epigraph", "preface"
}
CONFIG_ALLOWED_BACK_KEYS = {
    "include_glossary", "include_bibliography", "historical_note", "historical_note_file",
    "afterword", "acknowledgments", "acknowledgements", "acknowledgments_file", "acknowledgements_file"
}
CONFIG_ALLOWED_COMPILATION_KEYS = {
    "include_glossary", "include_bibliography", "foreword", "foreword_file",
    "historical_note", "historical_note_file"
}
CONFIG_ALLOWED_BUDGET_KEYS = {
    "target_words", "tolerance_pct", "expansion_factors"
}
CONFIG_ALLOWED_PUBLICATION_KEYS = {
    "publisher", "imprint", "isbn"
}
CONFIG_ALLOWED_AUTHORING_KEYS = {
    "harvest_mode"
}


@dataclass
class ProjectConfig:
    raw: dict = field(default_factory=dict)
    schema_version: str = "1.0"
    title: str = "Untitled Novel"
    subtitle: str = ""
    edition: str = "1.0.0"
    copyright_year: Optional[int] = None
    license: str = "All rights reserved"
    author_name: str = ""
    author_legal_name: str = ""
    author_email: str = ""
    author_url: str = ""
    primary_language: str = "en-US"
    target_languages: List[str] = field(default_factory=lambda: ["en-US"])
    foreword_path: Optional[str] = None
    dedication: Optional[str] = None
    epigraph: Optional[dict] = None
    include_glossary: bool = True
    include_bibliography: bool = True
    historical_note_path: Optional[str] = None
    afterword_path: Optional[str] = None
    acknowledgments_path: Optional[str] = None
    contributors: List[dict] = field(default_factory=list)
    publication: dict = field(default_factory=dict)
    budget: dict = field(default_factory=dict)
    locales: dict = field(default_factory=dict)
    harvest_mode: str = "batch"
    errors: List[str] = field(default_factory=list)


def validate_and_load_config(raw: dict) -> ProjectConfig:
    errors: List[str] = []
    if not isinstance(raw, dict):
        return ProjectConfig(errors=["configuration root must be a mapping/dictionary"])

    # Strict check: unknown top-level keys
    for k in raw:
        if k not in CONFIG_ALLOWED_TOP_KEYS:
            errors.append(f"unknown top-level configuration key '{k}'")

    # Required fields
    schema_version = str(raw.get("schema_version") or "")
    if not schema_version:
        errors.append("missing required field: 'schema_version'")

    proj = raw.get("project")
    title, subtitle, edition, copyright_year, lic = "Untitled Novel", "", "1.0.0", None, "All rights reserved"
    if not isinstance(proj, dict):
        errors.append("missing required section: 'project' (must be a dictionary)")
    else:
        for k in proj:
            if k not in CONFIG_ALLOWED_PROJECT_KEYS:
                errors.append(f"unknown key in 'project': '{k}'")
        title = str(proj.get("title") or "")
        if not title:
            errors.append("missing required field: 'project.title'")
        subtitle = str(proj.get("subtitle") or "")
        edition = str(proj.get("edition") or "1.0.0")
        copyright_year = proj.get("copyright_year")
        lic = str(proj.get("license") or "All rights reserved")

    auth = raw.get("author")
    author_name, legal_name, email, url = "", "", "", ""
    if not isinstance(auth, dict):
        errors.append("missing required section: 'author' (must be a dictionary)")
    else:
        for k in auth:
            if k not in CONFIG_ALLOWED_AUTHOR_KEYS:
                errors.append(f"unknown key in 'author': '{k}'")
        author_name = str(auth.get("name") or "")
        if not author_name:
            errors.append("missing required field: 'author.name'")
        legal_name = str(auth.get("legal_name") or "")
        email = str(auth.get("email") or "")
        url = str(auth.get("url") or "")

    langs = raw.get("languages")
    primary_lang = "en-US"
    target_langs = ["en-US"]
    if not isinstance(langs, dict):
        errors.append("missing required section: 'languages' (must be a dictionary)")
    else:
        for k in langs:
            if k not in CONFIG_ALLOWED_LANGUAGES_KEYS:
                errors.append(f"unknown key in 'languages': '{k}'")
        primary_lang = str(langs.get("primary") or "")
        if not primary_lang:
            errors.append("missing required field: 'languages.primary'")
        raw_targets = langs.get("targets") if "targets" in langs else langs.get("target_languages")
        if not isinstance(raw_targets, list) or not raw_targets:
            errors.append("missing or empty required field: 'languages.targets' (must be a non-empty list of locale codes)")
        else:
            target_langs = [str(t) for t in raw_targets]
            if primary_lang and primary_lang not in target_langs:
                errors.append(f"primary language '{primary_lang}' must be included in 'languages.targets' {target_langs}")

    fm = raw.get("front_matter") or {}
    foreword_path = None
    dedication = None
    epigraph = None
    if isinstance(fm, dict):
        foreword_val = fm.get("foreword") if "foreword" in fm else fm.get("foreword_file")
        if foreword_val is not None:
            foreword_path = str(foreword_val)
        dedication = fm.get("dedication")
        epigraph = fm.get("epigraph")
        for k in fm:
            if k not in CONFIG_ALLOWED_FRONT_KEYS:
                errors.append(f"unknown key in 'front_matter': '{k}'")
    elif fm is not None:
        errors.append("'front_matter' must be a dictionary")

    bm = raw.get("back_matter") or {}
    include_glossary = True
    include_bibliography = True
    historical_note_path = None
    afterword_path = None
    acknowledgments_path = None
    if isinstance(bm, dict):
        if "include_glossary" in bm:
            if not isinstance(bm["include_glossary"], bool):
                errors.append("'back_matter.include_glossary' must be a boolean (true/false)")
            else:
                include_glossary = bm["include_glossary"]
        if "include_bibliography" in bm:
            if not isinstance(bm["include_bibliography"], bool):
                errors.append("'back_matter.include_bibliography' must be a boolean (true/false)")
            else:
                include_bibliography = bm["include_bibliography"]
        hn_val = bm.get("historical_note") if "historical_note" in bm else bm.get("historical_note_file")
        if hn_val:
            historical_note_path = str(hn_val)
        if bm.get("afterword"):
            afterword_path = str(bm["afterword"])
        ack_val = bm.get("acknowledgements") or bm.get("acknowledgments") or bm.get("acknowledgements_file") or bm.get("acknowledgments_file")
        if ack_val:
            acknowledgments_path = str(ack_val)
        for k in bm:
            if k not in CONFIG_ALLOWED_BACK_KEYS:
                errors.append(f"unknown key in 'back_matter': '{k}'")
    elif bm is not None:
        errors.append("'back_matter' must be a dictionary")

    # If compilation section was supplied (support both formats)
    comp = raw.get("compilation")
    if isinstance(comp, dict):
        for k in comp:
            if k not in CONFIG_ALLOWED_COMPILATION_KEYS:
                errors.append(f"unknown key in 'compilation': '{k}'")
        if "include_glossary" in comp:
            if not isinstance(comp["include_glossary"], bool):
                errors.append("'compilation.include_glossary' must be a boolean (true/false)")
            else:
                include_glossary = comp["include_glossary"]
        if "include_bibliography" in comp:
            if not isinstance(comp["include_bibliography"], bool):
                errors.append("'compilation.include_bibliography' must be a boolean (true/false)")
            else:
                include_bibliography = comp["include_bibliography"]
        cfwd = comp.get("foreword_file") if "foreword_file" in comp else comp.get("foreword")
        if cfwd:
            foreword_path = str(cfwd)
        chn = comp.get("historical_note_file") if "historical_note_file" in comp else comp.get("historical_note")
        if chn:
            historical_note_path = str(chn)

    contributors = raw.get("contributors") or []
    if not isinstance(contributors, list):
        errors.append("'contributors' must be a list")

    publication = raw.get("publication") or {}
    if isinstance(publication, dict):
        for k in publication:
            if k not in CONFIG_ALLOWED_PUBLICATION_KEYS:
                errors.append(f"unknown key in 'publication': '{k}'")
    elif publication is not None:
        errors.append("'publication' must be a dictionary")

    budget = raw.get("budget") or {}
    if isinstance(budget, dict):
        for k in budget:
            if k not in CONFIG_ALLOWED_BUDGET_KEYS:
                errors.append(f"unknown key in 'budget': '{k}'")
    elif budget is not None:
        errors.append("'budget' must be a dictionary")

    locales = raw.get("locales") or {}

    authoring = raw.get("authoring") or {}
    harvest_mode = "batch"
    if isinstance(authoring, dict):
        for k in authoring:
            if k not in CONFIG_ALLOWED_AUTHORING_KEYS:
                errors.append(f"unknown key in 'authoring': '{k}'")
        if "harvest_mode" in authoring:
            harvest_mode = str(authoring["harvest_mode"]).lower()
            if harvest_mode not in ("batch", "interactive"):
                errors.append(f"invalid 'authoring.harvest_mode': '{harvest_mode}', must be 'batch' or 'interactive'")
    elif authoring is not None:
        errors.append("'authoring' must be a dictionary")

    return ProjectConfig(
        raw=raw,
        schema_version=schema_version or "1.0",
        title=title,
        subtitle=subtitle,
        edition=edition,
        copyright_year=copyright_year,
        license=lic,
        author_name=author_name,
        author_legal_name=legal_name,
        author_email=email,
        author_url=url,
        primary_language=primary_lang or "en-US",
        target_languages=target_langs,
        foreword_path=foreword_path,
        dedication=dedication,
        epigraph=epigraph,
        include_glossary=include_glossary,
        include_bibliography=include_bibliography,
        historical_note_path=historical_note_path,
        afterword_path=afterword_path,
        acknowledgments_path=acknowledgments_path,
        contributors=contributors if isinstance(contributors, list) else [],
        publication=publication if isinstance(publication, dict) else {},
        budget=budget if isinstance(budget, dict) else {},
        locales=locales if isinstance(locales, dict) else {},
        harvest_mode=harvest_mode,
        errors=errors,
    )


def load_project_config(git: Git) -> ProjectConfig:
    md_path = git.root / CONFIG_FILE
    yaml_path = git.root / "story/config.yaml"
    json_path = git.root / "story/config.json"
    if md_path.is_file():
        try:
            raw = parse_config_markdown(md_path.read_text(encoding="utf-8", errors="replace"))
            return validate_and_load_config(raw)
        except Exception as e:
            return ProjectConfig(errors=[f"failed to parse {CONFIG_FILE}: {e}"])
    elif yaml_path.is_file():
        return ProjectConfig(errors=[
            f"legacy configuration file '{yaml_path.name}' detected; "
            f"SpecNovelist has unified on Markdown. Please migrate to '{CONFIG_FILE}'"
        ])
    elif json_path.is_file():
        return ProjectConfig(errors=[
            f"legacy configuration file '{json_path.name}' detected; "
            f"SpecNovelist has unified on Markdown. Please migrate to '{CONFIG_FILE}'"
        ])
    return ProjectConfig(errors=[f"missing project configuration file: {CONFIG_FILE}"])


# ------------------------------------------------------------------ project state
@dataclass
class Project:
    git: Git
    plan: Model
    outline: Outline
    layers: Dict[str, Derived]
    config: ProjectConfig = field(default_factory=ProjectConfig)
    manuscript_locales: Dict[str, Derived] = field(default_factory=dict)


def load_project(git: Git) -> Project:
    plan = build_model(git.working_md(*PLAN_DIRS))
    cfg = load_project_config(git)

    abridged_layer = derived_of(build_model(git.working_md(ABRIDGED)))

    manuscript_locales: Dict[str, Derived] = {}
    for loc in cfg.target_languages:
        loc_dir = f"{MANUSCRIPT}/{loc}"
        if (git.root / MANUSCRIPT / loc).is_dir():
            manuscript_locales[loc] = derived_of(build_model(git.working_md(loc_dir)))
        else:
            manuscript_locales[loc] = derived_of(Model())

    flat_manuscript = derived_of(build_model(git.working_md(MANUSCRIPT)))
    primary_ms = manuscript_locales.get(cfg.primary_language)
    if not primary_ms or not primary_ms.scenes:
        if flat_manuscript.scenes:
            primary_ms = flat_manuscript
            manuscript_locales[cfg.primary_language] = flat_manuscript

    layers = {
        "abridged": abridged_layer,
        "manuscript": primary_ms or derived_of(Model()),
    }
    return Project(git, plan, outline_of(plan), layers, cfg, manuscript_locales)


def project_title(git: Git) -> str:
    cfg = load_project_config(git)
    if cfg.title and not cfg.title.startswith("<") and cfg.title != "Untitled Novel":
        return cfg.title
    for rel in (BRIEF_FILE, SYNOPSIS_FILE):
        p = git.root / rel
        if p.is_file():
            t = front_matter(p.read_text(encoding="utf-8", errors="replace")).get("title")
            if t and not t.startswith("<"):
                return t
    return "Untitled Novel"


# ------------------------------------------------------------------ story causality DAG
@dataclass
class StoryDAG:
    nodes: Set[str] = field(default_factory=set)
    edges: Dict[str, Set[str]] = field(default_factory=dict)         # u -> {v}: u is prerequisite for v
    reverse_edges: Dict[str, Set[str]] = field(default_factory=dict) # v -> {u}: v requires u
    root: Optional[str] = None
    positions: Dict[str, int] = field(default_factory=dict)          # ID -> 1-based scene index where it first appears


def build_story_dag(p: Project) -> StoryDAG:
    dag = StoryDAG()
    plan, o = p.plan, p.outline
    if not o.scenes:
        return dag

    # 1. Compute positions: scene index (1-based) where each ID first appears in reading order
    for idx, sid in enumerate(o.scenes, 1):
        dag.positions[sid] = idx
        # Map all referenced items in the scene section and its ancestors
        for a in ancestors(plan, sid):
            for rid in a.ref_ids():
                if rid not in dag.positions:
                    dag.positions[rid] = idx

    # 2. Identify designated root denouement
    explicit_root = None
    # Check for explicit denouement pointer (e.g. - **Denouement:** [[SCN-...]])
    for sec in plan.sections():
        m = re.search(r"^\s*[-*]?\s*\**(?:denouement|root)\**\s*:\**\s*(?:\[\[\s*)?(?P<id>[A-Z][A-Z0-9]*-\d{3,})", sec.text, re.I | re.M)
        if m:
            explicit_root = m.group("id")
            break
    # Check for section marked with - **Denouement:** true
    if not explicit_root:
        for sec in plan.sections():
            if sec.id and sec.is_denouement and (sec.id in o.scenes or sec.prefix == "PLT"):
                explicit_root = sec.id
                break

    dag.root = explicit_root if explicit_root and explicit_root in plan.defs else (o.scenes[-1] if o.scenes else None)

    # 3. Collect all nodes that belong to the story
    # All scenes in outline are story elements
    for sid in o.scenes:
        dag.nodes.add(sid)

    # All plot elements appearing in the outline
    for sec in plan.of_type("PLT"):
        if sec.id in dag.positions:
            dag.nodes.add(sec.id)

    # Any story element in the plan that explicitly declares prerequisites or is referenced as a prerequisite
    for sec in plan.defs.values():
        if sec.prefix not in ("SCN", "CHP", "PRT", "PLT"):
            continue
        prereqs = sec.prereq_ids()
        if prereqs:
            dag.nodes.add(sec.id)
            for req in prereqs:
                dag.nodes.add(req)

    # 4. Build edges: u -> v means u is prerequisite for v
    for node in list(dag.nodes):
        sec = plan.defs.get(node)
        if not sec:
            continue
        for req in sec.prereq_ids():
            dag.nodes.add(req)
            dag.edges.setdefault(req, set()).add(node)
            dag.reverse_edges.setdefault(node, set()).add(req)

    # 5. Plant -> Payoff edges (Chekhov's gun setups form causal prerequisites for payoffs)
    for sid in o.scenes:
        sec = plan.defs.get(sid)
        if not sec:
            continue
        pays_off = sec.ref_ids_for_field("pays_off", "pays-off", "paysoff", "payoff", "pays")
        for poy_id in pays_off:
            for earlier_sid in o.scenes:
                if earlier_sid == sid:
                    break
                earlier_sec = plan.defs.get(earlier_sid)
                if earlier_sec and poy_id in earlier_sec.ref_ids_for_field("plants", "plant", "setups", "setup"):
                    dag.edges.setdefault(earlier_sid, set()).add(sid)
                    dag.reverse_edges.setdefault(sid, set()).add(earlier_sid)

    return dag


def check_dag_cycles(dag: StoryDAG) -> List[str]:
    """Detect directed cycles in the story causality graph."""
    state: Dict[str, int] = {}  # 0=unvisited, 1=visiting, 2=visited
    cycles: List[str] = []

    def dfs(node: str, path: List[str]):
        state[node] = 1
        path.append(node)
        for neighbor in sorted(dag.edges.get(node, set())):
            if state.get(neighbor, 0) == 1:
                idx = path.index(neighbor)
                cycle = path[idx:] + [neighbor]
                cycles.append(" -> ".join(cycle))
            elif state.get(neighbor, 0) == 0:
                dfs(neighbor, path)
        path.pop()
        state[node] = 2

    for n in sorted(dag.nodes):
        if state.get(n, 0) == 0:
            dfs(n, [])
    return cycles


def check_reading_order_coherence(dag: StoryDAG, outline: Outline) -> List[str]:
    """Verify that every element in the outline is preceded by all its prerequisites."""
    errors: List[str] = []
    for node in sorted(dag.nodes):
        prereqs = dag.reverse_edges.get(node, set())
        node_pos = dag.positions.get(node, float('inf'))
        for p in sorted(prereqs):
            p_pos = dag.positions.get(p, float('inf'))
            if p_pos == float('inf'):
                errors.append(f"reading order violation: prerequisite {p} of {node} never appears in the outline")
            elif node_pos == float('inf'):
                errors.append(f"reading order violation: story element {node} (requires {p}) never appears in the outline")
            elif node.startswith("SCN-") and p.startswith("SCN-"):
                if p_pos >= node_pos:
                    errors.append(
                        f"reading order violation: scene {node} (scene #{int(node_pos)}) requires {p} (scene #{int(p_pos)}), "
                        f"but {p} does not precede {node} in the outline"
                    )
            elif p_pos > node_pos:
                errors.append(
                    f"reading order violation: {node} (first appears in scene #{int(node_pos)}) requires {p} (first appears in scene #{int(p_pos)}), "
                    f"but {p} appears later in reading order"
                )
    return errors


def check_essentiality_to_root(dag: StoryDAG, p: Optional["Project"] = None) -> Tuple[Optional[str], List[str]]:
    """Verify that every element in the story is essential by having a directed path to the root denouement."""
    errors: List[str] = []
    if not dag.root:
        return None, ["no root denouement found (outline is empty)"]
    if dag.root not in dag.nodes:
        return dag.root, [f"designated root denouement {dag.root} does not exist in the story DAG"]

    reachable: Set[str] = set()
    queue = [dag.root]
    reachable.add(dag.root)

    while queue:
        curr = queue.pop(0)
        for pred in dag.reverse_edges.get(curr, set()):
            if pred not in reachable:
                reachable.add(pred)
                queue.append(pred)

    inessential = sorted([n for n in dag.nodes if n not in reachable])
    if p and inessential:
        for n in list(inessential):
            sec = p.plan.defs.get(n)
            if sec:
                func = (sec.field_value("function", "role") or "").strip().lower()
                artistic_functions = {
                    "atmospheric-breather", "thematic-mirror", "comic-relief",
                    "character-reflection", "epistolary-interlude", "pacing-breather",
                    "breather", "thematic-pause", "reflection"
                }
                if func in artistic_functions:
                    chap = p.outline.chapter_of.get(n)
                    chap_scenes = p.outline.by_chapter.get(chap, []) if chap else []
                    if any(s in reachable for s in chap_scenes if s != n) or not reachable:
                        reachable.add(n)
                        inessential.remove(n)

    for n in inessential:
        errors.append(f"inessential element: {n} has no causal path to the root denouement ({dag.root})")
    return dag.root, errors


def check_epistemic_and_setup_payoffs(p: "Project") -> Tuple[List[str], List[str], List[str]]:
    """Validate Chekhov's gun setups/payoffs and epistemic character knowledge integrity."""
    errors: List[str] = []
    warnings: List[str] = []
    infos: List[str] = []
    o = p.outline
    plan = p.plan
    if not o.scenes:
        return errors, warnings, infos

    # 1. Setup & Payoff (Chekhov's Gun)
    planted_map: Dict[str, Tuple[str, int, Section]] = {}
    paid_off_map: Dict[str, List[Tuple[str, int, Section]]] = {}

    # 2. Epistemic Tracking (Knowledge state)
    revealed_map: Dict[str, Tuple[str, int, Set[str]]] = {}
    hidden_from_map: Dict[str, Set[str]] = {}

    for idx, sid in enumerate(o.scenes, 1):
        sec = plan.defs.get(sid)
        if not sec:
            continue

        plants = sec.ref_ids_for_field("plants", "plant", "setups", "setup")
        pays_off = sec.ref_ids_for_field("pays_off", "pays-off", "paysoff", "payoff", "pays")
        reveals = sec.ref_ids_for_field("reveals", "reveal", "revelations")
        learns = sec.ref_ids_for_field("learns", "learn", "learners")
        hidden_from = sec.ref_ids_for_field("hidden_from", "hidden-from", "hidden", "concealed_from")
        cast = sec.ref_ids_for_field("cast", "characters")
        pov = sec.ref_ids_for_field("pov")

        # Track Plants
        for pid in sorted(plants):
            if pid not in planted_map:
                planted_map[pid] = (sid, idx, sec)

        # Track Payoffs
        for poy_id in sorted(pays_off):
            if poy_id not in planted_map:
                errors.append(
                    f"unearned payoff (Chekhov's gun violation): [[{poy_id}]] is paid off in scene {sid} (scene #{idx}), "
                    f"but was never planted in any preceding scene"
                )
            else:
                paid_off_map.setdefault(poy_id, []).append((sid, idx, sec))

        # Track Reveals & Learns
        if reveals:
            effective_learners = learns or pov or cast
            for rid in sorted(reveals):
                if rid not in revealed_map:
                    revealed_map[rid] = (sid, idx, set(effective_learners))
                else:
                    revealed_map[rid][2].update(effective_learners)

                if hidden_from:
                    hidden_from_map.setdefault(rid, set()).update(hidden_from)
                    contradiction = set(effective_learners) & set(hidden_from)
                    if contradiction:
                        errors.append(
                            f"epistemic contradiction in scene {sid}: {', '.join(sorted(contradiction))} is declared as both learning and hidden from [[{rid}]]"
                        )

        # Epistemic violations: characters acting on secrets they don't know
        if hidden_from_map:
            for rid, excluded_chars in hidden_from_map.items():
                if (cast & excluded_chars) or (pov & excluded_chars):
                    if rid in pays_off or rid in sec.prereq_ids():
                        present_excluded = sorted((cast | pov) & excluded_chars)
                        already_learned = False
                        if rid in revealed_map and any(c in revealed_map[rid][2] for c in present_excluded):
                            already_learned = True
                        if not already_learned:
                            errors.append(
                                f"epistemic violation in scene {sid}: character(s) {', '.join(present_excluded)} act on [[{rid}]] while it was declared hidden from them"
                            )

    # Check for Orphan Plants
    for pid, (sid, idx, sec) in sorted(planted_map.items(), key=lambda x: x[1][1]):
        if pid not in paid_off_map:
            errors.append(
                f"orphan plant (Chekhov's gun violation): [[{pid}]] is planted in scene {sid} (scene #{idx}), "
                f"but is never paid off in any downstream scene"
            )
        else:
            first_pay_idx = paid_off_map[pid][0][1]
            gap = first_pay_idx - idx
            total_scenes = len(o.scenes)
            if total_scenes > 8 and gap >= total_scenes * 0.8:
                warnings.append(
                    f"prolonged setup-payoff gap: [[{pid}]] is planted in scene #{idx} ({sid}) and paid off in scene #{first_pay_idx} ({paid_off_map[pid][0][0]}) across {gap} scenes"
                )

    if planted_map and not errors:
        infos.append(f"Chekhov's gun validation passed: {len(planted_map)} setup/payoff pairs verified across outline.")
    if revealed_map and not errors:
        infos.append(f"epistemic validation passed: {len(revealed_map)} narrative reveals verified with coherent character knowledge.")

    return errors, warnings, infos


def run_dag_checks(p: Project) -> Tuple[List[str], List[str], List[str]]:
    """Run all DAG causality, reading order coherence, and denouement essentiality checks."""
    errors: List[str] = []
    warnings: List[str] = []
    infos: List[str] = []

    if not p.outline.scenes:
        return errors, warnings, infos

    dag = build_story_dag(p)

    # 1. Cycle detection (must be a DAG)
    cycles = check_dag_cycles(dag)
    for c in cycles:
        errors.append(f"cycle detected in story causality graph: {c}")

    # 2. Reading order coherence (all prerequisites precede dependents)
    ro_errors = check_reading_order_coherence(dag, p.outline)
    errors += ro_errors

    # 3. Essentiality to root denouement (path to root)
    root, ess_errors = check_essentiality_to_root(dag, p)
    errors += ess_errors

    if not (cycles or ro_errors or ess_errors):
        total_edges = sum(len(v) for v in dag.edges.values())
        infos.append(f"story DAG verified: {len(dag.nodes)} elements, {total_edges} causal edges, root denouement is {root}")

    return errors, warnings, infos


# ------------------------------------------------------------------ placeholders
def scan_placeholders(p: Project, target_path: Optional[str] = None) -> List[PlaceholderItem]:
    git = p.git
    root = git.root

    if target_path:
        tp = (root / target_path).resolve()
        if tp.is_file():
            files = [tp.relative_to(root).as_posix()]
        elif tp.is_dir():
            files = sorted(f.relative_to(root).as_posix() for f in tp.rglob("*.md"))
        else:
            raise NovelError(f"Path not found: {target_path}")
    else:
        files = []
        for d in PLAN_DIRS:
            dp = root / d
            if dp.is_dir():
                for f in dp.rglob("*.md"):
                    rel = f.relative_to(root).as_posix()
                    if rel == "kb/INDEX.md" or rel.startswith("kb/sources/") or rel.startswith("story/scenarios/") or rel.startswith("story/takes/"):
                        continue
                    files.append(rel)
        files.sort()

    items_by_key: Dict[str, PlaceholderItem] = OrderedDict()
    existing_rqs = p.plan.of_type("RQ")

    for rel in files:
        fp = root / rel
        if not fp.is_file():
            continue
        content = fp.read_text(encoding="utf-8", errors="replace")

        in_fence = False
        cur_id = None
        in_placeholder_section = False

        for line_no, raw_line in enumerate(content.splitlines(), 1):
            if FENCE_RE.match(raw_line):
                in_fence = not in_fence
                continue
            if in_fence:
                continue

            clean_line = COMMENT_RE.sub("", raw_line).strip()
            if not clean_line:
                continue

            hm = HEADING_RE.match(raw_line)
            if hm:
                htext = hm.group(2).strip()
                id_m = ID_HEADING_RE.match(htext)
                if id_m:
                    cur_id = id_m.group("id")
                in_placeholder_section = bool(re.search(r"placeholder|research\s*(?:question|need|backlog)", htext, re.I))

            # Skip markdown reference links definitions e.g. [1]: https://...
            if re.match(r"^\s*\[[^\]]+\]:\s*\S+", clean_line):
                continue

            # 1. Bracket placeholders
            for bm in BRACKET_PLACEHOLDER_RE.finditer(clean_line):
                inner = bm.group(1).strip()
                if inner.lower() in {"x", " ", "todo", "tbd"} or inner.isdigit():
                    continue
                is_gfx = bool(re.match(r"^(?:GFX|GRAPHIC)\s*:\s*", inner, re.I))
                clean_text = re.sub(r"^(?:TODO|TBD|FIXME|RESEARCH|PLACEHOLDER|GFX|GRAPHIC)\s*:\s*", "", inner, flags=re.I).strip()
                key = clean_text.lower()
                kind = "gfx" if is_gfx else "bracket"
                if key not in items_by_key:
                    items_by_key[key] = PlaceholderItem(raw=f"[{inner}]", text=clean_text, kind=kind)
                ctx = clean_line[:120]
                items_by_key[key].occurrences.append(PlaceholderOccurrence(rel, line_no, cur_id, ctx))

            # 2. Angle placeholders
            for am in ANGLE_PLACEHOLDER_RE.finditer(clean_line):
                inner = am.group(1).strip()
                if not inner or inner.lower() in {"br", "hr"}:
                    continue
                clean_text = re.sub(r"^(?:e\.g\.|ie\.|todo|tbd)\s*", "", inner, flags=re.I).strip()
                key = clean_text.lower()
                if key not in items_by_key:
                    items_by_key[key] = PlaceholderItem(raw=f"<{inner}>", text=clean_text, kind="angle")
                ctx = clean_line[:120]
                items_by_key[key].occurrences.append(PlaceholderOccurrence(rel, line_no, cur_id, ctx))

            # 3. TODO / TBD placeholders
            if not BRACKET_PLACEHOLDER_RE.search(clean_line):
                for tm in TODO_PLACEHOLDER_RE.finditer(clean_line):
                    inner = tm.group(1).strip()
                    if inner and len(inner) > 2:
                        key = inner.lower()
                        if key not in items_by_key:
                            items_by_key[key] = PlaceholderItem(raw=tm.group(0), text=inner, kind="todo")
                        ctx = clean_line[:120]
                        items_by_key[key].occurrences.append(PlaceholderOccurrence(rel, line_no, cur_id, ctx))

            # 4. List items under a placeholder section
            if in_placeholder_section and re.match(r"^[-*]\s+", clean_line):
                item_content = re.sub(r"^[-*]\s+", "", clean_line).strip()
                if not BRACKET_PLACEHOLDER_RE.search(item_content):
                    key = item_content.lower()
                    if key not in items_by_key:
                        items_by_key[key] = PlaceholderItem(raw=item_content, text=item_content, kind="section_list")
                    ctx = clean_line[:120]
                    items_by_key[key].occurrences.append(PlaceholderOccurrence(rel, line_no, cur_id, ctx))

    for item in items_by_key.values():
        key = item.text.lower()
        sec_ids = {occ.section_id for occ in item.occurrences if occ.section_id}
        for rq in existing_rqs:
            rq_text = rq.text.lower()
            if key in rq_text or (item.raw.lower() in rq_text):
                item.tracked_by = rq.id
                break
            if sec_ids and any(sid in rq.ref_ids() for sid in sec_ids):
                words = [w for w in re.split(r"\W+", key) if len(w) > 3]
                if any(w in rq_text for w in words):
                    item.tracked_by = rq.id
                    break

    return list(items_by_key.values())


# ------------------------------------------------------------------ ai models & acknowledgements
def normalize_model_text(text: str) -> str:
    """Normalize model names and text for robust substring matching."""
    return re.sub(r"[-_.:/]", " ", text).lower()


def model_mentioned_in_text(model: str, raw_text: str, norm_text: Optional[str] = None) -> bool:
    """Verify whether a model is mentioned in the acknowledgements text."""
    if not model or not raw_text:
        return False
    m_lower = model.strip().lower()
    if m_lower in raw_text.lower():
        return True
    if norm_text is None:
        norm_text = normalize_model_text(raw_text)
    norm_m = normalize_model_text(model)
    if norm_m in norm_text:
        return True
    if "/" in model:
        sub = model.split("/")[-1]
        if sub.lower() in raw_text.lower() or normalize_model_text(sub) in norm_text:
            return True
    return False


def get_contributing_ai_models(git: Git, p: Optional["Project"] = None) -> Set[str]:
    """Extract all AI models that have contributed to the novel across git history and specifications."""
    models: Set[str] = set()
    if git.has_commits():
        try:
            lines = git.lines("log", "--format=%(trailers:key=Novel-Model,valueonly=true)", "HEAD")
            for line in lines:
                for part in line.split(","):
                    val = part.strip()
                    if val:
                        models.add(val)
        except Exception:
            pass
        try:
            lines = git.lines("log", "--format=%(trailers:key=AI-Model,valueonly=true)", "HEAD")
            for line in lines:
                for part in line.split(","):
                    val = part.strip()
                    if val:
                        models.add(val)
        except Exception:
            pass
    env_m = os.environ.get("SPECNOVEL_MODEL")
    if env_m:
        for part in env_m.split(","):
            val = part.strip()
            if val:
                models.add(val)
    try:
        cfg_m = git.run("config", "--get", "specnovelist.model", check=False).stdout.strip()
        if cfg_m:
            for part in cfg_m.split(","):
                val = part.strip()
                if val:
                    models.add(val)
    except Exception:
        pass
    if p and p.config:
        for c in p.config.contributors:
            if isinstance(c, dict):
                c_type = (c.get("type") or "").lower()
                c_role = (c.get("role") or "").lower()
                if "ai" in c_type or "model" in c_type or "ai" in c_role or "model" in c_role:
                    if c.get("name"):
                        models.add(str(c["name"]).strip())
        if "ai_models" in p.config.raw:
            aim = p.config.raw["ai_models"]
            if isinstance(aim, list):
                for m in aim:
                    if m: models.add(str(m).strip())
            elif isinstance(aim, dict):
                for m in aim:
                    if m: models.add(str(m).strip())
    return models


# ------------------------------------------------------------------ checks
def run_checks(p: Project, require: Sequence[str] = ()) -> Tuple[List[str], List[str], List[str]]:
    errors: List[str] = []
    warnings: List[str] = []
    infos: List[str] = []
    plan, o = p.plan, p.outline
    root = p.git.root

    # inputs
    if p.config.errors:
        errors += [f"config error: {e}" for e in p.config.errors]
    if p.config.foreword_path and not (root / p.config.foreword_path).is_file():
        errors.append(f"config front_matter.foreword references missing file: '{p.config.foreword_path}'")
    if p.config.historical_note_path and not (root / p.config.historical_note_path).is_file():
        warnings.append(f"config back_matter.historical_note references missing file: '{p.config.historical_note_path}'")
    if not (root / SYNOPSIS_FILE).is_file():
        errors.append(f"missing seed synopsis: {SYNOPSIS_FILE}")

    # mandatory acknowledgements & contributing AI models verification
    ack_path = p.config.acknowledgments_path or ACKNOWLEDGEMENTS_FILE
    ack_file = root / ack_path
    if not ack_file.is_file():
        fallback = root / "story/acknowledgments.md" if "acknowledgements" in ack_path else root / "story/acknowledgements.md"
        if fallback.is_file():
            ack_file = fallback
            ack_path = fallback.relative_to(root).as_posix()
    if not ack_file.is_file():
        errors.append(f"missing mandatory acknowledgements file: '{ack_path}'")
    else:
        ack_text = ack_file.read_text(encoding="utf-8", errors="replace")
        if not ack_text.strip():
            errors.append(f"mandatory acknowledgements file '{ack_path}' is empty")
        else:
            contributing_models = get_contributing_ai_models(p.git, p)
            for req in require:
                if req.startswith("model:"):
                    contributing_models.add(req.split(":", 1)[1].strip())
            norm_ack = normalize_model_text(ack_text)
            for m in sorted(contributing_models):
                if not model_mentioned_in_text(m, ack_text, norm_ack):
                    errors.append(
                        f"mandatory acknowledgements file '{ack_path}' does not mention contributing AI model '{m}'"
                    )

    style = root / STYLE_FILE
    if not style.is_file():
        errors.append(f"missing writing-style guide: {STYLE_FILE} (required input for the manuscript stage)")
    else:
        n = word_count(style.read_text(encoding="utf-8", errors="replace").splitlines())
        if n < MIN_STYLE_WORDS:
            warnings.append(f"{STYLE_FILE} has only {n} words of guidance (excluding comments); a thorough "
                            f"guide (>= {MIN_STYLE_WORDS} words) is expected before writing the manuscript")
        style_text = style.read_text(encoding="utf-8", errors="replace")
        for loc in p.config.target_languages:
            if not re.search(r"^#{1,3}\s+Locale:\s*" + re.escape(loc) + r"\b", style_text, re.I | re.M):
                warnings.append(f"writing-style guide '{STYLE_FILE}' lacks guidance section for configured locale '{loc}' (expected heading '# Locale: {loc}')")
        if not re.search(r"^#{1,3}\s+Glossary\s+(?:Guidelines|Criteria)\b", style_text, re.I | re.M):
            warnings.append(f"writing-style guide '{STYLE_FILE}' lacks '## Glossary Guidelines' section for automated term discovery")
        if not re.search(r"^#{1,3}\s+(?:Graphics|Visual\s+Assets?)\s+(?:Guidelines|Rules|Style)?\b", style_text, re.I | re.M):
            warnings.append(f"writing-style guide '{STYLE_FILE}' lacks '## Graphics Guidelines' section to govern visual asset usage, intensity, and rendering styles")
        if not re.search(r"^#{1,3}\s+Publication(?:\s+&|\s+and)?\s+(?:Book\s+Design\s+)?Guidelines\b", style_text, re.I | re.M):
            warnings.append(f"writing-style guide '{STYLE_FILE}' lacks '## Publication & Book Design Guidelines' section (defines trim size, typography, margins, and EPUB/PDF styling)")

    # catalog integrity
    errors += [f"duplicate ID {d['id']}: {d['first']} and {d['second']}" for d in plan.duplicates]
    errors += o.problems
    for s in plan.sections():
        for rid, line in s.refs:
            if rid not in plan.defs:
                errors.append(f"dangling reference [[{rid}]] at {s.file}:{line}")
    for s in plan.defs.values():
        if s.prefix not in TYPES:
            infos.append(f"{s.id} uses unregistered prefix '{s.prefix}' ({s.location})")

    # research integrity
    for s in plan.of_type("FCT"):
        if not any(r.startswith("SRC-") for r in s.ref_ids()):
            errors.append(f"fact {s.id} does not cite any [[SRC-...]] source ({s.location})")
    for s in plan.of_type("SRC"):
        has_url = s.has_field("url") or "http://" in s.text or "https://" in s.text
        if not has_url and not s.has_field("citation"):
            errors.append(f"source {s.id} has neither a URL nor a Citation ({s.location})")
        if has_url and not s.has_field("accessed"):
            warnings.append(f"source {s.id} has a URL but no 'Accessed:' date ({s.location})")
        if not s.has_field("type"):
            warnings.append(f"source {s.id} lacks a 'Type:' (primary/secondary/tertiary) ({s.location})")
    for s in plan.of_type("WLD"):
        if not s.has_field("basis"):
            warnings.append(f"world rule {s.id} has no 'Basis:' line (cite [[FCT-...]] or state 'invented') ({s.location})")
    open_rq = [s for s in plan.of_type("RQ") if re.search(FIELD_RE.format(name="status") + r"\s*\**\s*open", s.text, re.I | re.M)]
    if open_rq:
        infos.append(f"{len(open_rq)} open research question(s): " + ", ".join(s.id for s in open_rq))

    # plot integrity (time and place metadata)
    for s in plan.of_type("PLT"):
        time_val = s.field_value("time", "when", "span", "timeline", "period", "date")
        if not time_val or (time_val.startswith("<") and time_val.endswith(">")) or time_val.lower() in {"todo", "tbd", "unspecified", "none"}:
            errors.append(f"plot element {s.id} is missing valid time metadata (e.g. 'Time:' or 'When:') ({s.location})")
        place_val = s.field_value("place", "where", "setting", "location")
        if not place_val or (place_val.startswith("<") and place_val.endswith(">")) or place_val.lower() in {"todo", "tbd", "unspecified", "none"}:
            errors.append(f"plot element {s.id} is missing valid place metadata (e.g. 'Place:' or 'Where:') ({s.location})")

    # editorial feedback validation
    valid_edt_stages = {"outline", "abridged", "manuscript", "all"}
    valid_edt_statuses = {"open", "applied", "superseded", "wontfix"}
    open_edts: List[Section] = []
    for s in plan.of_type("EDT"):
        target_val = (s.field_value("target") or "").strip()
        if not target_val or (target_val.startswith("<") and target_val.endswith(">")):
            errors.append(f"editorial directive {s.id} lacks a valid 'Target:' field ({s.location})")
        stage_val = (s.field_value("stage") or "").lower()
        if not stage_val or stage_val not in valid_edt_stages:
            errors.append(f"editorial directive {s.id} has invalid or missing 'Stage:' ({stage_val or 'none'}); must be one of {', '.join(sorted(valid_edt_stages))} ({s.location})")
        status_val = (s.field_value("status") or "").lower()
        if not status_val or status_val not in valid_edt_statuses:
            errors.append(f"editorial directive {s.id} has invalid or missing 'Status:' ({status_val or 'none'}); must be one of {', '.join(sorted(valid_edt_statuses))} ({s.location})")
        elif status_val == "open":
            open_edts.append(s)
        loc_val = (s.field_value("locale", "lang", "language") or "").strip()
        if not loc_val:
            if len(p.config.target_languages) > 1:
                errors.append(f"editorial directive {s.id} is missing required 'Locale:' field ({s.location}); must be 'all' or one of {', '.join(p.config.target_languages)}")
            else:
                warnings.append(f"editorial directive {s.id} is missing 'Locale:' field (defaults to 'all') ({s.location})")
        elif loc_val.lower() not in ("all", "global") and loc_val not in p.config.target_languages:
            errors.append(f"editorial directive {s.id} has invalid 'Locale:' '{loc_val}' ({s.location}); must be 'all' or one of {', '.join(p.config.target_languages)}")

    if open_edts:
        infos.append(f"{len(open_edts)} open editorial directive(s): " + ", ".join(s.id for s in open_edts))

    # graphics integrity
    dag = build_story_dag(p)
    for s in plan.of_type("GFX"):
        gtype = (s.field_value("type") or "").strip().lower()
        if not gtype:
            warnings.append(f"graphic {s.id} has no 'Type:' field (e.g. map, diagram, cover, illustration) ({s.location})")
        target_path = (s.field_value("target", "file", "path") or "").strip()
        if not target_path:
            warnings.append(f"graphic {s.id} has no 'Target:' file path (defaults to graphics/{s.id}.png) ({s.location})")
        if s.id in dag.positions or s.id in dag.nodes:
            rel_file = target_path or f"graphics/{s.id}.png"
            if not (root / rel_file).is_file():
                warnings.append(f"active graphic {s.id} ({s.title}) in Story DAG has missing rendered file '{rel_file}'")

    # localized graphics references verification
    img_ref_pattern = re.compile(r"""(?:!\[.*?\]\((?P<url1>[^)\s]+)\)|(?P<url2>(?:graphics/)?[a-zA-Z0-9_\-\./]+\.(?:png|svg|jpg|jpeg|webp)))""", re.I)
    gfx_filename_pattern = re.compile(r"""(?:^|.*/)(?P<id>GFX-\d{3,})(?:\.(?P<locale>[a-zA-Z0-9_-]+))?\.(?P<ext>png|svg|jpg|jpeg|webp)$""", re.I)

    for loc in p.config.target_languages:
        loc_ms_dir = root / MANUSCRIPT / loc
        target_files = []
        if loc_ms_dir.is_dir():
            target_files = sorted(loc_ms_dir.glob("*.md"))
        elif loc == p.config.primary_language and (root / MANUSCRIPT).is_dir():
            target_files = [f for f in (root / MANUSCRIPT).glob("*.md") if f.name != Path(STYLE_FILE).name]

        for mf in target_files:
            rel = mf.relative_to(root).as_posix()
            text = mf.read_text(encoding="utf-8", errors="replace")
            for line_no, line in enumerate(text.splitlines(), 1):
                for match in img_ref_pattern.finditer(line):
                    url = match.group("url1") or match.group("url2")
                    if not url or "http://" in url or "https://" in url:
                        continue
                    gm = gfx_filename_pattern.search(url)
                    if not gm:
                        continue
                    gid = gm.group("id")
                    file_loc = gm.group("locale")
                    ext = gm.group("ext")

                    gsec = plan.defs.get(gid)
                    expected_loc_path = f"graphics/{gid}.{loc}.{ext}"
                    has_loc_file = (root / expected_loc_path).is_file()
                    has_text = gsec and (gsec.has_field("has-text") or re.search(r"###\s+" + re.escape(loc), gsec.text))

                    if has_loc_file or has_text:
                        if file_loc != loc:
                            errors.append(f"manuscript '{rel}:{line_no}' (locale: {loc}) references mismatched graphic '{url}'; expected localized version '{expected_loc_path}'")
                    else:
                        norm_url = url.replace("../", "").lstrip("./")
                        if not (root / norm_url).is_file() and not (root / "graphics" / norm_url).is_file():
                            warnings.append(f"manuscript '{rel}:{line_no}' references missing graphic asset '{url}'")

    # usage
    outline_refs: Set[str] = set()
    for s in plan.sections():
        if s.file.startswith(OUTLINE + "/"):
            outline_refs |= s.ref_ids()
    unused = [s.id for s in plan.defs.values() if s.prefix in STORY_TYPES and s.id not in outline_refs]
    if o.scenes and unused:
        infos.append(f"{len(unused)} knowledge item(s) not referenced by the outline: " + ", ".join(unused))
    cited = {r for s in plan.of_type("FCT") for r in s.ref_ids()}
    uncited = [s.id for s in plan.of_type("SRC") if s.id not in cited]
    if uncited:
        infos.append(f"{len(uncited)} source(s) not cited by any fact: " + ", ".join(uncited))

    # story causality DAG, reading order coherence and denouement essentiality
    dag_errors, dag_warnings, dag_infos = run_dag_checks(p)
    errors += dag_errors
    warnings += dag_warnings
    infos += dag_infos

    # Chekhov's gun (plants/payoffs) and epistemic character knowledge integrity
    ep_errors, ep_warnings, ep_infos = check_epistemic_and_setup_payoffs(p)
    errors += ep_errors
    warnings += ep_warnings
    infos += ep_infos

    # derived layers
    for name, d in p.layers.items():
        errors += [f"{name}: duplicate {x['id']}: {x['first']} and {x['second']}" for x in d.model.duplicates]
        for sid, s in d.scenes.items():
            if sid not in o.chapter_of:
                errors.append(f"{name}: scene {sid} is not in the outline ({s.location})")
            elif d.chapter_of.get(sid) != o.chapter_of[sid]:
                errors.append(f"{name}: scene {sid} is under {d.chapter_of.get(sid)} but the outline places it "
                              f"in {o.chapter_of[sid]} ({s.location})")
        for cid, s in d.chapters.items():
            if cid not in o.by_chapter:
                errors.append(f"{name}: chapter {cid} is not in the outline ({s.location})")
        for cid, expected in o.by_chapter.items():
            present = [sid for sid, c in d.chapter_of.items() if c == cid]
            if present != [sid for sid in expected if sid in present]:
                errors.append(f"{name}: scene order in {cid} is {', '.join(present)} but the outline order is "
                              f"{', '.join(expected)}")
        for sid, s in d.scenes.items():
            for rid, line in s.refs:
                if rid not in plan.defs:
                    errors.append(f"{name}: dangling reference [[{rid}]] at {s.file}:{line}")
            if name == "manuscript":
                clean_body = COMMENT_RE.sub("", "\n".join(s.body))
                if REF_RE.search(clean_body):
                    warnings.append(f"manuscript: visible [[ID]] markup left in prose of {sid} ({s.location})")
                for bm in BRACKET_PLACEHOLDER_RE.finditer(clean_body):
                    inner = bm.group(1).strip()
                    if inner.lower() not in {"x", " "} and not inner.isdigit():
                        warnings.append(f"manuscript: unresolved placeholder '[{inner}]' left in prose of {sid} ({s.location})")
        missing = [sid for sid in o.scenes if sid not in d.scenes]
        if missing:
            msg = f"{name}: {len(missing)} of {len(o.scenes)} outline scene(s) not written yet"
            if name in require:
                errors.append(msg + ": " + ", ".join(missing))
            elif d.scenes:
                infos.append(msg)

    # placeholders in specs
    placeholders = scan_placeholders(p)
    untracked_pl = [pl for pl in placeholders if pl.tracked_by is None]
    if untracked_pl:
        infos.append(f"{len(untracked_pl)} untracked placeholder(s) in specs (run 'specnovel.py placeholders --create-rq')")

    return errors, warnings, infos


# ------------------------------------------------------------------ delta / impact
KIND_ORDER = {"ADDED": 0, "MODIFIED": 1, "REMOVED": 2, "MOVED": 3}


@dataclass
class Change:
    kind: str
    section: Section
    before: List[str]
    after: List[str]
    old_file: Optional[str] = None

    @property
    def id(self) -> Optional[str]:
        return self.section.id

    def label(self) -> str:
        s = self.section
        return f"{s.id}: {s.title}" if s.id else f"[context] {s.key}"

    def to_dict(self) -> dict:
        s = self.section
        return {"kind": self.kind, "id": s.id, "key": s.key, "title": s.title, "file": s.file,
                "line": s.line, "oldFile": self.old_file, "before": "\n".join(self.before),
                "after": "\n".join(self.after)}


def diff_models(old: Model, new: Model) -> List[Change]:
    changes: List[Change] = []
    for table_new, table_old in ((new.defs, old.defs), (new.contexts, old.contexts)):
        for k, c in table_new.items():
            b = table_old.get(k)
            if b is None:
                changes.append(Change("ADDED", c, [], c.lines))
            elif b.digest != c.digest:
                changes.append(Change("MODIFIED", c, b.lines, c.lines, b.file))
            elif c.id and b.file != c.file:
                changes.append(Change("MOVED", c, b.lines, c.lines, b.file))
        for k, b in table_old.items():
            if k not in table_new:
                changes.append(Change("REMOVED", b, b.lines, [], b.file))
    changes.sort(key=lambda ch: (ch.id is None, KIND_ORDER[ch.kind], ch.section.file, ch.section.line))
    return changes


def compute_graphics_impact(p: Project) -> dict:
    git, plan, o = p.git, p.plan, p.outline
    dag = build_story_dag(p)
    gfx_items = plan.of_type("GFX")

    active_items = []
    inactive_items = []

    for gfx in gfx_items:
        gid = gfx.id
        is_active = (gid in dag.positions) or (gid in dag.nodes)
        embed_target = gfx.field_value("embed", "placement", "scene", "target_scene")
        if embed_target:
            for s_ref in gfx.ref_ids():
                if s_ref in o.scenes:
                    is_active = True
                    break

        target_path = (gfx.field_value("target", "file", "path") or f"graphics/{gid}.png").strip()
        gtype = (gfx.field_value("type") or "image").strip()
        asset_base = git.gfx_baseline(gid)
        commits_behind = git.commits_behind(asset_base) if asset_base else None

        rendered_file_exists = (git.root / target_path).is_file()

        reasons: List[str] = []
        upstream_changes: List[str] = []

        if not is_active:
            status = "INACTIVE"
            if asset_base:
                desc = f"skipped (not in Story DAG - 0 tokens used; last synced {commits_behind} commits ago)"
            else:
                desc = "skipped (not in Story DAG - 0 tokens used; never rendered)"
            inactive_items.append({
                "id": gid,
                "title": gfx.title,
                "type": gtype,
                "target": target_path,
                "status": status,
                "active": False,
                "baseline": git.commit_info(asset_base),
                "commits_behind": commits_behind,
                "reason": desc,
            })
            continue

        if not rendered_file_exists:
            reasons.append(f"rendered file missing on disk ({target_path})")

        if not asset_base:
            reasons.append("no sync baseline (never rendered)")
        else:
            old_plan_md = git.commit_md(asset_base, "kb/graphics")
            old_model = build_model(old_plan_md)
            if gid not in old_model.defs:
                upstream_changes.append("GFX definition added after baseline")
            else:
                old_sec = old_model.defs[gid]
                if old_sec.lines != gfx.lines:
                    upstream_changes.append("GFX definition modified")

            dep_ids = (gfx.ref_ids() | gfx.prereq_ids()) - {gid}
            if dep_ids:
                old_all_md = git.commit_md(asset_base, *PLAN_DIRS)
                old_all = build_model(old_all_md)
                for did in sorted(dep_ids):
                    if did not in old_all.defs:
                        upstream_changes.append(f"referenced [[{did}]] added")
                    elif did in plan.defs and old_all.defs[did].lines != plan.defs[did].lines:
                        upstream_changes.append(f"referenced [[{did}]] modified")

            if upstream_changes:
                reasons.extend(upstream_changes)

        if not rendered_file_exists or not asset_base:
            status = "NEEDS_RENDERING"
        elif upstream_changes:
            status = "OUT_OF_SYNC"
        else:
            status = "UP_TO_DATE"

        active_items.append({
            "id": gid,
            "title": gfx.title,
            "type": gtype,
            "target": target_path,
            "status": status,
            "active": True,
            "baseline": git.commit_info(asset_base),
            "commits_behind": commits_behind,
            "reasons": reasons,
            "upstream_changes": upstream_changes,
        })

    needs_update_count = sum(1 for it in active_items if it["status"] != "UP_TO_DATE")
    return {
        "stage": "graphics",
        "active": active_items,
        "inactive": inactive_items,
        "needs_update_count": needs_update_count,
        "token_savings_count": len(inactive_items),
    }


def compute_impact(p: Project, stage: str, locale: Optional[str] = None) -> dict:
    git, plan, o = p.git, p.plan, p.outline
    base = git.baseline(stage)
    old_plan = build_model(git.commit_md(base, *PLAN_DIRS))
    old_o = outline_of(old_plan)
    changes = diff_models(old_plan, plan)
    changed_ids = {c.id for c in changes if c.id}
    target = p.manuscript_locales.get(locale, p.layers[stage]) if (stage == "manuscript" and locale) else p.layers[stage]
    ab_old = derived_of(build_model(git.commit_md(base, ABRIDGED))) if stage == "manuscript" else None
    ab_now = p.layers["abridged"]

    # Open editorial directives for this stage
    edt_reasons_by_scene: Dict[str, List[str]] = {}
    global_edt_notes: List[str] = []
    for edt in plan.of_type("EDT"):
        if (edt.field_value("status") or "").lower() != "open":
            continue
        edt_stage = (edt.field_value("stage") or "").lower()
        if edt_stage != "all" and edt_stage != stage:
            continue
        edt_loc = (edt.field_value("locale", "lang", "language") or "all").lower()
        if locale and edt_loc not in ("all", "global", locale.lower()):
            continue
        target_val = (edt.field_value("target") or "").strip()
        if "global" in target_val.lower():
            global_edt_notes.append(f"open editorial directive {edt.id}: {edt.title}")
            continue
        targeted_sids: Set[str] = set()
        for ref_id in edt.ref_ids():
            if ref_id in o.scenes:
                targeted_sids.add(ref_id)
            elif ref_id in o.chapters:
                for sid in o.by_chapter.get(ref_id, []):
                    targeted_sids.add(sid)
        for sid in targeted_sids:
            edt_reasons_by_scene.setdefault(sid, []).append(f"open editorial directive {edt.id}: {edt.title}")

    scenes = []
    for sid in o.scenes:
        reasons: List[str] = []
        cid = o.chapter_of[sid]
        if sid not in target.scenes:
            reasons.append("not yet written")
        else:
            if base is None:
                reasons.append("no baseline yet (accept this stage once reviewed)")
            if sid in changed_ids:
                reasons.append("outline scene changed")
            if stage == "abridged" and cid in changed_ids:
                reasons.append(f"chapter {cid} changed")
            if stage == "manuscript" and sid in ab_now.scenes:
                old = ab_old.scenes.get(sid) if ab_old else None
                if old is None or old.digest != ab_now.scenes[sid].digest:
                    reasons.append("abridged scene changed")
            refs: Set[str] = set()
            for a in ancestors(plan, sid):
                refs |= a.ref_ids()
            hits = sorted(refs & changed_ids - {sid, cid})
            if hits:
                reasons.append("references changed " + ", ".join(hits))
            if sid in old_o.chapter_of and old_o.chapter_of[sid] != cid:
                reasons.append(f"moved from {old_o.chapter_of[sid]} to {cid}")
        if sid in edt_reasons_by_scene:
            reasons.extend(edt_reasons_by_scene[sid])
        if stage == "manuscript" and sid not in ab_now.scenes:
            reasons.append("blocked: abridged scene missing")
        if reasons:
            scenes.append({"id": sid, "chapter": cid, "title": plan.defs[sid].title, "reasons": reasons})

    removed = [sid for sid in target.scenes if sid not in o.chapter_of]
    global_notes = list(global_edt_notes)
    for c in changes:
        if c.id:
            continue
        if c.section.file == STYLE_FILE:
            if stage == "manuscript":
                global_notes.append(f"{c.kind} style guide section '{c.section.path}': review every rendered scene")
        else:
            global_notes.append(f"{c.kind} context '{c.section.key}': judge which scenes it affects")
    if stage == "manuscript":
        for c in changes:
            if c.id and c.section.file == STYLE_FILE:
                global_notes.append(f"{c.kind} style rule {c.label()}: review every rendered scene")
    return {"stage": stage, "baseline": git.commit_info(base), "upstreamChanges": [c.label() for c in changes],
            "scenes": scenes, "remove": removed, "global": global_notes}


# ------------------------------------------------------------------ output helpers
OUT_FENCE = "````"


def emit_json(obj) -> None:
    print(json.dumps(obj, indent=2, ensure_ascii=False))


def baseline_line(stage: str, info: Optional[dict]) -> str:
    if info:
        return f"{stage:<10} baseline: {info['short']} ({info['date'][:10]}) {info['subject']}"
    return f"{stage:<10} baseline: none"


def num_words(n: int) -> str:
    ones = ["Zero", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten",
            "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen"]
    tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]
    if n < 20:
        return ones[n]
    if n < 100:
        return tens[n // 10] + (f"-{ones[n % 10]}" if n % 10 else "")
    if n < 1000:
        return f"{ones[n // 100]} Hundred" + (f" and {num_words(n % 100)}" if n % 100 else "")
    return str(n)


def clean_prose(lines: Sequence[str]) -> List[str]:
    text = COMMENT_RE.sub("", "\n".join(lines))
    text = REF_ALIAS_RE.sub(r"\1", text)
    text = REF_BARE_RE.sub(r"\1", text)
    return normalize(text.splitlines())


# ------------------------------------------------------------------ commands
def cmd_init(root: Path, args) -> int:
    if subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=root, capture_output=True).returncode != 0:
        subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
        print("created  git repository")
    git = Git(root)
    templates = Path(__file__).resolve().parent.parent / "templates" / "project"
    if templates.is_dir():
        for src in sorted(templates.rglob("*")):
            if src.is_file():
                rel = src.relative_to(templates)
                dst = git.root / rel
                if dst.exists():
                    print(f"exists   {rel.as_posix()}")
                else:
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(src, dst)
                    print(f"created  {rel.as_posix()}")
    else:
        print(f"warning: templates not found at {templates}", file=sys.stderr)
    for d in [f"{KB}/{k}" for k in KB_FOLDERS] + ["story/editorial", GRAPHICS, OUTLINE, ABRIDGED, MANUSCRIPT, f"{MANUSCRIPT}/en-US"]:
        p = git.root / d
        if not p.exists():
            p.mkdir(parents=True)
            (p / ".gitkeep").write_text("", encoding="utf-8")
            print(f"created  {d}/")
    gi = git.root / ".gitignore"
    content = gi.read_text(encoding="utf-8") if gi.exists() else ""
    if "build/" not in content.split():
        gi.write_text(content.rstrip() + ("\n" if content.strip() else "") + "build/\n", encoding="utf-8")
        print("updated  .gitignore (build/)")
    return 0


def cmd_status(git: Git, args) -> int:
    p = load_project(git)
    errors, warnings, infos = run_checks(p)
    counts = OrderedDict((pre, len(p.plan.of_type(pre))) for pre in TYPES)
    impacts = {st: compute_impact(p, st) for st in LAYERS}
    gfx_impact = compute_graphics_impact(p)
    drift = {st: git.changed_since(git.baseline(st), *STAGE_DIRS.get(st, (st,))) for st in STAGES}
    words = {st: sum(word_count(s.body) for s in p.layers[st].scenes.values()) for st in LAYERS}
    placeholders = scan_placeholders(p)
    untracked_pl = [pl for pl in placeholders if pl.tracked_by is None]
    if args.json:
        emit_json({"title": project_title(git),
                   "baselines": {st: git.commit_info(git.baseline(st)) for st in STAGES},
                   "catalog": counts, "scenes": {"outline": len(p.outline.scenes),
                                                 **{st: len(p.layers[st].scenes) for st in LAYERS}},
                   "words": words, "pending": {st: len(impacts[st]["scenes"]) + len(impacts[st]["remove"]) for st in LAYERS},
                   "graphics": {"active": len(gfx_impact["active"]), "pending": gfx_impact["needs_update_count"],
                                "inactive": len(gfx_impact["inactive"])},
                   "placeholders": {"total": len(placeholders), "untracked": len(untracked_pl)},
                   "drift": drift, "errors": errors, "warnings": warnings, "infos": infos,
                   "next": next_step(p, impacts, gfx_impact, errors)})
        return 0
    out = [f"# SpecNovelist status: {project_title(git)}", ""]
    out += [baseline_line(st, git.commit_info(git.baseline(st))) for st in STAGES]
    out += ["", "Knowledge base & outline:"]
    out += [f"  {pre:<4} {TYPES[pre]:<18} {n}" for pre, n in counts.items() if n]
    if not any(counts.values()):
        out.append("  (empty)")
    total = len(p.outline.scenes)
    out += ["", f"Scenes: outline {total} | abridged {len(p.layers['abridged'].scenes)} ({words['abridged']:,} words)"
                f" | manuscript {len(p.layers['manuscript'].scenes)} ({words['manuscript']:,} words)"]
    if gfx_impact["needs_update_count"]:
        out.append(f"Pending graphics: {gfx_impact['needs_update_count']} active asset(s) to render - run 'impact --stage graphics'")
    for st in LAYERS:
        imp = impacts[st]
        n = len(imp["scenes"]) + len(imp["remove"])
        out.append(f"Pending {st}: {n} scene(s) to (re)generate or remove"
                   + (f", {len(imp['global'])} global note(s)" if imp["global"] else "") + f" - run 'impact --stage {st}'")
    for st in STAGES:
        if drift[st] and git.baseline(st):
            out.append(f"  {len(drift[st])} file(s) in {st} changed since the {st} baseline "
                       f"(see 'specnovel delta --stage {st}')")
    if untracked_pl:
        out += ["", f"Placeholders: {len(untracked_pl)} untracked placeholder(s) - run 'specnovel.py placeholders --create-rq'"]
    out += ["", f"Check: {len(errors)} error(s), {len(warnings)} warning(s) - run 'check' for details",
            f"Next: {next_step(p, impacts, gfx_impact, errors)}"]
    print("\n".join(out))
    return 0


def next_step(p: Project, impacts: dict, gfx_impact: dict, errors: List[str]) -> str:
    root = p.git.root
    syn = root / SYNOPSIS_FILE
    if not syn.is_file() or word_count(syn.read_text(encoding="utf-8").splitlines()) < 30:
        return "write the seed synopsis in story/synopsis.md, then run novel-init"
    if not p.plan.of_type("CHR"):
        return "novel-init: interview and seed the knowledge base"
    if errors:
        return "fix the errors reported by 'check'"
    pl_untracked = [pl for pl in scan_placeholders(p) if pl.tracked_by is None]
    if pl_untracked and not p.plan.of_type("RQ"):
        return "run 'specnovel.py placeholders --create-rq' to generate research questions from placeholders"
    if not p.git.baseline("brief"):
        return "review the brief and run 'accept --stage brief'"
    high = [s.id for s in p.plan.of_type("RQ")
            if re.search(r"status\**\s*:\**\s*open", s.text, re.I) and re.search(r"priority\**\s*:\**\s*high", s.text, re.I)]
    if high:
        return "novel-research: answer high-priority research questions " + ", ".join(high[:5])
    if not p.git.baseline("research"):
        return "review research and run 'accept --stage research'"
    if not p.git.baseline("bible"):
        return "review story bible and run 'accept --stage bible'"
    if pl_untracked:
        return "run 'specnovel.py placeholders --create-rq' to track remaining placeholders"
    if not p.outline.scenes:
        return "novel-outline: build the outline"
    if not p.git.baseline("outline"):
        return "review the outline and run 'accept --stage outline'"
    if gfx_impact["needs_update_count"] > 0:
        return "render pending graphics with 'specnovel.py impact --stage graphics' and accept --stage graphics"
    if impacts["abridged"]["scenes"] or impacts["abridged"]["remove"]:
        return "novel-abridge (or novel-sync): update the abridged draft"
    if impacts["manuscript"]["scenes"] or impacts["manuscript"]["remove"]:
        style = root / STYLE_FILE
        if not style.is_file() or word_count(style.read_text(encoding="utf-8").splitlines()) < MIN_STYLE_WORDS:
            return "complete story/style.md before writing the manuscript"
        return "novel-write (or novel-sync): render the manuscript"
    return "novel-verify: audit continuity, facts and style; then 'compile'"


def cmd_check(git: Git, args) -> int:
    p = load_project(git)
    errors, warnings, infos = run_checks(p, args.require or [])
    if args.json:
        emit_json({"ok": not errors, "errors": errors, "warnings": warnings, "infos": infos})
        return 1 if errors else 0
    if errors:
        print(f"CHECK FAILED - {len(errors)} error(s):")
        print("\n".join(f"  - {e}" for e in errors))
    else:
        print("CHECK OK - IDs unique, references resolve, facts cite sources, derived layers match the outline.")
    if warnings:
        print(f"Warnings ({len(warnings)}):")
        print("\n".join(f"  - {w}" for w in warnings))
    if infos:
        print("Info:")
        print("\n".join(f"  - {i}" for i in infos))
    return 1 if errors else 0


def cmd_dag(git: Git, args) -> int:
    p = load_project(git)
    if not p.outline.scenes:
        print("No scenes in outline yet.")
        return 0
    dag = build_story_dag(p)
    cycles = check_dag_cycles(dag)
    ro_errors = check_reading_order_coherence(dag, p.outline)
    root, ess_errors = check_essentiality_to_root(dag, p)
    total_edges = sum(len(v) for v in dag.edges.values())

    if args.json:
        emit_json({
            "root": root,
            "nodes": sorted(dag.nodes),
            "edges": {k: sorted(v) for k, v in dag.edges.items()},
            "reverseEdges": {k: sorted(v) for k, v in dag.reverse_edges.items()},
            "positions": dag.positions,
            "cycles": cycles,
            "readingOrderErrors": ro_errors,
            "essentialityErrors": ess_errors,
            "ok": not (cycles or ro_errors or ess_errors),
        })
        return 1 if (cycles or ro_errors or ess_errors) else 0

    if args.mermaid:
        out = ["```mermaid", "graph TD"]
        for node in sorted(dag.nodes):
            sec = p.plan.defs.get(node)
            title = sec.title if sec else node
            safe_title = title.replace('"', "'")
            is_root = " (Denouement)" if node == root else ""
            out.append(f'    {node}["{node}: {safe_title}{is_root}"]')
        for u in sorted(dag.edges):
            for v in sorted(dag.edges[u]):
                out.append(f"    {u} --> {v}")
        out.append("```")
        print("\n".join(out))
        return 0

    out = [
        f"# Story Causality DAG & Reading Order Coherence: {project_title(git)}", "",
        f"Root Denouement: {root} ({p.plan.defs[root].title if root in p.plan.defs else 'unknown'})",
        f"Story Elements in DAG: {len(dag.nodes)}",
        f"Causal Prerequisite Edges: {total_edges}", "",
        "## Verification Results:"
    ]

    if cycles:
        out.append(f"  [FAIL] Acyclic Check: {len(cycles)} causality cycle(s) detected:")
        out += [f"    - {c}" for c in cycles]
    else:
        out.append("  [OK] Acyclic Check: Graph is a valid DAG (no causality loops)")

    if ro_errors:
        out.append(f"  [FAIL] Reading Order Coherence: {len(ro_errors)} violation(s):")
        out += [f"    - {e}" for e in ro_errors]
    else:
        out.append("  [OK] Reading Order Coherence: All prerequisites precede dependents in the outline")

    if ess_errors:
        out.append(f"  [FAIL] Essentiality Check: {len(ess_errors)} inessential element(s):")
        out += [f"    - {e}" for e in ess_errors]
    else:
        out.append(f"  [OK] Essentiality Check: All {len(dag.nodes)} elements have a path to the root denouement ({root})")

    out += ["", "## Elements & Prerequisites in Reading Order:"]
    for sid in p.outline.scenes:
        s = p.plan.defs.get(sid)
        title = s.title if s else sid
        prereqs = dag.reverse_edges.get(sid, set())
        enables = dag.edges.get(sid, set())
        flags = " [ROOT DENOUEMENT]" if sid == root else ""
        out.append(f"  {sid}: {title}{flags}")
        if prereqs:
            out.append(f"    prerequisites: {', '.join(sorted(prereqs))}")
        if enables:
            out.append(f"    enables:       {', '.join(sorted(enables))}")

    non_scenes = sorted([n for n in dag.nodes if not n.startswith("SCN-")])
    if non_scenes:
        out += ["", "## Knowledge & Plot Elements in DAG:"]
        for n in non_scenes:
            s = p.plan.defs.get(n)
            title = s.title if s else n
            prereqs = dag.reverse_edges.get(n, set())
            enables = dag.edges.get(n, set())
            flags = " [ROOT DENOUEMENT]" if n == root else ""
            pos = dag.positions.get(n)
            pos_str = f"first appears in scene #{pos}" if pos else "not in outline"
            out.append(f"  {n}: {title}{flags} ({pos_str})")
            if prereqs:
                out.append(f"    prerequisites: {', '.join(sorted(prereqs))}")
            if enables:
                out.append(f"    enables:       {', '.join(sorted(enables))}")

    print("\n".join(out))
    return 1 if (cycles or ro_errors or ess_errors) else 0


def allocate_next_ids(git: Git, prefix: str, count: int = 1) -> List[str]:
    prefix = prefix.upper()
    if not re.fullmatch(r"[A-Z][A-Z0-9]*", prefix):
        raise NovelError("Prefix must be uppercase letters/digits, e.g. CHR")
    rx = re.compile(rf"^[+\- ]?#{{1,6}}\s+{prefix}-(\d+)\b")
    lines: List[str] = []
    for text in git.working_md(*ALL_DIRS).values():
        lines += text.splitlines()
    if git.has_commits():  # every ID that ever appeared in history (any branch) is retired
        lines += (git.run("log", "--all", "--format=", "-p", "--", *ALL_DIRS) or "").splitlines()
    nums = [int(m.group(1)) for m in map(rx.match, lines) if m]
    start = (max(nums) if nums else 0) + 1
    return [f"{prefix}-{n:03d}" for n in range(start, start + count)]


def cmd_next_id(git: Git, args) -> int:
    ids = allocate_next_ids(git, args.prefix, 1)
    print(ids[0])
    return 0


def cmd_trace(git: Git, args) -> int:
    p = load_project(git)
    rid = args.id.upper()
    s = p.plan.defs.get(rid)
    referenced_by = []
    for sec in p.plan.sections():
        if rid in sec.ref_ids() and sec.id != rid:
            referenced_by.append({"key": sec.key, "title": sec.title, "location": sec.location})
    numbering = {cid: i for i, cid in enumerate(p.outline.chapters, 1)}
    scenes = []
    for sid in p.outline.scenes:
        refs: Set[str] = set()
        for a in ancestors(p.plan, sid):
            refs |= a.ref_ids()
        if rid in refs or sid == rid or p.outline.chapter_of[sid] == rid:
            cid = p.outline.chapter_of[sid]
            row = {"id": sid, "chapter": cid, "chapterNo": numbering[cid], "title": p.plan.defs[sid].title}
            for st, d in p.layers.items():
                row[st] = d.scenes[sid].location if sid in d.scenes else None
            scenes.append(row)
    result = {"id": rid, "defined": s is not None, "type": TYPES.get(rid.split("-")[0], "unknown"),
              "title": s.title if s else None, "location": s.location if s else None,
              "references": sorted(s.ref_ids()) if s else [], "referencedBy": referenced_by, "scenes": scenes}
    if args.json:
        emit_json(result)
        return 0
    if not s:
        print(f"{rid} is not defined in story/, kb/ or outline/ (removed or never existed).")
    else:
        print(f"{rid}: {s.title}  [{result['type']}]  defined at {s.location}")
    if result["references"]:
        print("References: " + ", ".join(result["references"]))
    print(f"Referenced by {len(referenced_by)} section(s):")
    print("\n".join(f"  {r['key']}  ({r['location']})" for r in referenced_by) or "  (none)")
    print(f"Appears in {len(scenes)} scene(s), in reading order:")
    for r in scenes:
        print(f"  Ch.{r['chapterNo']:>3} {r['id']}: {r['title']}"
              f"  | abridged: {r['abridged'] or '-'} | manuscript: {r['manuscript'] or '-'}")
    return 0


def cmd_delta(git: Git, args) -> int:
    stage = args.stage
    base = git.baseline(stage)
    if stage == "plan":
        scope_dirs = PLAN_DIRS
        scope_desc = "plan (story/, kb/, outline/)"
    elif stage in STAGE_DIRS:
        scope_dirs = STAGE_DIRS[stage]
        scope_desc = f"{stage} ({', '.join(scope_dirs)})"
    else:
        scope_dirs = PLAN_DIRS
        scope_desc = stage

    changes = diff_models(build_model(git.commit_md(base, *scope_dirs)), build_model(git.working_md(*scope_dirs)))
    if args.json:
        emit_json({"stage": stage, "baseline": base, "changes": [c.to_dict() for c in changes]})
        return 0
    out = [f"# Delta for {scope_desc}", "", baseline_line(stage, git.commit_info(base)),
           f"Changes: {sum(1 for c in changes if c.kind == 'ADDED')} added, "
           f"{sum(1 for c in changes if c.kind == 'MODIFIED')} modified, "
           f"{sum(1 for c in changes if c.kind == 'REMOVED')} removed, "
           f"{sum(1 for c in changes if c.kind == 'MOVED')} moved", ""]
    if not changes:
        out.append(f"No changes in {stage} since this baseline.")
    for c in changes:
        s = c.section
        where = {"MOVED": f"{c.old_file} -> {s.location}", "REMOVED": f"was {s.location}"}.get(c.kind, s.location)
        out += [f"## {c.kind} {c.label()}", f"_{where}_", ""]
        if c.kind == "MODIFIED":
            diff = list(difflib.unified_diff(c.before, c.after, lineterm="", n=max(len(c.before), len(c.after))))[2:]
            out += [OUT_FENCE + "diff", *diff, OUT_FENCE]
        elif c.kind in ("ADDED", "REMOVED"):
            out += [OUT_FENCE + "markdown", *(c.after or c.before), OUT_FENCE]
        else:
            out.append("(content unchanged)")
        out.append("")
    print("\n".join(out))
    return 0


def cmd_impact(git: Git, args) -> int:
    p = load_project(git)
    if args.stage == "graphics":
        imp = compute_graphics_impact(p)
        if args.json:
            emit_json(imp)
            return 0
        out = ["# Impact on graphics/", ""]
        active = imp["active"]
        inactive = imp["inactive"]
        if not active and not inactive:
            out.append("No graphical assets defined in kb/graphics/.")
            print("\n".join(out))
            return 0
        out.append(f"Active assets in Story DAG: {len(active)} ({imp['needs_update_count']} need generation/update)")
        out.append(f"Inactive assets (skipped - token savings): {len(inactive)}")
        out.append("")
        if active:
            out.append("Active Assets:")
            for a in active:
                behind = f" ({a['commits_behind']} commits behind)" if a['commits_behind'] is not None else ""
                base_str = a['baseline']['short'] if a['baseline'] else "none"
                out.append(f"  [{a['status']}] {a['id']}: {a['title']}{behind}")
                out.append(f"      Type: {a['type']} | Target: {a['target']} | Baseline: {base_str}")
                if a["reasons"]:
                    for r in a["reasons"]:
                        out.append(f"      - {r}")
            out.append("")
        if inactive:
            out.append("Inactive Assets (Skipped to save AI tokens):")
            for a in inactive:
                out.append(f"  [{a['status']}] {a['id']}: {a['title']}")
                out.append(f"      {a['reason']}")
            out.append("")
        if imp["needs_update_count"] == 0:
            out.append("All active graphical assets in Story DAG are up to date.")
        else:
            out.append(f"{imp['needs_update_count']} active asset(s) need rendering. Run novel-sync with --stage graphics to accept.")
        print("\n".join(out))
        return 0

    imp = compute_impact(p, args.stage)
    if args.json:
        emit_json(imp)
        return 0
    info = imp["baseline"]
    out = [f"# Impact on {args.stage}/", "", baseline_line(args.stage, info),
           f"Upstream plan changes since baseline: {len(imp['upstreamChanges'])}", ""]
    if imp["global"]:
        out += ["Global notes:"] + [f"  - {g}" for g in imp["global"]] + [""]
    if imp["scenes"]:
        out.append(f"Scenes to (re)generate ({len(imp['scenes'])}), in reading order:")
        for r in imp["scenes"]:
            out.append(f"  {r['chapter']} / {r['id']}: {r['title']}")
            out += [f"      - {why}" for why in r["reasons"]]
    if imp["remove"]:
        out.append(f"Scenes to remove (no longer in outline): {', '.join(imp['remove'])}")
    if not imp["scenes"] and not imp["remove"] and not imp["global"]:
        out.append(f"{args.stage}/ is in sync with the plan.")
    print("\n".join(out))
    return 0


def cmd_accept(git: Git, args) -> int:
    requested = args.stage or []
    stages: List[str] = []
    if "all" in requested:
        stages = list(STAGES)
    else:
        for s in requested:
            if s == "plan":
                for st in SPEC_STAGES:
                    if st not in stages:
                        stages.append(st)
                if "plan" not in stages:
                    stages.append("plan")
            elif s in STAGES:
                if s not in stages:
                    stages.append(s)
            else:
                stages.append(s)

    model_name = getattr(args, "model", None) or os.environ.get("SPECNOVEL_MODEL")
    if not model_name:
        try:
            cfg_m = git.run("config", "--get", "specnovelist.model", check=False).stdout.strip()
            if cfg_m:
                model_name = cfg_m
        except Exception:
            pass

    reqs = list(stages)
    if model_name:
        for m in model_name.split(","):
            if m.strip():
                reqs.append(f"model:{m.strip()}")

    p = load_project(git)
    errors, _, _ = run_checks(p, require=reqs)
    if errors and not args.force:
        raise NovelError("Refusing to accept - check failed (use --force to override):\n  - " + "\n  - ".join(errors))

    trailers = [f"{TRAILER}: {', '.join(stages)}"]
    if model_name:
        trailers.append(f"Novel-Model: {model_name.strip()}")

    dirs_to_stage = set()
    for st in stages:
        if st in STAGE_DIRS:
            dirs_to_stage.update(STAGE_DIRS[st])
        elif st == "plan":
            dirs_to_stage.update(PLAN_DIRS)

    for st in stages:
        if st in ("plan", "bible", "research", "outline", "graphics"):
            scope = STAGE_DIRS.get(st, PLAN_DIRS)
            base = git.baseline(st)
            changes = diff_models(build_model(git.commit_md(base, *scope)), build_model(git.working_md(*scope)))
            for kind in ("ADDED", "MODIFIED", "REMOVED"):
                ids = [c.id for c in changes if c.id and c.kind == kind]
                if ids:
                    prefix = f"Novel-{st.capitalize()}-" if st != "plan" else "Novel-"
                    trailers.append(f"{prefix}{kind.capitalize()}: {', '.join(ids)}")
            if st == "graphics":
                gfx_imp = compute_graphics_impact(p)
                if getattr(args, "asset", None):
                    sync_ids = [gid for gid in args.asset if gid in p.plan.defs]
                else:
                    sync_ids = [item["id"] for item in gfx_imp["active"]]
                if sync_ids:
                    trailers.append(f"Novel-GFX-Sync: {', '.join(sync_ids)}")
        elif st == "brief":
            base = git.baseline("brief")
            scope = STAGE_DIRS["brief"]
            changes = diff_models(build_model(git.commit_md(base, *scope)), build_model(git.working_md(*scope)))
            if changes:
                files_mod = sorted({c.section.file for c in changes})
                trailers.append(f"Novel-Brief-Modified: {', '.join(files_mod)}")
        elif st in LAYERS:
            old = derived_of(build_model(git.commit_md(git.baseline(st), LAYERS[st])))
            cur = p.layers[st]
            updated = [sid for sid, s in cur.scenes.items() if sid not in old.scenes or old.scenes[sid].digest != s.digest]
            removed = [sid for sid in old.scenes if sid not in cur.scenes]
            if updated:
                trailers.append(f"Novel-{st.capitalize()}-Updated: {', '.join(updated)}")
            if removed:
                trailers.append(f"Novel-{st.capitalize()}-Removed: {', '.join(removed)}")

    existing_paths = [path for path in dirs_to_stage if (git.root / path).exists()]
    if existing_paths:
        git.run("add", "-A", "--", *existing_paths)

    msg = [f"novel-sync({', '.join(stages)}): {args.message}" if args.message else f"novel-sync({', '.join(stages)})",
           "", *trailers]
    fd, tmp = tempfile.mkstemp(prefix="specnovel-", suffix=".txt")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(msg) + "\n")
        git.run("commit", "--allow-empty", "-F", tmp)
    finally:
        os.unlink(tmp)
    info = git.commit_info(git.baseline(stages[-1]))
    print(f"Accepted {', '.join(stages)}. New baseline: {info['short']} {info['subject']}")
    return 0


def cmd_index(git: Git, args) -> int:
    p = load_project(git)
    out = ["<!-- GENERATED by specnovel.py index - do not edit; regenerate instead. -->",
           f"# Knowledge Base Index: {project_title(git)}", ""]
    for pre, name in TYPES.items():
        items = p.plan.of_type(pre)
        if not items:
            continue
        out += [f"## {name.title()}s ({pre})" if not name.endswith("y") else f"## {name[:-1].title()}ies ({pre})", "",
                "| ID | Title | File | Used in scenes |", "|----|-------|------|---------------:|"]
        for s in items:
            link = os.path.relpath(git.root / s.file, git.root / KB).replace("\\", "/")
            used = sum(1 for sid in p.outline.scenes
                       if s.id in set().union(*(a.ref_ids() for a in ancestors(p.plan, sid))))
            out.append(f"| {s.id} | {s.title.replace('|', '/')} | [{s.file}]({link}#L{s.line}) | {used} |")
        out.append("")
    dst = git.root / "kb" / "INDEX.md"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text("\n".join(out), encoding="utf-8")
    print(f"Wrote kb/INDEX.md ({len(p.plan.defs)} items)")
    return 0


def cmd_stats(git: Git, args) -> int:
    p = load_project(git)
    rows = []
    for n, cid in enumerate(p.outline.chapters, 1):
        sids = p.outline.by_chapter[cid]
        srows = []
        for sid in sids:
            srows.append({"id": sid, "title": p.plan.defs[sid].title, "target": target_words(p.plan.defs[sid]),
                          **{st: word_count(p.layers[st].scenes[sid].body) if sid in p.layers[st].scenes else 0
                             for st in LAYERS}})
        ch_target = target_words(p.plan.defs[cid]) or sum(r["target"] for r in srows)
        rows.append({"no": n, "id": cid, "title": p.plan.defs[cid].title, "target": ch_target,
                     "abridged": sum(r["abridged"] for r in srows), "manuscript": sum(r["manuscript"] for r in srows),
                     "scenes": srows})
    totals = {k: sum(r[k] for r in rows) for k in ("target", "abridged", "manuscript")}
    if args.json:
        emit_json({"chapters": rows, "totals": totals})
        return 0
    out = ["| # | Chapter | Scenes | Target | Abridged | Manuscript |", "|--:|---------|-------:|-------:|---------:|-----------:|"]
    for r in rows:
        out.append(f"| {r['no']} | {r['id']}: {r['title']} | {len(r['scenes'])} | {r['target']:,} | "
                   f"{r['abridged']:,} | {r['manuscript']:,} |")
        if args.scenes:
            out += [f"|   | &nbsp;&nbsp;{s['id']}: {s['title']} |  | {s['target']:,} | {s['abridged']:,} | "
                    f"{s['manuscript']:,} |" for s in r["scenes"]]
    out.append(f"|   | **Total** | {len(p.outline.scenes)} | {totals['target']:,} | {totals['abridged']:,} | "
               f"{totals['manuscript']:,} |")
    if totals["manuscript"] and totals["abridged"]:
        out.append(f"\nAbridged/manuscript ratio: {totals['abridged'] / totals['manuscript']:.0%}")
    print("\n".join(out))
    return 0


def generate_bibliography_markdown(p: Project) -> Tuple[str, List[str], List[str]]:
    git, plan = p.git, p.plan
    dag = build_story_dag(p)

    active_facts: Set[str] = set()
    for sid in p.outline.scenes:
        sec = plan.defs.get(sid)
        if sec:
            for rid in sec.ref_ids():
                if rid.startswith("FCT-"):
                    active_facts.add(rid)
        for a in ancestors(plan, sid):
            for rid in a.ref_ids():
                if rid.startswith("FCT-"):
                    active_facts.add(rid)

    for nid in dag.nodes:
        if nid.startswith("FCT-"):
            active_facts.add(nid)
        sec = plan.defs.get(nid)
        if sec:
            for rid in sec.ref_ids():
                if rid.startswith("FCT-"):
                    active_facts.add(rid)

    active_sources: Dict[str, Set[str]] = {}
    for fid in sorted(active_facts):
        fsec = plan.defs.get(fid)
        if not fsec:
            continue
        for rid in fsec.ref_ids():
            if rid.startswith("SRC-"):
                active_sources.setdefault(rid, set()).add(fid)

    by_type: Dict[str, List[Tuple[str, Section, Set[str]]]] = {}
    for s_id, f_ids in active_sources.items():
        s_sec = plan.defs.get(s_id)
        if not s_sec:
            continue
        stype = (s_sec.field_value("type") or "other").strip().title()
        by_type.setdefault(stype, []).append((s_id, s_sec, f_ids))

    lines = ["# Bibliography", ""]

    if not active_sources:
        lines.append("*(No historical or empirical sources attached to active story elements.)*")
    else:
        for stype in sorted(by_type):
            lines.append(f"## {stype} Sources")
            lines.append("")
            for s_id, s_sec, f_ids in sorted(by_type[stype], key=lambda t: t[1].title):
                citation = s_sec.field_value("citation") or s_sec.title
                url = s_sec.field_value("url")
                accessed = s_sec.field_value("accessed")
                supported = ", ".join(sorted(f"[[{fid}]]" for fid in f_ids))

                line = f"- **{s_id}**: {citation}."
                if url:
                    line += f" <{url}>"
                if accessed:
                    line += f" (accessed {accessed})."
                if supported:
                    line += f" *[Supports: {supported}]*"
                lines.append(line)
            lines.append("")

    return "\n".join(lines).strip(), sorted(active_facts), sorted(active_sources.keys())


def cmd_bibliography(git: Git, args) -> int:
    p = load_project(git)
    md_text, facts, sources = generate_bibliography_markdown(p)
    if args.json:
        emit_json({
            "activeFacts": facts,
            "activeSources": sources,
            "markdown": md_text,
        })
        return 0
    if args.output:
        out_p = Path(args.output)
        if not out_p.is_absolute():
            out_p = git.root / out_p
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(md_text + "\n", encoding="utf-8")
        print(f"Wrote bibliography to {out_p.relative_to(git.root).as_posix()} ({len(sources)} sources cited by {len(facts)} facts)")
    else:
        print(md_text)
    return 0


def parse_publication_style(style_text: str) -> dict:
    """Extract publication, typography, and book design specifications from story/style.md."""
    config = {
        "formats": ["epub", "pdf"],
        "trim_size": "5.5in x 8.5in",
        "inner_margin": "0.75in",
        "outer_margin": "0.5in",
        "top_margin": "0.75in",
        "bottom_margin": "0.75in",
        "body_font": "EB Garamond",
        "heading_font": "Cinzel",
        "font_size": "11pt",
        "line_height": "1.35",
        "paragraph_indent": "1.25em",
        "scene_break": "* * *",
        "chapter_openings": "recto",
        "drop_caps": True,
        "toc_depth": 2,
        "cover_asset": None,
        "hyphenation": True,
        "justification": True,
        "running_headers": "recto-verso",
    }
    if not style_text:
        return config

    m_sec = re.search(
        r"^#{1,3}\s+Publication(?:\s+&|\s+and)?\s+(?:Book\s+Design\s+)?Guidelines\b.*?(?=\n#{1,2}\s+|\Z)",
        style_text,
        re.I | re.M | re.S,
    )
    target_text = m_sec.group(0) if m_sec else style_text

    field_map = {
        "trim_size": r"(?:trim[-_\s]*size|paper[-_\s]*size|page[-_\s]*size)",
        "inner_margin": r"(?:inner[-_\s]*margin|gutter(?:[-_\s]*margin)?)",
        "outer_margin": r"outer[-_\s]*margin",
        "top_margin": r"top[-_\s]*margin",
        "bottom_margin": r"bottom[-_\s]*margin",
        "body_font": r"(?:body[-_\s]*font(?:[-_\s]*family)?|main[-_\s]*font)",
        "heading_font": r"(?:heading[-_\s]*font(?:[-_\s]*family)?|display[-_\s]*font)",
        "font_size": r"(?:font[-_\s]*size|body[-_\s]*size|base[-_\s]*size)",
        "line_height": r"(?:line[-_\s]*height|leading|linestretch)",
        "paragraph_indent": r"(?:paragraph[-_\s]*indent|first[-_\s]*line[-_\s]*indent|indent)",
        "scene_break": r"(?:scene[-_\s]*break(?:[-_\s]*ornament)?|divider(?:[-_\s]*glyph)?)",
        "chapter_openings": r"(?:chapter[-_\s]*openings?|opening[-_\s]*pages?)",
        "drop_caps": r"(?:drop[-_\s]*caps?|initial[-_\s]*caps?)",
        "toc_depth": r"(?:toc[-_\s]*depth|table[-_\s]*of[-_\s]*contents[-_\s]*depth)",
        "cover_asset": r"(?:cover(?:[-_\s]*asset|[-_\s]*image|[-_\s]*file)?)",
        "hyphenation": r"hyphenation",
        "justification": r"(?:justification|text[-_\s]*alignment)",
        "running_headers": r"(?:running[-_\s]*headers?(?:[-_\s]*&[-_\s]*footers?)?|headers?)",
    }

    for key, pattern in field_map.items():
        m = re.search(r"[-*]\s*\**" + pattern + r"(?:\**\s*:|\s*:\**)\s*([^\n#<]+)", target_text, re.I)
        if m:
            val = re.sub(r"^\**|\**$", "", m.group(1)).strip()
            if key in ("drop_caps", "hyphenation", "justification"):
                config[key] = val.lower() in ("true", "yes", "1", "enabled", "on", "3 lines", "2 lines")
            elif key == "toc_depth":
                try:
                    config[key] = int(re.search(r"\d+", val).group(0))
                except Exception:
                    pass
            elif key == "cover_asset":
                clean_cov = re.sub(r"[\[\]]", "", val).strip()
                if clean_cov.lower() not in ("none", "null", "false"):
                    config[key] = clean_cov
            elif key == "formats":
                config[key] = [f.strip().lower() for f in val.split(",") if f.strip()]
            else:
                config[key] = val

    m_marg = re.search(r"[-*]\s*\**margins?\**(?:\**\s*:|\s*:\**)\s*([^\n#<]+)", target_text, re.I)
    if m_marg:
        val = re.sub(r"^\**|\**$", "", m_marg.group(1)).strip()
        parts = [p.strip() for p in val.split(",")]
        if len(parts) == 4:
            config["top_margin"], config["bottom_margin"], config["inner_margin"], config["outer_margin"] = parts

    return config


def generate_epub_css(pub_conf: dict) -> str:
    """Generate modern, accessible EPUB stylesheet customized from publication guidelines."""
    body_font = pub_conf.get("body_font", "EB Garamond")
    heading_font = pub_conf.get("heading_font", "Cinzel")
    line_height = pub_conf.get("line_height", "1.35")
    indent = pub_conf.get("paragraph_indent", "1.25em")
    justified = "justify" if pub_conf.get("justification", True) else "left"
    hyphens = "auto" if pub_conf.get("hyphenation", True) else "manual"

    return f"""/* SpecNovelist EPUB Stylesheet - Generated from story/style.md */
@charset "utf-8";

body {{
    margin: 5% 5%;
    padding: 0;
    font-family: "{body_font}", "Georgia", serif;
    line-height: {line_height};
    text-align: {justified};
    -webkit-hyphens: {hyphens};
    -moz-hyphens: {hyphens};
    -ms-hyphens: {hyphens};
    hyphens: {hyphens};
}}

/* Paragraph formatting */
p {{
    margin: 0;
    text-indent: {indent};
}}

/* Unindented first paragraphs */
h1 + p, h2 + p, h3 + p, hr + p, .scene-break + p {{
    text-indent: 0;
}}

/* Headings */
h1, h2, h3, h4 {{
    font-family: "{heading_font}", "{body_font}", serif;
    font-weight: normal;
    text-align: center;
    page-break-inside: avoid;
    break-inside: avoid;
}}

h1 {{
    margin-top: 3em;
    margin-bottom: 1.5em;
    font-size: 1.8em;
    page-break-before: always;
    break-before: page;
}}

h2 {{
    margin-top: 2.5em;
    margin-bottom: 1.2em;
    font-size: 1.4em;
    page-break-before: always;
    break-before: page;
}}

h3 {{
    margin-top: 1.5em;
    margin-bottom: 0.8em;
    font-size: 1.15em;
}}

/* Scene breaks */
.scene-break, hr {{
    border: none;
    text-align: center;
    margin: 1.8em auto;
    letter-spacing: 0.25em;
    color: inherit;
    font-size: 1em;
}}

/* Figures and Illustrations */
figure, img {{
    max-width: 100%;
    height: auto;
    display: block;
    margin: 1.5em auto;
    page-break-inside: avoid;
    break-inside: avoid;
}}

figcaption {{
    font-size: 0.85em;
    font-style: italic;
    text-align: center;
    margin-top: 0.5em;
}}

/* Front and Back matter */
.foreword, .glossary, .bibliography, .acknowledgements {{
    page-break-before: always;
    break-before: page;
}}
"""


def cmd_compile(git: Git, args) -> int:
    p = load_project(git)
    target_locale = getattr(args, "locale", None) or p.config.primary_language
    if args.layer == "manuscript" and target_locale in p.manuscript_locales and p.manuscript_locales[target_locale].scenes:
        d = p.manuscript_locales[target_locale]
    else:
        d = p.layers[args.layer]
    title = project_title(git)

    # Load publication and interior design guidelines from story/style.md
    style_p = git.root / STYLE_FILE
    style_text = style_p.read_text(encoding="utf-8", errors="replace") if style_p.is_file() else ""
    pub_conf = parse_publication_style(style_text)

    # Resolve scene break ornament
    scene_break = args.scene_break
    if scene_break == "* * *" and pub_conf.get("scene_break"):
        scene_break = pub_conf["scene_break"]

    # Resolve cover asset
    cover_file = None
    if getattr(args, "cover", None):
        c_cand = git.root / args.cover
        if c_cand.is_file():
            cover_file = c_cand
    elif pub_conf.get("cover_asset"):
        c_cand = git.root / pub_conf["cover_asset"]
        if c_cand.is_file():
            cover_file = c_cand
    if not cover_file:
        for loc_cand in (f"graphics/cover.{target_locale}.png", "graphics/cover.png", "graphics/cover.jpg"):
            c_cand = git.root / loc_cand
            if c_cand.is_file():
                cover_file = c_cand
                break

    # Construct rich metadata YAML front matter
    author_name = p.config.author_name or p.config.author_legal_name or ""
    out = ["---"]
    out.append(f"title: \"{title}\"")
    if p.config.subtitle:
        out.append(f"subtitle: \"{p.config.subtitle}\"")
    if author_name:
        out.append(f"author: \"{author_name}\"")
    out.append(f"lang: \"{target_locale}\"")
    out.append("documentclass: book")
    out.append("toc: true")
    out.append(f"toc-depth: {pub_conf.get('toc_depth', 2)}")

    # Geometry & typography for PDF
    trim = pub_conf.get("trim_size", "5.5in x 8.5in")
    trim_m = re.match(r"([\d\.]+(?:in|mm|cm|pt))\s*[xX*,\s]\s*([\d\.]+(?:in|mm|cm|pt))", trim)
    geom = []
    if trim_m:
        geom.append(f"paperwidth={trim_m.group(1)}")
        geom.append(f"paperheight={trim_m.group(2)}")
    elif trim.lower() in ("a5", "a4", "b6"):
        out.append(f"papersize: {trim.lower()}")

    geom.append(f"inner={pub_conf.get('inner_margin', '0.75in')}")
    geom.append(f"outer={pub_conf.get('outer_margin', '0.5in')}")
    geom.append(f"top={pub_conf.get('top_margin', '0.75in')}")
    geom.append(f"bottom={pub_conf.get('bottom_margin', '0.75in')}")
    out.append("geometry:")
    for g in geom:
        out.append(f"  - {g}")
    out.append(f"fontsize: {pub_conf.get('font_size', '11pt')}")
    out.append(f"mainfont: \"{pub_conf.get('body_font', 'EB Garamond')}\"")
    out.append(f"linestretch: {pub_conf.get('line_height', '1.35')}")
    if cover_file:
        out.append(f"cover-image: \"{cover_file.relative_to(git.root).as_posix()}\"")
    out.append("---")
    out.append("")

    # Optional Foreword
    if p.config.foreword_path:
        fwd_p = git.root / p.config.foreword_path
        if fwd_p.is_file():
            out += ["# Foreword", ""] + fwd_p.read_text(encoding="utf-8").splitlines() + [""]

    has_parts = bool(p.outline.parts)
    cur_part, part_no, missing = None, 0, []
    for n, cid in enumerate(p.outline.chapters, 1):
        part = p.outline.part_of.get(cid)
        if has_parts and part and part != cur_part:
            part_no += 1
            cur_part = part
            out += [f"# " + args.part_heading.format(n=part_no, N=num_words(part_no), title=p.plan.defs[part].title), ""]
        sids = [sid for sid in p.outline.by_chapter[cid] if sid in d.scenes]
        missing += [sid for sid in p.outline.by_chapter[cid] if sid not in d.scenes]
        if not sids:
            continue
        hashes = "##" if has_parts else "#"
        out += [f"{hashes} " + args.chapter_heading.format(n=n, N=num_words(n), title=p.plan.defs[cid].title), ""]
        if cid in d.chapters:
            pre = clean_prose(d.chapters[cid].body)
            if pre:
                out += pre + [""]
        for i, sid in enumerate(sids):
            if i:
                out += [scene_break, ""]
            out += clean_prose(d.scenes[sid].body) + [""]

    # Optional Glossary
    if p.config.include_glossary:
        glossary_items = p.plan.of_type("GLS")
        if glossary_items:
            out += ["# Glossary", ""]
            for item in sorted(glossary_items, key=lambda it: it.title):
                loc_filter = (item.field_value("locale", "locales") or "all").lower()
                if loc_filter not in ("all", "global", target_locale.lower()):
                    continue
                defn = item.field_value("definition") or "\n".join(item.body).strip()
                pron = item.field_value("pronunciation")
                pron_str = f" *({pron})*" if pron else ""
                out.append(f"- **{item.title}**{pron_str}: {defn}")
            out.append("")

    # Optional Bibliography
    if p.config.include_bibliography:
        bib_md, _, _ = generate_bibliography_markdown(p)
        out += [bib_md, ""]

    # Mandatory Acknowledgements (stored verbatim from acknowledgements.md)
    ack_path = p.config.acknowledgments_path or ACKNOWLEDGEMENTS_FILE
    ack_file = git.root / ack_path
    if not ack_file.is_file():
        fallback = git.root / "story/acknowledgments.md" if "acknowledgements" in ack_path else git.root / "story/acknowledgements.md"
        if fallback.is_file():
            ack_file = fallback
    if ack_file.is_file():
        ack_text = ack_file.read_text(encoding="utf-8", errors="replace").strip()
        if ack_text:
            out += [ack_text, ""]

    dst_dir = git.root / BUILD
    dst_dir.mkdir(exist_ok=True)
    suffix = f".{target_locale}" if args.layer == "manuscript" and len(p.config.target_languages) > 1 else ""
    md = dst_dir / f"{args.layer}{suffix}.md"
    md.write_text("\n".join(out), encoding="utf-8")
    words = sum(word_count(s.body) for s in d.scenes.values())
    print(f"Wrote {md.relative_to(git.root).as_posix()} ({words:,} words)")
    if missing:
        print(f"Note: {len(missing)} outline scene(s) not yet written in {args.layer}/ were skipped.")

    # Generate companion EPUB stylesheet
    css_content = generate_epub_css(pub_conf)
    css_path = dst_dir / "epub.css"
    css_path.write_text(css_content, encoding="utf-8")

    if args.format != "md":
        pandoc = shutil.which("pandoc")
        if not pandoc:
            raise NovelError(
                f"pandoc is required for --format {args.format} (https://pandoc.org)\n"
                f"Compiled Markdown source written to: {md.relative_to(git.root).as_posix()}\n"
                f"Generated EPUB stylesheet written to: {css_path.relative_to(git.root).as_posix()}"
            )
        dst = dst_dir / f"{args.layer}{suffix}.{args.format}"
        cmd = [pandoc, str(md), "-o", str(dst)]
        if args.format == "epub":
            custom_css = getattr(args, "css", None)
            use_css = (git.root / custom_css) if custom_css else css_path
            if use_css.is_file():
                cmd.extend(["--css", str(use_css)])
            if cover_file and cover_file.is_file():
                cmd.extend(["--epub-cover-image", str(cover_file)])
            cmd.extend(["--toc", f"--toc-depth={pub_conf.get('toc_depth', 2)}"])
        elif args.format == "pdf":
            engine = getattr(args, "pdf_engine", None)
            if not engine:
                for cand in ("xelatex", "lualatex", "pdflatex", "weasyprint", "typst"):
                    if shutil.which(cand):
                        engine = cand
                        break
            if engine:
                cmd.extend([f"--pdf-engine={engine}"])
        try:
            subprocess.run(cmd, check=True)
            print(f"Wrote {dst.relative_to(git.root).as_posix()}")
        except subprocess.CalledProcessError as e:
            raise NovelError(f"pandoc conversion to {args.format} failed (exit code {e.returncode}). Check LaTeX/PDF engine installation.")
    return 0


def cmd_log(git: Git, args) -> int:
    if not git.has_commits():
        print("No commits yet.")
        return 0
    keys = ",".join(f"key={k}" for k in (TRAILER, "Novel-Model", "Novel-GFX-Sync", "Novel-Added", "Novel-Modified", "Novel-Removed",
                                         "Novel-Abridged-Updated", "Novel-Abridged-Removed",
                                         "Novel-Manuscript-Updated", "Novel-Manuscript-Removed"))
    out = git.lines("log", "--extended-regexp", f"--grep=^{TRAILER}:", f"--format=%h %cs %s%n%(trailers:{keys})", "HEAD")
    print("\n".join(out) if out else "No sync commits yet.")
    return 0


def cmd_models(git: Git, args) -> int:
    p = load_project(git)
    models = get_contributing_ai_models(git, p)
    ack_path = p.config.acknowledgments_path or ACKNOWLEDGEMENTS_FILE
    ack_file = git.root / ack_path
    if not ack_file.is_file():
        fallback = git.root / "story/acknowledgments.md" if "acknowledgements" in ack_path else git.root / "story/acknowledgements.md"
        if fallback.is_file():
            ack_file = fallback
            ack_path = fallback.relative_to(git.root).as_posix()
    ack_text = ack_file.read_text(encoding="utf-8", errors="replace") if ack_file.is_file() else ""
    norm_ack = normalize_model_text(ack_text)

    records = []
    for m in sorted(models):
        acknowledged = model_mentioned_in_text(m, ack_text, norm_ack)
        records.append({"model": m, "acknowledged": acknowledged})

    if getattr(args, "json", False):
        emit_json({"models": records, "acknowledgements_file": ack_path, "all_acknowledged": all(r["acknowledged"] for r in records) if records else True})
        return 0

    if not records:
        print(f"No contributing AI models tracked yet in git history or configuration.")
        print(f"Acknowledgements file: {ack_path}")
        return 0

    print(f"Tracked Contributing AI Models ({len(records)} total):")
    for r in records:
        status = "ACKNOWLEDGED" if r["acknowledged"] else "MISSING FROM ACKNOWLEDGEMENTS"
        print(f"  - {r['model']}: [{status}]")
    if not all(r["acknowledged"] for r in records):
        print(f"\nWarning: Some AI models are missing from '{ack_path}'. Run 'specnovel.py check' for details.")
        return 1
    return 0


def cmd_feedback(git: Git, args) -> int:
    p = load_project(git)
    plan, o = p.plan, p.outline
    edts = plan.of_type("EDT")

    target_filter = args.id
    status_filter = (args.status or "open").lower()
    stage_filter = (args.stage or "").lower()
    locale_filter = (getattr(args, "locale", None) or "").lower()

    matched: List[Section] = []
    for s in edts:
        st = (s.field_value("status") or "").lower()
        if status_filter != "all" and st != status_filter:
            continue
        stage = (s.field_value("stage") or "").lower()
        if stage_filter and stage_filter != "all" and stage != "all" and stage != stage_filter:
            continue
        loc = (s.field_value("locale", "lang", "language") or "all").lower()
        if locale_filter and locale_filter != "all" and loc not in ("all", "global", locale_filter):
            continue
        if target_filter:
            if target_filter == s.id:
                matched.append(s)
                continue
            target_val = s.field_value("target") or ""
            if target_filter in target_val or target_filter in s.ref_ids():
                matched.append(s)
                continue
            if target_filter in o.scenes:
                cid = o.chapter_of.get(target_filter)
                if cid and (cid in target_val or cid in s.ref_ids()):
                    matched.append(s)
                    continue
        else:
            matched.append(s)

    if args.json:
        data = []
        for s in matched:
            data.append({
                "id": s.id,
                "title": s.title,
                "target": s.field_value("target"),
                "stage": s.field_value("stage"),
                "status": s.field_value("status"),
                "locale": s.field_value("locale") or "all",
                "file": s.file,
                "text": s.text
            })
        emit_json(data)
        return 0

    if not matched:
        scope = f" matching '{target_filter}'" if target_filter else ""
        print(f"No {status_filter} editorial directives found{scope}.")
        return 0

    if target_filter and len(matched) == 1 and matched[0].id == target_filter:
        print(matched[0].text)
        return 0

    out = ["| ID | Target | Stage | Status | Locale | Title |",
           "|----|--------|-------|--------|--------|-------|"]
    for s in matched:
        tgt = s.field_value("target") or "-"
        stg = s.field_value("stage") or "-"
        st = s.field_value("status") or "-"
        loc = s.field_value("locale") or "all"
        out.append(f"| {s.id} | {tgt} | {stg} | {st} | {loc} | {s.title} |")
    print("\n".join(out))
    return 0


def cmd_placeholders(git: Git, args) -> int:
    p = load_project(git)
    target = getattr(args, "path", None)
    items = scan_placeholders(p, target)
    untracked = [item for item in items if item.tracked_by is None]

    if getattr(args, "create_rq", False):
        if not untracked:
            print("All detected placeholders are already tracked by research questions.")
            return 0

        new_ids = allocate_next_ids(git, "RQ", len(untracked))
        rq_blocks = []
        created_info = []

        for rq_id, item in zip(new_ids, untracked):
            if getattr(args, "priority", None):
                priority = args.priority
            else:
                sec_ids = {occ.section_id for occ in item.occurrences if occ.section_id}
                is_high = any(sid.startswith(("CHR-", "PLC-", "PLT-", "ORG-", "OBJ-")) for sid in sec_ids)
                high_keywords = {"name", "who", "when", "date", "year", "poison", "weapon", "kill", "murder",
                                 "father", "daughter", "mother", "son", "immigrant", "historical", "census"}
                if is_high or any(k in item.text.lower() for k in high_keywords):
                    priority = "high"
                else:
                    priority = "medium"

            sec_ids = sorted({occ.section_id for occ in item.occurrences if occ.section_id})
            if sec_ids:
                needed_for = ", ".join(f"[[{sid}]]" for sid in sec_ids)
            else:
                needed_for = ", ".join(sorted({occ.file for occ in item.occurrences}))

            if sec_ids and any(sid.startswith("CHR-") for sid in sec_ids):
                q = f"What are authentic period, demographic, and character details (including name, ethnicity, generation) for '{item.text}'?"
            elif sec_ids and any(sid.startswith("PLC-") for sid in sec_ids):
                q = f"What are historical, geographical, and sensory details for '{item.text}'?"
            elif sec_ids and any(sid.startswith("PLT-") for sid in sec_ids):
                q = f"What are historical constraints and causal details for plot element '{item.text}'?"
            elif any(k in item.text.lower() for k in {"date", "when", "year", "summer", "winter", "spring", "autumn", "fall", "18", "19", "month"}):
                q = f"What was the historical chronology, timeline, or seasonal context for '{item.text}'?"
            else:
                q = f"Determine authentic historical, technical, or narrative details for '{item.text}'."

            first_occ = item.occurrences[0]
            context = first_occ.context.replace("\n", " ").strip()

            block = f"""## {rq_id}: Research for {item.raw}
- **Status:** open
- **Priority:** {priority}
- **Needed for:** {needed_for}
- **Question:** {q}
- **Context:** {context}
- **Answer:**
- **Notes:** Automatically generated from placeholder in {first_occ.file}:{first_occ.line}"""
            rq_blocks.append(block)
            created_info.append({"id": rq_id, "placeholder": item.raw, "needed_for": needed_for, "priority": priority})

        q_file = git.root / "kb" / "research" / "questions.md"
        q_file.parent.mkdir(parents=True, exist_ok=True)
        if q_file.exists():
            existing = q_file.read_text(encoding="utf-8")
            sep = "\n\n" if existing.strip() else ""
            new_content = existing.rstrip() + sep + "\n\n".join(rq_blocks) + "\n"
        else:
            new_content = "# Research Questions\n\n" + "\n\n".join(rq_blocks) + "\n"
        q_file.write_text(new_content, encoding="utf-8")

        if getattr(args, "json", False):
            emit_json({"created": created_info, "file": "kb/research/questions.md"})
            return 0

        print(f"Generated {len(created_info)} research question(s) in kb/research/questions.md:\n")
        for ci in created_info:
            print(f"  + {ci['id']}: Research for {ci['placeholder']} ({ci['priority']} priority, needed for {ci['needed_for']})")
        print("\nUpdated kb/research/questions.md.")
        print("Run 'python scripts/specnovel.py check' to verify catalog integrity.")
        return 0

    if getattr(args, "json", False):
        data = []
        for item in items:
            data.append({
                "raw": item.raw,
                "text": item.text,
                "kind": item.kind,
                "tracked_by": item.tracked_by,
                "occurrences": [{"file": o.file, "line": o.line, "section_id": o.section_id, "context": o.context} for o in item.occurrences]
            })
        emit_json(data)
        return 0

    if not items:
        print("No placeholders detected in project specifications.")
        return 0

    print("# Placeholders detected in project specifications:\n")
    for item in items:
        status_str = f"TRACKED by [[{item.tracked_by}]]" if item.tracked_by else "UNTRACKED"
        locs = ", ".join(f"{o.file}:{o.line}" + (f" (in [[{o.section_id}]])" if o.section_id else "") for o in item.occurrences)
        print(f"  {item.raw}")
        print(f"    Locations: {locs}")
        print(f"    Status:    {status_str}\n")

    if untracked:
        print(f"{len(untracked)} untracked placeholder(s) found out of {len(items)} total.")
        print("Run 'python scripts/specnovel.py placeholders --create-rq' to automatically generate research questions in kb/research/questions.md.")
    else:
        print(f"All {len(items)} detected placeholder(s) are tracked by research questions.")
    return 0


# ------------------------------------------------------------------ harvest, scenario, audit, takes
STOPWORDS_LOWER = {
    "the", "a", "an", "this", "that", "these", "those", "he", "she", "it", "they", "we", "you", "i",
    "his", "her", "their", "our", "my", "your", "its", "then", "there", "here", "what", "where", "when",
    "why", "how", "who", "whom", "whose", "if", "as", "while", "after", "before", "once", "since",
    "until", "although", "though", "even", "because", "but", "and", "or", "so", "yet", "for", "nor",
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    "january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
    "november", "december", "mr", "mrs", "ms", "miss", "dr", "sir", "madam", "lady", "lord", "captain",
    "suddenly", "meanwhile", "later", "yesterday", "today", "tomorrow", "tonight", "everybody", "everyone",
    "somebody", "someone", "nobody", "no one", "everything", "something", "nothing"
}


def extract_entities_and_beats_from_prose(text: str, p: Project) -> Dict[str, Any]:
    words = WORD_RE.findall(text)
    total_words = len(words)

    # 1. Candidate title
    title_match = re.search(r"^(?:#{1,3})\s+(?:(?:SCN-\d+[:\s]+)?(.+)|(.+))", text, re.M)
    if title_match:
        candidate_title = (title_match.group(1) or title_match.group(2) or "").strip()
    else:
        first_line = next((l.strip() for l in text.splitlines() if l.strip()), "Harvested Scene")
        first_line = re.sub(r"^[#\s\-*]+", "", first_line)
        candidate_title = first_line[:40].strip()

    # 2. Dialogues
    dialogues: List[str] = []
    d_matches = re.findall(r'["“]([^"”]+)["”]', text)
    for dm in d_matches:
        dm_clean = dm.strip()
        if len(dm_clean.split()) >= 2:
            dialogues.append(dm_clean)

    # 3. Characters
    attr_verbs = (
        r"(?:said|asked|replied|answered|whispered|muttered|shouted|yelled|cried|sighed|"
        r"gasped|groaned|laughed|chuckled|nodded|repeated|insisted|snapped|murmured)"
    )
    char_candidates: Set[str] = set()

    for m in re.finditer(rf'["”]\s*{attr_verbs}\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)', text, re.I):
        name = m.group(1).strip()
        if name.lower() not in STOPWORDS_LOWER:
            char_candidates.add(name)

    for m in re.finditer(rf'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+{attr_verbs}\b', text):
        name = m.group(1).strip()
        if name.lower() not in STOPWORDS_LOWER:
            char_candidates.add(name)

    if len(char_candidates) < 2:
        for m in re.finditer(r'\b([A-Z][a-z]{2,}\s+[A-Z][a-z]{2,})\b', text):
            cand = m.group(1).strip()
            w1, w2 = cand.split(maxsplit=1)
            if w1.lower() not in STOPWORDS_LOWER and w2.lower() not in STOPWORDS_LOWER:
                char_candidates.add(cand)

    # 4. Places
    place_candidates: Set[str] = set()
    place_suffixes = (
        r"(?:Street|Avenue|Road|Boulevard|Lane|Tower|Castle|Room|Hall|Bridge|"
        r"Station|Harbor|Port|Forest|Mountain|City|Town|Village|Cafe|Bar|Pub|Library|Office|Chamber|Palace|Hotel|Inn)"
    )
    for m in re.finditer(rf'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+{place_suffixes})\b', text):
        place_candidates.add(m.group(1).strip())

    for m in re.finditer(r'\b(?:in|at|to|into|inside)\s+(?:the\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b', text):
        cand = m.group(1).strip()
        if cand.lower() not in STOPWORDS_LOWER and cand not in char_candidates:
            place_candidates.add(cand)

    # 5. Beats
    raw_paras = [pr.strip() for pr in re.split(r'\n\s*\n', text) if pr.strip()]
    beats: List[str] = []
    for p_text in raw_paras:
        if p_text.startswith("#") or p_text.startswith("***") or p_text.startswith("---"):
            continue
        first_sent = re.split(r'(?<=[.!?])\s+', p_text)[0].strip()
        first_sent = re.sub(r'^[#>\-\*\s"]+', '', first_sent)
        if len(first_sent) > 120:
            first_sent = first_sent[:117] + "..."
        if len(first_sent) > 15:
            beats.append(first_sent)
        if len(beats) >= 8:
            break

    return {
        "word_count": total_words,
        "candidate_title": candidate_title,
        "characters": sorted(char_candidates),
        "places": sorted(place_candidates),
        "dialogues": dialogues,
        "beats": beats
    }


def cmd_harvest(git: Git, args) -> int:
    p = load_project(git)
    draft_file = args.draft_file
    if draft_file == "-":
        raw_text = sys.stdin.read()
        source_label = "stdin"
    else:
        path = (git.root / draft_file).resolve()
        if not path.is_file():
            print(f"specnovel: draft file not found: {draft_file}", file=sys.stderr)
            return 1
        raw_text = path.read_text(encoding="utf-8", errors="replace")
        source_label = str(draft_file)

    harvest_data = extract_entities_and_beats_from_prose(raw_text, p)

    mode = "batch"
    if getattr(args, "interactive", False):
        mode = "interactive"
    elif getattr(args, "batch", False):
        mode = "batch"
    elif getattr(p.config, "harvest_mode", "batch") == "interactive":
        mode = "interactive"

    if mode == "interactive" and sys.stdin.isatty():
        print(f"\nHarvested draft analysis for '{source_label}':")
        print(f"  Word count:           {harvest_data['word_count']}")
        print(f"  Extracted Characters: {', '.join(harvest_data['characters']) or 'None'}")
        print(f"  Extracted Places:     {', '.join(harvest_data['places']) or 'None'}")
        print(f"  Identified Beats:     {len(harvest_data['beats'])}")
        print(f"  Key Dialogues:        {len(harvest_data['dialogues'])}")
        ans = input("\nProceed with scaffolding entities and candidate scene? [y/N]: ").strip().lower()
        if ans not in ("y", "yes"):
            print("Harvest canceled.")
            return 0

    created_files = []
    applied = False

    if getattr(args, "apply", False):
        applied = True
        char_links = []
        for cname in harvest_data["characters"]:
            existing_chr = None
            for s in p.plan.of_type("CHR"):
                if cname.lower() in s.title.lower() or cname.lower() in s.text.lower():
                    existing_chr = s.id
                    break
            if existing_chr:
                char_links.append(f"[[{existing_chr}|{cname}]]")
            else:
                cid = allocate_next_ids(git, "CHR", 1)[0]
                cpath = git.root / f"kb/characters/{cid}.md"
                cpath.parent.mkdir(parents=True, exist_ok=True)
                cpath.write_text(
                    f"# {cid}: {cname}\n- **Category:** Secondary\n- **Status:** Provisional (Harvested)\n- **Aliases:** {cname}\n\n## Overview\nProvisional character entity harvested from draft `{source_label}`.\n",
                    encoding="utf-8"
                )
                char_links.append(f"[[{cid}|{cname}]]")
                created_files.append(f"kb/characters/{cid}.md")

        place_links = []
        for pname in harvest_data["places"]:
            existing_plc = None
            for s in p.plan.of_type("PLC"):
                if pname.lower() in s.title.lower() or pname.lower() in s.text.lower():
                    existing_plc = s.id
                    break
            if existing_plc:
                place_links.append(f"[[{existing_plc}|{pname}]]")
            else:
                pid = allocate_next_ids(git, "PLC", 1)[0]
                ppath = git.root / f"kb/places/{pid}.md"
                ppath.parent.mkdir(parents=True, exist_ok=True)
                ppath.write_text(
                    f"# {pid}: {pname}\n- **Category:** Setting\n- **Status:** Provisional (Harvested)\n\n## Overview\nProvisional place entity harvested from draft `{source_label}`.\n",
                    encoding="utf-8"
                )
                place_links.append(f"[[{pid}|{pname}]]")
                created_files.append(f"kb/places/{pid}.md")

        primary_place = place_links[0] if place_links else "[[PLC-001]]"

        sid = allocate_next_ids(git, "SCN", 1)[0]
        stitle = getattr(args, "title", None) or harvest_data["candidate_title"] or f"Harvested Scene ({sid})"

        chap_id = getattr(args, "chapter", None)
        if not chap_id:
            if p.outline.chapters:
                chap_id = p.outline.chapters[-1]
            else:
                chap_id = allocate_next_ids(git, "CHP", 1)[0]

        beats_md = "\n".join(f"  - {b}" for b in harvest_data["beats"]) if harvest_data["beats"] else "  - Scene progression unfolds"
        dialogues_md = "\n".join(f"  - \"{d}\"" for d in harvest_data["dialogues"][:5]) if harvest_data["dialogues"] else "  - None captured"

        scene_spec = (
            f"\n\n### {sid}: {stitle}\n"
            f"- **Status:** draft\n"
            f"- **Function:** causal-progression\n"
            f"- **When:** provisional\n"
            f"- **Where:** {primary_place}\n"
            f"- **Cast:** {', '.join(char_links) or 'provisional'}\n"
            f"- **Goal / conflict / outcome:** G: provisional goal / C: provisional conflict / O: provisional outcome\n"
            f"- **Target words:** {harvest_data['word_count']}\n"
            f"- **Beats:**\n{beats_md}\n"
            f"- **Key dialogue:**\n{dialogues_md}\n"
        )
        outline_file = git.root / "outline" / "outline.md"
        if outline_file.is_file():
            existing_outline = outline_file.read_text(encoding="utf-8")
            outline_file.write_text(existing_outline + scene_spec, encoding="utf-8")
        else:
            outline_file.parent.mkdir(parents=True, exist_ok=True)
            outline_file.write_text(f"# Outline\n\n## {chap_id}: Chapter\n{scene_spec}", encoding="utf-8")
        created_files.append("outline/outline.md")

        abridged_file = git.root / "abridged" / f"{chap_id}.md"
        abridged_file.parent.mkdir(parents=True, exist_ok=True)
        scene_body = raw_text.strip()
        if abridged_file.is_file():
            current_ab = abridged_file.read_text(encoding="utf-8")
            abridged_file.write_text(current_ab + f"\n\n### {sid}: {stitle}\n\n{scene_body}\n", encoding="utf-8")
        else:
            abridged_file.write_text(f"# {chap_id}: Chapter\n\n### {sid}: {stitle}\n\n{scene_body}\n", encoding="utf-8")
        created_files.append(f"abridged/{chap_id}.md")

    if getattr(args, "json", False):
        out = {
            "source": source_label,
            "word_count": harvest_data["word_count"],
            "entities": {
                "characters": harvest_data["characters"],
                "places": harvest_data["places"],
            },
            "dialogue_count": len(harvest_data["dialogues"]),
            "dialogues": harvest_data["dialogues"][:10],
            "beats": harvest_data["beats"],
            "candidate_title": harvest_data["candidate_title"],
            "applied": applied,
            "created_files": created_files
        }
        print(json.dumps(out, indent=2))
        return 0

    print(f"SpecNovelist Prose Harvest: {source_label}")
    print(f"  Word count:           {harvest_data['word_count']}")
    print(f"  Characters extracted: {', '.join(harvest_data['characters']) or 'none'}")
    print(f"  Places extracted:     {', '.join(harvest_data['places']) or 'none'}")
    print(f"  Beats extracted:      {len(harvest_data['beats'])}")
    print(f"  Dialogues extracted:  {len(harvest_data['dialogues'])}")
    if applied:
        print("\nApplied harvest to project:")
        for f in created_files:
            print(f"  + {f}")
    else:
        print("\nDry-run mode (use --apply to scaffold KB entries, outline scene, and abridged draft).")
    return 0


def cmd_scenario(git: Git, args) -> int:
    action = args.action
    scenarios_dir = git.root / "story" / "scenarios"

    if action == "list":
        scenarios = []
        if scenarios_dir.is_dir():
            for sp in sorted(scenarios_dir.iterdir()):
                if sp.is_dir() and not sp.name.startswith("."):
                    notes_file = sp / "notes.md"
                    desc, status, created = "", "active", ""
                    if notes_file.is_file():
                        nt = notes_file.read_text(encoding="utf-8", errors="replace")
                        m_desc = re.search(r"[-*]\s*\*\*Description:\*\*\s*(.+)", nt)
                        if m_desc: desc = m_desc.group(1).strip()
                        m_stat = re.search(r"[-*]\s*\*\*Status:\*\*\s*(.+)", nt)
                        if m_stat: status = m_stat.group(1).strip()
                        m_cr = re.search(r"[-*]\s*\*\*Created:\*\*\s*(.+)", nt)
                        if m_cr: created = m_cr.group(1).strip()
                    outline_exists = (sp / "outline.md").is_file()
                    scenarios.append({
                        "name": sp.name,
                        "status": status,
                        "description": desc,
                        "created": created,
                        "has_outline": outline_exists,
                        "path": f"story/scenarios/{sp.name}"
                    })
        if getattr(args, "json", False):
            print(json.dumps(scenarios, indent=2))
            return 0
        if not scenarios:
            print("No scenarios found in story/scenarios/.")
            return 0
        print(f"{'SCENARIO':<20} {'STATUS':<12} {'DESCRIPTION'}")
        print("-" * 65)
        for s in scenarios:
            print(f"{s['name']:<20} {s['status']:<12} {s['description']}")
        return 0

    if not args.name:
        print(f"specnovel: scenario name required for '{action}'", file=sys.stderr)
        return 1

    name = args.name
    target_dir = scenarios_dir / name

    if action == "create":
        if target_dir.is_dir():
            print(f"specnovel: scenario '{name}' already exists at story/scenarios/{name}", file=sys.stderr)
            return 1
        target_dir.mkdir(parents=True, exist_ok=True)
        cur_outline = git.root / "outline" / "outline.md"
        if cur_outline.is_file():
            shutil.copy2(cur_outline, target_dir / "outline.md")
        else:
            (target_dir / "outline.md").write_text("# Outline\n", encoding="utf-8")

        now_str = datetime.now().isoformat()
        desc = args.message or f"Exploratory scenario: {name}"
        head_sha = (git.run("rev-parse", "HEAD", allow_fail=True) or "")[:8] if git.has_commits() else "uncommitted"
        notes_content = (
            f"# Scenario: {name}\n\n"
            f"- **Created:** {now_str}\n"
            f"- **Description:** {desc}\n"
            f"- **Base Commit:** {head_sha}\n"
            f"- **Status:** active\n\n"
            f"## Scenario Notes\n"
            f"Record premise alterations, alternate character fates, and divergent plot trajectories here.\n"
        )
        (target_dir / "notes.md").write_text(notes_content, encoding="utf-8")
        if getattr(args, "json", False):
            print(json.dumps({"scenario": name, "created": True, "path": f"story/scenarios/{name}"}))
        else:
            print(f"Created scenario '{name}' at story/scenarios/{name}/")
        return 0

    if not target_dir.is_dir():
        print(f"specnovel: scenario '{name}' not found at story/scenarios/{name}", file=sys.stderr)
        return 1

    scen_outline = target_dir / "outline.md"
    main_outline = git.root / "outline" / "outline.md"

    if action == "diff":
        scen_txt = scen_outline.read_text(encoding="utf-8", errors="replace") if scen_outline.is_file() else ""
        main_txt = main_outline.read_text(encoding="utf-8", errors="replace") if main_outline.is_file() else ""
        diff_lines = list(difflib.unified_diff(
            main_txt.splitlines(keepends=True),
            scen_txt.splitlines(keepends=True),
            fromfile="outline/outline.md (main)",
            tofile=f"story/scenarios/{name}/outline.md",
        ))
        if getattr(args, "json", False):
            print(json.dumps({"scenario": name, "diff": "".join(diff_lines), "has_diff": bool(diff_lines)}))
            return 0
        if not diff_lines:
            print(f"No differences between main outline and scenario '{name}'.")
        else:
            sys.stdout.writelines(diff_lines)
        return 0

    if action == "activate":
        if not scen_outline.is_file():
            print(f"specnovel: scenario '{name}' has no outline.md", file=sys.stderr)
            return 1
        backup_file = scenarios_dir / ".previous_main_outline.md"
        if main_outline.is_file():
            shutil.copy2(main_outline, backup_file)
        shutil.copy2(scen_outline, main_outline)
        if getattr(args, "json", False):
            print(json.dumps({"scenario": name, "activated": True}))
        else:
            print(f"Activated scenario '{name}': outline/outline.md replaced with scenario outline.")
            print("Previous outline backed up to story/scenarios/.previous_main_outline.md")
        return 0

    if action == "merge":
        if not scen_outline.is_file():
            print(f"specnovel: scenario '{name}' has no outline.md", file=sys.stderr)
            return 1
        shutil.copy2(scen_outline, main_outline)
        notes_file = target_dir / "notes.md"
        if notes_file.is_file():
            nt = notes_file.read_text(encoding="utf-8")
            nt = re.sub(r"(\*\*Status:\*\*)\s*[^\n]+", r"\1 merged", nt)
            notes_file.write_text(nt, encoding="utf-8")
        if getattr(args, "json", False):
            print(json.dumps({"scenario": name, "merged": True}))
        else:
            print(f"Merged scenario '{name}' into outline/outline.md.")
        return 0

    if action == "delete":
        shutil.rmtree(target_dir)
        if getattr(args, "json", False):
            print(json.dumps({"scenario": name, "deleted": True}))
        else:
            print(f"Deleted scenario '{name}' from story/scenarios/{name}.")
        return 0

    return 0


# ------------------------------------------------------------------ metrics & telemetry
SENSORY_LEXICON = {
    "visual": {
        "see", "saw", "sight", "look", "looked", "glance", "glanced", "stare", "stared", "peer", "peered",
        "gleam", "gleamed", "glow", "glowed", "shadow", "shadows", "dark", "darkness", "light", "bright",
        "color", "crimson", "pale", "shimmer", "flash", "flicker", "silhouette", "behold", "dim", "dusk",
        "dawn", "glint", "shine", "shining", "obscure", "vivid", "hazy", "gleaming", "glisten", "glistening"
    },
    "auditory": {
        "hear", "heard", "sound", "sounds", "listen", "listened", "echo", "echoes", "whisper", "whispered",
        "shout", "shouted", "scream", "screamed", "cry", "cried", "rustle", "click", "clatter", "clang",
        "roar", "rumble", "thud", "buzz", "hum", "chime", "groan", "groaned", "hiss", "creak", "muffled",
        "silence", "deafening", "murmur", "murmured", "crack", "snap", "rattle", "shriek", "screech"
    },
    "tactile": {
        "touch", "touched", "felt", "cold", "hot", "warm", "warmth", "chill", "chilly", "freeze", "freezing",
        "rough", "smooth", "sharp", "prick", "shiver", "shivering", "tremble", "trembling", "shudder",
        "shuddered", "damp", "wet", "dry", "sweat", "sweating", "scalding", "numb", "sting", "ache", "itching",
        "clammy", "coarse", "silky", "hard", "soft", "heavy", "pressure", "grip", "gripped", "grasp", "grasped"
    },
    "olfactory": {
        "smell", "smelled", "scent", "scented", "odor", "stench", "reek", "reeked", "perfume", "fragrance",
        "aroma", "sniff", "sniffed", "inhale", "inhaled", "musk", "musky", "sulfur", "brine", "smoke",
        "incense", "stale", "pungent", "fetid", "musty", "acrid", "rank"
    },
    "gustatory": {
        "taste", "tasted", "flavor", "sweet", "bitter", "sour", "salty", "savory", "tangy", "swallow",
        "swallowed", "chew", "chewed", "sip", "sipped", "gulp", "gulped", "lick", "licked", "delicious",
        "bland", "parched", "spicy", "tart"
    }
}

CLICHE_CATALOG = [
    ("cold sweat", "somatic shivering or bead of sweat"),
    ("piercing blue eyes", "specific eye detail or focused gaze"),
    ("piercing eyes", "intense stare or narrowed gaze"),
    ("time stood still", "slowed physical perception or suspended breath"),
    ("dead silence", "absence of specific ambient sounds"),
    ("heavy heart", "visceral ache or dropped posture"),
    ("crystal clear", "distinct or unclouded"),
    ("bated breath", "shallow breathing or caught breath"),
    ("heart skipped a beat", "somatic pulse flutter or sharp intake"),
    ("blood ran cold", "sudden chill or dread"),
    ("white as a sheet", "blanched pallor or drained color"),
    ("pitch black", "ink-dark or impenetrable dark"),
    ("in the blink of an eye", "in an instant or before a breath could form"),
    ("calm before the storm", "ominous stillness or taut quiet"),
]

BE_VERBS = {"was", "were", "is", "are", "been", "being", "be", "am"}
IRREGULAR_PAST_PARTICIPLES = {
    "done", "seen", "taken", "broken", "given", "known", "made", "found", "built", "left", "sent",
    "struck", "shot", "slain", "borne", "hidden", "chosen", "drawn", "driven", "eaten", "fallen",
    "forgotten", "frozen", "grown", "rung", "risen", "run", "spoken", "stolen", "sworn", "torn",
    "thrown", "worn", "written", "lost", "kept", "held", "heard", "felt", "spent", "caught", "brought"
}

POSITIVE_WORDS = {
    "love", "loved", "hope", "hoped", "joy", "joyful", "triumph", "smile", "smiled", "laugh",
    "laughed", "comfort", "comforted", "peace", "peaceful", "brave", "kind", "kindness", "delight",
    "delighted", "warm", "warmth", "safe", "safety", "alive", "freedom", "honor", "victory",
    "beauty", "beautiful", "glow", "glowed", "tender", "cherish", "cherished", "radiant"
}
NEGATIVE_WORDS = {
    "death", "died", "dead", "fear", "feared", "pain", "painful", "terror", "terrified", "dread",
    "dreaded", "grief", "blood", "bloody", "wound", "wounded", "loss", "lost", "dark", "darkness",
    "cold", "cruel", "cruelty", "threat", "threatened", "despair", "fail", "failed", "hate", "hated",
    "kill", "killed", "suffer", "suffered", "enemy", "destroy", "destroyed", "ruin", "ruined", "shame",
    "corpse", "agony"
}


def compute_cadence_entropy(lengths: List[int]) -> float:
    if len(lengths) <= 1:
        return 0.0
    bins = [0] * 7
    for l in lengths:
        if l <= 5: bins[0] += 1
        elif l <= 10: bins[1] += 1
        elif l <= 15: bins[2] += 1
        elif l <= 20: bins[3] += 1
        elif l <= 30: bins[4] += 1
        elif l <= 40: bins[5] += 1
        else: bins[6] += 1
    total = len(lengths)
    entropy = 0.0
    for c in bins:
        if c > 0:
            p = c / total
            entropy -= p * math.log2(p)
    return round(entropy, 2)


def detect_passive_voice(lines: List[str], start_line: int = 1) -> List[Dict[str, Any]]:
    hits = []
    for idx, line in enumerate(lines, start_line):
        clean = COMMENT_RE.sub("", line).strip()
        if not clean or clean.startswith("#"):
            continue
        words = [w.lower() for w in WORD_RE.findall(clean)]
        for i, w in enumerate(words):
            if w in BE_VERBS:
                for j in range(i + 1, min(i + 4, len(words))):
                    target = words[j]
                    if target.endswith("ed") or target in IRREGULAR_PAST_PARTICIPLES:
                        phrase = " ".join(words[i:j+1])
                        hits.append({"line": idx, "phrase": phrase, "text": clean[:80]})
                        break
    return hits


def compute_sensory_palette(lines: List[str], start_line: int = 1) -> Dict[str, Any]:
    counts = {m: 0 for m in SENSORY_LEXICON}
    occurrences = []
    for idx, line in enumerate(lines, start_line):
        clean = COMMENT_RE.sub("", line).strip()
        if not clean or clean.startswith("#"):
            continue
        words = [w.lower() for w in WORD_RE.findall(clean)]
        for w in words:
            for modality, word_set in SENSORY_LEXICON.items():
                if w in word_set:
                    counts[modality] += 1
                    occurrences.append({"line": idx, "modality": modality, "word": w})
    return {"counts": counts, "occurrences": occurrences}


def detect_cliches(lines: List[str], start_line: int = 1) -> List[Dict[str, Any]]:
    hits = []
    for idx, line in enumerate(lines, start_line):
        clean = COMMENT_RE.sub("", line).strip()
        if not clean or clean.startswith("#"):
            continue
        line_lower = clean.lower()
        for cliche, suggestion in CLICHE_CATALOG:
            if cliche in line_lower:
                hits.append({
                    "line": idx,
                    "cliche": cliche,
                    "suggestion": suggestion,
                    "text": clean[:80]
                })
    return hits


def compute_emotional_valence(lines: List[str]) -> float:
    pos_count = 0
    neg_count = 0
    total_words = 0
    for line in lines:
        clean = COMMENT_RE.sub("", line).strip()
        if not clean or clean.startswith("#"):
            continue
        words = [w.lower() for w in WORD_RE.findall(clean)]
        total_words += len(words)
        for w in words:
            if w in POSITIVE_WORDS: pos_count += 1
            elif w in NEGATIVE_WORDS: neg_count += 1
    if total_words == 0:
        return 0.0
    val = (pos_count - neg_count) / math.sqrt(max(total_words, 10))
    return round(max(-1.0, min(1.0, val / 3.0)), 2)


def compute_single_scene_metrics(sid: str, outline_sec: Optional[Section], derived_sec: Optional[Section], plan: Model) -> Dict[str, Any]:
    target_wc = target_words(outline_sec)
    lines = derived_sec.lines if derived_sec else []
    start_line = derived_sec.line if derived_sec else 1
    file_rel = derived_sec.file if derived_sec else (outline_sec.file if outline_sec else "")

    clean_lines = [COMMENT_RE.sub("", l) for l in lines]
    raw_text = "\n".join(clean_lines)
    actual_wc = word_count(lines) if derived_sec else 0

    dialogue_wc = 0
    quotes = re.findall(r'["“]([^"”]+)["”]', raw_text)
    for q in quotes:
        dialogue_wc += len(WORD_RE.findall(q))
    dialogue_ratio = round(dialogue_wc / max(actual_wc, 1), 2)

    clean_prose = re.sub(r'#+.*', '', raw_text)
    sents = [s.strip() for s in re.split(r'[.!?]+', clean_prose) if s.strip() and len(WORD_RE.findall(s)) > 1]
    sentence_count = len(sents)
    sent_lengths = [len(WORD_RE.findall(s)) for s in sents]
    avg_sentence_len = round(sum(sent_lengths) / max(len(sent_lengths), 1), 1) if sent_lengths else 0.0
    cadence_entropy = compute_cadence_entropy(sent_lengths)

    paras = [pr.strip() for pr in re.split(r'\n\s*\n', clean_prose) if pr.strip()]
    paragraph_count = len(paras)

    passive_hits = detect_passive_voice(lines, start_line)
    sensory_data = compute_sensory_palette(lines, start_line)
    cliches = detect_cliches(lines, start_line)
    valence = compute_emotional_valence(lines)

    refs = sorted(outline_sec.ref_ids()) if outline_sec else []
    plot_advancements = len([r for r in refs if r.startswith("PLT-")])
    has_change = bool(outline_sec and outline_sec.field_value("change"))
    velocity = round((plot_advancements + (1 if has_change else 0)) / (max(actual_wc, 100) / 1000.0), 2)

    return {
        "scene_id": sid,
        "title": outline_sec.title if outline_sec else sid,
        "file": file_rel,
        "line": start_line,
        "target_words": target_wc,
        "actual_words": actual_wc,
        "dialogue_words": dialogue_wc,
        "dialogue_ratio": dialogue_ratio,
        "sentence_count": sentence_count,
        "avg_sentence_len": avg_sentence_len,
        "cadence_entropy": cadence_entropy,
        "paragraph_count": paragraph_count,
        "passive_count": len(passive_hits),
        "passive_hits": passive_hits,
        "sensory_counts": sensory_data["counts"],
        "sensory_occurrences": sensory_data["occurrences"],
        "cliches": cliches,
        "emotional_valence": valence,
        "narrative_velocity": velocity,
        "referenced_ids": refs
    }


def get_or_update_metrics_cache(p: Project, stage: str = "manuscript", force_recompute: bool = False) -> Tuple[Dict[str, Any], Set[str], Optional[str]]:
    git = p.git
    base_sha = git.baseline(stage)
    base_label = base_sha or "uncommitted"
    cache_dir = git.root / ".specnovel"
    cache_file = cache_dir / "metrics_cache.json"

    cached_data: Dict[str, Any] = {}
    if not force_recompute and cache_file.is_file():
        try:
            cached_data = json.loads(cache_file.read_text(encoding="utf-8"))
        except Exception:
            cached_data = {}

    cached_base = cached_data.get("baseline_sha")
    cached_scenes = cached_data.get("scenes", {})

    dirty_scenes: Set[str] = set()

    if force_recompute or cached_base != base_label or not cached_scenes:
        if base_sha:
            old_plan = build_model(git.commit_md(base_sha, *PLAN_DIRS))
            changes = diff_models(old_plan, p.plan)
            changed_ids = {c.id for c in changes if c.id}
            changed_files = {d["file"] for d in git.changed_since(base_sha, MANUSCRIPT, ABRIDGED)}
        else:
            changed_ids = set()
            changed_files = set()

        for sid in p.outline.scenes:
            d_sec = p.layers[stage].scenes.get(sid) or p.layers["abridged"].scenes.get(sid)
            if not d_sec or d_sec.file in changed_files:
                dirty_scenes.add(sid)
                continue
            if sid in changed_ids:
                dirty_scenes.add(sid)
                continue
            refs = set()
            for a in ancestors(p.plan, sid):
                refs |= a.ref_ids()
            if refs & changed_ids:
                dirty_scenes.add(sid)
                continue
            if sid not in cached_scenes:
                dirty_scenes.add(sid)
    else:
        uncommitted_files = {d["file"] for d in git.changed_since("HEAD", MANUSCRIPT, ABRIDGED, *PLAN_DIRS)} if git.has_commits() else set()
        for sid in p.outline.scenes:
            d_sec = p.layers[stage].scenes.get(sid) or p.layers["abridged"].scenes.get(sid)
            if not d_sec or d_sec.file in uncommitted_files or sid not in cached_scenes:
                dirty_scenes.add(sid)

    metrics_by_scene = dict(cached_scenes)
    for sid in p.outline.scenes:
        if sid in dirty_scenes or sid not in metrics_by_scene:
            outline_sec = p.plan.defs.get(sid)
            derived_sec = p.layers[stage].scenes.get(sid) or p.layers["abridged"].scenes.get(sid)
            metrics_by_scene[sid] = compute_single_scene_metrics(sid, outline_sec, derived_sec, p.plan)

    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        new_cache = {
            "baseline_sha": base_label,
            "scenes": metrics_by_scene
        }
        cache_file.write_text(json.dumps(new_cache, indent=2), encoding="utf-8")
    except Exception:
        pass

    return metrics_by_scene, dirty_scenes, base_sha


def generate_analysis_report(
    p: Project,
    metrics_by_scene: Dict[str, Any],
    pacing_waveform: List[Dict[str, Any]],
    character_agency: OrderedDict,
    chekhov_matrix: List[Dict[str, Any]],
    secrets_revealed: OrderedDict,
    consecutive_slow_scenes: List[List[str]],
    novel_sensory: Dict[str, int],
    sensory_alerts: List[Dict[str, Any]],
    total_words_outline: int,
    total_words_actual: int,
    total_dialogue_words: int,
    total_cliches: int,
    total_passive: int,
    base_sha: Optional[str]
) -> str:
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    title = p.config.title or "Untitled Novel"
    author = p.config.author_name or p.config.author_legal_name or "Unknown Author"
    lang = p.config.primary_language or "en-US"
    overall_dialogue_ratio = round(total_dialogue_words / max(total_words_actual, 1), 2)
    avg_entropy = round(sum(w["cadence_entropy"] for w in pacing_waveform) / max(len(pacing_waveform), 1), 2)
    tot_sents = sum(w["sentences"] for w in pacing_waveform)
    avg_sent_len = round(total_words_actual / max(tot_sents, 1), 1)
    base_label = base_sha[:8] if base_sha else "uncommitted"

    lines = []
    lines.append(f"# Developmental Editorial & Style Analysis Report")
    lines.append(f"**Work:** [[{title}]]  ")
    lines.append(f"**Author:** {author}  ")
    lines.append(f"**Locale:** `{lang}`  ")
    lines.append(f"**Baseline Commit:** `{base_label}`  ")
    lines.append(f"**Generated:** {now_str}\n")
    lines.append("---\n")

    # Executive Dashboard
    lines.append("## 1. Executive Metrics Dashboard\n")
    lines.append("| Metric | Dimension / Type | Observed Value | Standard / Style Target | Assessment |")
    lines.append("|---|---|---|---|---|")

    wc_status = "On Budget" if abs(total_words_actual - total_words_outline) <= total_words_outline * 0.15 else "Review Length"
    lines.append(f"| Total Word Count | Scope (Raw) | {total_words_actual:,} wds | {total_words_outline:,} wds | {wc_status} |")

    lines.append(f"| Dialogue Ratio | Style-Reflective | {overall_dialogue_ratio:.0%} | 25% – 45% (Balanced) | {'Optimal' if 0.20 <= overall_dialogue_ratio <= 0.50 else 'Investigate'} |")

    entropy_eval = "Lyrical / Dynamic" if avg_entropy >= 2.5 else ("Moderate" if avg_entropy >= 1.8 else "Monotone Cadence")
    lines.append(f"| Cadence Entropy ($H_{{cad}}$) | Style-Reflective | {avg_entropy} bits | ≥ 2.2 bits | {entropy_eval} |")

    lines.append(f"| Avg Sentence Length | Style-Reflective | {avg_sent_len} words | per `story/style.md` | Calibrated |")

    ck_unresolved = len([c for c in chekhov_matrix if "dormant" in c["assessment"]])
    lines.append(f"| Chekhov Guns Tracked | Dramatic (Raw) | {len(chekhov_matrix)} setups | 0 orphan setups | {'All Paid Off' if ck_unresolved == 0 else f'{ck_unresolved} Dormant Guns'} |")

    lines.append(f"| Pacing Sag Sequences | Dramatic (Raw) | {len(consecutive_slow_scenes)} sequence(s) | 0 sags | {'Clean Flow' if len(consecutive_slow_scenes) == 0 else 'Review Sags'} |")

    lines.append(f"| Clichés / Dead Metaphors | Literary (Raw) | {total_cliches} detected | 0 clichés | {'Clean Diction' if total_cliches == 0 else 'Polish Required'} |")

    passive_pct = round((total_passive / max(tot_sents, 1)) * 100, 1)
    lines.append(f"| Passive Voice Ratio | Linguistic (Raw) | {passive_pct}% ({total_passive}) | ≤ 5.0% | {'Punchy Active' if passive_pct <= 5.0 else 'Tighten Passive'} |\n")

    lines.append("## 2. Raw Quality Indicators Audit\n")
    lines.append("Raw quality indicators measure objective storytelling integrity, narrative coherence, and technical craft faults that detract from immersion regardless of chosen style.\n")

    lines.append("### 2.1 Story Causality & Epistemic Secrets")
    if not secrets_revealed:
        lines.append("- No epistemic secrets registered in outline.\n")
    else:
        lines.append("| Secret Element | Revelation Scene | Learned By | Kept Hidden From | Integrity |")
        lines.append("|---|---|---|---|---|")
        for sec_id, data in secrets_revealed.items():
            l_str = ", ".join(f"[[{ch}]]" for ch in data["learns"]) or "None"
            h_str = ", ".join(f"[[{ch}]]" for ch in data["hidden_from"]) or "None"
            leak = any(ch in data["hidden_from"] for ch in data["learns"])
            integrity = "**Violation: Leaked**" if leak else "Preserved"
            lines.append(f"| [[{sec_id}]] | [[{data['scene']}]] | {l_str} | {h_str} | {integrity} |")
        lines.append("")

    lines.append("### 2.2 Chekhov's Gun Setups & Payoffs")
    if not chekhov_matrix:
        lines.append("- No paired plants and payoffs tracked in outline.\n")
    else:
        lines.append("| Planted Entity | Setup Scene | Payoff Scene | Scene Gap | Diagnostic Assessment |")
        lines.append("|---|---|---|---|---|")
        for ck in chekhov_matrix:
            lines.append(f"| [[{ck['entity']}]] | [[{ck['plant_scene']}]] | [[{ck['payoff_scene']}]] | {ck['scene_gap']} scenes | {ck['assessment']} |")
        lines.append("")

    lines.append("### 2.3 Pacing Sags & Momentum Stalls")
    if not consecutive_slow_scenes:
        lines.append("- No pacing sag sequences detected. Plot progression and scene lengths are causally balanced.\n")
    else:
        for seq in consecutive_slow_scenes:
            seq_links = ", ".join(f"[[{sid}]]" for sid in seq)
            lines.append(f"> [!WARNING]\n> **Pacing Sag Detected in:** {seq_links}\n> These consecutive scenes exceed target word counts without advancing a cataloged plot element (`PLT`). Consider condensing descriptive texture or introducing a dramatic turning point.\n")

    lines.append("### 2.4 Cliché & Passive Phrasing Hotspots")
    cliche_scenes = [sid for sid, m in metrics_by_scene.items() if m.get("cliches")]
    if not cliche_scenes:
        lines.append("- Zero clichés or dead metaphors detected in manuscript prose.\n")
    else:
        lines.append("| Scene | Location | Flagged Cliché | Suggested Somatic / Visceral Alternative |")
        lines.append("|---|---|---|---|")
        for sid in cliche_scenes[:8]:
            for cl in metrics_by_scene[sid]["cliches"]:
                lines.append(f"| [[{sid}]] | `{metrics_by_scene[sid]['file']}#L{cl['line']}` | *\"{cl['cliche']}\"* | {cl['suggestion']} |")
        lines.append("")

    lines.append("## 3. Style-Reflective Metrics vs. `story/style.md` Compliance\n")
    lines.append("Style-reflective metrics evaluate whether the prose's technical execution aligns with the artistic choices declared in `story/style.md`.\n")

    lines.append("### 3.1 Sentence Rhythm & Prose Cadence (`style.md` §3)")
    lines.append(f"- **Observed Average Sentence Length:** {avg_sent_len} words.")
    lines.append(f"- **Cadence Entropy ($H_{{cad}}$):** {avg_entropy} bits (measures length variety across short, medium, and long sentences).")
    lines.append(f"- **Consistency:** Verify that action scenes deploy terse, staccato phrasing while contemplative scenes expand into longer periodic clauses per `story/style.md`.\n")

    lines.append("### 3.2 Sensory Palette Grounding (`style.md` §6)")
    tot_sensory = max(sum(novel_sensory.values()), 1)
    lines.append("| Sensory Modality | Occurrences | Percentage | Grounding Role |")
    lines.append("|---|---|---|---|")
    for mod, cnt in novel_sensory.items():
        pct = (cnt / tot_sensory) * 100
        lines.append(f"| {mod.capitalize()} | {cnt} | {pct:.1f}% | {'Primary anchor' if pct >= 25 else 'Texture element'} |")
    lines.append("")
    if sensory_alerts:
        lines.append("> [!TIP]\n> **Sensory Grounding Warnings:**")
        for sa in sensory_alerts[:5]:
            lines.append(f"> - Scene [[{sa['scene']}]] ({sa['words']} words, setting: {sa['where']}) lacks tactile or olfactory grounding. Check the sensory palette of [[{sa['where'].strip('[]')}]] and weave in physical textures.\n")

    lines.append("### 3.3 Visual Graphics Intensity (`style.md` ## Graphics Guidelines)")
    gfx_in_outline = [r[0] for sid in p.outline.scenes for r in p.plan.defs[sid].refs if r[0].startswith("GFX-")] if p.outline.scenes else []
    lines.append(f"- **Cataloged Graphics References in Outline:** {len(set(gfx_in_outline))} asset(s): {', '.join(f'[[{g}]]' for g in sorted(set(gfx_in_outline))) or 'None'}.")
    lines.append(f"- **Alignment:** Verify that visual assets match the style guide's declared intensity level and trigger rules (spatial transitions, tactical cutaways, epistolary artifacts).\n")

    lines.append("## 4. Cross-Chapter Style Consistency\n")
    lines.append("| Chapter | Scenes | Words | Dialogue % | Avg Sentence | Cadence Entropy | Stylistic Footprint |")
    lines.append("|---|---|---|---|---|---|---|")
    for cid, sids in p.outline.by_chapter.items():
        ch_words = sum(metrics_by_scene.get(sid, {}).get("actual_words", 0) for sid in sids)
        ch_dlg = sum(metrics_by_scene.get(sid, {}).get("dialogue_words", 0) for sid in sids)
        ch_dlg_pct = (ch_dlg / max(ch_words, 1)) * 100
        ch_sents = sum(metrics_by_scene.get(sid, {}).get("sentence_count", 0) for sid in sids)
        ch_avg_sent = round(ch_words / max(ch_sents, 1), 1)
        ch_entropy = round(sum(metrics_by_scene.get(sid, {}).get("cadence_entropy", 0.0) for sid in sids) / max(len(sids), 1), 2)
        footprint = "Balanced" if 12 <= ch_avg_sent <= 20 and ch_entropy >= 2.0 else "Check Variance"
        lines.append(f"| [[{cid}]] | {len(sids)} | {ch_words:,} | {ch_dlg_pct:.0f}% | {ch_avg_sent} wds | {ch_entropy} bits | {footprint} |")
    lines.append("")

    lines.append("## 5. Multi-Level Zoom-In on Critical Areas\n")

    lines.append("### 5.1 Scene Pacing Waveform & Emotional Arc")
    lines.append("| Scene | Chapter | Words | Dlg % | Velocity ($V_n$) | Emotional Valence ($E_v$) | Focus |")
    lines.append("|---|---|---|---|---|---|---|")
    for w in pacing_waveform:
        sid = w["scene"]
        m = metrics_by_scene.get(sid, {})
        vel = m.get("narrative_velocity", 0.0)
        val = m.get("emotional_valence", 0.0)
        val_str = f"+{val:.2f}" if val > 0 else f"{val:.2f}"
        lines.append(f"| [[{sid}]] | [[{w['chapter']}]] | {w['actual_words']:,} | {w['dialogue_ratio']:.0%} | {vel} | {val_str} | {w['title'][:25]} |")
    lines.append("")

    lines.append("### 5.2 Character Agency & Screen-Time")
    lines.append("| Character | POV Scenes | Cast Appearances | Novel Coverage | Agency Assessment |")
    lines.append("|---|---|---|---|---|")
    tot_scenes = max(len(p.outline.scenes), 1)
    for c in character_agency.values():
        c_count = c["cast_count"]
        cov = (c_count / tot_scenes) * 100
        agency = "Protagonist / Primary" if c["pov_count"] >= 3 else ("Key Secondary" if c_count >= 2 else "Incidental")
        lines.append(f"| [[{c['id']}]] ({c['name']}) | {c['pov_count']} | {c_count} | {cov:.0f}% | {agency} |")
    lines.append("")

    lines.append("## 6. Actionable Editorial Roadmap\n")
    lines.append("1. **High Priority (Quality & Logic)**:")
    if consecutive_slow_scenes:
        lines.append(f"   - Resolve pacing sag in {', '.join(f'[[{sid}]]' for s in consecutive_slow_scenes for sid in s)} by introducing external conflict or cutting expository filler.")
    if ck_unresolved > 0:
        lines.append(f"   - Address {ck_unresolved} dormant Chekhov gun setups to ensure all planted items earn a meaningful payoff before the climax.")
    if not consecutive_slow_scenes and ck_unresolved == 0:
        lines.append("   - Zero structural blockers detected. Narrative causality and Chekhov engines are healthy.")

    lines.append("2. **Medium Priority (Style & Sensory Polish)**:")
    if sensory_alerts:
        for sa in sensory_alerts[:3]:
            lines.append(f"   - Enrich sensory textures in [[{sa['scene']}]] using the tactile and olfactory palette of [[{sa['where'].strip('[]')}]] to eliminate white-room syndrome.")
    if total_cliches > 0:
        lines.append(f"   - Replace {total_cliches} flagged novelistic cliché(s) with somatic reactions or era-authentic figurative language.")

    lines.append("3. **Consistency & Rhythm**:")
    lines.append(f"   - Maintain sentence cadence entropy (≥ 2.2 bits) and audit chapters flagged with stylistic variance in Section 4.\n")

    return "\n".join(lines) + "\n"


def cmd_audit(git: Git, args) -> int:
    p = load_project(git)
    target_stage = "manuscript" if p.layers["manuscript"].scenes else "abridged"

    # 1. Handle --compare baseline
    if getattr(args, "compare", None):
        base_sha = git.baseline(target_stage)
        if not base_sha:
            msg = f"specnovel: no baseline commit found for stage '{target_stage}'. Accept a baseline using 'specnovel accept --stage {target_stage}'."
            if getattr(args, "json", False):
                print(json.dumps({"error": msg}, indent=2))
            else:
                print(msg, file=sys.stderr)
            return 1

        curr_metrics, _, _ = get_or_update_metrics_cache(p, target_stage, force_recompute=getattr(args, "no_cache", False))

        old_plan = build_model(git.commit_md(base_sha, *PLAN_DIRS))
        old_outline = outline_of(old_plan)
        old_layer = derived_of(build_model(git.commit_md(base_sha, MANUSCRIPT)))
        if not old_layer.scenes:
            old_layer = derived_of(build_model(git.commit_md(base_sha, ABRIDGED)))

        base_metrics = {}
        for sid in old_outline.scenes:
            base_metrics[sid] = compute_single_scene_metrics(sid, old_plan.defs.get(sid), old_layer.scenes.get(sid), old_plan)

        curr_words = sum(m["actual_words"] for m in curr_metrics.values())
        base_words = sum(m["actual_words"] for m in base_metrics.values())

        curr_sents = sum(m["sentence_count"] for m in curr_metrics.values())
        base_sents = sum(m["sentence_count"] for m in base_metrics.values())

        curr_avg_sent = round(curr_words / max(curr_sents, 1), 1)
        base_avg_sent = round(base_words / max(base_sents, 1), 1)

        curr_entropy = round(sum(m["cadence_entropy"] for m in curr_metrics.values()) / max(len(curr_metrics), 1), 2)
        base_entropy = round(sum(m["cadence_entropy"] for m in base_metrics.values()) / max(len(base_metrics), 1), 2)

        curr_dlg = round(sum(m["dialogue_words"] for m in curr_metrics.values()) / max(curr_words, 1), 2)
        base_dlg = round(sum(m["dialogue_words"] for m in base_metrics.values()) / max(base_words, 1), 2)

        curr_sensory_tot = sum(sum(m["sensory_counts"].values()) for m in curr_metrics.values())
        base_sensory_tot = sum(sum(m["sensory_counts"].values()) for m in base_metrics.values())
        curr_sensory_dens = round((curr_sensory_tot / max(curr_words, 1)) * 1000, 1)
        base_sensory_dens = round((base_sensory_tot / max(base_words, 1)) * 1000, 1)

        curr_passive_tot = sum(m["passive_count"] for m in curr_metrics.values())
        base_passive_tot = sum(m["passive_count"] for m in base_metrics.values())
        curr_passive_pct = round((curr_passive_tot / max(curr_sents, 1)) * 100, 1)
        base_passive_pct = round((base_passive_tot / max(base_sents, 1)) * 100, 1)

        curr_cliches = sum(len(m["cliches"]) for m in curr_metrics.values())
        base_cliches = sum(len(m["cliches"]) for m in base_metrics.values())

        delta_data = {
            "baseline_sha": base_sha[:8],
            "metrics": {
                "word_count": {"baseline": base_words, "current": curr_words, "delta": curr_words - base_words},
                "avg_sentence_len": {"baseline": base_avg_sent, "current": curr_avg_sent, "delta": round(curr_avg_sent - base_avg_sent, 1)},
                "cadence_entropy": {"baseline": base_entropy, "current": curr_entropy, "delta": round(curr_entropy - base_entropy, 2)},
                "dialogue_ratio": {"baseline": base_dlg, "current": curr_dlg, "delta": round(curr_dlg - base_dlg, 2)},
                "sensory_density_per_k": {"baseline": base_sensory_dens, "current": curr_sensory_dens, "delta": round(curr_sensory_dens - base_sensory_dens, 1)},
                "passive_voice_pct": {"baseline": base_passive_pct, "current": curr_passive_pct, "delta": round(curr_passive_pct - base_passive_pct, 1)},
                "cliches_count": {"baseline": base_cliches, "current": curr_cliches, "delta": curr_cliches - base_cliches}
            }
        }

        if getattr(args, "json", False):
            print(json.dumps(delta_data, indent=2))
            return 0

        print("=" * 80)
        print(f"LONGITUDINAL TELEMETRY DELTA (baseline: {base_sha[:8]} -> working tree)")
        print("=" * 80)
        print(f"{'METRIC':<30} {'BASELINE':<12} {'CURRENT':<12} {'DELTA':<10}")
        print("-" * 80)
        for k, v in delta_data["metrics"].items():
            b_val = str(v["baseline"])
            c_val = str(v["current"])
            d_val = f"+{v['delta']}" if v['delta'] > 0 else str(v['delta'])
            print(f"{k:<30} {b_val:<12} {c_val:<12} {d_val:<10}")
        print("=" * 80)
        return 0

    # 2. Handle --scene <sid> drill-down
    if getattr(args, "scene", None):
        target_sid = args.scene
        if target_sid not in p.outline.scenes:
            print(f"specnovel: scene '{target_sid}' not found in outline", file=sys.stderr)
            return 1

        metrics_by_scene, _, base_sha = get_or_update_metrics_cache(p, target_stage, force_recompute=getattr(args, "no_cache", False))
        m = metrics_by_scene[target_sid]

        if getattr(args, "json", False):
            print(json.dumps(m, indent=2))
            return 0

        outline_sec = p.plan.defs.get(target_sid)
        print("=" * 80)
        print(f"SCENE TELEMETRY DRILL-DOWN: {target_sid} ({m['title']})")
        print("=" * 80)
        print(f"Location:            {m['file']} (line {m['line']})")
        print(f"Word Count:          {m['actual_words']} actual (target: {m['target_words']})")
        print(f"Dialogue Ratio:      {m['dialogue_ratio']:.0%} ({m['dialogue_words']} dialogue words)")
        print(f"Narrative Velocity:  {m['narrative_velocity']} plot shifts / 1k words")
        print(f"Emotional Valence:   {m['emotional_valence']:+.2f} (trajectory score)")
        print(f"Sentence Rhythm:     {m['avg_sentence_len']} avg words / sentence | Cadence Entropy: {m['cadence_entropy']} bits")

        print("\n" + "-" * 80)
        print("SENSORY PALETTE RADAR")
        print("-" * 80)
        for mod, count in m["sensory_counts"].items():
            bar = "█" * min(20, count) if count > 0 else "-"
            print(f"  {mod.capitalize():<12} {count:<4} {bar}")

        if m["passive_count"] > 0:
            print("\n" + "-" * 80)
            print(f"PASSIVE VOICE OCCURRENCES ({m['passive_count']} detected)")
            print("-" * 80)
            for p_hit in m["passive_hits"][:5]:
                print(f"  Line {p_hit['line']}: \"{p_hit['phrase']}\" -> {p_hit['text']}")

        if m["cliches"]:
            print("\n" + "-" * 80)
            print(f"CLICHÉS DETECTED ({len(m['cliches'])} detected)")
            print("-" * 80)
            for cl in m["cliches"]:
                print(f"  Line {cl['line']}: \"{cl['cliche']}\"")
                print(f"    Suggested Somatic/Visceral Alternative: {cl['suggestion']}")

        print("\n" + "-" * 80)
        print("UPSTREAM SPECIFICATION CONNECTIONS")
        print("-" * 80)
        if outline_sec:
            where_val = outline_sec.field_value("where") or ""
            cast_val = outline_sec.field_value("cast") or ""
            plants_val = outline_sec.field_value("plants") or "none"
            pays_val = outline_sec.field_value("pays_off") or "none"
            reveals_val = outline_sec.field_value("reveals") or "none"
            hidden_val = outline_sec.field_value("hidden_from") or "none"
            print(f"  Setting (Where):   {where_val}")
            print(f"  Cast:              {cast_val}")
            print(f"  Chekhov Plants:    {plants_val}")
            print(f"  Chekhov Payoffs:   {pays_val}")
            print(f"  Reveals (Secret):  {reveals_val}")
            print(f"  Hidden From:       {hidden_val}")
        print("=" * 80)
        return 0

    # 3. Standard / Deep Whole-Novel Audit
    metrics_by_scene, dirty_scenes, base_sha = get_or_update_metrics_cache(p, target_stage, force_recompute=getattr(args, "no_cache", False))
    scene_ids = p.outline.scenes

    pacing_waveform = []
    character_agency = OrderedDict()
    all_plants = OrderedDict()
    all_payoffs = OrderedDict()
    secrets_revealed = OrderedDict()
    consecutive_slow_scenes = []
    current_slow_run = []

    total_words_outline = 0
    total_words_actual = 0
    total_dialogue_words = 0
    total_cliches = 0
    total_passive = 0

    novel_sensory = {m: 0 for m in SENSORY_LEXICON}
    sensory_alerts = []

    for chr_sec in p.plan.of_type("CHR"):
        character_agency[chr_sec.id] = {
            "id": chr_sec.id,
            "name": chr_sec.title,
            "cast_count": 0,
            "pov_count": 0,
            "scenes": []
        }

    for idx, sid in enumerate(scene_ids, 1):
        outline_sec = p.plan.defs.get(sid)
        ch_id = p.outline.chapter_of.get(sid, "CHP-???")
        m = metrics_by_scene.get(sid, {})

        actual_wc = m.get("actual_words", 0)
        target_wc = m.get("target_words", 0)
        total_words_outline += target_wc
        total_words_actual += actual_wc
        total_dialogue_words += m.get("dialogue_words", 0)
        total_cliches += len(m.get("cliches", []))
        total_passive += m.get("passive_count", 0)

        for mod, cnt in m.get("sensory_counts", {}).items():
            novel_sensory[mod] += cnt

        # Check sensory alert: actual_words > 300 but tactile == 0 or olfactory == 0
        if actual_wc > 300 and (m.get("sensory_counts", {}).get("tactile", 0) == 0 or m.get("sensory_counts", {}).get("olfactory", 0) == 0):
            where_val = outline_sec.field_value("where") if outline_sec else "unknown"
            sensory_alerts.append({"scene": sid, "words": actual_wc, "where": where_val})

        waveform_entry = {
            "index": idx,
            "scene": sid,
            "title": m.get("title", sid),
            "chapter": ch_id,
            "target_words": target_wc,
            "actual_words": actual_wc,
            "dialogue_ratio": m.get("dialogue_ratio", 0.0),
            "avg_sentence_len": m.get("avg_sentence_len", 0.0),
            "cadence_entropy": m.get("cadence_entropy", 0.0),
            "sentences": m.get("sentence_count", 0),
            "paragraphs": m.get("paragraph_count", 0),
            "emotional_valence": m.get("emotional_valence", 0.0),
            "narrative_velocity": m.get("narrative_velocity", 0.0)
        }
        pacing_waveform.append(waveform_entry)

        if outline_sec:
            pov_val = outline_sec.field_value("pov") or ""
            for chr_id in character_agency:
                if chr_id in pov_val:
                    character_agency[chr_id]["pov_count"] += 1

            cast_val = outline_sec.field_value("cast") or ""
            for chr_id in character_agency:
                if chr_id in cast_val or any(r[0] == chr_id for r in outline_sec.refs):
                    character_agency[chr_id]["cast_count"] += 1
                    character_agency[chr_id]["scenes"].append(sid)

            plants_str = outline_sec.field_value("plants") or ""
            for rm in REF_RE.finditer(plants_str):
                eid = rm.group("id")
                all_plants.setdefault(eid, []).append({"scene": sid, "index": idx, "chapter": ch_id})

            payoffs_str = outline_sec.field_value("pays_off") or outline_sec.field_value("paysoff") or ""
            for rm in REF_RE.finditer(payoffs_str):
                eid = rm.group("id")
                all_payoffs.setdefault(eid, []).append({"scene": sid, "index": idx, "chapter": ch_id})

            reveals_str = outline_sec.field_value("reveals") or ""
            learns_str = outline_sec.field_value("learns") or ""
            hidden_str = outline_sec.field_value("hidden_from") or ""
            if reveals_str:
                for rm in REF_RE.finditer(reveals_str):
                    sec_id = rm.group("id")
                    learners = [lm.group("id") for lm in REF_RE.finditer(learns_str)]
                    hidden = [hm.group("id") for hm in REF_RE.finditer(hidden_str)]
                    secrets_revealed[sec_id] = {
                        "scene": sid,
                        "chapter": ch_id,
                        "index": idx,
                        "learns": learners,
                        "hidden_from": hidden
                    }

            has_plt = any(r[0].startswith("PLT-") for r in outline_sec.refs)
            fn_tag = (outline_sec.field_value("function") or "").lower()
            is_slow = (actual_wc > 1500 or (target_wc > 0 and actual_wc >= target_wc)) and not has_plt and fn_tag not in ("climactic-turn", "turning-point", "denouement")
            if is_slow:
                current_slow_run.append(sid)
            else:
                if len(current_slow_run) >= 2:
                    consecutive_slow_scenes.append(list(current_slow_run))
                current_slow_run = []

    if len(current_slow_run) >= 2:
        consecutive_slow_scenes.append(list(current_slow_run))

    chekhov_matrix = []
    for eid, plants in all_plants.items():
        payoffs = all_payoffs.get(eid, [])
        for pl in plants:
            for po in payoffs:
                gap = po["index"] - pl["index"]
                flag = "optimal"
                if gap <= 1:
                    flag = "immediate_payoff (anticlimax risk: setup paid off in same or next scene)"
                elif gap > 10:
                    flag = "long_dormant (dormant for >10 scenes without progression)"
                chekhov_matrix.append({
                    "entity": eid,
                    "plant_scene": pl["scene"],
                    "payoff_scene": po["scene"],
                    "scene_gap": gap,
                    "assessment": flag
                })

    overall_dialogue_ratio = round(total_dialogue_words / max(total_words_actual, 1), 2)
    avg_entropy = round(sum(w["cadence_entropy"] for w in pacing_waveform) / max(len(pacing_waveform), 1), 2)

    if getattr(args, "report", False):
        report_text = generate_analysis_report(
            p=p,
            metrics_by_scene=metrics_by_scene,
            pacing_waveform=pacing_waveform,
            character_agency=character_agency,
            chekhov_matrix=chekhov_matrix,
            secrets_revealed=secrets_revealed,
            consecutive_slow_scenes=consecutive_slow_scenes,
            novel_sensory=novel_sensory,
            sensory_alerts=sensory_alerts,
            total_words_outline=total_words_outline,
            total_words_actual=total_words_actual,
            total_dialogue_words=total_dialogue_words,
            total_cliches=total_cliches,
            total_passive=total_passive,
            base_sha=base_sha
        )
        out_path_str = getattr(args, "output", None)
        if not out_path_str:
            reports_dir = git.root / "reports"
            reports_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_file = reports_dir / f"analysis_{ts}.md"
        else:
            out_file = Path(out_path_str)
            if not out_file.is_absolute():
                out_file = git.root / out_file
            out_file.parent.mkdir(parents=True, exist_ok=True)

        out_file.write_text(report_text, encoding="utf-8")
        rel_path = out_file.relative_to(git.root).as_posix()
        if getattr(args, "json", False):
            print(json.dumps({"report_path": rel_path}, indent=2))
        else:
            print(f"Generated analysis report: {rel_path}")
        return 0

    if getattr(args, "json", False):
        res = {
            "summary": {
                "total_scenes": len(scene_ids),
                "target_words": total_words_outline,
                "actual_words": total_words_actual,
                "overall_dialogue_ratio": overall_dialogue_ratio,
                "average_cadence_entropy": avg_entropy,
                "total_cliches": total_cliches,
                "total_passive_constructions": total_passive,
                "pacing_sags_detected": len(consecutive_slow_scenes),
                "baseline_sha": base_sha[:8] if base_sha else "uncommitted",
                "cached_scenes_count": len(scene_ids) - len(dirty_scenes),
                "dirty_scenes_count": len(dirty_scenes)
            },
            "waveform": pacing_waveform,
            "character_agency": list(character_agency.values()),
            "chekhov_matrix": chekhov_matrix,
            "epistemic_matrix": secrets_revealed,
            "pacing_sag_sequences": consecutive_slow_scenes,
            "sensory_palette": novel_sensory,
            "sensory_alerts": sensory_alerts
        }
        print(json.dumps(res, indent=2))
        return 0

    print("=" * 80)
    print("DEVELOPMENTAL EDITORIAL TELEMETRY & PACING AUDIT")
    print("=" * 80)
    base_info = f"baseline: {base_sha[:8]}" if base_sha else "baseline: none (uncommitted)"
    cache_info = f"{len(scene_ids) - len(dirty_scenes)} cached, {len(dirty_scenes)} recomputed"
    print(f"Incremental Cache:          {base_info} ({cache_info})")
    print(f"Total outline target words: {total_words_outline:,}")
    print(f"Total actual prose words:   {total_words_actual:,}")
    print(f"Overall dialogue ratio:     {overall_dialogue_ratio:.0%}")
    print(f"Average sentence cadence:   {avg_entropy} bits entropy")
    print(f"Total cataloged scenes:     {len(scene_ids)}")

    print("\n" + "-" * 80)
    print("1. PACING WAVEFORM & SCENE RHYTHM")
    print("-" * 80)
    print(f"{'#':<3} {'SCENE':<9} {'CHAPTER':<9} {'WORDS':<7} {'DLG %':<6} {'AVG-SNT':<8} {'WAVEFORM'}")
    print("-" * 80)
    for w in pacing_waveform:
        wc = w["actual_words"]
        bars = "█" * min(25, max(1, wc // 100)) if wc > 0 else "-"
        flags = ""
        if w["dialogue_ratio"] > 0.8:
            flags = " [HIGH DLG >80%]"
        elif wc > 0 and w["dialogue_ratio"] < 0.05:
            flags = " [LOW DLG <5%]"
        print(f"{w['index']:<3} {w['scene']:<9} {w['chapter']:<9} {wc:<7} {w['dialogue_ratio']:<6.0%} {w['avg_sentence_len']:<8.1f} {bars}{flags}")

    print("\n" + "-" * 80)
    print("2. CHARACTER AGENCY & SCREEN-TIME DISTRIBUTION")
    print("-" * 80)
    print(f"{'ID':<10} {'NAME':<24} {'POV SCENES':<12} {'CAST SCENES':<12} {'COVERAGE %'}")
    print("-" * 80)
    tot_scns = max(len(scene_ids), 1)
    for c in character_agency.values():
        c_count = c["cast_count"]
        cov = (c_count / tot_scns) * 100
        print(f"{c['id']:<10} {c['name'][:23]:<24} {c['pov_count']:<12} {c_count:<12} {cov:.0f}%")

    print("\n" + "-" * 80)
    print("3. CHEKHOV'S GUN SETUP & PAYOFF MATRIX")
    print("-" * 80)
    if not chekhov_matrix:
        print("No paired plants and payoffs tracked in outline (or all isolated).")
    else:
        print(f"{'ENTITY':<12} {'PLANT':<10} {'PAYOFF':<10} {'GAP':<5} {'ASSESSMENT'}")
        print("-" * 80)
        for ck in chekhov_matrix:
            print(f"{ck['entity']:<12} {ck['plant_scene']:<10} {ck['payoff_scene']:<10} {ck['scene_gap']:<5} {ck['assessment']}")

    print("\n" + "-" * 80)
    print("4. EPISTEMIC KNOWLEDGE MATRIX (SECRETS & REVELATIONS)")
    print("-" * 80)
    if not secrets_revealed:
        print("No epistemic secrets (Reveals / Learns / Hidden From) registered in outline.")
    else:
        print(f"{'SECRET':<12} {'SCENE':<10} {'LEARNED BY':<25} {'HIDDEN FROM'}")
        print("-" * 80)
        for sec_id, data in secrets_revealed.items():
            l_str = ", ".join(data["learns"]) or "all"
            h_str = ", ".join(data["hidden_from"]) or "none"
            print(f"{sec_id:<12} {data['scene']:<10} {l_str[:24]:<25} {h_str}")

    print("\n" + "-" * 80)
    print("5. PACING SAG DETECTOR & DEVELOPMENTAL FLAGS")
    print("-" * 80)
    if consecutive_slow_scenes:
        for seq in consecutive_slow_scenes:
            print(f"[WARNING] Potential pacing sag sequence: scenes {', '.join(seq)} (2+ consecutive long scenes with no major plot progression).")
    else:
        print("No pacing sags detected. Narrative progression is evenly distributed.")

    if getattr(args, "deep", False):
        print("\n" + "-" * 80)
        print("6. MULTI-DIMENSIONAL CRAFT & SENSORY HEALTH")
        print("-" * 80)
        tot_sensory = max(sum(novel_sensory.values()), 1)
        print("Sensory Palette Distribution across Manuscript:")
        for mod, cnt in novel_sensory.items():
            pct = (cnt / tot_sensory) * 100
            bars = "█" * int(pct / 4)
            print(f"  {mod.capitalize():<12} {cnt:<5} ({pct:>4.1f}%) {bars}")

        if sensory_alerts:
            print("\nSensory Grounding Warnings (scenes > 300 words lacking tactile or olfactory anchors):")
            for sa in sensory_alerts[:5]:
                print(f"  - {sa['scene']} ({sa['words']} words, setting: {sa['where']})")
        else:
            print("\nSensory grounding is balanced across scenes.")

        print(f"\nLiterary & Syntactic Polish:")
        print(f"  - Total clichés detected: {total_cliches}")
        print(f"  - Total passive voice constructions: {total_passive}")
        print("Run 'specnovel.py audit --scene <SCN-ID>' for line-by-line attribution drill-down.")

    print("=" * 80)
    return 0


def cmd_takes(git: Git, args) -> int:
    p = load_project(git)
    action = args.action
    scene_id = args.id
    takes_base = git.root / "story" / "takes"

    if action == "list":
        takes_found = []
        if takes_base.is_dir():
            target_dirs = [takes_base / scene_id] if (scene_id and scene_id != "all") else sorted(takes_base.iterdir())
            for d in target_dirs:
                if d.is_dir():
                    sid = d.name
                    for tf in sorted(d.glob("*.md")):
                        txt = tf.read_text(encoding="utf-8", errors="replace")
                        fm = front_matter(txt)
                        wc = word_count(txt.splitlines())
                        takes_found.append({
                            "scene": sid,
                            "take": tf.stem,
                            "path": tf.relative_to(git.root).as_posix(),
                            "layer": fm.get("layer", "manuscript"),
                            "saved_at": fm.get("saved_at", ""),
                            "notes": fm.get("notes", ""),
                            "word_count": wc
                        })
        if getattr(args, "json", False):
            print(json.dumps(takes_found, indent=2))
            return 0
        if not takes_found:
            print(f"No takes found for scene '{scene_id}'.")
            return 0
        print(f"{'SCENE':<10} {'TAKE':<20} {'WORDS':<8} {'SAVED AT':<20} {'NOTES'}")
        print("-" * 75)
        for tk in takes_found:
            print(f"{tk['scene']:<10} {tk['take']:<20} {tk['word_count']:<8} {tk['saved_at'][:19]:<20} {tk['notes']}")
        return 0

    if not getattr(args, "take", None):
        print(f"specnovel: take name required for '{action}'", file=sys.stderr)
        return 1

    take_name = args.take
    scene_take_dir = takes_base / scene_id
    take_file = scene_take_dir / f"{take_name}.md"

    if action == "save":
        layer = getattr(args, "layer", None) or "manuscript"
        target_layer = p.layers.get(layer)
        if not target_layer or scene_id not in target_layer.scenes:
            print(f"specnovel: scene '{scene_id}' not found in layer '{layer}'", file=sys.stderr)
            return 1
        scene_sec = target_layer.scenes[scene_id]
        scene_take_dir.mkdir(parents=True, exist_ok=True)

        now_str = datetime.now().isoformat()
        notes_str = getattr(args, "message", "") or f"Snapshot of {scene_id} ({layer})"
        content = (
            f"---\n"
            f"scene: {scene_id}\n"
            f"take: {take_name}\n"
            f"layer: {layer}\n"
            f"saved_at: {now_str}\n"
            f"notes: {notes_str}\n"
            f"---\n\n"
            + "\n".join(scene_sec.lines) + "\n"
        )
        take_file.write_text(content, encoding="utf-8")
        if getattr(args, "json", False):
            print(json.dumps({"scene": scene_id, "take": take_name, "saved": True, "path": take_file.relative_to(git.root).as_posix()}))
        else:
            print(f"Saved take '{take_name}' for {scene_id} at {take_file.relative_to(git.root).as_posix()}")
        return 0

    if action == "diff":
        if not take_file.is_file():
            print(f"specnovel: take '{take_name}' not found at {take_file.relative_to(git.root).as_posix()}", file=sys.stderr)
            return 1
        t1_txt = take_file.read_text(encoding="utf-8", errors="replace")
        t1_prose = FRONT_RE.sub("", t1_txt).strip()
        t1_lines = [l + "\n" for l in t1_prose.splitlines()]

        if getattr(args, "take2", None):
            take2_file = scene_take_dir / f"{args.take2}.md"
            if not take2_file.is_file():
                print(f"specnovel: take2 '{args.take2}' not found", file=sys.stderr)
                return 1
            t2_txt = take2_file.read_text(encoding="utf-8", errors="replace")
            t2_prose = FRONT_RE.sub("", t2_txt).strip()
            t2_lines = [l + "\n" for l in t2_prose.splitlines()]
            from_name = f"take:{take_name}"
            to_name = f"take:{args.take2}"
        else:
            layer = getattr(args, "layer", None) or "manuscript"
            target_layer = p.layers.get(layer)
            if not target_layer or scene_id not in target_layer.scenes:
                print(f"specnovel: scene '{scene_id}' not found in active layer '{layer}'", file=sys.stderr)
                return 1
            scene_sec = target_layer.scenes[scene_id]
            t2_lines = [l + "\n" for l in scene_sec.lines]
            from_name = f"take:{take_name}"
            to_name = f"active:{layer}/{scene_id}"

        diff = list(difflib.unified_diff(t1_lines, t2_lines, fromfile=from_name, tofile=to_name))
        if getattr(args, "json", False):
            print(json.dumps({"scene": scene_id, "diff": "".join(diff), "has_diff": bool(diff)}))
            return 0
        if not diff:
            print(f"No differences between {from_name} and {to_name}.")
        else:
            sys.stdout.writelines(diff)
        return 0

    if action == "activate":
        if not take_file.is_file():
            print(f"specnovel: take '{take_name}' not found at {take_file.relative_to(git.root).as_posix()}", file=sys.stderr)
            return 1
        layer = getattr(args, "layer", None) or "manuscript"
        target_layer = p.layers.get(layer)
        if not target_layer or scene_id not in target_layer.scenes:
            print(f"specnovel: scene '{scene_id}' not found in active layer '{layer}'", file=sys.stderr)
            return 1
        scene_sec = target_layer.scenes[scene_id]

        take_txt = take_file.read_text(encoding="utf-8", errors="replace")
        take_prose = FRONT_RE.sub("", take_txt).strip()

        file_path = git.root / scene_sec.file
        content = file_path.read_text(encoding="utf-8", errors="replace")
        lines = content.splitlines()

        start_idx = scene_sec.line - 1
        end_idx = len(lines)
        for i in range(start_idx + 1, len(lines)):
            hm = HEADING_RE.match(lines[i])
            if hm and len(hm.group(1)) <= scene_sec.level:
                end_idx = i
                break

        new_lines = lines[:start_idx] + take_prose.splitlines() + lines[end_idx:]
        file_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

        if getattr(args, "json", False):
            print(json.dumps({"scene": scene_id, "activated_take": take_name, "file": scene_sec.file}))
        else:
            print(f"Activated take '{take_name}' into {scene_sec.file} for scene {scene_id}.")
        return 0

    if action == "delete":
        if take_file.is_file():
            take_file.unlink()
            if getattr(args, "json", False):
                print(json.dumps({"scene": scene_id, "deleted_take": take_name}))
            else:
                print(f"Deleted take '{take_name}' for scene {scene_id}.")
            return 0
        else:
            print(f"specnovel: take '{take_name}' not found", file=sys.stderr)
            return 1

    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="specnovel", description=__doc__.split("\n\n")[0])
    ap.add_argument("-C", "--root", default=".", help="path inside the novel's git repository (default: cwd)")
    sub = ap.add_subparsers(dest="command")
    specs = [("init", "scaffold story/ kb/ outline/ abridged/ manuscript/ from templates"),
             ("status", "dashboard: catalog, coverage, pending work, next step"),
             ("check", "integrity checks (exit 1 on errors)"),
             ("dag", "verify story causality DAG and reading order coherence"),
             ("next-id", "allocate the next unused ID for a prefix"),
             ("trace", "where an ID is defined, referenced and used in scenes"),
             ("delta", "ID-level changes in story/ kb/ outline/ since a stage baseline"),
             ("impact", "scenes to (re)generate in a derived layer"),
             ("accept", "commit and advance one or more stage baselines"),
             ("feedback", "list and inspect editorial directives (story/editorial/EDT-xxx)"),
             ("placeholders", "scan and convert placeholders into research questions (RQ)"),
             ("bibliography", "auto-generate bibliography from facts attached to the Story DAG"),
             ("models", "list AI models contributing to the project and check acknowledgements"),
             ("index", "regenerate kb/INDEX.md (catalog of all IDs)"),
             ("stats", "word counts per chapter/scene vs targets"),
             ("compile", "assemble the novel in reading order into build/"),
             ("log", "list sync commits"),
             ("harvest", "extract characters, places, dialogue and outline beats from raw text/draft"),
             ("scenario", "manage folder-based outline/spec scenarios (story/scenarios/<name>/)"),
             ("audit", "developmental editorial telemetry: pacing waveform, dialogue ratio, agency, Chekhov guns"),
             ("takes", "manage versioned scene takes (story/takes/<SCN-ID>/<take-name>.md)")]
    for name, help_ in specs:
        p = sub.add_parser(name, help=help_)
        if name in ("status", "check", "dag", "trace", "delta", "impact", "stats", "feedback", "placeholders", "bibliography", "models", "harvest", "scenario", "audit", "takes"):
            p.add_argument("--json", action="store_true", help="machine-readable output")
        if name == "bibliography":
            p.add_argument("--format", choices=["md", "json"], default="md")
            p.add_argument("--output", help="write bibliography to output file")
        if name == "placeholders":
            p.add_argument("path", nargs="?", help="optional file or directory to scan (default: all plan dirs)")
            p.add_argument("--create-rq", action="store_true", help="automatically create RQ entries in kb/research/questions.md")
            p.add_argument("--priority", choices=["high", "medium", "low"], help="override priority for generated RQs")
        if name == "dag":
            p.add_argument("--mermaid", action="store_true", help="output story DAG as a mermaid diagram")
        if name == "check":
            p.add_argument("--require", action="append", choices=list(LAYERS),
                           help="treat outline scenes missing from this layer as errors")
        if name == "next-id":
            p.add_argument("prefix", help="uppercase ID prefix, e.g. CHR, PLC, FCT, SCN")
        if name == "trace":
            p.add_argument("id", help="ID to trace, e.g. CHR-001")
        if name == "delta":
            p.add_argument("--stage", choices=list(STAGES) + ["plan", "all"], default="plan", help="baseline to compare against")
        if name == "impact":
            p.add_argument("--stage", choices=list(LAYERS) + ["graphics"], required=True)
            p.add_argument("--locale", help="filter manuscript impact by locale")
        if name == "feedback":
            p.add_argument("id", nargs="?", help="optional target scene/chapter ID (e.g. SCN-014) or EDT-xxx ID")
            p.add_argument("--status", choices=["open", "applied", "superseded", "wontfix", "all"], default="open",
                           help="filter by directive status (default: open)")
            p.add_argument("--stage", choices=["outline", "abridged", "manuscript", "all"],
                           help="filter by target stage")
            p.add_argument("--locale", help="filter by directive locale (e.g. all, fr-FR)")
        if name == "accept":
            p.add_argument("--stage", action="append", required=True, choices=list(STAGES) + ["plan", "all"])
            p.add_argument("--asset", action="append", help="specific asset ID(s) to accept (e.g. GFX-001)")
            p.add_argument("--model", help="AI model name contributing to this sync step (e.g. 'gemini-2.5-pro', 'gpt-4o')")
            p.add_argument("-m", "--message", default="", help="short summary for the commit subject")
            p.add_argument("--force", action="store_true", help="accept even if 'check' reports errors")
        if name == "stats":
            p.add_argument("--scenes", action="store_true", help="include per-scene rows")
        if name == "compile":
            p.add_argument("--layer", choices=list(LAYERS), default="manuscript")
            p.add_argument("--locale", help="target manuscript locale (default: primary from config)")
            p.add_argument("--format", choices=["md", "docx", "epub", "odt", "pdf", "html"], default="md")
            p.add_argument("--chapter-heading", default="Chapter {N}: {title}",
                           help="format; fields {n} (1), {N} (One), {title}")
            p.add_argument("--part-heading", default="Part {N}: {title}")
            p.add_argument("--scene-break", default="* * *")
            p.add_argument("--cover", help="custom cover image path (default: auto-detect from graphics/ or config)")
            p.add_argument("--css", help="custom CSS stylesheet for EPUB/HTML")
            p.add_argument("--pdf-engine", help="PDF engine for pandoc (e.g. xelatex, pdflatex, weasyprint, typst)")
        if name == "harvest":
            p.add_argument("draft_file", help="path to raw text or markdown draft file (or '-' for stdin)")
            p.add_argument("--apply", action="store_true", help="scaffold extracted entities into kb/ and outline/ and draft into abridged/")
            p.add_argument("--interactive", action="store_true", help="prompt author for entity names and titles")
            p.add_argument("--batch", action="store_true", help="non-interactive batch ingestion")
            p.add_argument("-t", "--title", help="provisional title for the harvested scene")
            p.add_argument("--chapter", help="target chapter ID (e.g. CHP-001) to attach harvested scene")
        if name == "scenario":
            p.add_argument("action", choices=["create", "list", "diff", "activate", "merge", "delete"], help="scenario action")
            p.add_argument("name", nargs="?", help="scenario name")
            p.add_argument("-m", "--message", default="", help="description or notes for scenario creation")
        if name == "audit":
            p.add_argument("--developmental", action="store_true", default=True, help="include full developmental telemetry")
            p.add_argument("--deep", action="store_true", help="run multi-dimensional literary, linguistic, and craft metrics")
            p.add_argument("--scene", help="drill-down into metrics and attribution for a single scene ID (e.g. SCN-001)")
            p.add_argument("--compare", nargs="?", const="baseline", help="compare current metrics against a Git baseline (default: stage baseline)")
            p.add_argument("--no-cache", action="store_true", help="bypass metrics cache and force full recomputation")
            p.add_argument("--report", action="store_true", help="generate a comprehensive markdown analysis report with wiki-links")
            p.add_argument("--output", help="destination file path for the report (default: reports/analysis-<timestamp>.md)")
        if name == "takes":
            p.add_argument("action", choices=["list", "save", "diff", "activate", "delete"], help="take action")
            p.add_argument("id", nargs="?", default="all", help="scene ID, e.g. SCN-001")
            p.add_argument("take", nargs="?", help="take name (e.g. first-person, noir, v2)")
            p.add_argument("take2", nargs="?", help="second take name for diffing two takes")
            p.add_argument("--layer", choices=["manuscript", "abridged"], default="manuscript", help="target layer")
            p.add_argument("--locale", help="target manuscript locale (default: primary language)")
            p.add_argument("-m", "--message", default="", help="notes or description for saving a take")
    args = ap.parse_args(argv)
    if not args.command:
        args.command, args.json = "status", False
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    root = Path(args.root).resolve()
    handlers = {"init": cmd_init, "status": cmd_status, "check": cmd_check, "dag": cmd_dag, "next-id": cmd_next_id,
                "trace": cmd_trace, "delta": cmd_delta, "impact": cmd_impact, "accept": cmd_accept, "index": cmd_index,
                "stats": cmd_stats, "compile": cmd_compile, "log": cmd_log, "feedback": cmd_feedback,
                "placeholders": cmd_placeholders, "bibliography": cmd_bibliography, "models": cmd_models,
                "harvest": cmd_harvest, "scenario": cmd_scenario, "audit": cmd_audit, "takes": cmd_takes}
    try:
        if args.command == "init":
            return cmd_init(root, args)
        return handlers[args.command](Git(root), args)
    except NovelError as e:
        print(f"specnovel: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
