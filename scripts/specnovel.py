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
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set, Tuple

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
STORY, KB, OUTLINE, ABRIDGED, MANUSCRIPT, BUILD = "story", "kb", "outline", "abridged", "manuscript", "build"
PLAN_DIRS = (STORY, KB, OUTLINE)
ALL_DIRS = (STORY, KB, OUTLINE, ABRIDGED, MANUSCRIPT)
LAYERS = {"abridged": ABRIDGED, "manuscript": MANUSCRIPT}
SYNOPSIS_FILE, BRIEF_FILE, STYLE_FILE = "story/synopsis.md", "story/brief.md", "story/style.md"
MIN_STYLE_WORDS = 400

SPEC_STAGES = ("brief", "research", "bible", "outline")
DERIVED_STAGES = ("abridged", "manuscript")
STAGES = SPEC_STAGES + DERIVED_STAGES
STAGE_DIRS: Dict[str, Tuple[str, ...]] = {
    "brief": (SYNOPSIS_FILE, BRIEF_FILE),
    "research": ("kb/research", "kb/sources", "kb/facts"),
    "bible": ("kb/characters", "kb/places", "kb/organizations", "kb/objects",
              "kb/plot", "kb/themes", "kb/world", "kb/timeline"),
    "outline": (OUTLINE,),
    "abridged": (ABRIDGED,),
    "manuscript": (MANUSCRIPT, STYLE_FILE, "story/editorial"),
}
GENERATED = {"kb/INDEX.md"}
KB_FOLDERS = ("characters", "places", "organizations", "objects", "plot", "themes", "world",
              "timeline", "facts", "sources", "research")

TYPES: "OrderedDict[str, str]" = OrderedDict([
    ("CHR", "character"), ("PLC", "place"), ("ORG", "organization"), ("OBJ", "object"),
    ("PLT", "plot element"), ("THM", "theme"), ("WLD", "world rule"), ("TML", "timeline event"),
    ("FCT", "fact"), ("SRC", "source"), ("RQ", "research question"), ("STY", "style rule"),
    ("EDT", "editorial directive"),
    ("PRT", "part"), ("CHP", "chapter"), ("SCN", "scene"),
])
# KB item types that are expected to be referenced from the outline (unused ones are reported).
STORY_TYPES = {"CHR", "PLC", "ORG", "OBJ", "PLT", "THM", "WLD", "TML", "FCT"}


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
        elif stage in DERIVED_STAGES:
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
        """Extract the text value of a named field (e.g. 'time', 'place')."""
        for name in names:
            m = re.search(r"^\s*[-*]?\s*\**" + re.escape(name) + r"\**\s*:\**\s*(.*)$", self.text, re.I | re.M)
            if m:
                val = COMMENT_RE.sub("", m.group(1)).strip()
                if val:
                    return val
                # Check for subsequent indented list or continuation lines
                lines_after: List[str] = []
                in_field = False
                for line in self.lines:
                    if re.match(r"^\s*[-*]?\s*\**" + re.escape(name) + r"\**\s*:\**", line, re.I):
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


# ------------------------------------------------------------------ project state
@dataclass
class Project:
    git: Git
    plan: Model
    outline: Outline
    layers: Dict[str, Derived]


def load_project(git: Git) -> Project:
    plan = build_model(git.working_md(*PLAN_DIRS))
    layers = {name: derived_of(build_model(git.working_md(d))) for name, d in LAYERS.items()}
    return Project(git, plan, outline_of(plan), layers)


def project_title(git: Git) -> str:
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

    # Any element in the plan that explicitly declares prerequisites or is referenced as a prerequisite
    for sec in plan.defs.values():
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


def check_essentiality_to_root(dag: StoryDAG) -> Tuple[Optional[str], List[str]]:
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
    for n in inessential:
        errors.append(f"inessential element: {n} has no causal path to the root denouement ({dag.root})")
    return dag.root, errors


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
    root, ess_errors = check_essentiality_to_root(dag)
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
                    if rel == "kb/INDEX.md" or rel.startswith("kb/sources/"):
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
                clean_text = re.sub(r"^(?:TODO|TBD|FIXME|RESEARCH|PLACEHOLDER)\s*:\s*", "", inner, flags=re.I).strip()
                key = clean_text.lower()
                if key not in items_by_key:
                    items_by_key[key] = PlaceholderItem(raw=f"[{inner}]", text=clean_text, kind="bracket")
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


# ------------------------------------------------------------------ checks
def run_checks(p: Project, require: Sequence[str] = ()) -> Tuple[List[str], List[str], List[str]]:
    errors: List[str] = []
    warnings: List[str] = []
    infos: List[str] = []
    plan, o = p.plan, p.outline
    root = p.git.root

    # inputs
    if not (root / SYNOPSIS_FILE).is_file():
        errors.append(f"missing seed synopsis: {SYNOPSIS_FILE}")
    style = root / STYLE_FILE
    if not style.is_file():
        errors.append(f"missing writing-style guide: {STYLE_FILE} (required input for the manuscript stage)")
    else:
        n = word_count(style.read_text(encoding="utf-8", errors="replace").splitlines())
        if n < MIN_STYLE_WORDS:
            warnings.append(f"{STYLE_FILE} has only {n} words of guidance (excluding comments); a thorough "
                            f"guide (>= {MIN_STYLE_WORDS} words) is expected before writing the manuscript")

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

    if open_edts:
        infos.append(f"{len(open_edts)} open editorial directive(s): " + ", ".join(s.id for s in open_edts))

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


def compute_impact(p: Project, stage: str) -> dict:
    git, plan, o = p.git, p.plan, p.outline
    base = git.baseline(stage)
    old_plan = build_model(git.commit_md(base, *PLAN_DIRS))
    old_o = outline_of(old_plan)
    changes = diff_models(old_plan, plan)
    changed_ids = {c.id for c in changes if c.id}
    target = p.layers[stage]
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
    for d in [f"{KB}/{k}" for k in KB_FOLDERS] + ["story/editorial", OUTLINE, ABRIDGED, MANUSCRIPT]:
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
                   "placeholders": {"total": len(placeholders), "untracked": len(untracked_pl)},
                   "drift": drift, "errors": errors, "warnings": warnings, "infos": infos,
                   "next": next_step(p, impacts, errors)})
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
            f"Next: {next_step(p, impacts, errors)}"]
    print("\n".join(out))
    return 0


def next_step(p: Project, impacts: dict, errors: List[str]) -> str:
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
    if impacts["abridged"]["scenes"] or impacts["abridged"]["remove"]:
        return "novel-abridge (or novel-sync): update the abridged draft"
    if impacts["manuscript"]["scenes"] or impacts["manuscript"]["remove"]:
        style = root / STYLE_FILE
        if not style.is_file() or word_count(style.read_text(encoding="utf-8").splitlines()) < MIN_STYLE_WORDS:
            return "complete story/style.md before writing the manuscript"
        return "novel-write (or novel-sync): render the manuscript"
    return "novel-verify: audit continuity, facts and style; then 'compile'"
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
    root, ess_errors = check_essentiality_to_root(dag)
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

    p = load_project(git)
    errors, _, _ = run_checks(p)
    if errors and not args.force:
        raise NovelError("Refusing to accept - check failed (use --force to override):\n  - " + "\n  - ".join(errors))

    trailers = [f"{TRAILER}: {', '.join(stages)}"]

    dirs_to_stage = set()
    for st in stages:
        if st in STAGE_DIRS:
            dirs_to_stage.update(STAGE_DIRS[st])
        elif st == "plan":
            dirs_to_stage.update(PLAN_DIRS)

    for st in stages:
        if st in ("plan", "bible", "research", "outline"):
            scope = STAGE_DIRS.get(st, PLAN_DIRS)
            base = git.baseline(st)
            changes = diff_models(build_model(git.commit_md(base, *scope)), build_model(git.working_md(*scope)))
            for kind in ("ADDED", "MODIFIED", "REMOVED"):
                ids = [c.id for c in changes if c.id and c.kind == kind]
                if ids:
                    prefix = f"Novel-{st.capitalize()}-" if st != "plan" else "Novel-"
                    trailers.append(f"{prefix}{kind.capitalize()}: {', '.join(ids)}")
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


def cmd_compile(git: Git, args) -> int:
    p = load_project(git)
    d = p.layers[args.layer]
    title = project_title(git)
    out = ["---", f"title: \"{title}\"", "---", ""]
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
                out += [args.scene_break, ""]
            out += clean_prose(d.scenes[sid].body) + [""]
    dst_dir = git.root / BUILD
    dst_dir.mkdir(exist_ok=True)
    md = dst_dir / f"{args.layer}.md"
    md.write_text("\n".join(out), encoding="utf-8")
    words = sum(word_count(s.body) for s in d.scenes.values())
    print(f"Wrote {md.relative_to(git.root).as_posix()} ({words:,} words)")
    if missing:
        print(f"Note: {len(missing)} outline scene(s) not yet written in {args.layer}/ were skipped.")
    if args.format != "md":
        pandoc = shutil.which("pandoc")
        if not pandoc:
            raise NovelError("pandoc is required for --format " + args.format + " (https://pandoc.org)")
        dst = dst_dir / f"{args.layer}.{args.format}"
        subprocess.run([pandoc, str(md), "-o", str(dst)], check=True)
        print(f"Wrote {dst.relative_to(git.root).as_posix()}")
    return 0


def cmd_log(git: Git, args) -> int:
    if not git.has_commits():
        print("No commits yet.")
        return 0
    keys = ",".join(f"key={k}" for k in (TRAILER, "Novel-Added", "Novel-Modified", "Novel-Removed",
                                         "Novel-Abridged-Updated", "Novel-Abridged-Removed",
                                         "Novel-Manuscript-Updated", "Novel-Manuscript-Removed"))
    out = git.lines("log", "--extended-regexp", f"--grep=^{TRAILER}:", f"--format=%h %cs %s%n%(trailers:{keys})", "HEAD")
    print("\n".join(out) if out else "No sync commits yet.")
    return 0


def cmd_feedback(git: Git, args) -> int:
    p = load_project(git)
    plan, o = p.plan, p.outline
    edts = plan.of_type("EDT")

    target_filter = args.id
    status_filter = (args.status or "open").lower()
    stage_filter = (args.stage or "").lower()

    matched: List[Section] = []
    for s in edts:
        st = (s.field_value("status") or "").lower()
        if status_filter != "all" and st != status_filter:
            continue
        stage = (s.field_value("stage") or "").lower()
        if stage_filter and stage_filter != "all" and stage != "all" and stage != stage_filter:
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

    out = ["| ID | Target | Stage | Status | Title |",
           "|----|--------|-------|--------|-------|"]
    for s in matched:
        tgt = s.field_value("target") or "-"
        stg = s.field_value("stage") or "-"
        st = s.field_value("status") or "-"
        out.append(f"| {s.id} | {tgt} | {stg} | {st} | {s.title} |")
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
             ("index", "regenerate kb/INDEX.md (catalog of all IDs)"),
             ("stats", "word counts per chapter/scene vs targets"),
             ("compile", "assemble the novel in reading order into build/"),
             ("log", "list sync commits")]
    for name, help_ in specs:
        p = sub.add_parser(name, help=help_)
        if name in ("status", "check", "dag", "trace", "delta", "impact", "stats", "feedback", "placeholders"):
            p.add_argument("--json", action="store_true", help="machine-readable output")
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
            p.add_argument("--stage", choices=list(LAYERS), required=True)
        if name == "feedback":
            p.add_argument("id", nargs="?", help="optional target scene/chapter ID (e.g. SCN-014) or EDT-xxx ID")
            p.add_argument("--status", choices=["open", "applied", "superseded", "wontfix", "all"], default="open",
                           help="filter by directive status (default: open)")
            p.add_argument("--stage", choices=["outline", "abridged", "manuscript", "all"],
                           help="filter by target stage")
        if name == "accept":
            p.add_argument("--stage", action="append", required=True, choices=list(STAGES) + ["plan", "all"])
            p.add_argument("-m", "--message", default="", help="short summary for the commit subject")
            p.add_argument("--force", action="store_true", help="accept even if 'check' reports errors")
        if name == "stats":
            p.add_argument("--scenes", action="store_true", help="include per-scene rows")
        if name == "compile":
            p.add_argument("--layer", choices=list(LAYERS), default="manuscript")
            p.add_argument("--format", choices=["md", "docx", "epub", "odt", "pdf", "html"], default="md")
            p.add_argument("--chapter-heading", default="Chapter {N}: {title}",
                           help="format; fields {n} (1), {N} (One), {title}")
            p.add_argument("--part-heading", default="Part {N}: {title}")
            p.add_argument("--scene-break", default="* * *")
    args = ap.parse_args(argv)
    if not args.command:
        args.command, args.json = "status", False
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    root = Path(args.root).resolve()
    handlers = {"init": cmd_init, "status": cmd_status, "check": cmd_check, "dag": cmd_dag, "next-id": cmd_next_id,
                "trace": cmd_trace, "delta": cmd_delta, "impact": cmd_impact, "accept": cmd_accept, "index": cmd_index,
                "stats": cmd_stats, "compile": cmd_compile, "log": cmd_log, "feedback": cmd_feedback,
                "placeholders": cmd_placeholders}
    try:
        if args.command == "init":
            return cmd_init(root, args)
        return handlers[args.command](Git(root), args)
    except NovelError as e:
        print(f"specnovel: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
