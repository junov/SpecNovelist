#!/usr/bin/env python3
"""SpecNovelist helper for spec-driven novel writing in a git repository.

A novel project is organized in 8 sequential stages plus a cross-stage directives directory:

  1. setup/        Synopsis, themes (THM), project configuration (config.md), brief.md, style.md.
  2. research/     Research questions (RQ) needed for world building.
  3. world/        Facts (FCT) & sources (SRC), characters (CHR), places (PLC), organizations (ORG),
                   objects (OBJ), world rules (WLD), timeline (TML), and glossary (GLS).
  4. narrative/    Story arcs (ARC), narrative beats (BET - forming a DAG rooted at the denouement),
                   and textual illustration specifications (ILL).
  5. structure/    Physical structure: Volumes (VOL), front/back matter (including mandatory
                   acknowledgements.md), Acts (ACT), Chapters (CHP), and Scenes (SCN - ordered
                   sequences of beats and illustrations).
  6. abridged/     Condensed novel chapters (all beats, plot movements, and key dialogues).
  7. manuscript/   Polished literary prose organized by target locale (manuscript/<locale>/CHP-NNN.md).
  8. publishable/  Rendered graphical assets (publishable/graphics/ILL-NNN.png) and compiled books.

  directives/      Cross-stage directives (DIR-NNN) that lock in user feedback and factor shared
                   instructions referenced by records at any stage via [[DIR-NNN]].

Standard library only; Python 3.8+.
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
SETUP = "setup"
RESEARCH = "research"
WORLD = "world"
NARRATIVE = "narrative"
STRUCTURE = "structure"
ABRIDGED = "abridged"
MANUSCRIPT = "manuscript"
PUBLISHABLE = "publishable"
DIRECTIVES = "directives"

STAGES = (
    SETUP,        # Stage 1
    RESEARCH,     # Stage 2
    WORLD,        # Stage 3
    NARRATIVE,    # Stage 4
    STRUCTURE,    # Stage 5
    ABRIDGED,     # Stage 6
    MANUSCRIPT,   # Stage 7
    PUBLISHABLE,  # Stage 8
)

SPEC_STAGES = (SETUP, RESEARCH, WORLD, NARRATIVE, STRUCTURE)
DERIVED_STAGES = (ABRIDGED, MANUSCRIPT, PUBLISHABLE)
PLAN_DIRS = (SETUP, RESEARCH, WORLD, NARRATIVE, STRUCTURE, DIRECTIVES)
ALL_DIRS = (SETUP, RESEARCH, WORLD, NARRATIVE, STRUCTURE, ABRIDGED, MANUSCRIPT, PUBLISHABLE, DIRECTIVES)
LAYERS = {"abridged": ABRIDGED, "manuscript": MANUSCRIPT}

SYNOPSIS_FILE = "setup/synopsis.md"
BRIEF_FILE = "setup/brief.md"
STYLE_FILE = "setup/style.md"
CONFIG_FILE = "setup/config.md"
THEMES_FILE = "setup/themes.md"
QUESTIONS_FILE = "research/questions.md"
ARCS_FILE = "narrative/arcs.md"
BEATS_FILE = "narrative/beats.md"
ILLUSTRATIONS_FILE = "narrative/illustrations.md"
OUTLINE_FILE = "structure/outline.md"
ACKNOWLEDGEMENTS_FILE = "structure/back-matter/acknowledgements.md"
GRAPHICS_DIR = "publishable/graphics"
MIN_STYLE_WORDS = 400

STAGE_DIRS: Dict[str, Tuple[str, ...]] = {
    SETUP: (SETUP,),
    RESEARCH: (RESEARCH,),
    WORLD: (WORLD,),
    NARRATIVE: (NARRATIVE,),
    STRUCTURE: (STRUCTURE,),
    ABRIDGED: (ABRIDGED,),
    MANUSCRIPT: (MANUSCRIPT,),
    PUBLISHABLE: (PUBLISHABLE,),
}

UPSTREAM_DIRS: Dict[str, Tuple[str, ...]] = {
    SETUP: (SETUP, DIRECTIVES),
    RESEARCH: (SETUP, DIRECTIVES),
    WORLD: (SETUP, RESEARCH, DIRECTIVES),
    NARRATIVE: (SETUP, RESEARCH, WORLD, DIRECTIVES),
    STRUCTURE: (SETUP, RESEARCH, WORLD, NARRATIVE, DIRECTIVES),
    ABRIDGED: (SETUP, RESEARCH, WORLD, NARRATIVE, STRUCTURE, DIRECTIVES),
    MANUSCRIPT: (SETUP, RESEARCH, WORLD, NARRATIVE, STRUCTURE, ABRIDGED, DIRECTIVES),
    PUBLISHABLE: (SETUP, RESEARCH, WORLD, NARRATIVE, STRUCTURE, ABRIDGED, MANUSCRIPT, DIRECTIVES),
}

GENERATED = {"world/INDEX.md"}
WORLD_FOLDERS = (
    "facts", "sources", "characters", "places", "organizations",
    "objects", "rules", "timeline", "glossary"
)

TYPES: "OrderedDict[str, str]" = OrderedDict([
    # Stage 1: Setup
    ("THM", "theme"),
    ("STY", "style rule"),
    # Stage 2: Research Questions
    ("RQ", "research question"),
    # Stage 3: World
    ("FCT", "fact"),
    ("SRC", "source"),
    ("CHR", "character"),
    ("PLC", "place"),
    ("ORG", "organization"),
    ("OBJ", "object"),
    ("WLD", "world rule"),
    ("TML", "timeline event"),
    ("GLS", "glossary entry"),
    # Stage 4: Narrative Structure
    ("ARC", "story arc"),
    ("BET", "narrative beat"),
    ("ILL", "illustration"),
    # Stage 5: Physical Structure
    ("VOL", "volume"),
    ("ACT", "act"),
    ("PRT", "part"),
    ("CHP", "chapter"),
    ("SCN", "scene"),
    # Cross-Stage: Directives
    ("DIR", "directive"),
])

PREFIX_STAGE: Dict[str, str] = {
    "THM": SETUP, "STY": SETUP,
    "RQ": RESEARCH,
    "FCT": WORLD, "SRC": WORLD, "CHR": WORLD, "PLC": WORLD,
    "ORG": WORLD, "OBJ": WORLD, "WLD": WORLD, "TML": WORLD, "GLS": WORLD,
    "ARC": NARRATIVE, "BET": NARRATIVE, "ILL": NARRATIVE,
    "VOL": STRUCTURE, "ACT": STRUCTURE, "PRT": STRUCTURE, "CHP": STRUCTURE, "SCN": STRUCTURE,
    "DIR": DIRECTIVES,
}

STORY_TYPES = {"CHR", "PLC", "ORG", "OBJ", "THM", "WLD", "TML", "FCT", "GLS", "ARC", "BET", "ILL"}


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
            pattern = rf"\b({re.escape(stage)}|plan|all)\b"
        elif stage in DERIVED_STAGES:
            pattern = rf"\b({re.escape(stage)}|all)\b"
        elif stage == "plan":
            pattern = r"\b(plan|all)\b"
        elif stage == "all":
            pattern = r"\ball\b"
        else:
            pattern = rf"\b{re.escape(stage)}\b"
        out = self.lines("log", "-1", "--format=%H", "--extended-regexp",
                         f"--grep=^{TRAILER}:.*{pattern}", "HEAD")
        return out[0].strip() if out else None

    def ill_baseline(self, ill_id: str) -> Optional[str]:
        """Most recent commit reachable from HEAD with Novel-ILL-Sync or Novel-GFX-Sync trailer containing ``ill_id``."""
        if not self.has_commits():
            return None
        pattern = rf"\b{re.escape(ill_id)}\b"
        out = self.lines("log", "-1", "--format=%H", "--extended-regexp",
                         f"--grep=^Novel-(ILL|GFX)-Sync:.*{pattern}", "HEAD")
        return out[0].strip() if out else None

    def commits_behind(self, sha: Optional[str]) -> int:
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
        existing = [f for f in folders if (self.root / f).exists()]
        if not existing:
            return []
        files = set(self.lines("ls-files", "--cached", "--others", "--exclude-standard", "--", *existing))
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
        existing = [f for f in folders if (self.root / f).exists()]
        if not existing:
            return []
        out = []
        for l in self.lines("diff", "--name-status", sha, "--", *existing):
            parts = l.split("\t")
            out.append({"change": parts[0], "file": parts[-1]})
        for f in self.lines("ls-files", "--others", "--exclude-standard", "--", *existing):
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
    parent: Optional[str] = None
    raw: List[Tuple[int, str, bool]] = field(default_factory=list)
    lines: List[str] = field(default_factory=list)
    refs: List[Tuple[str, int]] = field(default_factory=list)
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
        """Extract the text value of a named field."""
        for name in names:
            pattern = re.sub(r"[-_\s]+", r"[-_\\s]+", re.escape(name))
            m = re.search(r"^\s*[-*]?\s*\**" + pattern + r"\**\s*:\**\s*(.*)$", self.text, re.I | re.M)
            if m:
                val = COMMENT_RE.sub("", m.group(1)).strip()
                if val:
                    return val
                lines_after: List[str] = []
                in_field = False
                for line in self.lines:
                    if re.match(r"^\s*[-*]?\s*\**" + pattern + r"\**\s*:\**", line, re.I):
                        in_field = True
                        continue
                    if in_field:
                        clean_line = COMMENT_RE.sub("", line).strip()
                        if re.match(r"^\s+[-*\d\.]+\s+", line) or (line.startswith(" ") and clean_line):
                            lines_after.append(clean_line)
                        elif re.match(r"^\s*[-*]?\s*\**[a-zA-Z0-9_-]+\**\s*:\**", line) or re.match(r"^#{1,6}\s+", line):
                            break
                if lines_after:
                    return " ".join(lines_after).strip()
        return None

    def ref_ids(self) -> Set[str]:
        return {r for r, _ in self.refs}

    def ref_ids_for_field(self, *names: str) -> Set[str]:
        ids: Set[str] = set()
        val = self.field_value(*names)
        if val:
            for ref_match in REF_RE.finditer(val):
                ids.add(ref_match.group("id"))
        return ids

    def ordered_ref_ids_for_field(self, *names: str) -> List[str]:
        """Extract [[ID]] references from named fields preserving exact sequence order."""
        out: List[str] = []
        val = self.field_value(*names)
        if val:
            for ref_match in REF_RE.finditer(val):
                rid = ref_match.group("id")
                if rid not in out:
                    out.append(rid)
        return out

    def prereq_ids(self) -> Set[str]:
        """Extract dependency / prerequisite IDs declared in this beat or section."""
        ids: Set[str] = set()
        in_prereq_block = False
        field_rx = re.compile(
            r"^\s*[-*]?\s*\**(?:dependencies|dependency|depends[-_\s]*on|prerequisites?|prereqs?|requires?)\**\s*:\**\s*(.*)$",
            re.I
        )
        for line in self.lines:
            m = field_rx.match(line)
            if m:
                content = COMMENT_RE.sub("", m.group(1)).strip()
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

    def directive_ids(self) -> Set[str]:
        """Extract all [[DIR-NNN]] references associated with this section."""
        out = {r for r, _ in self.refs if r.startswith("DIR-")}
        # Also check HTML comments for manuscript sections where directives are embedded as comments
        for line in self.lines:
            for m in REF_RE.finditer(line):
                if m.group("id").startswith("DIR-"):
                    out.add(m.group("id"))
        return out

    @property
    def is_denouement(self) -> bool:
        return re.search(r"^\s*[-*]?\s*\**(?:denouement|root)\**\s*:\**\s*(?:true|yes|1)\b", self.text, re.I | re.M) is not None


def normalize(lines: Sequence[str]) -> List[str]:
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
        if rel in GENERATED or rel.endswith("/template.md"):
            continue
        if "/scenarios/" in rel or "/takes/" in rel or ".take-" in rel:
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


# ------------------------------------------------------------------ Stage 4 (Narrative) & Stage 5 (Physical Structure)
@dataclass
class Narrative:
    arcs: List[str] = field(default_factory=list)
    beats: List[str] = field(default_factory=list)
    illustrations: List[str] = field(default_factory=list)
    beat_deps: Dict[str, Set[str]] = field(default_factory=dict)
    beat_arcs: Dict[str, Set[str]] = field(default_factory=dict)
    beat_places: Dict[str, Set[str]] = field(default_factory=dict)
    beat_time: Dict[str, str] = field(default_factory=dict)
    denouement_beats: List[str] = field(default_factory=list)
    problems: List[str] = field(default_factory=list)


def narrative_of(model: Model) -> Narrative:
    nar = Narrative()
    for sid, s in model.defs.items():
        in_narrative = s.file.startswith(NARRATIVE + "/")
        if s.prefix in ("ARC", "BET", "ILL") and not in_narrative:
            nar.problems.append(f"{sid} is defined outside {NARRATIVE}/ ({s.location})")
            continue
        if not in_narrative:
            continue
        if s.prefix == "ARC":
            nar.arcs.append(sid)
        elif s.prefix == "ILL":
            nar.illustrations.append(sid)
        elif s.prefix == "BET":
            nar.beats.append(sid)
            # 1. Place validation
            places = s.ref_ids_for_field("place", "where", "setting", "location")
            if not places:
                places = {r for r in s.ref_ids() if r.startswith("PLC-")}
            nar.beat_places[sid] = places
            if not places:
                nar.problems.append(f"beat {sid} is missing a valid Place referencing [[PLC-...]] ({s.location})")

            # 2. Time validation
            tval = s.field_value("time", "when", "date", "timeline")
            if not tval or (tval.startswith("<") and tval.endswith(">")) or tval.lower() in {"todo", "tbd", "unspecified", "none"}:
                nar.problems.append(f"beat {sid} is missing valid Time metadata ({s.location})")
            else:
                nar.beat_time[sid] = tval

            # 3. Arcs validation
            arcs = s.ref_ids_for_field("arcs", "arc", "story_arc", "story-arc", "plot")
            if not arcs:
                arcs = {r for r in s.ref_ids() if r.startswith("ARC-")}
            nar.beat_arcs[sid] = arcs
            if not arcs:
                nar.problems.append(f"beat {sid} must be associated with at least one story arc [[ARC-...]] ({s.location})")

            # 4. Dependencies
            deps = s.prereq_ids()
            for d in sorted(deps):
                if not d.startswith("BET-"):
                    nar.problems.append(f"beat {sid} declares non-beat dependency [[{d}]]; beat dependencies must refer to other beats (BET-...) ({s.location})")
                elif d == sid:
                    nar.problems.append(f"beat {sid} cannot depend on itself ({s.location})")
            nar.beat_deps[sid] = {d for d in deps if d.startswith("BET-")}

            if s.is_denouement:
                nar.denouement_beats.append(sid)

    return nar


@dataclass
class Outline:
    volumes: List[str] = field(default_factory=list)
    acts: List[str] = field(default_factory=list)
    parts: List[str] = field(default_factory=list)  # alias of acts for compatibility
    chapters: List[str] = field(default_factory=list)
    scenes: List[str] = field(default_factory=list)
    volume_of: Dict[str, Optional[str]] = field(default_factory=dict)
    act_of: Dict[str, Optional[str]] = field(default_factory=dict)
    part_of: Dict[str, Optional[str]] = field(default_factory=dict)
    chapter_of: Dict[str, str] = field(default_factory=dict)
    by_chapter: "OrderedDict[str, List[str]]" = field(default_factory=OrderedDict)
    scene_sequence: Dict[str, List[str]] = field(default_factory=dict)       # SCN -> ordered [BET-..., ILL-...]
    scene_beats: Dict[str, List[str]] = field(default_factory=dict)          # SCN -> ordered [BET-...]
    scene_illustrations: Dict[str, List[str]] = field(default_factory=dict)  # SCN -> ordered [ILL-...]
    beat_positions: Dict[str, Tuple[int, int, str]] = field(default_factory=dict)  # BET -> (scene_idx, seq_idx, SCN)
    problems: List[str] = field(default_factory=list)


def ancestors(model: Model, sid: str) -> List[Section]:
    out, cur = [], model.defs.get(sid)
    while cur is not None:
        out.append(cur)
        cur = model.defs.get(cur.parent) if cur.parent else None
    return out


def outline_of(model: Model) -> Outline:
    o = Outline()
    for sid, s in model.defs.items():
        in_structure = s.file.startswith(STRUCTURE + "/")
        if s.prefix in ("VOL", "ACT", "PRT", "CHP", "SCN") and not in_structure:
            o.problems.append(f"{sid} is defined outside {STRUCTURE}/ ({s.location})")
            continue
        if not in_structure:
            continue
        if s.prefix == "VOL":
            o.volumes.append(sid)
        elif s.prefix in ("ACT", "PRT"):
            o.acts.append(sid)
            o.parts.append(sid)
            for anc in ancestors(model, sid):
                if anc.prefix == "VOL":
                    o.volume_of[sid] = anc.id
                    break
        elif s.prefix == "CHP":
            o.chapters.append(sid)
            o.by_chapter[sid] = []
            act_id, vol_id = None, None
            for anc in ancestors(model, sid):
                if anc.prefix in ("ACT", "PRT") and not act_id:
                    act_id = anc.id
                elif anc.prefix == "VOL" and not vol_id:
                    vol_id = anc.id
            o.act_of[sid] = act_id
            o.part_of[sid] = act_id
            o.volume_of[sid] = vol_id
        elif s.prefix == "SCN":
            chp_id = None
            for anc in ancestors(model, sid):
                if anc.prefix == "CHP":
                    chp_id = anc.id
                    break
            if chp_id:
                o.scenes.append(sid)
                o.chapter_of[sid] = chp_id
                o.by_chapter.setdefault(chp_id, []).append(sid)
                # Extract ordered sequence of beats and illustrations
                seq = s.ordered_ref_ids_for_field("sequence", "beats_and_illustrations", "elements")
                if not seq:
                    # Combine ordered refs from Beats/Illustrations fields or body in appearance order
                    for rid, _ in s.refs:
                        if rid.startswith(("BET-", "ILL-")) and rid not in seq:
                            seq.append(rid)
                o.scene_sequence[sid] = seq
                o.scene_beats[sid] = [r for r in seq if r.startswith("BET-")]
                o.scene_illustrations[sid] = [r for r in seq if r.startswith("ILL-")]
            else:
                o.problems.append(f"scene {sid} is not nested under a chapter heading ({s.location})")

    # Compute global beat positions in reading order: (1-based scene index, 1-based sequence index in scene, scene ID)
    for scn_idx, sid in enumerate(o.scenes, 1):
        for seq_idx, bid in enumerate(o.scene_beats.get(sid, []), 1):
            if bid not in o.beat_positions:
                o.beat_positions[bid] = (scn_idx, seq_idx, sid)

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


# ------------------------------------------------------------------ configuration parser
def parse_config_markdown(text: str) -> dict:
    """Parse Markdown-based project configuration (setup/config.md)."""
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
CONFIG_ALLOWED_AUTHOR_KEYS = {"name", "legal_name", "email", "url"}
CONFIG_ALLOWED_LANGUAGES_KEYS = {"primary", "targets", "target_languages"}
CONFIG_ALLOWED_FRONT_KEYS = {"foreword", "foreword_file", "dedication", "epigraph", "preface"}
CONFIG_ALLOWED_BACK_KEYS = {
    "include_glossary", "include_bibliography", "historical_note", "historical_note_file",
    "afterword", "acknowledgments", "acknowledgements", "acknowledgments_file", "acknowledgements_file"
}
CONFIG_ALLOWED_COMPILATION_KEYS = {
    "include_glossary", "include_bibliography", "foreword", "foreword_file",
    "historical_note", "historical_note_file"
}
CONFIG_ALLOWED_BUDGET_KEYS = {"target_words", "tolerance_pct", "expansion_factors"}
CONFIG_ALLOWED_PUBLICATION_KEYS = {"publisher", "imprint", "isbn"}
CONFIG_ALLOWED_AUTHORING_KEYS = {"harvest_mode"}


@dataclass
class ProjectConfig:
    raw: dict = field(default_factory=dict)
    schema_version: str = "2.0"
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

    for k in raw:
        if k not in CONFIG_ALLOWED_TOP_KEYS:
            errors.append(f"unknown top-level configuration key '{k}'")

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
    foreword_path, dedication, epigraph = None, None, None
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
    include_glossary, include_bibliography = True, True
    historical_note_path, afterword_path, acknowledgments_path = None, None, None
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
        schema_version=schema_version or "2.0",
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
    if md_path.is_file():
        try:
            raw = parse_config_markdown(md_path.read_text(encoding="utf-8", errors="replace"))
            return validate_and_load_config(raw)
        except Exception as e:
            return ProjectConfig(errors=[f"failed to parse {CONFIG_FILE}: {e}"])
    return ProjectConfig(errors=[f"missing project configuration file: {CONFIG_FILE}"])


# ------------------------------------------------------------------ project state
@dataclass
class Project:
    git: Git
    plan: Model
    narrative: Narrative
    outline: Outline
    layers: Dict[str, Derived]
    config: ProjectConfig = field(default_factory=ProjectConfig)
    manuscript_locales: Dict[str, Derived] = field(default_factory=dict)


def load_project(git: Git) -> Project:
    plan = build_model(git.working_md(*PLAN_DIRS))
    cfg = load_project_config(git)
    nar = narrative_of(plan)
    out = outline_of(plan)

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
    return Project(git, plan, nar, out, layers, cfg, manuscript_locales)


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


# ------------------------------------------------------------------ directives subsystem (DIR-NNN)
def stage_of_section(sec: Section) -> str:
    top_dir = sec.file.split("/", 1)[0]
    if top_dir in STAGES or top_dir == DIRECTIVES:
        return top_dir
    return PREFIX_STAGE.get(sec.prefix, "unknown")


def effective_refs_of_section(sec: Section, p: Project) -> Set[str]:
    """Return all IDs referenced by this section, including transitive refs through sequenced beats for scenes."""
    refs = set(sec.ref_ids())
    if sec.id and sec.prefix == "SCN":
        for anc in ancestors(p.plan, sec.id):
            refs |= anc.ref_ids()
        for bid in p.outline.scene_beats.get(sec.id, []):
            bsec = p.plan.defs.get(bid)
            if bsec:
                refs |= bsec.ref_ids()
        for iid in p.outline.scene_illustrations.get(sec.id, []):
            isec = p.plan.defs.get(iid)
            if isec:
                refs |= isec.ref_ids()
    elif sec.id and sec.prefix == "BET":
        for anc in ancestors(p.plan, sec.id):
            refs |= anc.ref_ids()
    return refs


def is_directive_relevant_to_section(dir_sec: Section, target_sec: Section, p: Project) -> bool:
    """Determine if a directive (DIR-NNN) is specifically relevant to a given record."""
    if not dir_sec.id or not target_sec.id or dir_sec.id == target_sec.id or target_sec.prefix == "DIR":
        return False

    status = (dir_sec.field_value("status") or "active").strip().lower()
    if status in ("superseded", "wontfix", "inactive", "closed"):
        return False

    dir_stage_raw = (dir_sec.field_value("stage", "stages") or "all").strip().lower()
    dir_stages = {s.strip() for s in re.split(r"[,/\s]+", dir_stage_raw) if s.strip()}
    target_stg = stage_of_section(target_sec)

    scope_val = (dir_sec.field_value("scope", "target", "targets", "applies_to", "applies-to") or "").strip()
    scope_refs = dir_sec.ref_ids_for_field("scope", "target", "targets", "applies_to", "applies-to")
    if not scope_refs:
        scope_refs = {r for r in dir_sec.ref_ids() if r != dir_sec.id}

    # 1. Direct ID match in Scope
    if target_sec.id in scope_refs or (scope_val and re.search(rf"\b{re.escape(target_sec.id)}\b", scope_val)):
        return True

    # Check stage compatibility for non-direct matches
    if "all" not in dir_stages and "global" not in dir_stages and target_stg not in dir_stages:
        return False

    # 2. Prefix filter in Scope (e.g. prefix:BET, prefix:SCN)
    prefix_matches = [m.group(1).upper() for m in re.finditer(r"\bprefix\s*:\s*([A-Za-z0-9]+)\b", scope_val, re.I)]
    if prefix_matches and target_sec.prefix not in prefix_matches:
        return False

    target_effective_refs = effective_refs_of_section(target_sec, p)

    # 3. Entity overlap match: if directive scopes specific entities (e.g. [[CHR-001]], [[PLC-001]], [[ARC-001]], [[BET-001]])
    non_dir_scope_refs = {r for r in scope_refs if not r.startswith("DIR-")}
    if non_dir_scope_refs:
        if target_effective_refs & non_dir_scope_refs:
            return True
        return False

    # 4. Keyword / tag match in Scope (e.g. tag:telegram, keyword:wireless)
    kw_matches = [m.group(1).lower() for m in re.finditer(r"\b(?:tag|keyword)\s*:\s*([A-Za-z0-9_\-]+)\b", scope_val, re.I)]
    if kw_matches:
        t_lower = target_sec.text.lower()
        if any(kw in t_lower for kw in kw_matches):
            return True
        return False

    # 5. Pure prefix match (when no specific entity refs were required)
    if prefix_matches and target_sec.prefix in prefix_matches:
        return True

    # 6. Global scope for the target stage
    if scope_val.lower() in ("all", "global", "*"):
        return True

    return False


def match_directives_for_section(target_sec: Section, p: Project) -> List[str]:
    """Return sorted list of DIR-NNN IDs relevant to target_sec."""
    matched: List[str] = []
    for dir_sec in p.plan.of_type("DIR"):
        if is_directive_relevant_to_section(dir_sec, target_sec, p):
            matched.append(dir_sec.id)
    return sorted(matched)


def inject_directive_links_into_file(root: Path, rel_file: str, section_id: str, new_dir_ids: List[str]) -> bool:
    """Insert or append [[DIR-NNN]] links into a section in rel_file."""
    if not new_dir_ids:
        return False
    fpath = root / rel_file
    if not fpath.is_file():
        return False
    text = fpath.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    is_manuscript = rel_file.startswith(MANUSCRIPT + "/")

    # Locate section heading
    sec_start = None
    sec_level = 0
    sec_end = len(lines)
    in_fence = False

    for idx, line in enumerate(lines):
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = HEADING_RE.match(line)
        if m:
            lvl, htext = len(m.group(1)), m.group(2).strip()
            rm = ID_HEADING_RE.match(htext)
            if sec_start is None:
                if rm and rm.group("id") == section_id:
                    sec_start = idx
                    sec_level = lvl
            else:
                if lvl <= sec_level or rm:
                    sec_end = idx
                    break

    if sec_start is None:
        return False

    # Check if Directives field or comment already exists in [sec_start+1 : sec_end]
    dir_links_str = ", ".join(f"[[{d}]]" for d in new_dir_ids)
    for idx in range(sec_start + 1, sec_end):
        if is_manuscript:
            m_com = re.match(r"^(\s*<!--\s*Directives:\s*)(.*?)(\s*-->\s*)$", lines[idx], re.I)
            if m_com:
                existing = m_com.group(2).strip()
                sep = ", " if existing else ""
                lines[idx] = f"{m_com.group(1)}{existing}{sep}{dir_links_str}{m_com.group(3)}"
                fpath.write_text("\n".join(lines) + "\n", encoding="utf-8")
                return True
        else:
            m_fld = re.match(r"^(\s*[-*]\s*\**Directives?\**\s*:\**\s*)(.*)$", lines[idx], re.I)
            if m_fld:
                existing = m_fld.group(2).strip()
                if existing.lower() in ("none", "null", "-"):
                    lines[idx] = f"{m_fld.group(1)}{dir_links_str}"
                else:
                    sep = ", " if existing else ""
                    lines[idx] = f"{m_fld.group(1)}{existing}{sep}{dir_links_str}"
                fpath.write_text("\n".join(lines) + "\n", encoding="utf-8")
                return True

    # Otherwise insert right after the heading (or after initial metadata bullets)
    insert_at = sec_start + 1
    if is_manuscript:
        lines.insert(insert_at, f"<!-- Directives: {dir_links_str} -->")
    else:
        while insert_at < sec_end and re.match(r"^\s*[-*]\s+\**[A-Za-z0-9_\s/-]+\**\s*:", lines[insert_at]):
            insert_at += 1
        lines.insert(insert_at, f"- **Directives:** {dir_links_str}")

    fpath.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return True


def auto_link_directives_in_project(
    p: Project,
    stage_filter: Optional[str] = None,
    record_id: Optional[str] = None,
    only_ids: Optional[Set[str]] = None
) -> List[Dict[str, Any]]:
    """Automatically link pre-existing relevant directives to records."""
    linked_events: List[Dict[str, Any]] = []
    candidate_sections: List[Section] = []

    for sid, sec in p.plan.defs.items():
        if sec.prefix == "DIR":
            continue
        if record_id and sid != record_id:
            continue
        if only_ids is not None and sid not in only_ids:
            continue
        if stage_filter and stage_filter != "all" and stage_of_section(sec) != stage_filter:
            continue
        candidate_sections.append(sec)

    for layer_name, d in p.layers.items():
        if stage_filter and stage_filter not in ("all", layer_name):
            continue
        for sid, sec in d.scenes.items():
            if record_id and sid != record_id:
                continue
            if only_ids is not None and sid not in only_ids:
                continue
            candidate_sections.append(sec)

    for sec in candidate_sections:
        relevant_dirs = match_directives_for_section(sec, p)
        if not relevant_dirs:
            continue
        existing_dirs = sec.directive_ids()
        missing_dirs = [d for d in relevant_dirs if d not in existing_dirs]
        if missing_dirs:
            if inject_directive_links_into_file(p.git.root, sec.file, sec.id, missing_dirs):
                linked_events.append({
                    "record": sec.id,
                    "file": sec.file,
                    "stage": stage_of_section(sec),
                    "linked_directives": missing_dirs
                })

    return linked_events


def check_preserved_directives(p: Project) -> List[str]:
    """Verify that synchronization/edits have not dropped active directive links from existing records."""
    errors: List[str] = []
    git = p.git
    if not git.has_commits():
        return errors

    active_dirs = {
        d.id for d in p.plan.of_type("DIR")
        if (d.field_value("status") or "active").strip().lower() not in ("superseded", "wontfix", "inactive", "closed")
    }
    if not active_dirs:
        return errors

    for st in SPEC_STAGES:
        base = git.baseline(st)
        if not base:
            continue
        old_model = build_model(git.commit_md(base, *STAGE_DIRS[st]))
        for rid, old_sec in old_model.defs.items():
            if rid not in p.plan.defs:
                continue
            new_sec = p.plan.defs[rid]
            old_dirs = old_sec.directive_ids() & active_dirs
            new_dirs = new_sec.directive_ids()
            dropped = sorted(old_dirs - new_dirs)
            for d_id in dropped:
                errors.append(
                    f"directive preservation violation: record {rid} in stage '{st}' dropped associated directive [[{d_id}]] ({new_sec.location})"
                )

    for st in ("abridged", "manuscript"):
        base = git.baseline(st)
        if not base:
            continue
        old_d = derived_of(build_model(git.commit_md(base, STAGE_DIRS[st][0])))
        cur_d = p.layers[st]
        for sid, old_sec in old_d.scenes.items():
            if sid not in cur_d.scenes:
                continue
            new_sec = cur_d.scenes[sid]
            old_dirs = old_sec.directive_ids() & active_dirs
            new_dirs = new_sec.directive_ids()
            dropped = sorted(old_dirs - new_dirs)
            for d_id in dropped:
                errors.append(
                    f"directive preservation violation: scene {sid} in stage '{st}' dropped associated directive [[{d_id}]] ({new_sec.location})"
                )

    return errors


# ------------------------------------------------------------------ Beat DAG & Physical Structure Serialization
@dataclass
class StoryDAG:
    nodes: Set[str] = field(default_factory=set)
    edges: Dict[str, Set[str]] = field(default_factory=dict)          # u -> {v}: u must precede v
    reverse_edges: Dict[str, Set[str]] = field(default_factory=dict)  # v -> {u}: v depends on u
    root: Optional[str] = None
    positions: Dict[str, int] = field(default_factory=dict)           # ID -> 1-based scene index
    beat_order: Dict[str, Tuple[int, int]] = field(default_factory=dict)  # BET -> (scene_idx, seq_idx)


def build_story_dag(p: Project) -> StoryDAG:
    dag = StoryDAG()
    plan, nar, o = p.plan, p.narrative, p.outline

    # 1. Map reading positions from Stage 5 (Physical Structure)
    for idx, sid in enumerate(o.scenes, 1):
        dag.positions[sid] = idx
        for a in ancestors(plan, sid):
            for rid in a.ref_ids():
                if rid not in dag.positions:
                    dag.positions[rid] = idx
        for bid in o.scene_beats.get(sid, []):
            bsec = plan.defs.get(bid)
            if bsec:
                for rid in bsec.ref_ids():
                    if rid not in dag.positions:
                        dag.positions[rid] = idx

    for bid, (scn_idx, seq_idx, _) in o.beat_positions.items():
        dag.beat_order[bid] = (scn_idx, seq_idx)
        if bid not in dag.positions:
            dag.positions[bid] = scn_idx

    # 2. Populate nodes & edges from Stage 4 Beat DAG (BET-NNN)
    for bid in nar.beats:
        dag.nodes.add(bid)
        for dep in nar.beat_deps.get(bid, set()):
            dag.nodes.add(dep)
            dag.edges.setdefault(dep, set()).add(bid)
            dag.reverse_edges.setdefault(bid, set()).add(dep)

    # Identify root denouement beat
    explicit_root = None
    if nar.denouement_beats:
        explicit_root = nar.denouement_beats[0]
    if not explicit_root:
        for sec in plan.sections():
            m = re.search(r"^\s*[-*]?\s*\**(?:denouement|root)\**\s*:\**\s*(?:\[\[\s*)?(?P<id>[A-Z][A-Z0-9]*-\d{3,})", sec.text, re.I | re.M)
            if m:
                cand = m.group("id")
                if cand in plan.defs:
                    explicit_root = cand
                    break
    if not explicit_root and nar.beats:
        explicit_root = nar.beats[-1]
    elif not explicit_root and o.scenes:
        explicit_root = o.scenes[-1]

    dag.root = explicit_root

    # 3. Plant -> Payoff causal edges across beats
    beat_list = [bid for bid, _ in sorted(dag.beat_order.items(), key=lambda x: x[1])] if dag.beat_order else list(nar.beats)
    for bid in beat_list:
        bsec = plan.defs.get(bid)
        if not bsec:
            continue
        pays_off = bsec.ref_ids_for_field("pays_off", "pays-off", "paysoff", "payoff", "pays")
        for poy_id in pays_off:
            for earlier_bid in beat_list:
                if earlier_bid == bid:
                    break
                earlier_sec = plan.defs.get(earlier_bid)
                if earlier_sec and poy_id in earlier_sec.ref_ids_for_field("plants", "plant", "setups", "setup"):
                    dag.edges.setdefault(earlier_bid, set()).add(bid)
                    dag.reverse_edges.setdefault(bid, set()).add(earlier_bid)

    return dag


def check_dag_cycles(dag: StoryDAG) -> List[str]:
    state: Dict[str, int] = {}
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


def check_reading_order_coherence(dag: StoryDAG, p: Project) -> List[str]:
    """Verify that Stage 5 (Physical Structure) serializes the Stage 4 Beat DAG in valid topological order."""
    errors: List[str] = []
    o = p.outline
    if not o.scenes:
        return errors

    for node in sorted(dag.nodes):
        if not node.startswith("BET-"):
            continue
        if node not in o.beat_positions:
            errors.append(f"reading order violation: beat {node} is defined in {NARRATIVE}/ but not scheduled in any scene in {STRUCTURE}/")
            continue
        node_scn_idx, node_seq_idx, node_scn = o.beat_positions[node]
        prereqs = dag.reverse_edges.get(node, set())
        for req in sorted(prereqs):
            if req not in o.beat_positions:
                errors.append(f"reading order violation: dependency {req} of {node} never appears in any scene in {STRUCTURE}/")
                continue
            req_scn_idx, req_seq_idx, req_scn = o.beat_positions[req]
            if (req_scn_idx, req_seq_idx) >= (node_scn_idx, node_seq_idx):
                errors.append(
                    f"reading order violation: beat {node} (in {node_scn}, scene #{node_scn_idx}) depends on {req} "
                    f"(in {req_scn}, scene #{req_scn_idx}), but {req} does not precede {node} in reading order"
                )
    return errors


def check_essentiality_to_root(dag: StoryDAG, p: Optional[Project] = None) -> Tuple[Optional[str], List[str]]:
    errors: List[str] = []
    if not dag.nodes:
        return None, []
    if not dag.root:
        return None, ["no root denouement beat found"]
    if dag.root not in dag.nodes:
        return dag.root, [f"designated root denouement {dag.root} does not exist in the Beat DAG"]

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
        artistic_functions = {
            "atmospheric-breather", "thematic-mirror", "comic-relief",
            "character-reflection", "epistolary-interlude", "pacing-breather",
            "breather", "thematic-pause", "reflection"
        }
        for n in list(inessential):
            sec = p.plan.defs.get(n)
            if sec:
                func = (sec.field_value("function", "role") or "").strip().lower()
                if func in artistic_functions:
                    reachable.add(n)
                    inessential.remove(n)

    for n in inessential:
        errors.append(f"inessential element: {n} has no causal path to the root denouement ({dag.root})")
    return dag.root, errors


def check_epistemic_and_setup_payoffs(p: Project) -> Tuple[List[str], List[str], List[str]]:
    """Validate Chekhov's gun setups/payoffs and epistemic character knowledge integrity across scenes & beats."""
    errors: List[str] = []
    warnings: List[str] = []
    infos: List[str] = []
    o = p.outline
    plan = p.plan
    if not o.scenes:
        return errors, warnings, infos

    planted_map: Dict[str, Tuple[str, int, Section]] = {}
    paid_off_map: Dict[str, List[Tuple[str, int, Section]]] = {}
    revealed_map: Dict[str, Tuple[str, int, Set[str]]] = {}
    hidden_from_map: Dict[str, Set[str]] = {}

    for idx, sid in enumerate(o.scenes, 1):
        sec = plan.defs.get(sid)
        if not sec:
            continue

        # Aggregate metadata from both the scene and its sequenced beats
        unit_sections = [sec] + [plan.defs[bid] for bid in o.scene_beats.get(sid, []) if bid in plan.defs]

        plants: Set[str] = set()
        pays_off: Set[str] = set()
        reveals: Set[str] = set()
        learns: Set[str] = set()
        hidden_from: Set[str] = set()
        cast: Set[str] = set()
        pov: Set[str] = set()
        prereqs: Set[str] = set()

        for usec in unit_sections:
            plants |= usec.ref_ids_for_field("plants", "plant", "setups", "setup")
            pays_off |= usec.ref_ids_for_field("pays_off", "pays-off", "paysoff", "payoff", "pays")
            reveals |= usec.ref_ids_for_field("reveals", "reveal", "revelations")
            learns |= usec.ref_ids_for_field("learns", "learn", "learners")
            hidden_from |= usec.ref_ids_for_field("hidden_from", "hidden-from", "hidden", "concealed_from")
            cast |= usec.ref_ids_for_field("cast", "characters")
            pov |= usec.ref_ids_for_field("pov")
            prereqs |= usec.prereq_ids()

        for pid in sorted(plants):
            if pid not in planted_map:
                planted_map[pid] = (sid, idx, sec)

        for poy_id in sorted(pays_off):
            if poy_id not in planted_map:
                errors.append(
                    f"unearned payoff (Chekhov's gun violation): [[{poy_id}]] is paid off in scene {sid} (scene #{idx}), "
                    f"but was never planted in any preceding scene or beat"
                )
            else:
                paid_off_map.setdefault(poy_id, []).append((sid, idx, sec))

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

        if hidden_from_map:
            for rid, excluded_chars in hidden_from_map.items():
                if (cast & excluded_chars) or (pov & excluded_chars):
                    if rid in pays_off or rid in prereqs:
                        present_excluded = sorted((cast | pov) & excluded_chars)
                        already_learned = False
                        if rid in revealed_map and any(c in revealed_map[rid][2] for c in present_excluded):
                            already_learned = True
                        if not already_learned:
                            errors.append(
                                f"epistemic violation in scene {sid}: character(s) {', '.join(present_excluded)} act on [[{rid}]] while it was declared hidden from them"
                            )

    for pid, (sid, idx, sec) in sorted(planted_map.items(), key=lambda x: x[1][1]):
        if pid not in paid_off_map:
            errors.append(
                f"orphan plant (Chekhov's gun violation): [[{pid}]] is planted in scene {sid} (scene #{idx}), "
                f"but is never paid off in any downstream scene or beat"
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
        infos.append(f"Chekhov's gun validation passed: {len(planted_map)} setup/payoff pairs verified.")
    if revealed_map and not errors:
        infos.append(f"epistemic validation passed: {len(revealed_map)} narrative reveals verified.")

    return errors, warnings, infos


def run_dag_checks(p: Project) -> Tuple[List[str], List[str], List[str]]:
    errors: List[str] = []
    warnings: List[str] = []
    infos: List[str] = []

    if not p.narrative.beats:
        return errors, warnings, infos

    dag = build_story_dag(p)

    cycles = check_dag_cycles(dag)
    for c in cycles:
        errors.append(f"cycle detected in Beat DAG: {c}")

    ro_errors = check_reading_order_coherence(dag, p)
    errors += ro_errors

    root, ess_errors = check_essentiality_to_root(dag, p)
    errors += ess_errors

    if not (cycles or ro_errors or ess_errors):
        total_edges = sum(len(v) for v in dag.edges.values())
        infos.append(f"Beat DAG verified: {len(dag.nodes)} beats, {total_edges} causal edges, root denouement is {root}")

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
        for d in (SETUP, WORLD, NARRATIVE, STRUCTURE):
            dp = root / d
            if dp.is_dir():
                for f in dp.rglob("*.md"):
                    rel = f.relative_to(root).as_posix()
                    if rel in GENERATED or rel.endswith("/template.md") or rel.startswith("world/sources/") or "/scenarios/" in rel or "/takes/" in rel:
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

            if re.match(r"^\s*\[[^\]]+\]:\s*\S+", clean_line):
                continue

            for bm in BRACKET_PLACEHOLDER_RE.finditer(clean_line):
                inner = bm.group(1).strip()
                if inner.lower() in {"x", " ", "todo", "tbd"} or inner.isdigit():
                    continue
                is_gfx = bool(re.match(r"^(?:ILL|GFX|GRAPHIC)\s*:\s*", inner, re.I))
                clean_text = re.sub(r"^(?:TODO|TBD|FIXME|RESEARCH|PLACEHOLDER|ILL|GFX|GRAPHIC)\s*:\s*", "", inner, flags=re.I).strip()
                key = clean_text.lower()
                kind = "gfx" if is_gfx else "bracket"
                if key not in items_by_key:
                    items_by_key[key] = PlaceholderItem(raw=f"[{inner}]", text=clean_text, kind=kind)
                ctx = clean_line[:120]
                items_by_key[key].occurrences.append(PlaceholderOccurrence(rel, line_no, cur_id, ctx))

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

            if not BRACKET_PLACEHOLDER_RE.search(clean_line):
                for tm in TODO_PLACEHOLDER_RE.finditer(clean_line):
                    inner = tm.group(1).strip()
                    if inner and len(inner) > 2:
                        key = inner.lower()
                        if key not in items_by_key:
                            items_by_key[key] = PlaceholderItem(raw=tm.group(0), text=inner, kind="todo")
                        ctx = clean_line[:120]
                        items_by_key[key].occurrences.append(PlaceholderOccurrence(rel, line_no, cur_id, ctx))

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
    return re.sub(r"[-_.:/]", " ", text).lower()


def model_mentioned_in_text(model: str, raw_text: str, norm_text: Optional[str] = None) -> bool:
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


def get_contributing_ai_models(git: Git, p: Optional[Project] = None) -> Set[str]:
    models: Set[str] = set()
    if git.has_commits():
        for key in ("Novel-Model", "AI-Model"):
            try:
                lines = git.lines("log", f"--format=%(trailers:key={key},valueonly=true)", "HEAD")
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
        cfg_m = git.run("config", "--get", "specnovelist.model", allow_fail=True)
        if cfg_m:
            for part in cfg_m.strip().split(","):
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
            if isinstance(aim, (list, dict)):
                for m in aim:
                    if m:
                        models.add(str(m).strip())
    return models


# ------------------------------------------------------------------ checks
def run_checks(p: Project, require: Sequence[str] = ()) -> Tuple[List[str], List[str], List[str]]:
    errors: List[str] = []
    warnings: List[str] = []
    infos: List[str] = []
    plan, nar, o = p.plan, p.narrative, p.outline
    root = p.git.root

    # 1. Stage 1 (Setup) checks
    if p.config.errors:
        errors += [f"config error: {e}" for e in p.config.errors]
    if p.config.foreword_path and not (root / p.config.foreword_path).is_file():
        errors.append(f"config front_matter.foreword references missing file: '{p.config.foreword_path}'")
    if p.config.historical_note_path and not (root / p.config.historical_note_path).is_file():
        warnings.append(f"config back_matter.historical_note references missing file: '{p.config.historical_note_path}'")
    if not (root / SYNOPSIS_FILE).is_file():
        errors.append(f"missing seed synopsis: {SYNOPSIS_FILE}")

    # Mandatory acknowledgements & contributing AI models verification
    ack_path = p.config.acknowledgments_path or ACKNOWLEDGEMENTS_FILE
    ack_file = root / ack_path
    if not ack_file.is_file():
        for fb in (ACKNOWLEDGEMENTS_FILE, "structure/back-matter/acknowledgments.md", "setup/acknowledgements.md"):
            if (root / fb).is_file():
                ack_file = root / fb
                ack_path = fb
                break
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
        errors.append(f"missing writing-style guide: {STYLE_FILE}")
    else:
        style_text = style.read_text(encoding="utf-8", errors="replace")
        n = word_count(style_text.splitlines())
        if n < MIN_STYLE_WORDS:
            warnings.append(f"{STYLE_FILE} has only {n} words of guidance (excluding comments); a thorough "
                            f"guide (>= {MIN_STYLE_WORDS} words) is expected before writing the manuscript")
        for loc in p.config.target_languages:
            if not re.search(r"^#{1,3}\s+Locale:\s*" + re.escape(loc) + r"\b", style_text, re.I | re.M):
                warnings.append(f"writing-style guide '{STYLE_FILE}' lacks guidance section for configured locale '{loc}' (expected heading '# Locale: {loc}')")
        if not re.search(r"^#{1,3}\s+Glossary\s+(?:Guidelines|Criteria)\b", style_text, re.I | re.M):
            warnings.append(f"writing-style guide '{STYLE_FILE}' lacks '## Glossary Guidelines' section")
        if not re.search(r"^#{1,3}\s+(?:Graphics|Illustrations?|Visual\s+Assets?)\s+(?:Guidelines|Rules|Style)?\b", style_text, re.I | re.M):
            warnings.append(f"writing-style guide '{STYLE_FILE}' lacks '## Graphics Guidelines' section")
        if not re.search(r"^#{1,3}\s+Publication(?:\s+&|\s+and)?\s+(?:Book\s+Design\s+)?Guidelines\b", style_text, re.I | re.M):
            warnings.append(f"writing-style guide '{STYLE_FILE}' lacks '## Publication & Book Design Guidelines' section")

    # 2. Catalog, stage placement, and reference integrity
    errors += [f"duplicate ID {d['id']}: {d['first']} and {d['second']}" for d in plan.duplicates]
    errors += nar.problems
    errors += o.problems

    for s in plan.sections():
        for rid, line in s.refs:
            if rid not in plan.defs:
                errors.append(f"dangling reference [[{rid}]] at {s.file}:{line}")

    for s in plan.defs.values():
        if s.prefix not in TYPES:
            infos.append(f"{s.id} uses unregistered prefix '{s.prefix}' ({s.location})")
        else:
            expected_stage = PREFIX_STAGE.get(s.prefix)
            actual_top = s.file.split("/", 1)[0]
            if expected_stage and actual_top != expected_stage:
                errors.append(f"{s.id} ({TYPES[s.prefix]}) must be stored in '{expected_stage}/' but was found in '{s.file}' ({s.location})")

    # 3. Stage 2 & 3 (Research & World) integrity
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

    # 4. Directives (DIR-NNN) validation & preservation check
    valid_dir_stages = set(STAGES) | {"all", "global"}
    valid_dir_statuses = {"active", "open", "applied", "superseded", "wontfix"}
    active_dirs: List[Section] = []
    for s in plan.of_type("DIR"):
        scope_val = (s.field_value("scope", "target", "targets", "applies_to", "applies-to") or "").strip()
        if not scope_val:
            errors.append(f"directive {s.id} lacks a valid 'Scope:' (or 'Target:') field ({s.location})")
        stage_val = (s.field_value("stage", "stages") or "all").lower()
        stages_split = {st.strip() for st in re.split(r"[,/\s]+", stage_val) if st.strip()}
        if not stages_split or not stages_split.issubset(valid_dir_stages):
            errors.append(f"directive {s.id} has invalid 'Stage:' ({stage_val}); must be 'all' or stage name(s) ({s.location})")
        status_val = (s.field_value("status") or "active").lower()
        if status_val not in valid_dir_statuses:
            errors.append(f"directive {s.id} has invalid 'Status:' ({status_val}) ({s.location})")
        elif status_val in ("active", "open"):
            active_dirs.append(s)
        loc_val = (s.field_value("locale", "lang", "language") or "all").strip()
        if loc_val.lower() not in ("all", "global") and loc_val not in p.config.target_languages:
            errors.append(f"directive {s.id} has invalid 'Locale:' '{loc_val}' ({s.location}); must be 'all' or one of {', '.join(p.config.target_languages)}")

    if active_dirs:
        infos.append(f"{len(active_dirs)} active directive(s): " + ", ".join(s.id for s in active_dirs))

    errors += check_preserved_directives(p)

    # 5. Stage 4 (Illustrations) & Stage 8 (Publishable Graphics) verification
    dag = build_story_dag(p)
    for s in plan.of_type("ILL"):
        desc = (s.field_value("description", "summary") or "\n".join(s.body)).strip()
        if not desc:
            errors.append(f"illustration {s.id} in {NARRATIVE}/ lacks a textual description ({s.location})")
        itype = (s.field_value("type") or "").strip().lower()
        if not itype:
            warnings.append(f"illustration {s.id} has no 'Type:' field (e.g. map, diagram, cover, scene) ({s.location})")

    img_ref_pattern = re.compile(r"""(?:!\[.*?\]\((?P<url1>[^)\s]+)\)|(?P<url2>(?:publishable/graphics/|graphics/)?[a-zA-Z0-9_\-\./]+\.(?:png|svg|jpg|jpeg|webp)))""", re.I)
    ill_filename_pattern = re.compile(r"""(?:^|.*/)(?P<id>(?:ILL|GFX)-\d{3,})(?:\.(?P<locale>[a-zA-Z0-9_-]+))?\.(?P<ext>png|svg|jpg|jpeg|webp)$""", re.I)

    for loc in p.config.target_languages:
        loc_ms_dir = root / MANUSCRIPT / loc
        target_files = sorted(loc_ms_dir.glob("*.md")) if loc_ms_dir.is_dir() else []
        for mf in target_files:
            rel = mf.relative_to(root).as_posix()
            text = mf.read_text(encoding="utf-8", errors="replace")
            for line_no, line in enumerate(text.splitlines(), 1):
                for match in img_ref_pattern.finditer(line):
                    url = match.group("url1") or match.group("url2")
                    if not url or "http://" in url or "https://" in url:
                        continue
                    gm = ill_filename_pattern.search(url)
                    if not gm:
                        continue
                    iid = gm.group("id")
                    file_loc = gm.group("locale")
                    ext = gm.group("ext")

                    isec = plan.defs.get(iid)
                    expected_loc_path = f"{GRAPHICS_DIR}/{iid}.{loc}.{ext}"
                    has_loc_file = (root / expected_loc_path).is_file()
                    has_text = isec and (isec.has_field("has-text") or isec.has_field("has_text") or re.search(r"###\s+" + re.escape(loc), isec.text))

                    if has_loc_file or has_text:
                        if file_loc != loc:
                            errors.append(f"manuscript '{rel}:{line_no}' (locale: {loc}) references mismatched illustration '{url}'; expected localized version '{expected_loc_path}'")

    # 6. Beat DAG, Physical Structure reading order, and Epistemic/Chekhov checks
    dag_errors, dag_warnings, dag_infos = run_dag_checks(p)
    errors += dag_errors
    warnings += dag_warnings
    infos += dag_infos

    ep_errors, ep_warnings, ep_infos = check_epistemic_and_setup_payoffs(p)
    errors += ep_errors
    warnings += ep_warnings
    infos += ep_infos

    # 7. Stage 6 (Abridged) & Stage 7 (Manuscript) consistency with Stage 5 (Physical Structure)
    for name, d in p.layers.items():
        errors += [f"{name}: duplicate {x['id']}: {x['first']} and {x['second']}" for x in d.model.duplicates]
        for sid, s in d.scenes.items():
            if sid not in o.chapter_of:
                errors.append(f"{name}: scene {sid} is not in {STRUCTURE}/ ({s.location})")
            elif d.chapter_of.get(sid) != o.chapter_of[sid]:
                errors.append(f"{name}: scene {sid} is under {d.chapter_of.get(sid)} but {STRUCTURE}/ places it "
                              f"in {o.chapter_of[sid]} ({s.location})")
        for cid, s in d.chapters.items():
            if cid not in o.by_chapter:
                errors.append(f"{name}: chapter {cid} is not in {STRUCTURE}/ ({s.location})")
        for cid, expected in o.by_chapter.items():
            present = [sid for sid, c in d.chapter_of.items() if c == cid]
            if present != [sid for sid in expected if sid in present]:
                errors.append(f"{name}: scene order in {cid} is {', '.join(present)} but {STRUCTURE}/ order is "
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
            msg = f"{name}: {len(missing)} of {len(o.scenes)} structure scene(s) not written yet"
            if name in require:
                errors.append(msg + ": " + ", ".join(missing))
            elif d.scenes:
                infos.append(msg)

    placeholders = scan_placeholders(p)
    untracked_pl = [pl for pl in placeholders if pl.tracked_by is None]
    if untracked_pl:
        infos.append(f"{len(untracked_pl)} untracked placeholder(s) in specs (run 'specnovel.py placeholders --create-rq')")

    return errors, warnings, infos


# ------------------------------------------------------------------ delta / impact across all 8 stages
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


def compute_illustrations_impact(p: Project) -> dict:
    """Compute rendering impact for Stage 4 textual illustrations (ILL-NNN) into Stage 8 publishable/graphics/."""
    git, plan, o = p.git, p.plan, p.outline
    dag = build_story_dag(p)
    ill_items = plan.of_type("ILL")

    active_items = []
    inactive_items = []

    scheduled_ills = {iid for sids in o.scene_illustrations.values() for iid in sids}

    for ill in ill_items:
        iid = ill.id
        is_active = (iid in scheduled_ills) or (iid in dag.positions)
        if not is_active:
            for b_ref in ill.ref_ids():
                if b_ref in dag.nodes:
                    is_active = True
                    break

        target_path = (ill.field_value("target", "file", "path") or f"{GRAPHICS_DIR}/{iid}.png").strip()
        itype = (ill.field_value("type") or "illustration").strip()
        asset_base = git.ill_baseline(iid)
        commits_behind = git.commits_behind(asset_base) if asset_base else None
        rendered_file_exists = (git.root / target_path).is_file()

        reasons: List[str] = []
        upstream_changes: List[str] = []

        if not is_active:
            status = "INACTIVE"
            desc = (
                f"skipped (not scheduled in active scenes/DAG - 0 tokens used; last synced {commits_behind} commits ago)"
                if asset_base else "skipped (not scheduled in active scenes/DAG - 0 tokens used; never rendered)"
            )
            inactive_items.append({
                "id": iid, "title": ill.title, "type": itype, "target": target_path,
                "status": status, "active": False, "baseline": git.commit_info(asset_base),
                "commits_behind": commits_behind, "reason": desc,
            })
            continue

        if not rendered_file_exists:
            reasons.append(f"rendered file missing on disk ({target_path})")

        if not asset_base:
            reasons.append("no sync baseline (never rendered)")
        else:
            old_nar = build_model(git.commit_md(asset_base, NARRATIVE))
            if iid not in old_nar.defs:
                upstream_changes.append("ILL specification added after baseline")
            elif old_nar.defs[iid].lines != ill.lines:
                upstream_changes.append("ILL specification modified")

            dep_ids = (ill.ref_ids() | ill.prereq_ids()) - {iid}
            if dep_ids:
                old_all = build_model(git.commit_md(asset_base, *PLAN_DIRS))
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
            "id": iid, "title": ill.title, "type": itype, "target": target_path,
            "status": status, "active": True, "baseline": git.commit_info(asset_base),
            "commits_behind": commits_behind, "reasons": reasons, "upstream_changes": upstream_changes,
            "preserved_directives": sorted(ill.directive_ids()),
        })

    needs_update_count = sum(1 for it in active_items if it["status"] != "UP_TO_DATE")
    return {
        "stage": PUBLISHABLE,
        "active": active_items,
        "inactive": inactive_items,
        "needs_update_count": needs_update_count,
        "token_savings_count": len(inactive_items),
    }


def compute_impact(p: Project, stage: str, locale: Optional[str] = None, allow_uninitialized: bool = False) -> dict:
    """Compute synchronization impact for any stage based on upstream changes since its baseline."""
    git, plan, nar, o = p.git, p.plan, p.narrative, p.outline
    base = git.baseline(stage)
    if base is None and not allow_uninitialized:
        raise NovelError(
            f"Synchronization cannot be performed for stage '{stage}' because generation has not been performed "
            f"at least once for '{stage}' (no baseline commit found). Run Generation (novel-generate) for '{stage}' first."
        )

    up_dirs = UPSTREAM_DIRS.get(stage, PLAN_DIRS)
    old_up = build_model(git.commit_md(base, *up_dirs))
    new_up = build_model(git.working_md(*up_dirs))
    changes = diff_models(old_up, new_up)
    changed_ids = {c.id for c in changes if c.id}

    # For Stage 8 (publishable), combine illustration rendering impact and book compilation impact
    if stage == PUBLISHABLE:
        ill_imp = compute_illustrations_impact(p)
        ill_imp["baseline"] = git.commit_info(base)
        ill_imp["upstreamChanges"] = [c.label() for c in changes]
        return ill_imp

    # For Stages 2-5 (spec stages: research, world, narrative, structure)
    if stage in (RESEARCH, WORLD, NARRATIVE, STRUCTURE):
        stage_records = [s for s in plan.defs.values() if stage_of_section(s) == stage]
        impacted_records = []
        for sec in stage_records:
            reasons: List[str] = []
            refs = effective_refs_of_section(sec, p) - {sec.id}
            hits = sorted(refs & changed_ids)
            if hits:
                reasons.append("upstream references changed: " + ", ".join(hits))
            matched_dirs = set(match_directives_for_section(sec, p))
            unlinked_dirs = sorted(matched_dirs - sec.directive_ids())
            if unlinked_dirs:
                reasons.append("new relevant directive(s) to auto-link: " + ", ".join(unlinked_dirs))
            if reasons:
                impacted_records.append({
                    "id": sec.id,
                    "title": sec.title,
                    "file": sec.file,
                    "reasons": reasons,
                    "preserved_directives": sorted(sec.directive_ids()),
                    "auto_link_directives": unlinked_dirs,
                })

        # Also check upstream additions that require new records in this stage
        unhandled_upstream = []
        if stage == WORLD:
            for rq in plan.of_type("RQ"):
                if rq.id in changed_ids or not any(rq.id in f.ref_ids() for f in plan.of_type("FCT")):
                    status_v = (rq.field_value("status") or "open").lower()
                    if status_v == "open":
                        unhandled_upstream.append(f"open research question {rq.id}: {rq.title}")
        elif stage == STRUCTURE:
            for bid in nar.beats:
                if bid not in o.beat_positions:
                    unhandled_upstream.append(f"unscheduled narrative beat {bid}: {plan.defs[bid].title}")

        return {
            "stage": stage,
            "baseline": git.commit_info(base),
            "upstreamChanges": [c.label() for c in changes],
            "records": impacted_records,
            "unhandledUpstream": unhandled_upstream,
        }

    # For Stage 6 (abridged) & Stage 7 (manuscript)
    old_o = outline_of(old_up)
    target = p.manuscript_locales.get(locale, p.layers[stage]) if (stage == "manuscript" and locale) else p.layers[stage]
    ab_old = derived_of(build_model(git.commit_md(base, ABRIDGED))) if stage == "manuscript" else None
    ab_now = p.layers["abridged"]

    scenes = []
    for sid in o.scenes:
        reasons = []
        cid = o.chapter_of[sid]
        scn_sec = plan.defs[sid]
        eff_refs = effective_refs_of_section(scn_sec, p)
        preserved_dirs = sorted({r for r in eff_refs if r.startswith("DIR-")} | (target.scenes[sid].directive_ids() if sid in target.scenes else set()))
        matched_dirs = sorted(set(match_directives_for_section(scn_sec, p)) - set(preserved_dirs))

        if sid not in target.scenes:
            reasons.append("not yet written")
        else:
            if base is None:
                reasons.append("no baseline yet (accept this stage once reviewed)")
            if sid in changed_ids:
                reasons.append("structure scene changed")
            if stage == "abridged" and cid in changed_ids:
                reasons.append(f"chapter {cid} changed")
            if stage == "manuscript" and sid in ab_now.scenes:
                old = ab_old.scenes.get(sid) if ab_old else None
                if old is None or old.digest != ab_now.scenes[sid].digest:
                    reasons.append("abridged scene changed")
            hits = sorted(eff_refs & changed_ids - {sid, cid})
            if hits:
                reasons.append("references changed " + ", ".join(hits))
            if sid in old_o.chapter_of and old_o.chapter_of[sid] != cid:
                reasons.append(f"moved from {old_o.chapter_of[sid]} to {cid}")
        if matched_dirs:
            reasons.append("new relevant directive(s) to apply: " + ", ".join(matched_dirs))
        if stage == "manuscript" and sid not in ab_now.scenes:
            reasons.append("blocked: abridged scene missing")
        if reasons:
            scenes.append({
                "id": sid,
                "chapter": cid,
                "title": scn_sec.title,
                "reasons": reasons,
                "preserved_directives": preserved_dirs,
                "auto_link_directives": matched_dirs,
            })

    removed = [sid for sid in target.scenes if sid not in o.chapter_of]
    global_notes = []
    for c in changes:
        if not c.id:
            if c.section.file == STYLE_FILE:
                if stage == "manuscript":
                    global_notes.append(f"{c.kind} style guide section '{c.section.path}': review every rendered scene")
            else:
                global_notes.append(f"{c.kind} context '{c.section.key}': judge which scenes it affects")
        elif c.section.file == STYLE_FILE and stage == "manuscript":
            global_notes.append(f"{c.kind} style rule {c.label()}: review every rendered scene")

    return {
        "stage": stage,
        "baseline": git.commit_info(base),
        "upstreamChanges": [c.label() for c in changes],
        "scenes": scenes,
        "remove": removed,
        "global": global_notes,
    }


# ------------------------------------------------------------------ output helpers
OUT_FENCE = "````"


def emit_json(obj) -> None:
    print(json.dumps(obj, indent=2, ensure_ascii=False))


def baseline_line(stage: str, info: Optional[dict]) -> str:
    if info:
        return f"{stage:<12} baseline: {info['short']} ({info['date'][:10]}) {info['subject']}"
    return f"{stage:<12} baseline: none (not yet generated)"


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

    scaffold_dirs = (
        [f"{WORLD}/{w}" for w in WORLD_FOLDERS]
        + [
            SETUP, RESEARCH, NARRATIVE, STRUCTURE,
            f"{STRUCTURE}/front-matter", f"{STRUCTURE}/back-matter",
            ABRIDGED, MANUSCRIPT, f"{MANUSCRIPT}/en-US",
            PUBLISHABLE, GRAPHICS_DIR, f"{PUBLISHABLE}/en-US",
            DIRECTIVES,
        ]
    )
    for d in scaffold_dirs:
        p = git.root / d
        if not p.exists():
            p.mkdir(parents=True)
            (p / ".gitkeep").write_text("", encoding="utf-8")
            print(f"created  {d}/")
        elif not any(p.iterdir()):
            (p / ".gitkeep").write_text("", encoding="utf-8")

    gi = git.root / ".gitignore"
    content = gi.read_text(encoding="utf-8") if gi.exists() else ""
    if ".specnovel/" not in content.split():
        gi.write_text(content.rstrip() + ("\n" if content.strip() else "") + ".specnovel/\n", encoding="utf-8")
        print("updated  .gitignore (.specnovel/)")
    return 0


def cmd_status(git: Git, args) -> int:
    p = load_project(git)
    errors, warnings, infos = run_checks(p)
    counts = OrderedDict((pre, len(p.plan.of_type(pre))) for pre in TYPES)
    baselines = {st: git.commit_info(git.baseline(st)) for st in STAGES}
    impacts = {st: compute_impact(p, st, allow_uninitialized=True) for st in LAYERS}
    pub_impact = compute_illustrations_impact(p)
    drift = {st: git.changed_since(git.baseline(st), *STAGE_DIRS.get(st, (st,))) for st in STAGES}
    upstream_drift = {
        st: [d for d in git.changed_since(git.baseline(st), *UPSTREAM_DIRS.get(st, ())) if d["file"] not in GENERATED]
        for st in STAGES if st != SETUP
    }
    words = {st: sum(word_count(s.body) for s in p.layers[st].scenes.values()) for st in LAYERS}
    placeholders = scan_placeholders(p)
    untracked_pl = [pl for pl in placeholders if pl.tracked_by is None]

    if args.json:
        pending_items = {
            st: [s["id"] for s in impacts[st]["scenes"]] + list(impacts[st]["remove"])
            for st in LAYERS
        }
        pending_items["publishable"] = [it["id"] for it in pub_impact["active"] if it["status"] != "UP_TO_DATE"]
        pending_items["graphics"] = pending_items["publishable"]
        pending_items["research"] = [rq.id for rq in p.plan.of_type("RQ") if (rq.field_value("status") or "open").lower() == "open"]
        emit_json({
            "title": project_title(git),
            "baselines": baselines,
            "generatedStages": {st: baselines[st] is not None for st in STAGES},
            "catalog": counts,
            "beats": len(p.narrative.beats),
            "scenes": {
                "structure": len(p.outline.scenes),
                "outline": len(p.outline.scenes),
                **{st: len(p.layers[st].scenes) for st in LAYERS}
            },
            "words": words,
            "pending": {st: len(impacts[st]["scenes"]) + len(impacts[st]["remove"]) for st in LAYERS},
            "pending_items": pending_items,
            "illustrations": {
                "active": len(pub_impact["active"]),
                "pending": pub_impact["needs_update_count"],
                "inactive": len(pub_impact["inactive"]),
                "pending_items": pending_items["publishable"],
            },
            "graphics": {
                "active": len(pub_impact["active"]),
                "pending": pub_impact["needs_update_count"],
                "inactive": len(pub_impact["inactive"]),
                "pending_items": pending_items["publishable"],
            },
            "directives": len(p.plan.of_type("DIR")),
            "placeholders": {"total": len(placeholders), "untracked": len(untracked_pl)},
            "drift": drift,
            "upstream_drift": upstream_drift,
            "errors": errors,
            "warnings": warnings,
            "infos": infos,
            "next": next_step(p, impacts, pub_impact, errors),
        })
        return 0

    out = [f"# SpecNovelist status: {project_title(git)}", ""]
    out += [baseline_line(st, baselines[st]) for st in STAGES]
    out += ["", "Catalog across stages & directives:"]
    out += [f"  {pre:<4} {TYPES[pre]:<20} {n}" for pre, n in counts.items() if n]
    if not any(counts.values()):
        out.append("  (empty)")
    total = len(p.outline.scenes)
    out += [
        "",
        f"Narrative Beats: {len(p.narrative.beats)} | Physical Scenes: {total}"
        f" | abridged {len(p.layers['abridged'].scenes)} ({words['abridged']:,} words)"
        f" | manuscript {len(p.layers['manuscript'].scenes)} ({words['manuscript']:,} words)"
    ]
    if pub_impact["needs_update_count"]:
        out.append(f"Pending illustrations: {pub_impact['needs_update_count']} active asset(s) to render for publishable/graphics/")
    for st in LAYERS:
        imp = impacts[st]
        n = len(imp["scenes"]) + len(imp["remove"])
        out.append(f"Pending {st}: {n} scene(s) to (re)generate or remove")
    if untracked_pl:
        out += ["", f"Placeholders: {len(untracked_pl)} untracked placeholder(s) - run 'specnovel.py placeholders --create-rq'"]
    out += ["", f"Check: {len(errors)} error(s), {len(warnings)} warning(s) - run 'check' for details",
            f"Next: {next_step(p, impacts, pub_impact, errors)}"]
    print("\n".join(out))
    return 0


def next_step(p: Project, impacts: dict, pub_impact: dict, errors: List[str]) -> str:
    if errors:
        return "fix the errors reported by 'check'"
    for st in STAGES:
        if not p.git.baseline(st):
            return f"novel-generate: generate stage '{st}' and run 'accept --stage {st}'"
    if impacts["abridged"]["scenes"] or impacts["abridged"]["remove"]:
        return "novel-sync: synchronize stage 'abridged'"
    if impacts["manuscript"]["scenes"] or impacts["manuscript"]["remove"]:
        return "novel-sync: synchronize stage 'manuscript'"
    if pub_impact["needs_update_count"] > 0:
        return "novel-sync: render illustrations and compile stage 'publishable'"
    return "novel-verify / novel-analyze: audit continuity, metrics, and publishable deliverables"


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
        print("CHECK OK - All 8 stages, Beat DAG, physical serialization, and directives are valid.")
    if warnings:
        print(f"Warnings ({len(warnings)}):")
        print("\n".join(f"  - {w}" for w in warnings))
    if infos:
        print("Info:")
        print("\n".join(f"  - {i}" for i in infos))
    return 1 if errors else 0


def cmd_dag(git: Git, args) -> int:
    p = load_project(git)
    if not p.narrative.beats:
        if args.json:
            emit_json({"root": None, "nodes": [], "edges": {}, "reverseEdges": {}, "positions": {},
                       "cycles": [], "readingOrderErrors": [], "essentialityErrors": [], "ok": True})
        else:
            print("No narrative beats defined in narrative/ yet.")
        return 0

    dag = build_story_dag(p)
    cycles = check_dag_cycles(dag)
    ro_errors = check_reading_order_coherence(dag, p)
    root, ess_errors = check_essentiality_to_root(dag, p)
    total_edges = sum(len(v) for v in dag.edges.values())
    all_errors = cycles + ro_errors + ess_errors + p.narrative.problems

    if args.json:
        emit_json({
            "root": root,
            "nodes": sorted(dag.nodes),
            "edges": {k: sorted(v) for k, v in dag.edges.items()},
            "reverseEdges": {k: sorted(v) for k, v in dag.reverse_edges.items()},
            "positions": dag.positions,
            "beatOrder": {k: list(v) for k, v in dag.beat_order.items()},
            "cycles": cycles,
            "readingOrderErrors": ro_errors,
            "essentialityErrors": ess_errors,
            "narrativeProblems": p.narrative.problems,
            "ok": not all_errors,
        })
        return 1 if all_errors else 0

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
        f"# Beat Causality DAG & Physical Structure Serialization: {project_title(git)}", "",
        f"Root Denouement Beat: {root} ({p.plan.defs[root].title if root and root in p.plan.defs else 'unknown'})",
        f"Narrative Beats in DAG: {len(dag.nodes)}",
        f"Causal Dependency Edges: {total_edges}", "",
        "## Verification Results:"
    ]
    if cycles:
        out.append(f"  [FAIL] Acyclic Check: {len(cycles)} cycle(s) detected:")
        out += [f"    - {c}" for c in cycles]
    else:
        out.append("  [OK] Acyclic Check: Beat graph is a valid DAG")
    if ro_errors:
        out.append(f"  [FAIL] Physical Serialization Coherence: {len(ro_errors)} violation(s):")
        out += [f"    - {e}" for e in ro_errors]
    else:
        out.append("  [OK] Physical Serialization Coherence: All beat dependencies precede dependents in structure/")
    if ess_errors:
        out.append(f"  [FAIL] Denouement Essentiality: {len(ess_errors)} inessential beat(s):")
        out += [f"    - {e}" for e in ess_errors]
    else:
        out.append(f"  [OK] Denouement Essentiality: All {len(dag.nodes)} beats have a path to root denouement ({root})")
    print("\n".join(out))
    return 1 if all_errors else 0


def allocate_next_ids(git: Git, prefix: str, count: int = 1) -> List[str]:
    prefix = prefix.upper()
    if not re.fullmatch(r"[A-Z][A-Z0-9]*", prefix):
        raise NovelError("Prefix must be uppercase letters/digits, e.g. CHR, BET, SCN, DIR")
    rx = re.compile(rf"^[+\- ]?#{{1,6}}\s+{prefix}-(\d+)\b")
    lines: List[str] = []
    for text in git.working_md(*ALL_DIRS).values():
        lines += COMMENT_RE.sub("", text).splitlines()
    if git.has_commits():
        lines += (git.run("log", "--all", "--format=", "-p") or "").splitlines()
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
    beats = []
    for bid in p.narrative.beats:
        bsec = p.plan.defs.get(bid)
        if bsec and (rid in bsec.ref_ids() or bid == rid):
            beats.append({"id": bid, "title": bsec.title, "location": bsec.location})
    numbering = {cid: i for i, cid in enumerate(p.outline.chapters, 1)}
    scenes = []
    for sid in p.outline.scenes:
        scn_sec = p.plan.defs[sid]
        refs = effective_refs_of_section(scn_sec, p)
        if rid in refs or sid == rid or p.outline.chapter_of[sid] == rid:
            cid = p.outline.chapter_of[sid]
            row = {"id": sid, "chapter": cid, "chapterNo": numbering[cid], "title": scn_sec.title}
            for st, d in p.layers.items():
                row[st] = d.scenes[sid].location if sid in d.scenes else None
            scenes.append(row)
    result = {
        "id": rid,
        "defined": s is not None,
        "type": TYPES.get(rid.split("-")[0], "unknown"),
        "stage": stage_of_section(s) if s else None,
        "title": s.title if s else None,
        "location": s.location if s else None,
        "directives": sorted(s.directive_ids()) if s else [],
        "references": sorted(s.ref_ids()) if s else [],
        "referencedBy": referenced_by,
        "beats": beats,
        "scenes": scenes,
    }
    if args.json:
        emit_json(result)
        return 0
    if not s:
        print(f"{rid} is not defined in any project stage.")
    else:
        print(f"{rid}: {s.title}  [{result['type']} | stage: {result['stage']}]  defined at {s.location}")
    if result["directives"]:
        print("Directives: " + ", ".join(result["directives"]))
    if result["references"]:
        print("References: " + ", ".join(result["references"]))
    print(f"Referenced by {len(referenced_by)} section(s):")
    print("\n".join(f"  {r['key']}  ({r['location']})" for r in referenced_by) or "  (none)")
    if beats:
        print(f"Used in {len(beats)} beat(s):")
        for b in beats:
            print(f"  {b['id']}: {b['title']} ({b['location']})")
    print(f"Appears in {len(scenes)} scene(s), in reading order:")
    for r in scenes:
        print(f"  Ch.{r['chapterNo']:>3} {r['id']}: {r['title']}"
              f"  | abridged: {r['abridged'] or '-'} | manuscript: {r['manuscript'] or '-'}")
    return 0


def cmd_delta(git: Git, args) -> int:
    stage = args.stage
    base = git.baseline(stage)
    if base is None and not getattr(args, "initial", False):
        msg = (
            f"Synchronization delta cannot be computed for stage '{stage}' because generation has not been "
            f"performed at least once for '{stage}' (no baseline commit found). Run Generation first."
        )
        if args.json:
            emit_json({"error": msg, "stage": stage, "generated": False})
            return 1
        raise NovelError(msg)

    if stage == "plan":
        scope_dirs = PLAN_DIRS
        scope_desc = "plan (" + ", ".join(PLAN_DIRS) + ")"
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
        out.append(f"No upstream changes for {stage} since this baseline.")
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
    stage = args.stage
    base = git.baseline(stage)
    if base is None and not getattr(args, "initial", False):
        msg = (
            f"Synchronization cannot be performed for stage '{stage}' because generation has not been "
            f"performed at least once for '{stage}' (no baseline commit found). Run Generation first."
        )
        if args.json:
            emit_json({"error": msg, "stage": stage, "generated": False})
            return 1
        raise NovelError(msg)

    imp = compute_impact(p, stage, locale=getattr(args, "locale", None), allow_uninitialized=getattr(args, "initial", False))
    if args.json:
        emit_json(imp)
        return 0

    if stage == PUBLISHABLE:
        out = [f"# Impact on {PUBLISHABLE}/", "", baseline_line(stage, imp.get("baseline"))]
        active = imp["active"]
        inactive = imp["inactive"]
        out.append(f"Active illustrations in Story DAG: {len(active)} ({imp['needs_update_count']} need rendering/update)")
        out.append(f"Inactive illustrations (skipped - token savings): {len(inactive)}")
        for a in active:
            out.append(f"  [{a['status']}] {a['id']}: {a['title']} -> {a['target']}")
            for r in a["reasons"]:
                out.append(f"      - {r}")
        print("\n".join(out))
        return 0

    if stage in (RESEARCH, WORLD, NARRATIVE, STRUCTURE):
        out = [f"# Impact on {stage}/", "", baseline_line(stage, imp.get("baseline")),
               f"Upstream changes since baseline: {len(imp['upstreamChanges'])}", ""]
        if imp.get("records"):
            out.append(f"Records to synchronize ({len(imp['records'])}):")
            for r in imp["records"]:
                dirs_note = f" [preserve directives: {', '.join(r['preserved_directives'])}]" if r["preserved_directives"] else ""
                out.append(f"  {r['id']}: {r['title']} ({r['file']}){dirs_note}")
                for why in r["reasons"]:
                    out.append(f"      - {why}")
        if imp.get("unhandledUpstream"):
            out.append("Unhandled upstream items requiring new records:")
            for u in imp["unhandledUpstream"]:
                out.append(f"  - {u}")
        if not imp.get("records") and not imp.get("unhandledUpstream"):
            out.append(f"{stage}/ is in sync with upstream stages.")
        print("\n".join(out))
        return 0

    info = imp["baseline"]
    out = [f"# Impact on {stage}/", "", baseline_line(stage, info),
           f"Upstream changes since baseline: {len(imp['upstreamChanges'])}", ""]
    if imp["global"]:
        out += ["Global notes:"] + [f"  - {g}" for g in imp["global"]] + [""]
    if imp["scenes"]:
        out.append(f"Scenes to (re)generate ({len(imp['scenes'])}), in reading order:")
        for r in imp["scenes"]:
            dirs_note = f" [directives: {', '.join(r['preserved_directives'])}]" if r.get("preserved_directives") else ""
            out.append(f"  {r['chapter']} / {r['id']}: {r['title']}{dirs_note}")
            out += [f"      - {why}" for why in r["reasons"]]
    if imp["remove"]:
        out.append(f"Scenes to remove (no longer in structure): {', '.join(imp['remove'])}")
    if not imp["scenes"] and not imp["remove"] and not imp["global"]:
        out.append(f"{stage}/ is in sync with upstream stages.")
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
            elif s in STAGES and s not in stages:
                stages.append(s)

    model_name = getattr(args, "model", None) or os.environ.get("SPECNOVEL_MODEL")
    if not model_name:
        try:
            cfg_m = git.run("config", "--get", "specnovelist.model", allow_fail=True)
            if cfg_m and cfg_m.strip():
                model_name = cfg_m.strip()
        except Exception:
            pass

    # Auto-link relevant pre-existing directives to any newly added records in the accepted stage(s)
    p = load_project(git)
    newly_added_ids: Set[str] = set()
    for st in stages:
        base = git.baseline(st)
        scope = STAGE_DIRS.get(st, (st,))
        old_m = build_model(git.commit_md(base, *scope))
        new_m = build_model(git.working_md(*scope))
        for cid in new_m.defs:
            if cid not in old_m.defs:
                newly_added_ids.add(cid)

    if newly_added_ids:
        linked = auto_link_directives_in_project(p, only_ids=newly_added_ids)
        if linked:
            p = load_project(git)  # reload after injecting directive links

    reqs = list(stages)
    if model_name:
        for m in model_name.split(","):
            if m.strip():
                reqs.append(f"model:{m.strip()}")

    errors, _, _ = run_checks(p, require=reqs)
    if errors and not args.force:
        raise NovelError("Refusing to accept - check failed (use --force to override):\n  - " + "\n  - ".join(errors))

    trailers = [f"{TRAILER}: {', '.join(stages)}"]
    if model_name:
        trailers.append(f"Novel-Model: {model_name.strip()}")

    dirs_to_stage = {DIRECTIVES}
    for st in stages:
        if st in STAGE_DIRS:
            dirs_to_stage.update(STAGE_DIRS[st])

    for st in stages:
        scope = STAGE_DIRS.get(st, (st,))
        base = git.baseline(st)
        if st in SPEC_STAGES:
            changes = diff_models(build_model(git.commit_md(base, *scope)), build_model(git.working_md(*scope)))
            for kind in ("ADDED", "MODIFIED", "REMOVED"):
                ids = [c.id for c in changes if c.id and c.kind == kind]
                if ids:
                    trailers.append(f"Novel-{st.capitalize()}-{kind.capitalize()}: {', '.join(ids)}")
        elif st in LAYERS:
            old = derived_of(build_model(git.commit_md(base, LAYERS[st])))
            cur = p.layers[st]
            updated = [sid for sid, s in cur.scenes.items() if sid not in old.scenes or old.scenes[sid].digest != s.digest]
            removed = [sid for sid in old.scenes if sid not in cur.scenes]
            if updated:
                trailers.append(f"Novel-{st.capitalize()}-Updated: {', '.join(updated)}")
            if removed:
                trailers.append(f"Novel-{st.capitalize()}-Removed: {', '.join(removed)}")
        elif st == PUBLISHABLE:
            ill_imp = compute_illustrations_impact(p)
            if getattr(args, "asset", None):
                sync_ids = [iid for iid in args.asset if iid in p.plan.defs]
            else:
                sync_ids = [item["id"] for item in ill_imp["active"]]
            if sync_ids:
                trailers.append(f"Novel-ILL-Sync: {', '.join(sync_ids)}")

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


def cmd_directives(git: Git, args) -> int:
    """Manage cross-stage directives (DIR-NNN): list, match, link, and factor."""
    p = load_project(git)
    action = getattr(args, "action", None) or "list"

    if action == "match":
        target_id = (getattr(args, "id", None) or "").upper()
        if not target_id or target_id not in p.plan.defs:
            print(f"specnovel: record '{target_id}' not found", file=sys.stderr)
            return 1
        sec = p.plan.defs[target_id]
        matched = match_directives_for_section(sec, p)
        existing = sorted(sec.directive_ids())
        res = {"record": target_id, "existing_directives": existing, "matched_directives": matched}
        if getattr(args, "json", False):
            emit_json(res)
            return 0
        print(f"Directives matching {target_id} ({sec.title}):")
        print(f"  Currently linked: {', '.join(existing) or 'none'}")
        print(f"  Relevant active:  {', '.join(matched) or 'none'}")
        return 0

    if action == "link":
        stage_f = getattr(args, "stage", None)
        rec_id = getattr(args, "record", None) or getattr(args, "id", None)
        linked = auto_link_directives_in_project(p, stage_filter=stage_f, record_id=rec_id.upper() if rec_id else None)
        links_compat = [{"record": ev["record"], "file": ev["file"], "directives": ev["linked_directives"]} for ev in linked]
        if getattr(args, "json", False):
            emit_json({"linked": linked, "links": links_compat, "count": len(linked)})
            return 0
        if not linked:
            print("All relevant directives are already linked.")
            return 0
        print(f"Automatically linked directives into {len(linked)} record(s):")
        for ev in linked:
            print(f"  + {ev['record']} ({ev['file']}): {', '.join(ev['linked_directives'])}")
        return 0

    if action == "factor":
        title = getattr(args, "title", None) or "Factored Directive"
        instruction = getattr(args, "instruction", None)
        targets_arg = getattr(args, "targets", None) or []
        if isinstance(targets_arg, str):
            targets_raw = targets_arg
        else:
            targets_raw = " ".join(targets_arg)
        target_ids = [t.strip().upper() for t in re.split(r"[,\s]+", targets_raw) if t.strip()]
        if not instruction:
            print("specnovel: --instruction is required for 'directives factor'", file=sys.stderr)
            return 1

        new_dir_id = allocate_next_ids(git, "DIR", 1)[0]
        stage_val = getattr(args, "stage", None) or "all"
        scope_val = getattr(args, "scope", None) or (", ".join(f"[[{tid}]]" for tid in target_ids) if target_ids else "all")
        locale_val = getattr(args, "locale", None) or "all"

        dir_file = git.root / DIRECTIVES / f"{new_dir_id}.md"
        dir_file.parent.mkdir(parents=True, exist_ok=True)
        dir_content = (
            f"# {new_dir_id}: {title}\n"
            f"- **Stage:** {stage_val}\n"
            f"- **Scope:** {scope_val}\n"
            f"- **Locale:** {locale_val}\n"
            f"- **Status:** active\n"
            f"- **Instruction:** {instruction}\n"
        )
        dir_file.write_text(dir_content, encoding="utf-8")

        p = load_project(git)
        linked = auto_link_directives_in_project(
            p,
            only_ids=set(target_ids) if target_ids else None
        )
        linked_recs = [ev["record"] for ev in linked]
        if getattr(args, "json", False):
            emit_json({
                "directive": new_dir_id,
                "directive_id": new_dir_id,
                "file": f"{DIRECTIVES}/{new_dir_id}.md",
                "linked_records": linked_recs,
                "linked_targets": linked_recs,
            })
            return 0
        print(f"Created factored directive {new_dir_id} at {DIRECTIVES}/{new_dir_id}.md")
        if linked:
            print(f"Linked [[{new_dir_id}]] to: {', '.join(ev['record'] for ev in linked)}")
        return 0

    # Default action: list
    dirs = p.plan.of_type("DIR")
    target_filter = getattr(args, "id", None)
    status_filter = (getattr(args, "status", None) or "active").lower()
    stage_filter = (getattr(args, "stage", None) or "").lower()
    locale_filter = (getattr(args, "locale", None) or "").lower()

    matched_secs: List[Section] = []
    for s in dirs:
        st = (s.field_value("status") or "active").lower()
        if status_filter == "open":
            status_filter = "active"
        if status_filter != "all" and st != status_filter and not (status_filter == "active" and st == "open"):
            continue
        stg = (s.field_value("stage", "stages") or "all").lower()
        if stage_filter and stage_filter != "all" and "all" not in stg and stage_filter not in stg:
            continue
        loc = (s.field_value("locale", "lang", "language") or "all").lower()
        if locale_filter and locale_filter != "all" and loc not in ("all", "global", locale_filter):
            continue
        if target_filter:
            tf = target_filter.upper()
            if tf == s.id or tf in s.ref_ids():
                matched_secs.append(s)
                continue
            if tf in p.plan.defs and is_directive_relevant_to_section(s, p.plan.defs[tf], p):
                matched_secs.append(s)
                continue
        else:
            matched_secs.append(s)

    if getattr(args, "json", False):
        data = [{
            "id": s.id,
            "title": s.title,
            "scope": s.field_value("scope", "target", "targets"),
            "stage": s.field_value("stage", "stages") or "all",
            "status": s.field_value("status") or "active",
            "locale": s.field_value("locale") or "all",
            "instruction": s.field_value("instruction") or "\n".join(s.body),
            "file": s.file,
        } for s in matched_secs]
        emit_json(data)
        return 0

    if not matched_secs:
        print("No matching directives found.")
        return 0

    out = ["| ID | Scope | Stage | Status | Locale | Title |",
           "|----|-------|-------|--------|--------|-------|"]
    for s in matched_secs:
        scp = s.field_value("scope", "target", "targets") or "-"
        stg = s.field_value("stage", "stages") or "all"
        st = s.field_value("status") or "active"
        loc = s.field_value("locale") or "all"
        out.append(f"| {s.id} | {scp} | {stg} | {st} | {loc} | {s.title} |")
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
            priority = getattr(args, "priority", None) or "high"
            sec_ids = sorted({occ.section_id for occ in item.occurrences if occ.section_id})
            needed_for = ", ".join(f"[[{sid}]]" for sid in sec_ids) if sec_ids else ", ".join(sorted({occ.file for occ in item.occurrences}))
            q = f"Determine authentic historical, technical, or world-building details for '{item.text}'."
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

        q_file = git.root / QUESTIONS_FILE
        q_file.parent.mkdir(parents=True, exist_ok=True)
        if q_file.exists():
            existing = q_file.read_text(encoding="utf-8")
            sep = "\n\n" if existing.strip() else ""
            new_content = existing.rstrip() + sep + "\n\n".join(rq_blocks) + "\n"
        else:
            new_content = "# Research Questions\n\n" + "\n\n".join(rq_blocks) + "\n"
        q_file.write_text(new_content, encoding="utf-8")

        if getattr(args, "json", False):
            emit_json({"created": created_info, "file": QUESTIONS_FILE})
            return 0

        created_ids = ", ".join(c["id"] for c in created_info)
        print(f"Generated {len(created_info)} research question(s) ({created_ids}) in {QUESTIONS_FILE}")
        return 0

    if getattr(args, "json", False):
        emit_json([{
            "raw": item.raw,
            "text": item.text,
            "kind": item.kind,
            "tracked_by": item.tracked_by,
            "occurrences": [{"file": o.file, "line": o.line, "section_id": o.section_id, "context": o.context} for o in item.occurrences]
        } for item in items])
        return 0

    if not items:
        print("No placeholders detected in project specifications.")
        return 0
    for item in items:
        status_str = f"TRACKED by [[{item.tracked_by}]]" if item.tracked_by else "UNTRACKED"
        print(f"  {item.raw} -> {status_str}")
    return 0


def cmd_index(git: Git, args) -> int:
    p = load_project(git)
    out = ["<!-- GENERATED by specnovel.py index - do not edit; regenerate instead. -->",
           f"# Project Catalog Index: {project_title(git)}", ""]
    for pre, name in TYPES.items():
        items = p.plan.of_type(pre)
        if not items:
            continue
        out += [f"## {name.title()}s ({pre})" if not name.endswith("y") else f"## {name[:-1].title()}ies ({pre})", "",
                "| ID | Title | File | Used in scenes |", "|----|-------|------|---------------:|"]
        for s in items:
            link = os.path.relpath(git.root / s.file, git.root / WORLD).replace("\\", "/")
            used = sum(1 for sid in p.outline.scenes
                       if s.id in effective_refs_of_section(p.plan.defs[sid], p))
            out.append(f"| {s.id} | {s.title.replace('|', '/')} | [{s.file}]({link}#L{s.line}) | {used} |")
        out.append("")
    dst = git.root / WORLD / "INDEX.md"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text("\n".join(out), encoding="utf-8")
    print(f"Wrote {WORLD}/INDEX.md ({len(p.plan.defs)} items)")
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
    print("\n".join(out))
    return 0


def generate_bibliography_markdown(p: Project) -> Tuple[str, List[str], List[str]]:
    plan = p.plan
    dag = build_story_dag(p)

    active_facts: Set[str] = set()
    for sid in p.outline.scenes:
        scn_sec = plan.defs.get(sid)
        if scn_sec:
            for rid in effective_refs_of_section(scn_sec, p):
                if rid.startswith("FCT-"):
                    active_facts.add(rid)

    for nid in dag.nodes:
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
        emit_json({"activeFacts": facts, "activeSources": sources, "markdown": md_text})
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

    return config


def generate_epub_css(pub_conf: dict) -> str:
    body_font = pub_conf.get("body_font", "EB Garamond")
    heading_font = pub_conf.get("heading_font", "Cinzel")
    line_height = pub_conf.get("line_height", "1.35")
    indent = pub_conf.get("paragraph_indent", "1.25em")
    justified = "justify" if pub_conf.get("justification", True) else "left"
    hyphens = "auto" if pub_conf.get("hyphenation", True) else "manual"

    return f"""/* SpecNovelist EPUB Stylesheet - Generated from setup/style.md */
@charset "utf-8";

body {{
    margin: 5% 5%;
    padding: 0;
    font-family: "{body_font}", "Georgia", serif;
    line-height: {line_height};
    text-align: {justified};
    hyphens: {hyphens};
}}
p {{
    margin: 0;
    text-indent: {indent};
}}
h1 + p, h2 + p, h3 + p, hr + p, .scene-break + p {{
    text-indent: 0;
}}
h1, h2, h3, h4 {{
    font-family: "{heading_font}", "{body_font}", serif;
    font-weight: normal;
    text-align: center;
    page-break-inside: avoid;
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

    style_p = git.root / STYLE_FILE
    style_text = style_p.read_text(encoding="utf-8", errors="replace") if style_p.is_file() else ""
    pub_conf = parse_publication_style(style_text)

    scene_break = args.scene_break
    if scene_break == "* * *" and pub_conf.get("scene_break"):
        scene_break = pub_conf["scene_break"]

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
        for loc_cand in (f"{GRAPHICS_DIR}/cover.{target_locale}.png", f"{GRAPHICS_DIR}/cover.png", f"{GRAPHICS_DIR}/cover.jpg"):
            c_cand = git.root / loc_cand
            if c_cand.is_file():
                cover_file = c_cand
                break

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

    if p.config.foreword_path:
        fwd_p = git.root / p.config.foreword_path
        if fwd_p.is_file():
            out += ["# Foreword", ""] + fwd_p.read_text(encoding="utf-8").splitlines() + [""]

    has_acts = bool(p.outline.acts)
    cur_act, act_no, missing = None, 0, []
    for n, cid in enumerate(p.outline.chapters, 1):
        act = p.outline.act_of.get(cid)
        if has_acts and act and act != cur_act:
            act_no += 1
            cur_act = act
            out += [f"# " + args.part_heading.format(n=act_no, N=num_words(act_no), title=p.plan.defs[act].title), ""]
        sids = [sid for sid in p.outline.by_chapter[cid] if sid in d.scenes]
        missing += [sid for sid in p.outline.by_chapter[cid] if sid not in d.scenes]
        if not sids:
            continue
        hashes = "##" if has_acts else "#"
        out += [f"{hashes} " + args.chapter_heading.format(n=n, N=num_words(n), title=p.plan.defs[cid].title), ""]
        if cid in d.chapters:
            pre = clean_prose(d.chapters[cid].body)
            if pre:
                out += pre + [""]
        for i, sid in enumerate(sids):
            if i:
                out += [scene_break, ""]
            out += clean_prose(d.scenes[sid].body) + [""]

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

    if p.config.include_bibliography:
        bib_md, _, _ = generate_bibliography_markdown(p)
        out += [bib_md, ""]

    ack_path = p.config.acknowledgments_path or ACKNOWLEDGEMENTS_FILE
    ack_file = git.root / ack_path
    if not ack_file.is_file():
        for fb in (ACKNOWLEDGEMENTS_FILE, "structure/back-matter/acknowledgments.md", "setup/acknowledgements.md"):
            if (git.root / fb).is_file():
                ack_file = git.root / fb
                break
    if ack_file.is_file():
        ack_text = COMMENT_RE.sub("", ack_file.read_text(encoding="utf-8", errors="replace")).strip()
        if ack_text:
            out += [ack_text, ""]

    dst_dir = git.root / PUBLISHABLE / target_locale
    dst_dir.mkdir(parents=True, exist_ok=True)
    md = dst_dir / f"{args.layer}.md"
    md.write_text("\n".join(out), encoding="utf-8")
    # Also write to publishable/<layer>.md when single-locale for convenience
    if len(p.config.target_languages) <= 1:
        (git.root / PUBLISHABLE / f"{args.layer}.md").write_text("\n".join(out), encoding="utf-8")
    words = sum(word_count(s.body) for s in d.scenes.values())
    print(f"Wrote {md.relative_to(git.root).as_posix()} ({words:,} words)")

    css_content = generate_epub_css(pub_conf)
    css_path = dst_dir / "epub.css"
    css_path.write_text(css_content, encoding="utf-8")
    if len(p.config.target_languages) <= 1:
        (git.root / PUBLISHABLE / "epub.css").write_text(css_content, encoding="utf-8")

    if args.format != "md":
        pandoc = shutil.which("pandoc")
        if not pandoc:
            raise NovelError(
                f"pandoc is required for --format {args.format} (https://pandoc.org)\n"
                f"Compiled Markdown source written to: {md.relative_to(git.root).as_posix()}\n"
                f"Generated EPUB stylesheet written to: {css_path.relative_to(git.root).as_posix()}"
            )
        dst = dst_dir / f"{args.layer}.{args.format}"
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
            raise NovelError(f"pandoc conversion to {args.format} failed (exit code {e.returncode}).")
    return 0


def cmd_log(git: Git, args) -> int:
    if not git.has_commits():
        print("No commits yet.")
        return 0
    keys = ",".join(f"key={k}" for k in (TRAILER, "Novel-Model", "Novel-ILL-Sync"))
    out = git.lines("log", "--extended-regexp", f"--grep=^{TRAILER}:", f"--format=%h %cs %s%n%(trailers:{keys})", "HEAD")
    print("\n".join(out) if out else "No sync commits yet.")
    return 0


def cmd_models(git: Git, args) -> int:
    p = load_project(git)
    models = get_contributing_ai_models(git, p)
    ack_path = p.config.acknowledgments_path or ACKNOWLEDGEMENTS_FILE
    ack_file = git.root / ack_path
    if not ack_file.is_file():
        for fb in (ACKNOWLEDGEMENTS_FILE, "structure/back-matter/acknowledgments.md", "setup/acknowledgements.md"):
            if (git.root / fb).is_file():
                ack_file = git.root / fb
                ack_path = fb
                break
    ack_text = ack_file.read_text(encoding="utf-8", errors="replace") if ack_file.is_file() else ""
    norm_ack = normalize_model_text(ack_text)

    records = []
    for m in sorted(models):
        acknowledged = model_mentioned_in_text(m, ack_text, norm_ack)
        records.append({"model": m, "acknowledged": acknowledged})

    if getattr(args, "json", False):
        emit_json({
            "models": records,
            "acknowledgements_file": ack_path,
            "all_acknowledged": all(r["acknowledged"] for r in records) if records else True
        })
        return 0

    if not records:
        print(f"No contributing AI models tracked yet in git history or configuration.")
        return 0

    print(f"Tracked Contributing AI Models ({len(records)} total):")
    for r in records:
        status = "ACKNOWLEDGED" if r["acknowledged"] else "MISSING FROM ACKNOWLEDGEMENTS"
        print(f"  - {r['model']}: [{status}]")
    return 0 if all(r["acknowledged"] for r in records) else 1


# ------------------------------------------------------------------ harvest, scenario, audit, takes
STOPWORDS_LOWER = {
    "the", "a", "an", "this", "that", "these", "those", "he", "she", "it", "they", "we", "you", "i",
    "his", "her", "their", "our", "my", "your", "its", "then", "there", "here", "what", "where", "when",
    "why", "how", "who", "whom", "whose", "if", "as", "while", "after", "before", "once", "since",
    "until", "although", "though", "even", "because", "but", "and", "or", "so", "yet", "for", "nor",
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    "january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
    "november", "december", "mr", "mrs", "ms", "miss", "dr", "sir", "madam", "lady", "lord", "captain",
    "suddenly", "meanwhile", "later", "yesterday", "today", "tomorrow", "tonight"
}


def extract_entities_and_beats_from_prose(text: str, p: Project) -> Dict[str, Any]:
    words = WORD_RE.findall(text)
    total_words = len(words)

    title_match = re.search(r"^(?:#{1,3})\s+(?:(?:SCN-\d+[:\s]+)?(.+)|(.+))", text, re.M)
    if title_match:
        candidate_title = (title_match.group(1) or title_match.group(2) or "").strip()
    else:
        first_line = next((l.strip() for l in text.splitlines() if l.strip()), "Harvested Scene")
        first_line = re.sub(r"^[#\s\-*]+", "", first_line)
        candidate_title = first_line[:40].strip()

    dialogues: List[str] = []
    for dm in re.findall(r'["“]([^"”]+)["”]', text):
        if len(dm.strip().split()) >= 2:
            dialogues.append(dm.strip())

    attr_verbs = r"(?:said|asked|replied|answered|whispered|muttered|shouted|yelled|cried|sighed|gasped|groaned|laughed|nodded|snapped|murmured)"
    char_candidates: Set[str] = set()
    for m in re.finditer(rf'["”]\s*{attr_verbs}\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)', text, re.I):
        name = m.group(1).strip()
        if name.lower() not in STOPWORDS_LOWER:
            char_candidates.add(name)
    for m in re.finditer(rf'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+{attr_verbs}\b', text):
        name = m.group(1).strip()
        if name.lower() not in STOPWORDS_LOWER:
            char_candidates.add(name)

    place_candidates: Set[str] = set()
    place_suffixes = r"(?:Street|Avenue|Road|Boulevard|Lane|Tower|Castle|Room|Hall|Bridge|Station|Harbor|Port|Forest|Mountain|City|Town|Village|Cafe|Bar|Pub|Library|Office|Chamber|Palace|Hotel|Inn)"
    for m in re.finditer(rf'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+{place_suffixes})\b', text):
        place_candidates.add(m.group(1).strip())

    raw_paras = [pr.strip() for pr in re.split(r'\n\s*\n', text) if pr.strip()]
    beats: List[str] = []
    for p_text in raw_paras:
        if p_text.startswith("#") or p_text.startswith("***") or p_text.startswith("---"):
            continue
        first_sent = re.split(r'(?<=[.!?])\s+', p_text)[0].strip()
        first_sent = re.sub(r'^[#>\-\*\s"]+', '', first_sent)
        if len(first_sent) > 15:
            beats.append(first_sent[:120])
        if len(beats) >= 8:
            break

    return {
        "word_count": total_words,
        "candidate_title": candidate_title,
        "characters": sorted(char_candidates),
        "places": sorted(place_candidates),
        "dialogues": dialogues,
        "beats": beats,
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
    created_files = []
    applied = False

    if getattr(args, "apply", False):
        applied = True
        char_links = []
        for cname in harvest_data["characters"]:
            existing_chr = next((s.id for s in p.plan.of_type("CHR") if cname.lower() in s.title.lower()), None)
            if existing_chr:
                char_links.append(f"[[{existing_chr}|{cname}]]")
            else:
                cid = allocate_next_ids(git, "CHR", 1)[0]
                cpath = git.root / f"{WORLD}/characters/{cid}.md"
                cpath.parent.mkdir(parents=True, exist_ok=True)
                cpath.write_text(f"# {cid}: {cname}\n- **Category:** Secondary\n- **Status:** Provisional\n", encoding="utf-8")
                char_links.append(f"[[{cid}|{cname}]]")
                created_files.append(f"{WORLD}/characters/{cid}.md")

        place_links = []
        for pname in harvest_data["places"]:
            existing_plc = next((s.id for s in p.plan.of_type("PLC") if pname.lower() in s.title.lower()), None)
            if existing_plc:
                place_links.append(f"[[{existing_plc}|{pname}]]")
            else:
                pid = allocate_next_ids(git, "PLC", 1)[0]
                ppath = git.root / f"{WORLD}/places/{pid}.md"
                ppath.parent.mkdir(parents=True, exist_ok=True)
                ppath.write_text(f"# {pid}: {pname}\n- **Category:** Setting\n- **Status:** Provisional\n", encoding="utf-8")
                place_links.append(f"[[{pid}|{pname}]]")
                created_files.append(f"{WORLD}/places/{pid}.md")

        primary_place = place_links[0] if place_links else (f"[[{p.plan.of_type('PLC')[0].id}]]" if p.plan.of_type("PLC") else "[[PLC-001]]")
        primary_arc = f"[[{p.narrative.arcs[0]}]]" if p.narrative.arcs else "[[ARC-001]]"

        stitle = getattr(args, "title", None) or harvest_data["candidate_title"]
        bid = allocate_next_ids(git, "BET", 1)[0]
        prev_beat = p.narrative.beats[-1] if p.narrative.beats else None
        dep_str = f"[[{prev_beat}]]" if prev_beat else "None"

        beats_file = git.root / BEATS_FILE
        beats_file.parent.mkdir(parents=True, exist_ok=True)
        beat_spec = (
            f"\n\n## {bid}: {stitle}\n"
            f"- **Place:** {primary_place}\n"
            f"- **Time:** provisional\n"
            f"- **Arcs:** {primary_arc}\n"
            f"- **Dependencies:** {dep_str}\n"
            f"- **Characters:** {', '.join(char_links) or 'provisional'}\n"
            f"- **Summary:** {' '.join(harvest_data['beats'][:2])}\n"
        )
        existing_beats = beats_file.read_text(encoding="utf-8") if beats_file.is_file() else "# Narrative Beats\n"
        beats_file.write_text(existing_beats + beat_spec, encoding="utf-8")
        created_files.append(BEATS_FILE)

        sid = allocate_next_ids(git, "SCN", 1)[0]
        chap_id = getattr(args, "chapter", None) or (p.outline.chapters[-1] if p.outline.chapters else allocate_next_ids(git, "CHP", 1)[0])
        scene_spec = (
            f"\n\n#### {sid}: {stitle}\n"
            f"- **When:** provisional\n"
            f"- **Where:** {primary_place}\n"
            f"- **Cast:** {', '.join(char_links) or 'provisional'}\n"
            f"- **Sequence:** [[{bid}]]\n"
            f"- **Target words:** {harvest_data['word_count']}\n"
        )
        outline_file = git.root / OUTLINE_FILE
        if outline_file.is_file():
            outline_file.write_text(outline_file.read_text(encoding="utf-8") + scene_spec, encoding="utf-8")
        else:
            outline_file.parent.mkdir(parents=True, exist_ok=True)
            outline_file.write_text(f"# Physical Structure\n\n### {chap_id}: Chapter\n{scene_spec}", encoding="utf-8")
        created_files.append(OUTLINE_FILE)

        abridged_file = git.root / ABRIDGED / f"{chap_id}.md"
        abridged_file.parent.mkdir(parents=True, exist_ok=True)
        scene_body = raw_text.strip()
        if abridged_file.is_file():
            abridged_file.write_text(abridged_file.read_text(encoding="utf-8") + f"\n\n## {sid}: {stitle}\n\n{scene_body}\n", encoding="utf-8")
        else:
            abridged_file.write_text(f"# {chap_id}: Chapter\n\n## {sid}: {stitle}\n\n{scene_body}\n", encoding="utf-8")
        created_files.append(f"{ABRIDGED}/{chap_id}.md")

    if getattr(args, "json", False):
        emit_json({
            "source": source_label,
            "word_count": harvest_data["word_count"],
            "entities": {"characters": harvest_data["characters"], "places": harvest_data["places"]},
            "dialogue_count": len(harvest_data["dialogues"]),
            "dialogues": harvest_data["dialogues"][:10],
            "beats": harvest_data["beats"],
            "candidate_title": harvest_data["candidate_title"],
            "applied": applied,
            "created_files": created_files,
        })
        return 0
    return 0


def cmd_scenario(git: Git, args) -> int:
    action = args.action
    scenarios_dir = git.root / SETUP / "scenarios"

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
                    scenarios.append({
                        "name": sp.name, "status": status, "description": desc,
                        "created": created, "has_outline": (sp / "outline.md").is_file(),
                        "path": f"{SETUP}/scenarios/{sp.name}"
                    })
        if getattr(args, "json", False):
            emit_json(scenarios)
        return 0

    name = args.name
    target_dir = scenarios_dir / name
    main_outline = git.root / OUTLINE_FILE
    scen_outline = target_dir / "outline.md"

    if action == "create":
        target_dir.mkdir(parents=True, exist_ok=True)
        if main_outline.is_file():
            shutil.copy2(main_outline, scen_outline)
        else:
            scen_outline.write_text("# Physical Structure\n", encoding="utf-8")
        (target_dir / "notes.md").write_text(f"# Scenario: {name}\n- **Description:** {args.message}\n- **Status:** active\n", encoding="utf-8")
        if getattr(args, "json", False):
            emit_json({"scenario": name, "created": True, "path": f"{SETUP}/scenarios/{name}"})
        return 0

    if action == "diff":
        scen_txt = scen_outline.read_text(encoding="utf-8") if scen_outline.is_file() else ""
        main_txt = main_outline.read_text(encoding="utf-8") if main_outline.is_file() else ""
        diff_lines = list(difflib.unified_diff(main_txt.splitlines(keepends=True), scen_txt.splitlines(keepends=True)))
        if getattr(args, "json", False):
            emit_json({"scenario": name, "diff": "".join(diff_lines), "has_diff": bool(diff_lines)})
        return 0

    if action in ("activate", "merge"):
        shutil.copy2(scen_outline, main_outline)
        if getattr(args, "json", False):
            emit_json({"scenario": name, "activated": action == "activate", "merged": action == "merge"})
        return 0

    if action == "delete":
        shutil.rmtree(target_dir)
        if getattr(args, "json", False):
            emit_json({"scenario": name, "deleted": True})
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
                hits.append({"line": idx, "cliche": cliche, "suggestion": suggestion, "text": clean[:80]})
    return hits


def compute_emotional_valence(lines: List[str]) -> float:
    pos_count, neg_count, total_words = 0, 0, 0
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


def compute_single_scene_metrics(sid: str, outline_sec: Optional[Section], derived_sec: Optional[Section], p: Project) -> Dict[str, Any]:
    target_wc = target_words(outline_sec)
    lines = derived_sec.lines if derived_sec else []
    start_line = derived_sec.line if derived_sec else 1
    file_rel = derived_sec.file if derived_sec else (outline_sec.file if outline_sec else "")

    clean_lines = [COMMENT_RE.sub("", l) for l in lines]
    raw_text = "\n".join(clean_lines)
    actual_wc = word_count(lines) if derived_sec else 0

    dialogue_wc = 0
    for q in re.findall(r'["“]([^"”]+)["”]', raw_text):
        dialogue_wc += len(WORD_RE.findall(q))
    dialogue_ratio = round(dialogue_wc / max(actual_wc, 1), 2)

    clean_prose_txt = re.sub(r'#+.*', '', raw_text)
    sents = [s.strip() for s in re.split(r'[.!?]+', clean_prose_txt) if s.strip() and len(WORD_RE.findall(s)) > 1]
    sentence_count = len(sents)
    sent_lengths = [len(WORD_RE.findall(s)) for s in sents]
    avg_sentence_len = round(sum(sent_lengths) / max(len(sent_lengths), 1), 1) if sent_lengths else 0.0
    cadence_entropy = compute_cadence_entropy(sent_lengths)

    paras = [pr.strip() for pr in re.split(r'\n\s*\n', clean_prose_txt) if pr.strip()]
    paragraph_count = len(paras)

    passive_hits = detect_passive_voice(lines, start_line)
    sensory_data = compute_sensory_palette(lines, start_line)
    cliches = detect_cliches(lines, start_line)
    valence = compute_emotional_valence(lines)

    eff_refs = sorted(effective_refs_of_section(outline_sec, p)) if outline_sec else []
    plot_advancements = len([r for r in eff_refs if r.startswith(("BET-", "ARC-"))])
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
        "sensory_occurrences": sensory_data["occurrences"][:15],
        "cliches": cliches,
        "emotional_valence": valence,
        "narrative_velocity": velocity,
        "plot_advancements": plot_advancements,
        "references": eff_refs,
    }


def get_or_update_metrics_cache(p: Project, target_stage: str, force_recompute: bool = False) -> Tuple[Dict[str, Any], Set[str], Optional[str]]:
    git = p.git
    cache_dir = git.root / ".specnovel"
    cache_file = cache_dir / "metrics_cache.json"
    base_sha = git.baseline(target_stage)

    cached_data: Dict[str, Any] = {}
    if not force_recompute and cache_file.is_file():
        try:
            cached_data = json.loads(cache_file.read_text(encoding="utf-8"))
        except Exception:
            cached_data = {}

    active_layer = p.layers["manuscript"] if p.layers["manuscript"].scenes else p.layers["abridged"]
    dirty_scenes: Set[str] = set()
    scene_ids = p.outline.scenes

    if force_recompute or not base_sha or cached_data.get("baseline_sha") != base_sha or cached_data.get("stage") != target_stage:
        dirty_scenes = set(scene_ids)
    else:
        imp = compute_impact(p, target_stage, allow_uninitialized=True)
        for s_item in imp.get("scenes", []):
            dirty_scenes.add(s_item["id"])

        old_layer_md = git.commit_md(base_sha, MANUSCRIPT if p.layers["manuscript"].scenes else ABRIDGED)
        old_derived = derived_of(build_model(old_layer_md))
        for sid in scene_ids:
            cur_sec = active_layer.scenes.get(sid)
            old_sec = old_derived.scenes.get(sid)
            if (cur_sec is None) != (old_sec is None):
                dirty_scenes.add(sid)
            elif cur_sec and old_sec and cur_sec.digest != old_sec.digest:
                dirty_scenes.add(sid)
            if sid not in cached_data.get("scenes", {}):
                dirty_scenes.add(sid)

    scenes_cache = cached_data.get("scenes", {}) if not force_recompute else {}
    result_metrics: Dict[str, Any] = {}

    for sid in scene_ids:
        if sid in dirty_scenes or sid not in scenes_cache:
            outline_sec = p.plan.defs.get(sid)
            derived_sec = active_layer.scenes.get(sid)
            result_metrics[sid] = compute_single_scene_metrics(sid, outline_sec, derived_sec, p)
        else:
            result_metrics[sid] = scenes_cache[sid]

    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_payload = {
            "stage": target_stage,
            "baseline_sha": base_sha,
            "updated_at": datetime.now().isoformat(),
            "scenes": result_metrics,
        }
        cache_file.write_text(json.dumps(cache_payload, indent=2), encoding="utf-8")
    except Exception:
        pass

    return result_metrics, dirty_scenes, base_sha


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

    lines = [
        "# Developmental Editorial & Style Analysis Report",
        f"**Work:** [[{title}]]  ",
        f"**Author:** {author}  ",
        f"**Locale:** `{lang}`  ",
        f"**Baseline Commit:** `{base_label}`  ",
        f"**Generated:** {now_str}\n",
        "---\n",
        "## 1. Executive Metrics Dashboard\n",
        "| Metric | Dimension / Type | Observed Value | Standard / Style Target | Assessment |",
        "|---|---|---|---|---|",
    ]
    wc_status = "On Budget" if abs(total_words_actual - total_words_outline) <= total_words_outline * 0.15 else "Review Length"
    lines.append(f"| Total Word Count | Scope (Raw) | {total_words_actual:,} wds | {total_words_outline:,} wds | {wc_status} |")
    lines.append(f"| Dialogue Ratio | Style-Reflective | {overall_dialogue_ratio:.0%} | 25% – 45% (Balanced) | {'Optimal' if 0.20 <= overall_dialogue_ratio <= 0.50 else 'Investigate'} |")
    entropy_eval = "Lyrical / Dynamic" if avg_entropy >= 2.5 else ("Moderate" if avg_entropy >= 1.8 else "Monotone Cadence")
    lines.append(f"| Cadence Entropy ($H_{{cad}}$) | Style-Reflective | {avg_entropy} bits | ≥ 2.2 bits | {entropy_eval} |")
    lines.append(f"| Avg Sentence Length | Style-Reflective | {avg_sent_len} words | per `{STYLE_FILE}` | Calibrated |")
    ck_unresolved = len([c for c in chekhov_matrix if "dormant" in c["assessment"]])
    lines.append(f"| Chekhov Guns Tracked | Dramatic (Raw) | {len(chekhov_matrix)} setups | 0 orphan setups | {'All Paid Off' if ck_unresolved == 0 else f'{ck_unresolved} Dormant Guns'} |")
    lines.append(f"| Pacing Sag Sequences | Dramatic (Raw) | {len(consecutive_slow_scenes)} sequence(s) | 0 sags | {'Clean Flow' if len(consecutive_slow_scenes) == 0 else 'Review Sags'} |")
    lines.append(f"| Clichés / Dead Metaphors | Literary (Raw) | {total_cliches} detected | 0 clichés | {'Clean Diction' if total_cliches == 0 else 'Needs Polish'} |")
    passive_pct = round((total_passive / max(tot_sents, 1)) * 100, 1)
    lines.append(f"| Passive Voice Ratio | Linguistic (Raw) | {passive_pct}% ({total_passive}) | ≤ 5.0% | {'Punchy Active' if passive_pct <= 5.0 else 'Tighten Passive'} |\n")

    lines.append("## 2. Raw Quality Indicators Audit\n")
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
            lines.append(f"| [[{sec_id}]] | [[{data['scene']}]] | {l_str} | {h_str} | {'**Violation: Leaked**' if leak else 'Preserved'} |")
        lines.append("")

    lines.append("### 2.2 Chekhov's Gun Setups & Payoffs")
    if not chekhov_matrix:
        lines.append("- No paired plants and payoffs tracked.\n")
    else:
        lines.append("| Planted Entity | Setup Scene | Payoff Scene | Scene Gap | Diagnostic Assessment |")
        lines.append("|---|---|---|---|---|")
        for ck in chekhov_matrix:
            lines.append(f"| [[{ck['entity']}]] | [[{ck['plant_scene']}]] | [[{ck['payoff_scene']}]] | {ck['scene_gap']} scenes | {ck['assessment']} |")
        lines.append("")

    lines.append("### 2.3 Pacing Sags & Momentum Stalls")
    if not consecutive_slow_scenes:
        lines.append("- No pacing sag sequences detected.\n")
    else:
        for seq in consecutive_slow_scenes:
            lines.append(f"> [!WARNING]\n> **Pacing Sag Detected in:** {', '.join(f'[[{sid}]]' for sid in seq)}\n")

    lines.append("### 2.4 Cliché & Passive Phrasing Hotspots")
    cliche_scenes = [sid for sid, m in metrics_by_scene.items() if m.get("cliches")]
    if not cliche_scenes:
        lines.append("- Zero clichés or dead metaphors detected.\n")
    else:
        lines.append("| Scene | Location | Flagged Cliché | Suggested Somatic Alternative |")
        lines.append("|---|---|---|---|")
        for sid in cliche_scenes[:8]:
            for cl in metrics_by_scene[sid]["cliches"]:
                lines.append(f"| [[{sid}]] | `{metrics_by_scene[sid]['file']}#L{cl['line']}` | *\"{cl['cliche']}\"* | {cl['suggestion']} |")
        lines.append("")

    lines.append(f"## 3. Style-Reflective Metrics vs. `{STYLE_FILE}` Compliance\n")
    lines.append(f"- **Observed Average Sentence Length:** {avg_sent_len} words.")
    lines.append(f"- **Cadence Entropy ($H_{{cad}}$):** {avg_entropy} bits.\n")
    tot_sensory = max(sum(novel_sensory.values()), 1)
    lines.append("| Sensory Modality | Occurrences | Percentage |")
    lines.append("|---|---|---|")
    for mod, cnt in novel_sensory.items():
        lines.append(f"| {mod.capitalize()} | {cnt} | {(cnt / tot_sensory) * 100:.1f}% |")
    lines.append("")

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
        lines.append(f"| [[{sid}]] | [[{w['chapter']}]] | {w['actual_words']:,} | {w['dialogue_ratio']:.0%} | {vel} | {val:+.2f} | {w['title'][:25]} |")
    lines.append("")

    lines.append("### 5.2 Character Agency & Screen-Time")
    lines.append("| Character | POV Scenes | Cast Appearances | Novel Coverage |")
    lines.append("|---|---|---|---|")
    tot_scenes = max(len(p.outline.scenes), 1)
    for c in character_agency.values():
        lines.append(f"| [[{c['id']}]] ({c['name']}) | {c['pov_count']} | {c['cast_count']} | {(c['cast_count'] / tot_scenes) * 100:.0f}% |")
    lines.append("")

    lines.append("## 6. Actionable Editorial Roadmap\n")
    lines.append("1. **High Priority (Quality & Logic)**: Verify DAG causality, epistemic integrity, and pacing sag sequences.")
    lines.append("2. **Medium Priority (Style & Sensory Polish)**: Enrich sensory grounding and replace flagged clichés.")
    lines.append("3. **Consistency & Rhythm**: Maintain sentence cadence entropy (≥ 2.2 bits) across chapters.\n")
    return "\n".join(lines) + "\n"


def cmd_audit(git: Git, args) -> int:
    p = load_project(git)
    target_stage = "manuscript" if p.layers["manuscript"].scenes else "abridged"

    if getattr(args, "compare", None):
        base_sha = git.baseline(target_stage)
        if not base_sha:
            msg = f"specnovel: no baseline commit found for stage '{target_stage}'."
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
        old_p = Project(git, old_plan, narrative_of(old_plan), old_outline, {"abridged": old_layer, "manuscript": old_layer}, p.config)

        base_metrics = {sid: compute_single_scene_metrics(sid, old_plan.defs.get(sid), old_layer.scenes.get(sid), old_p) for sid in old_outline.scenes}
        curr_words = sum(m["actual_words"] for m in curr_metrics.values())
        base_words = sum(m["actual_words"] for m in base_metrics.values())
        curr_cliches = sum(len(m["cliches"]) for m in curr_metrics.values())
        base_cliches = sum(len(m["cliches"]) for m in base_metrics.values())

        delta_data = {
            "baseline_sha": base_sha[:8],
            "metrics": {
                "word_count": {"baseline": base_words, "current": curr_words, "delta": curr_words - base_words},
                "cliches_count": {"baseline": base_cliches, "current": curr_cliches, "delta": curr_cliches - base_cliches},
            }
        }
        if getattr(args, "json", False):
            print(json.dumps(delta_data, indent=2))
        return 0

    if getattr(args, "scene", None):
        target_sid = args.scene
        if target_sid not in p.outline.scenes:
            print(f"specnovel: scene '{target_sid}' not found in {STRUCTURE}/", file=sys.stderr)
            return 1
        metrics_by_scene, _, _ = get_or_update_metrics_cache(p, target_stage, force_recompute=getattr(args, "no_cache", False))
        if getattr(args, "json", False):
            print(json.dumps(metrics_by_scene[target_sid], indent=2))
        return 0

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
        character_agency[chr_sec.id] = {"id": chr_sec.id, "name": chr_sec.title, "cast_count": 0, "pov_count": 0, "scenes": []}

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
        if actual_wc > 300 and (m.get("sensory_counts", {}).get("tactile", 0) == 0 or m.get("sensory_counts", {}).get("olfactory", 0) == 0):
            where_val = outline_sec.field_value("where", "place") if outline_sec else "unknown"
            sensory_alerts.append({"scene": sid, "words": actual_wc, "where": where_val})

        pacing_waveform.append({
            "index": idx, "scene": sid, "chapter": ch_id, "title": m.get("title", sid),
            "target_words": target_wc, "actual_words": actual_wc, "dialogue_ratio": m.get("dialogue_ratio", 0.0),
            "sentences": m.get("sentence_count", 0), "avg_sentence_len": m.get("avg_sentence_len", 0.0),
            "cadence_entropy": m.get("cadence_entropy", 0.0), "paragraphs": m.get("paragraph_count", 0),
            "emotional_valence": m.get("emotional_valence", 0.0), "narrative_velocity": m.get("narrative_velocity", 0.0),
            "cliches_count": len(m.get("cliches", [])), "passive_count": m.get("passive_count", 0),
        })

        if outline_sec:
            unit_sections = [outline_sec] + [p.plan.defs[bid] for bid in p.outline.scene_beats.get(sid, []) if bid in p.plan.defs]
            pov_refs, cast_refs, plants, payoffs, reveals, learns, hidden_from = set(), set(), set(), set(), set(), set(), set()
            for usec in unit_sections:
                pov_refs |= usec.ref_ids_for_field("pov")
                cast_refs |= usec.ref_ids_for_field("cast", "characters")
                plants |= usec.ref_ids_for_field("plants", "plant", "setups", "setup")
                payoffs |= usec.ref_ids_for_field("pays_off", "pays-off", "paysoff", "payoff", "pays")
                reveals |= usec.ref_ids_for_field("reveals", "reveal", "revelations")
                learns |= usec.ref_ids_for_field("learns", "learn", "learners")
                hidden_from |= usec.ref_ids_for_field("hidden_from", "hidden-from", "hidden", "concealed_from")

            if not pov_refs and ch_id in p.plan.defs:
                pov_refs = p.plan.defs[ch_id].ref_ids_for_field("pov")
            all_chars_in_scene = pov_refs | cast_refs
            for cid_ref in all_chars_in_scene:
                if cid_ref in character_agency:
                    character_agency[cid_ref]["cast_count"] += 1
                    character_agency[cid_ref]["scenes"].append(sid)
            for pid_ref in pov_refs:
                if pid_ref in character_agency:
                    character_agency[pid_ref]["pov_count"] += 1
            for pl in plants:
                all_plants.setdefault(pl, []).append({"scene": sid, "index": idx})
            for po in payoffs:
                all_payoffs.setdefault(po, []).append({"scene": sid, "index": idx})
            for rv in reveals:
                secrets_revealed[rv] = {"scene": sid, "index": idx, "learns": sorted(learns), "hidden_from": sorted(hidden_from)}

            has_plot_move = m.get("plot_advancements", 0) > 0
            if not has_plot_move and max(actual_wc, target_wc) >= 1200:
                current_slow_run.append(sid)
            else:
                if len(current_slow_run) >= 2:
                    consecutive_slow_scenes.append(list(current_slow_run))
                current_slow_run = []

    if len(current_slow_run) >= 2:
        consecutive_slow_scenes.append(list(current_slow_run))

    chekhov_matrix = []
    for eid, plants in all_plants.items():
        for pl in plants:
            for po in all_payoffs.get(eid, []):
                gap = po["index"] - pl["index"]
                flag = "immediate_payoff" if gap <= 1 else ("long_dormant" if gap > 10 else "optimal")
                chekhov_matrix.append({"entity": eid, "plant_scene": pl["scene"], "payoff_scene": po["scene"], "scene_gap": gap, "assessment": flag})

    overall_dialogue_ratio = round(total_dialogue_words / max(total_words_actual, 1), 2)
    avg_entropy = round(sum(w["cadence_entropy"] for w in pacing_waveform) / max(len(pacing_waveform), 1), 2)

    if getattr(args, "report", False):
        report_text = generate_analysis_report(
            p=p, metrics_by_scene=metrics_by_scene, pacing_waveform=pacing_waveform,
            character_agency=character_agency, chekhov_matrix=chekhov_matrix,
            secrets_revealed=secrets_revealed, consecutive_slow_scenes=consecutive_slow_scenes,
            novel_sensory=novel_sensory, sensory_alerts=sensory_alerts,
            total_words_outline=total_words_outline, total_words_actual=total_words_actual,
            total_dialogue_words=total_dialogue_words, total_cliches=total_cliches,
            total_passive=total_passive, base_sha=base_sha
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
                "dirty_scenes_count": len(dirty_scenes),
            },
            "waveform": pacing_waveform,
            "character_agency": list(character_agency.values()),
            "chekhov_matrix": chekhov_matrix,
            "epistemic_matrix": secrets_revealed,
            "pacing_sag_sequences": consecutive_slow_scenes,
            "sensory_palette": novel_sensory,
            "sensory_alerts": sensory_alerts,
        }
        print(json.dumps(res, indent=2))
        return 0

    print(f"Total scenes: {len(scene_ids)} | Words: {total_words_actual:,}")
    return 0


def cmd_takes(git: Git, args) -> int:
    p = load_project(git)
    action = args.action
    scene_id = args.id
    takes_base = git.root / STRUCTURE / "takes"

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
                        takes_found.append({
                            "scene": sid, "take": tf.stem, "path": tf.relative_to(git.root).as_posix(),
                            "layer": fm.get("layer", "manuscript"), "saved_at": fm.get("saved_at", ""),
                            "notes": fm.get("notes", ""), "word_count": word_count(txt.splitlines()),
                        })
        if getattr(args, "json", False):
            print(json.dumps(takes_found, indent=2))
        return 0

    take_name = getattr(args, "take", None)
    layer = getattr(args, "layer", "manuscript")
    locale = getattr(args, "locale", None) or p.config.primary_language
    scene_dir = takes_base / scene_id
    take_file = scene_dir / f"{take_name}.md" if take_name else None

    active_layer = p.manuscript_locales.get(locale, p.layers["manuscript"]) if layer == "manuscript" else p.layers["abridged"]

    if action == "save":
        if scene_id not in active_layer.scenes:
            print(f"specnovel: scene '{scene_id}' not found in {layer}", file=sys.stderr)
            return 1
        sec = active_layer.scenes[scene_id]
        scene_dir.mkdir(parents=True, exist_ok=True)
        now_str = datetime.now().isoformat()
        notes = getattr(args, "message", "") or f"Saved take '{take_name}'"
        header = f"---\nscene: {scene_id}\ntake: {take_name}\nlayer: {layer}\nlocale: {locale}\nsaved_at: {now_str}\nnotes: {notes}\n---\n\n"
        take_file.write_text(header + "\n".join(sec.lines) + "\n", encoding="utf-8")
        if getattr(args, "json", False):
            print(json.dumps({"scene": scene_id, "take": take_name, "saved": True, "path": take_file.relative_to(git.root).as_posix()}))
        return 0

    if action == "diff":
        take2_name = getattr(args, "take2", None)
        t1_body = FRONT_RE.sub("", take_file.read_text(encoding="utf-8")).strip()
        if take2_name:
            t2_file = scene_dir / f"{take2_name}.md"
            t2_body = FRONT_RE.sub("", t2_file.read_text(encoding="utf-8")).strip()
        else:
            t2_body = "\n".join(active_layer.scenes[scene_id].lines).strip() if scene_id in active_layer.scenes else ""
        diff_lines = list(difflib.unified_diff(t2_body.splitlines(keepends=True), t1_body.splitlines(keepends=True)))
        if getattr(args, "json", False):
            print(json.dumps({"scene": scene_id, "diff": "".join(diff_lines), "has_diff": bool(diff_lines)}))
        return 0

    if action == "activate":
        take_body = FRONT_RE.sub("", take_file.read_text(encoding="utf-8")).strip()
        sec = active_layer.scenes[scene_id]
        chap_file = git.root / sec.file
        chap_text = chap_file.read_text(encoding="utf-8")
        old_scene_block = "\n".join(sec.lines)
        if old_scene_block in chap_text:
            chap_file.write_text(chap_text.replace(old_scene_block, take_body, 1), encoding="utf-8")
        if getattr(args, "json", False):
            print(json.dumps({"scene": scene_id, "activated_take": take_name, "target_file": sec.file}))
        return 0

    if action == "delete":
        if take_file and take_file.is_file():
            take_file.unlink()
            if getattr(args, "json", False):
                print(json.dumps({"scene": scene_id, "deleted_take": take_name}))
            return 0
        return 1

    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="specnovel", description=__doc__.split("\n\n")[0])
    ap.add_argument("-C", "--root", default=".", help="path inside the novel's git repository (default: cwd)")
    sub = ap.add_subparsers(dest="command")
    specs = [
        ("init", "scaffold 8-stage directory structure and directives/ from templates"),
        ("status", "dashboard across all 8 stages and directives"),
        ("check", "integrity checks across all 8 stages, Beat DAG, serialization, and directives"),
        ("dag", "verify Stage 4 Beat DAG and Stage 5 physical structure serialization"),
        ("next-id", "allocate the next unused ID for a prefix"),
        ("trace", "where an ID is defined, referenced, used in beats, and scheduled in scenes"),
        ("delta", "upstream changes since a stage's baseline (requires stage generation)"),
        ("impact", "records/scenes to synchronize in a stage (requires stage generation)"),
        ("accept", "commit, auto-link relevant directives, and advance stage baseline(s)"),
        ("directives", "manage cross-stage directives (list, match, link, factor)"),
        ("feedback", "alias for directives command"),
        ("placeholders", "scan and convert placeholders into research questions (RQ) in research/"),
        ("bibliography", "auto-generate bibliography from facts attached to the Beat DAG"),
        ("models", "list AI models contributing to the project and check acknowledgements"),
        ("index", "regenerate world/INDEX.md (catalog of all IDs)"),
        ("stats", "word counts per chapter/scene vs targets"),
        ("compile", "assemble the novel in reading order into publishable/"),
        ("log", "list sync commits"),
        ("harvest", "extract characters, places, beats, and scene from raw text/draft"),
        ("scenario", "manage folder-based scenarios (setup/scenarios/<name>/)"),
        ("audit", "developmental editorial telemetry and markdown analysis report generation"),
        ("takes", "manage versioned scene takes (structure/takes/<SCN-ID>/<take-name>.md)"),
    ]
    for name, help_ in specs:
        p = sub.add_parser(name, help=help_)
        if name in ("status", "check", "dag", "trace", "delta", "impact", "stats", "directives", "feedback", "placeholders", "bibliography", "models", "harvest", "scenario", "audit", "takes"):
            p.add_argument("--json", action="store_true", help="machine-readable output")
        if name == "bibliography":
            p.add_argument("--format", choices=["md", "json"], default="md")
            p.add_argument("--output", help="write bibliography to output file")
        if name == "placeholders":
            p.add_argument("path", nargs="?", help="optional file or directory to scan")
            p.add_argument("--create-rq", action="store_true", help="automatically create RQ entries in research/questions.md")
            p.add_argument("--priority", choices=["high", "medium", "low"], help="override priority for generated RQs")
        if name == "dag":
            p.add_argument("--mermaid", action="store_true", help="output Beat DAG as a mermaid diagram")
        if name == "check":
            p.add_argument("--require", action="append", choices=list(LAYERS), help="treat structure scenes missing from this layer as errors")
        if name == "next-id":
            p.add_argument("prefix", help="uppercase ID prefix, e.g. THM, RQ, CHR, BET, SCN, DIR")
        if name == "trace":
            p.add_argument("id", help="ID to trace, e.g. CHR-001")
        if name == "delta":
            p.add_argument("--stage", choices=list(STAGES) + ["plan", "all"], default="world", help="stage baseline to compare against")
            p.add_argument("--initial", action="store_true", help="allow delta inspection before initial stage generation")
        if name == "impact":
            p.add_argument("--stage", choices=list(STAGES), required=True, help="target stage to synchronize")
            p.add_argument("--locale", help="filter manuscript impact by locale")
            p.add_argument("--initial", action="store_true", help="allow impact inspection before initial stage generation")
        if name == "directives" or name == "feedback":
            p.add_argument("action", nargs="?", choices=["list", "match", "link", "factor"], default="list", help="directive action")
            p.add_argument("id", nargs="?", help="optional target record ID (e.g. SCN-001, BET-001) or DIR-NNN")
            p.add_argument("--record", help="optional target record ID for 'link' action")
            p.add_argument("--apply", action="store_true", help="apply auto-linking in place")
            p.add_argument("--status", choices=["active", "open", "applied", "superseded", "wontfix", "all"], default="active")
            p.add_argument("--stage", choices=list(STAGES) + ["all"], help="filter or scope by stage")
            p.add_argument("--locale", help="filter or scope by locale")
            p.add_argument("--title", help="title for factored directive")
            p.add_argument("--instruction", help="instruction text for factored directive")
            p.add_argument("--targets", nargs="+", help="record IDs to link to factored directive")
            p.add_argument("--scope", help="scope expression for factored directive")
        if name == "accept":
            p.add_argument("--stage", action="append", required=True, choices=list(STAGES) + ["plan", "all"])
            p.add_argument("--asset", action="append", help="specific illustration ID(s) to accept (e.g. ILL-001)")
            p.add_argument("--model", help="AI model name contributing to this step")
            p.add_argument("-m", "--message", default="", help="short summary for the commit subject")
            p.add_argument("--force", action="store_true", help="accept even if 'check' reports errors")
        if name == "stats":
            p.add_argument("--scenes", action="store_true", help="include per-scene rows")
        if name == "compile":
            p.add_argument("--layer", choices=list(LAYERS), default="manuscript")
            p.add_argument("--locale", help="target manuscript locale")
            p.add_argument("--format", choices=["md", "docx", "epub", "odt", "pdf", "html"], default="md")
            p.add_argument("--chapter-heading", default="Chapter {N}: {title}")
            p.add_argument("--part-heading", default="Act {N}: {title}")
            p.add_argument("--scene-break", default="* * *")
            p.add_argument("--cover", help="custom cover image path")
            p.add_argument("--css", help="custom CSS stylesheet for EPUB/HTML")
            p.add_argument("--pdf-engine", help="PDF engine for pandoc")
        if name == "harvest":
            p.add_argument("draft_file", help="path to raw text or markdown draft file")
            p.add_argument("--apply", action="store_true", help="scaffold extracted entities into world/, narrative/, structure/, and abridged/")
            p.add_argument("--interactive", action="store_true")
            p.add_argument("--batch", action="store_true")
            p.add_argument("-t", "--title", help="provisional title for the harvested beat/scene")
            p.add_argument("--chapter", help="target chapter ID (e.g. CHP-001)")
        if name == "scenario":
            p.add_argument("action", choices=["create", "list", "diff", "activate", "merge", "delete"])
            p.add_argument("name", nargs="?", help="scenario name")
            p.add_argument("-m", "--message", default="")
        if name == "audit":
            p.add_argument("--developmental", action="store_true", default=True)
            p.add_argument("--deep", action="store_true")
            p.add_argument("--scene", help="drill-down into metrics for a single scene ID")
            p.add_argument("--compare", nargs="?", const="baseline")
            p.add_argument("--no-cache", action="store_true")
            p.add_argument("--report", action="store_true", help="generate a comprehensive markdown analysis report with wiki-links")
            p.add_argument("--output", help="destination file path for the report")
        if name == "takes":
            p.add_argument("action", choices=["list", "save", "diff", "activate", "delete"])
            p.add_argument("id", nargs="?", default="all", help="scene ID, e.g. SCN-001")
            p.add_argument("take", nargs="?", help="take name")
            p.add_argument("take2", nargs="?", help="second take name")
            p.add_argument("--layer", choices=["manuscript", "abridged"], default="manuscript")
            p.add_argument("--locale", help="target manuscript locale")
            p.add_argument("-m", "--message", default="")

    args = ap.parse_args(argv)
    if not args.command:
        args.command, args.json = "status", False
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    root = Path(args.root).resolve()
    handlers = {
        "init": cmd_init, "status": cmd_status, "check": cmd_check, "dag": cmd_dag,
        "next-id": cmd_next_id, "trace": cmd_trace, "delta": cmd_delta, "impact": cmd_impact,
        "accept": cmd_accept, "index": cmd_index, "stats": cmd_stats, "compile": cmd_compile,
        "log": cmd_log, "directives": cmd_directives, "feedback": cmd_directives,
        "placeholders": cmd_placeholders, "bibliography": cmd_bibliography, "models": cmd_models,
        "harvest": cmd_harvest, "scenario": cmd_scenario, "audit": cmd_audit, "takes": cmd_takes,
    }
    try:
        if args.command == "init":
            return cmd_init(root, args)
        return handlers[args.command](Git(root), args)
    except NovelError as e:
        print(f"specnovel: {e}", file=sys.stderr)
        print(f"specnovel: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
