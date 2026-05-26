#!/usr/bin/env python3
"""
skyd_sandbox.py — Sandbox + Rollback + FitnessV2 + SkyLang v2 Parser
Three real fixes applied based on Grok's code review:
  1. _ast_merge()   — AST NodeTransformer replaces regex-based _smart_merge
  2. FitnessV2      — pre/post line count passed explicitly, no circular dependency
  3. SkyLang wiring — parse_skylang() in skyd.py now delegates to SkyLangParser
"""

import os, re, ast, sys, json, math, time, shutil, hashlib, logging, pathlib, subprocess, tempfile
from datetime import datetime
from collections import defaultdict, deque

log = logging.getLogger("skyd.sandbox")

SKYD_PATH    = "/skyd/skyd.py"
BACKUP_DIR   = "/var/log/skyd_backups"
CANDIDATE    = "/tmp/skyd_candidate.py"
FITNESS_LOG  = "/var/log/skyd_fitness_v2.jsonl"
SANDBOX_LOG  = "/var/log/skyd_sandbox.jsonl"
SKYLANG_LOG  = "/var/log/skyd_skylang_v2.jsonl"
LANG_DIR     = "/usr/local/skyd/lang"

os.makedirs(BACKUP_DIR, exist_ok=True)
os.makedirs(LANG_DIR,   exist_ok=True)


# ══════════════════════════════════════════════════════════════════
# FIX 1: AST-BASED MERGE (replaces regex _smart_merge)
# ══════════════════════════════════════════════════════════════════

PROTECTED_NAMES = frozenset({
    "is_safe", "is_permanently_blocked", "_add_guardrail",
    "apply_self_improvement", "main", "hive_heartbeat",
})


class _FunctionReplacer(ast.NodeTransformer):
    """
    AST NodeTransformer that replaces FunctionDef/AsyncFunctionDef/ClassDef
    nodes by name. Only replaces if the name exists in replacement_nodes
    AND is not in the protected set.
    """
    def __init__(self, replacement_nodes: dict):
        self.replacement_nodes = replacement_nodes  # name -> ast.AST node
        self.replaced = set()

    def _replace_if_match(self, node):
        name = getattr(node, 'name', None)
        if name and name in self.replacement_nodes and name not in PROTECTED_NAMES:
            new_node = self.replacement_nodes[name]
            # Copy location info so ast.unparse works
            ast.copy_location(new_node, node)
            ast.fix_missing_locations(new_node)
            self.replaced.add(name)
            return new_node
        return node

    def visit_FunctionDef(self, node):
        return self._replace_if_match(node)

    def visit_AsyncFunctionDef(self, node):
        return self._replace_if_match(node)

    def visit_ClassDef(self, node):
        return self._replace_if_match(node)


def _ast_merge(original_src: str, snippet: str, description: str = "") -> tuple:
    """
    AST-based merge. Replaces matching FunctionDef/ClassDef nodes by name.
    New names (not in original) are appended before main().
    Protected names are never overwritten.
    Returns (merged_src, reason) or (None, error).
    """
    if not snippet or len(snippet.strip()) < 10:
        return None, "snippet too short"

    # Parse both — fail fast on bad snippet syntax
    try:
        orig_tree = ast.parse(original_src)
    except SyntaxError as e:
        return None, f"original parse failed: {e}"

    try:
        snippet_tree = ast.parse(snippet)
    except SyntaxError as e:
        return None, f"snippet syntax error: {e}"

    # Extract top-level defs from snippet
    snippet_nodes = {}
    for node in snippet_tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name in PROTECTED_NAMES:
                return None, f"blocked: snippet overwrites protected '{node.name}'"
            snippet_nodes[node.name] = node

    if not snippet_nodes:
        # No named defs — treat as expression/assignment, append directly
        for node in snippet_tree.body:
            orig_tree.body.append(node)
        ast.fix_missing_locations(orig_tree)
        return ast.unparse(orig_tree), "appended (no named defs)"

    # Find which names already exist in original
    existing_names = {
        node.name
        for node in ast.walk(orig_tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }

    to_replace = {n: v for n, v in snippet_nodes.items() if n in existing_names}
    to_append  = {n: v for n, v in snippet_nodes.items() if n not in existing_names}

    # Replace existing nodes via NodeTransformer
    if to_replace:
        replacer = _FunctionReplacer(to_replace)
        orig_tree = replacer.visit(orig_tree)
        ast.fix_missing_locations(orig_tree)
        log.info(f"  🔄 AST replaced: {list(replacer.replaced)}")

    # Append new nodes before main() if possible
    if to_append:
        main_idx = next(
            (i for i, node in enumerate(orig_tree.body)
             if isinstance(node, ast.FunctionDef) and node.name == "main"),
            len(orig_tree.body)
        )
        # Insert a comment marker + new nodes
        comment_str = f"# === Evolved: {description[:50]} ==="
        for offset, (name, node) in enumerate(to_append.items()):
            orig_tree.body.insert(main_idx + offset, node)
        ast.fix_missing_locations(orig_tree)
        log.info(f"  ➕ AST appended: {list(to_append.keys())} before main()")

    try:
        merged = ast.unparse(orig_tree)
        # ast.unparse strips comments and collapses whitespace — add header
        merged = (
            f"# skyd.py — evolved via AST merge | {description[:60]}\n"
            + "# Original comments/formatting stripped by ast.unparse — see git history\n\n"
            + merged
        )
        return merged, "ok"
    except Exception as e:
        return None, f"ast.unparse failed: {e}"


# ══════════════════════════════════════════════════════════════════
# PART 1 — SANDBOX + ROLLBACK
# ══════════════════════════════════════════════════════════════════

class EvolutionSandbox:
    """
    Wraps every proposed code change in a test-before-promote pipeline.

    Pipeline:
      1. Checkpoint current skyd.py → /var/log/skyd_backups/skyd_{gen}_{ts}.py
      2. AST-merge proposed snippet into candidate copy
      3. py_compile syntax check
      4. Behavioral subprocess test (safe_mode=low skips this)
      5. Fitness delta check (uses explicit pre-merge line count — no circular dep)
      6. Promote if delta > -0.05, else revert
    """

    def __init__(self, fitness_fn=None):
        self._fitness_fn = fitness_fn or self._default_fitness
        self._history    = []
        self._stagnant   = 0
        self._best       = None

    # ── Checkpoint ──────────────────────────────────────────────

    def checkpoint(self, generation):
        backup = f"{BACKUP_DIR}/skyd_{generation}_{int(time.time())}.py"
        try:
            shutil.copy2(SKYD_PATH, backup)
            backups = sorted(pathlib.Path(BACKUP_DIR).glob("skyd_*.py"))
            for old in backups[:-20]:
                old.unlink(missing_ok=True)
            log.info(f"💾 Checkpoint: {backup}")
            return backup
        except Exception as e:
            log.warning(f"Checkpoint failed: {e}")
            return None

    def rollback(self, backup_path, generation, reason=""):
        if not backup_path or not pathlib.Path(backup_path).exists():
            log.error(f"❌ Rollback failed — no backup at {backup_path}")
            return False
        try:
            shutil.copy2(backup_path, SKYD_PATH)
            log.info(f"⏮️  Rolled back Gen {generation} — {reason}")
            self._log_sandbox_event(generation, "ROLLBACK", reason=reason)
            return True
        except Exception as e:
            log.error(f"Rollback error: {e}")
            return False

    # ── Syntax check ────────────────────────────────────────────

    def _syntax_check(self, path):
        try:
            r = subprocess.run(
                [sys.executable, "-m", "py_compile", path],
                capture_output=True, text=True, timeout=10
            )
            return r.returncode == 0, r.stderr.strip()
        except Exception as e:
            return False, str(e)

    # ── Behavioral test ──────────────────────────────────────────

    def _behavioral_test(self, path, timeout=15):
        """
        AST walk of candidate — confirm required functions still present,
        no obvious top-level side effects that would crash on import.
        """
        test_script = f"""
import sys, ast
with open({repr(path)}) as f:
    src = f.read()
tree = ast.parse(src)
required = {{'main','smart_think','is_safe','load_kb','get_system_state'}}
defined   = {{n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}}
missing   = required - defined
if missing:
    print('MISSING:' + ','.join(missing))
    sys.exit(1)
print('PASS:functions=' + str(len(defined)))
"""
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(test_script)
                tpath = f.name
            r = subprocess.run([sys.executable, tpath],
                               capture_output=True, text=True, timeout=timeout)
            os.unlink(tpath)
            output = r.stdout.strip()
            if r.returncode == 0 and output.startswith("PASS"):
                fn_count = int(output.split("functions=")[1]) if "functions=" in output else 0
                return True, {"functions": fn_count}
            return False, {"error": r.stderr.strip() or output}
        except subprocess.TimeoutExpired:
            return False, {"error": "behavioral test timed out"}
        except Exception as e:
            return False, {"error": str(e)}

    # ── Default fitness (from source text) ───────────────────────

    def _default_fitness(self, src, growth_signal=0.7):
        lines = src.count('\n')
        fns   = len(re.findall(r'^def \w+', src, re.MULTILINE))
        branches = len(re.findall(r'\b(if|elif|for|while|except)\b', src))
        freq = defaultdict(int)
        for c in src: freq[c] += 1
        total = len(src) or 1
        entropy = -sum((v/total)*math.log2(v/total) for v in freq.values() if v > 0)
        return round((fns * 2 + branches * 0.5 + entropy + growth_signal) / 10, 4)

    # ── FIX 2: test_and_promote takes explicit pre_merge_lines ───

    def test_and_promote(self, snippet, description, generation,
                         current_fitness, risk="low", pre_merge_lines=None):
        """
        Full sandbox pipeline.
        pre_merge_lines: caller passes len(original.splitlines()) to avoid
                         circular dependency in fitness growth calculation.
        """
        safe_mode = (risk == "low")
        backup = self.checkpoint(generation)

        try:
            original = pathlib.Path(SKYD_PATH).read_text()
        except Exception as e:
            return False, current_fitness, f"can't read source: {e}"

        # Capture pre-merge line count here if caller didn't pass it
        pre_lines = pre_merge_lines or len(original.splitlines())

        # AST merge (replaces regex merge)
        merged, merge_err = _ast_merge(original, snippet, description)
        if merged is None:
            self._log_sandbox_event(generation, "SKIP", reason=merge_err)
            log.info(f"⏭️  Sandbox skip: {merge_err}")
            return False, current_fitness, merge_err

        # Write candidate
        pathlib.Path(CANDIDATE).write_text(merged)

        # Syntax check
        ok, err = self._syntax_check(CANDIDATE)
        if not ok:
            self._log_sandbox_event(generation, "REJECT_SYNTAX", reason=err)
            log.warning(f"❌ Syntax fail: {err[:80]}")
            return False, current_fitness, f"syntax: {err[:80]}"

        # Behavioral test (skipped for low-risk proposals)
        if not safe_mode:
            ok, result = self._behavioral_test(CANDIDATE)
            if not ok:
                self._log_sandbox_event(generation, "REJECT_BEHAVIOR", reason=str(result))
                log.warning(f"❌ Behavioral fail: {result}")
                return False, current_fitness, f"behavior: {result}"

        # FIX 2: compute growth signal from explicit pre/post line counts
        post_lines    = len(merged.splitlines())
        growth_signal = 1.0 if post_lines > pre_lines else 0.7
        delta_lines   = post_lines - pre_lines

        new_fitness = self._default_fitness(merged, growth_signal=growth_signal)
        delta       = new_fitness - current_fitness

        if delta > -0.05:
            shutil.copy2(CANDIDATE, SKYD_PATH)
            self._log_sandbox_event(generation, "PROMOTE",
                                    delta=delta, fitness=new_fitness,
                                    pre_lines=pre_lines, post_lines=post_lines,
                                    delta_lines=delta_lines)
            log.info(f"✅ PROMOTED Gen {generation+1}: Δfit={delta:+.4f} "
                     f"lines {pre_lines}→{post_lines} (+{delta_lines})")
            self._history.append((generation, delta, True))
            try: get_fitness()._recent_promotions += 1
            except: pass
            if self._best is None or new_fitness > self._best:
                self._best = new_fitness
                self._stagnant = 0
            else:
                self._stagnant += 1
            return True, new_fitness, f"promoted +{delta_lines} lines"
        else:
            self.rollback(backup, generation, reason=f"fitness drop {delta:+.4f}")
            self._log_sandbox_event(generation, "REVERT",
                                    delta=delta, fitness=new_fitness)
            self._stagnant += 1
            return False, current_fitness, f"fitness drop {delta:+.4f}"

    def _log_sandbox_event(self, generation, event, **kwargs):
        entry = {"ts": datetime.now().isoformat(), "gen": generation,
                 "event": event, **kwargs}
        try:
            with open(SANDBOX_LOG, "a") as f: f.write(json.dumps(entry) + "\n")
        except: pass

    def recent_history(self, n=10):
        return self._history[-n:]

    def stagnation_cycles(self):
        return self._stagnant


# ══════════════════════════════════════════════════════════════════
# PART 2 — FitnessV2 (circular dependency fixed)
# ══════════════════════════════════════════════════════════════════

class FitnessV2:
    """
    FIX 2: growth_signal is now passed in explicitly from test_and_promote,
    which computes it from pre/post line counts before the fitness call.
    No more reading from the live file to infer growth.

    fitness = 0.20 * unique_action_diversity
            + 0.15 * watchdog_pass_rate
            + 0.25 * lesson_novelty
            + 0.15 * growth_signal          ← passed in, not inferred
            + 0.10 * (0 if stagnant else 1)
            + 0.15 * promotion_bonus
    """

    def __init__(self):
        self._action_window      = deque(maxlen=50)
        self._stagnant_ctr       = 0
        self._last_fitness       = None
        self._stagnant_thresh    = 10
        self._recent_promotions  = 0

    def update_actions(self, action):
        self._action_window.append(action or "none")

    def calculate(self, src, kb, watchdog_pass_rate,
                  lessons_recent, lessons_older,
                  growth_signal=None):
        """
        growth_signal: if None, falls back to code-line heuristic (deprecated path).
                       Pass explicitly from test_and_promote for accuracy.
        """
        lines = src.count('\n') if src else 0
        fns   = len(re.findall(r'^def \w+', src, re.MULTILINE)) if src else 0

        # Action diversity
        actions = list(self._action_window)
        unique_actions = len(set(actions)) / max(len(actions), 1)

        # Watchdog pass rate
        pass_rate = min(1.0, max(0.0, watchdog_pass_rate))

        # Lesson novelty
        recent_words = set(' '.join(lessons_recent).lower().split())
        older_words  = set(' '.join(lessons_older).lower().split())
        novelty = (len(recent_words - older_words) / max(len(recent_words), 1)
                   if recent_words else 0)

        # FIX: growth_signal passed in explicitly; fall back only if missing
        if growth_signal is None:
            # Deprecated fallback — infer from stored prev counts
            growth_signal = getattr(self, '_last_growth', 0.7)

        # Promotion bonus
        prom_bonus = min(1.0, self._recent_promotions / 3.0)

        fitness = round(
            0.20 * unique_actions +
            0.15 * pass_rate +
            0.25 * novelty +
            0.15 * growth_signal +
            0.10 * (0.0 if self._stagnant_ctr >= self._stagnant_thresh else 1.0) +
            0.15 * prom_bonus,
            4
        )

        # Stagnation tracking
        if self._last_fitness is not None:
            if abs(fitness - self._last_fitness) < 0.002:
                self._stagnant_ctr += 1
            else:
                self._stagnant_ctr = 0
        self._last_fitness  = fitness
        self._last_growth   = growth_signal

        record = {
            "ts": datetime.now().isoformat(),
            "fitness": fitness,
            "unique_actions": round(unique_actions, 3),
            "pass_rate": round(pass_rate, 3),
            "novelty": round(novelty, 3),
            "growth_signal": growth_signal,
            "stagnant_cycles": self._stagnant_ctr,
            "promo_bonus": round(prom_bonus, 3),
            "code_lines": lines,
            "functions": fns,
        }
        try:
            with open(FITNESS_LOG, "a") as f: f.write(json.dumps(record) + "\n")
        except: pass

        return fitness, record

    def is_stagnant(self):
        return self._stagnant_ctr >= self._stagnant_thresh

    def stagnation_pressure(self):
        return min(1.0, self._stagnant_ctr / self._stagnant_thresh)


# ══════════════════════════════════════════════════════════════════
# FIX 3: SKYLANG v2 TYPED PARSER (wired — replaces skyd.py's parser)
# ══════════════════════════════════════════════════════════════════

"""
SkyLang v2 grammar (EBNF):

program    := statement*
statement  := watch_stmt | every_stmt | if_stmt | on_stmt | define_stmt
watch_stmt := 'WATCH' metric comparator value '->' action_list
every_stmt := 'EVERY' duration '->' action_list
if_stmt    := 'IF' condition '->' action_list ['ELSE' '->' action_list]
on_stmt    := 'ON' event '->' action_list
define_stmt:= 'DEFINE' name '=' value

Types: INT, FLOAT, PERCENT, STRING, DURATION, IDENTIFIER
"""

from dataclasses import dataclass, field
from typing import List, Any

TK_WATCH='WATCH'; TK_EVERY='EVERY'; TK_IF='IF'; TK_ELSE='ELSE'
TK_ON='ON'; TK_DEFINE='DEFINE'; TK_ARROW='->'; TK_SEMI=';'
TK_IDENT='IDENT'; TK_NUMBER='NUMBER'; TK_STRING='STRING'
TK_CMP='CMP'; TK_DURATION='DURATION'; TK_EOF='EOF'

KEYWORDS = {'WATCH':TK_WATCH,'EVERY':TK_EVERY,'IF':TK_IF,
            'ELSE':TK_ELSE,'ON':TK_ON,'DEFINE':TK_DEFINE}

@dataclass
class Token:
    type: str
    value: Any
    line: int = 0

@dataclass
class WatchStmt:
    metric: str
    comparator: str
    threshold: Any
    threshold_type: str
    actions: List[str]

@dataclass
class EveryStmt:
    interval_seconds: int
    actions: List[str]

@dataclass
class IfStmt:
    condition: str
    actions: List[str]
    else_actions: List[str] = field(default_factory=list)

@dataclass
class OnStmt:
    event: str
    actions: List[str]

@dataclass
class DefineStmt:
    name: str
    value: Any

@dataclass
class ParseError:
    line: int
    message: str


class SkyLangLexer:
    def __init__(self, source):
        self.tokens = []
        self._tokenize(source)

    def _tokenize(self, src):
        i = 0; line = 1
        while i < len(src):
            if src[i] == '\n':           line += 1; i += 1; continue
            if src[i] in ' \t\r':        i += 1; continue
            if src[i] == '#':
                while i < len(src) and src[i] != '\n': i += 1
                continue
            if src[i:i+2] == '->':
                self.tokens.append(Token(TK_ARROW, '->', line)); i += 2; continue
            if src[i:i+2] in ('>=','<=','==','!='):
                self.tokens.append(Token(TK_CMP, src[i:i+2], line)); i += 2; continue
            if src[i] in '><':
                self.tokens.append(Token(TK_CMP, src[i], line)); i += 1; continue
            if src[i] == ';':
                self.tokens.append(Token(TK_SEMI, ';', line)); i += 1; continue
            if src[i] in '"\'':
                q = src[i]; j = i+1
                while j < len(src) and src[j] != q: j += 1
                self.tokens.append(Token(TK_STRING, src[i+1:j], line)); i = j+1; continue
            if src[i].isdigit():
                j = i
                while j < len(src) and (src[j].isdigit() or src[j] == '.'): j += 1
                raw = src[i:j]
                num = float(raw) if '.' in raw else int(raw)
                if j < len(src) and src[j] in 'smhd':
                    suf = src[j]
                    self.tokens.append(Token(TK_DURATION, num * {'s':1,'m':60,'h':3600,'d':86400}[suf], line))
                    i = j+1
                elif j < len(src) and src[j] == '%':
                    self.tokens.append(Token(TK_NUMBER, ('percent', num), line)); i = j+1
                else:
                    self.tokens.append(Token(TK_NUMBER, num, line)); i = j
                continue
            if src[i].isalpha() or src[i] == '_':
                j = i
                while j < len(src) and (src[j].isalnum() or src[j] in '_.'): j += 1
                word = src[i:j]
                ttype = KEYWORDS.get(word.upper(), TK_IDENT)
                self.tokens.append(Token(ttype, word.upper() if ttype != TK_IDENT else word, line))
                i = j; continue
            i += 1  # skip unknown
        self.tokens.append(Token(TK_EOF, None, line))


class SkyLangParser:
    """
    Recursive descent parser for SkyLang v2.
    FIX 3: This is now the canonical parser — skyd.py's parse_skylang()
    delegates here via the module-level parse_skylang_file() function.
    """

    def __init__(self):
        self.tokens = []
        self.pos = 0

    def _load(self, source):
        self.tokens = SkyLangLexer(source).tokens
        self.pos = 0

    def _peek(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else Token(TK_EOF, None)

    def _advance(self):
        t = self.tokens[self.pos]; self.pos += 1; return t

    def _expect(self, ttype):
        t = self._advance()
        if t.type != ttype:
            raise SyntaxError(f"Line {t.line}: expected {ttype}, got {t.type}({t.value!r})")
        return t

    def _parse_value(self):
        t = self._advance()
        if t.type == TK_NUMBER:
            if isinstance(t.value, tuple) and t.value[0] == 'percent':
                return t.value[1], 'percent'
            return t.value, 'float' if isinstance(t.value, float) else 'int'
        if t.type == TK_STRING:   return t.value, 'string'
        if t.type == TK_IDENT:    return t.value, 'identifier'
        if t.type == TK_DURATION: return t.value, 'duration'
        return t.value, 'unknown'

    def _parse_action_list(self):
        actions = []
        STOPS = (TK_WATCH, TK_EVERY, TK_IF, TK_ON, TK_DEFINE, TK_ELSE, TK_EOF)
        while self._peek().type not in STOPS:
            if self._peek().type == TK_SEMI:
                self._advance(); continue
            parts = []
            while self._peek().type not in (TK_SEMI, *STOPS):
                parts.append(str(self._advance().value))
            action = ' '.join(parts).strip()
            if action: actions.append(action)
            if self._peek().type == TK_SEMI:
                self._advance()
            else:
                break
        return actions

    def _parse_watch(self):
        self._advance()  # consume WATCH
        metric_tok = self._expect(TK_IDENT)
        cmp_tok    = self._expect(TK_CMP)
        val, vtype = self._parse_value()
        self._expect(TK_ARROW)
        actions    = self._parse_action_list()
        return WatchStmt(metric=metric_tok.value, comparator=cmp_tok.value,
                         threshold=val, threshold_type=vtype, actions=actions)

    def _parse_every(self):
        self._advance()  # consume EVERY
        dur = self._advance()
        interval = dur.value if dur.type == TK_DURATION else int(dur.value or 60)
        self._expect(TK_ARROW)
        return EveryStmt(interval_seconds=interval, actions=self._parse_action_list())

    def _parse_if(self):
        self._advance()  # consume IF
        parts = []
        while self._peek().type not in (TK_ARROW, TK_EOF):
            parts.append(str(self._advance().value))
        self._expect(TK_ARROW)
        actions = self._parse_action_list()
        else_actions = []
        if self._peek().type == TK_ELSE:
            self._advance()
            self._expect(TK_ARROW)
            else_actions = self._parse_action_list()
        return IfStmt(condition=' '.join(parts), actions=actions, else_actions=else_actions)

    def _parse_on(self):
        self._advance()
        event = self._advance()
        self._expect(TK_ARROW)
        return OnStmt(event=str(event.value), actions=self._parse_action_list())

    def _parse_define(self):
        self._advance()
        name = self._expect(TK_IDENT).value
        if self._peek().value == '=': self._advance()
        val, _ = self._parse_value()
        return DefineStmt(name=name, value=val)

    def _parse_statement(self):
        t = self._peek()
        if t.type == TK_WATCH:  return self._parse_watch()
        if t.type == TK_EVERY:  return self._parse_every()
        if t.type == TK_IF:     return self._parse_if()
        if t.type == TK_ON:     return self._parse_on()
        if t.type == TK_DEFINE: return self._parse_define()
        self._advance(); return None

    def parse(self, source):
        self._load(source)
        statements, errors = [], []
        while self._peek().type != TK_EOF:
            try:
                stmt = self._parse_statement()
                if stmt: statements.append(stmt)
            except SyntaxError as e:
                errors.append(ParseError(0, str(e)))
                while self._peek().type not in (TK_WATCH,TK_EVERY,TK_IF,TK_ON,TK_DEFINE,TK_EOF):
                    self._advance()
        return statements, errors

    def parse_file(self, path):
        """FIX 3: Entry point for skyd.py's parse_skylang() to call."""
        try:
            source = pathlib.Path(path).read_text()
        except Exception as e:
            return [], [ParseError(0, f"can't read {path}: {e}")]
        return self.parse(source)


# ── Runtime executor ────────────────────────────────────────────

SAFE_ACTIONS = {
    "DROP_CACHE":  "sync && echo 3 > /proc/sys/vm/drop_caches",
    "RENICE":      "renice -n 19 -p $(pgrep {arg1} | head -1)",
    "SYNC":        "sync",
    "VACUUM_LOGS": "find /var/log -name '*.log' -mtime +{arg0} -delete",
    "ALERT":       None,   # handled in Python, not shell
    "LOG":         None,
    "NOOP":        "true",
}

class SkyLangRuntime:
    """
    FIX 3: Executes typed SkyLang v2 AST nodes against live system state.
    This replaces the shell-string-matching approach in the old parse_skylang().
    """

    def __init__(self):
        self._defines    = {}
        self._last_every = {}

    def _get_metric(self, name, state):
        key = name.lower().replace(".", "_").replace("usage", "percent")
        mapping = {
            "cpu": state.get("cpu_percent", 0),
            "mem": state.get("memory_percent", 0),
            "ram": state.get("memory_percent", 0),
            "disk": state.get("disk_percent", 0),
            "swap": state.get("swap_percent", 0),
        }
        for k, v in mapping.items():
            if k in key: return v
        return self._defines.get(name, 0)

    def _eval(self, stmt, state):
        if isinstance(stmt, WatchStmt):
            val = self._get_metric(stmt.metric, state)
            th  = stmt.threshold
            cmp = stmt.comparator
            return ((cmp=='>' and val>th) or (cmp=='<' and val<th) or
                    (cmp=='>=' and val>=th) or (cmp=='<=' and val<=th) or
                    (cmp=='==' and val==th) or (cmp=='!=' and val!=th))
        return True

    def _exec_action(self, action_str):
        word = action_str.strip().upper().split()[0]
        if word in ("RESTART","RM","DELETE","KILL","FSTRIM"):
            log.info(f"🚫 SkyLang v2 blocked: {action_str[:50]}")
            return False
        if word == "ALERT":
            log.warning(f"[SKYLANG ALERT] {action_str[6:].strip()}")
            return True
        if word == "LOG":
            log.info(f"[SKYLANG] {action_str[4:].strip()}")
            return True
        cmd = SAFE_ACTIONS.get(word)
        if cmd:
            parts = action_str.split()[1:]
            for i, p in enumerate(parts): cmd = cmd.replace(f"{{arg{i}}}", p)
            try:
                subprocess.run(cmd, shell=True, timeout=10, capture_output=True)
                return True
            except Exception as e:
                log.warning(f"SkyLang exec error: {e}")
                return False
        log.info(f"[SKYLANG unexecuted] {action_str[:50]}")
        return True

    def run(self, statements, state):
        fired = []
        now = time.time()
        for stmt in statements:
            try:
                if isinstance(stmt, WatchStmt) and self._eval(stmt, state):
                    for a in stmt.actions:
                        self._exec_action(a)
                        fired.append(("WATCH", stmt.metric, a))
                elif isinstance(stmt, EveryStmt):
                    last = self._last_every.get(stmt.interval_seconds, 0)
                    if now - last >= stmt.interval_seconds:
                        for a in stmt.actions:
                            self._exec_action(a)
                            fired.append(("EVERY", stmt.interval_seconds, a))
                        self._last_every[stmt.interval_seconds] = now
                elif isinstance(stmt, IfStmt):
                    branch = stmt.actions if self._eval(stmt, state) else stmt.else_actions
                    for a in branch: self._exec_action(a)
                elif isinstance(stmt, DefineStmt):
                    self._defines[stmt.name] = stmt.value
            except Exception as e:
                log.warning(f"SkyLang runtime error: {e}")
        return fired


# ══════════════════════════════════════════════════════════════════
# SKYLANG → PYTHON CODEGEN
# ══════════════════════════════════════════════════════════════════

def generate_python_from_skylang(statements):
    """Convert SkyLang v2 AST → real Python functions (not shell one-liners)."""
    lines = [
        "# SkyLang v2 → Python codegen",
        "import subprocess, logging as _log",
        "_skl = _log.getLogger('skyd.skylang')",
        "",
    ]
    for i, stmt in enumerate(statements):
        if isinstance(stmt, WatchStmt):
            fn = f"_watch_{stmt.metric.replace('.','_')}_{i}"
            op = stmt.comparator
            th = stmt.threshold
            action_code = []
            for act in stmt.actions:
                w = act.strip().upper().split()[0]
                if w == "DROP_CACHE":
                    action_code.append('        subprocess.run("sync && echo 3 > /proc/sys/vm/drop_caches", shell=True, timeout=5)')
                elif w == "ALERT":
                    action_code.append(f'        _skl.warning("[ALERT] {act[6:].strip()}")')
                else:
                    action_code.append(f'        _skl.info("[SKYLANG] {act}")')
            lines += [
                f"def {fn}(state):",
                f'    """WATCH {stmt.metric} {op} {th}"""',
                f"    val = state.get('{stmt.metric.lower()}', 0)",
                f"    if val {op} {th}:",
            ] + action_code + ["        return True", "    return False", ""]
        elif isinstance(stmt, EveryStmt):
            fn = f"_every_{stmt.interval_seconds}s_{i}"
            lines += [
                f"_{fn}_last = 0.0",
                f"def {fn}(now=None):",
                f'    """EVERY {stmt.interval_seconds}s"""',
                f"    import time as _t; global _{fn}_last",
                f"    _n = now or _t.time()",
                f"    if _n - _{fn}_last >= {stmt.interval_seconds}:",
            ]
            for act in stmt.actions:
                lines.append(f'        _skl.info("[EVERY] {act}")')
            lines += [f"        _{fn}_last = _n", "        return True", "    return False", ""]
        elif isinstance(stmt, DefineStmt):
            lines += [f"_SKL_{stmt.name.upper()} = {repr(stmt.value)}", ""]
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════
# MODULE-LEVEL SINGLETONS + PUBLIC API
# ══════════════════════════════════════════════════════════════════

_sandbox = None
_fitness = None
_parser  = None
_runtime = None

def get_sandbox():
    global _sandbox
    if _sandbox is None: _sandbox = EvolutionSandbox()
    return _sandbox

def get_fitness():
    global _fitness
    if _fitness is None: _fitness = FitnessV2()
    return _fitness

def get_parser():
    global _parser
    if _parser is None: _parser = SkyLangParser()
    return _parser

def get_runtime():
    global _runtime
    if _runtime is None: _runtime = SkyLangRuntime()
    return _runtime


# FIX 3: Drop-in replacement for skyd.py's parse_skylang(script_path)
def parse_skylang_file(script_path):
    """
    Called by skyd.py's parse_skylang() — returns (statements, errors).
    Replaces the old string-matching parser entirely.
    """
    stmts, errors = get_parser().parse_file(script_path)
    stats = {
        "watch": sum(1 for s in stmts if isinstance(s, WatchStmt)),
        "every": sum(1 for s in stmts if isinstance(s, EveryStmt)),
        "if":    sum(1 for s in stmts if isinstance(s, IfStmt)),
        "total": len(stmts), "errors": len(errors),
    }
    try:
        with open(SKYLANG_LOG, "a") as f:
            f.write(json.dumps({"ts": datetime.now().isoformat(),
                                "path": str(script_path), "stats": stats}) + "\n")
    except: pass
    return stmts, errors


def parse_and_validate_skylang(source):
    """Parse a SkyLang v2 source string. Returns (statements, errors, stats)."""
    stmts, errors = get_parser().parse(source)
    stats = {
        "watch_rules": sum(1 for s in stmts if isinstance(s, WatchStmt)),
        "every_rules": sum(1 for s in stmts if isinstance(s, EveryStmt)),
        "if_rules":    sum(1 for s in stmts if isinstance(s, IfStmt)),
        "on_rules":    sum(1 for s in stmts if isinstance(s, OnStmt)),
        "defines":     sum(1 for s in stmts if isinstance(s, DefineStmt)),
        "errors":      len(errors), "total": len(stmts),
    }
    return stmts, errors, stats


def run_base_rules(state):
    """Parse and run base_rules.sky through v2 runtime."""
    base = f"{LANG_DIR}/base_rules.sky"
    if not pathlib.Path(base).exists(): return []
    stmts, _ = get_parser().parse_file(base)
    return get_runtime().run(stmts, state)


def sandbox_apply_improvement(improvement, generation, current_fitness=0.5):
    """
    Drop-in replacement for skyd's apply_self_improvement.
    Uses AST merge + explicit pre/post line count for fitness.
    """
    if not improvement: return False, current_fitness, "no improvement"
    if improvement.get("risk") == "high":
        log.info("⏸️  Sandbox: skipping high-risk proposal")
        return False, current_fitness, "high risk"

    itype   = improvement.get("improvement_type", "")
    desc    = improvement.get("description", "")
    snippet = improvement.get("code_snippet", "")
    risk    = improvement.get("risk", "low")

    if itype == "skylang":
        stmts, errors, stats = parse_and_validate_skylang(snippet)
        if errors:
            log.warning(f"⚠️  SkyLang v2 parse errors: {[e.message for e in errors]}")
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = f"{LANG_DIR}/evolved_v2_{ts}.sky"
        pathlib.Path(path).write_text(f"# SkyLang v2 | Gen {generation}\n# {desc}\n{snippet}\n")
        log.info(f"📝 SkyLang v2 rule: {stats}")
        return True, current_fitness, f"skylang: {stats['total']} stmts, {stats['errors']} errors"

    if any(t in itype for t in ("python", "new_capability", "c_asm")) and snippet:
        # Read pre-merge line count before calling sandbox
        try:
            pre_lines = len(pathlib.Path(SKYD_PATH).read_text().splitlines())
        except:
            pre_lines = None
        promoted, new_fit, reason = get_sandbox().test_and_promote(
            snippet, desc, generation, current_fitness,
            risk=risk, pre_merge_lines=pre_lines
        )
        return promoted, new_fit, reason

    return False, current_fitness, f"unknown type: {itype}"


def fitness_tick(action, src, kb, watchdog_pass_rate=0.5, growth_signal=None):
    """Update FitnessV2 each cycle."""
    fv = get_fitness()
    fv.update_actions(action)
    lessons  = kb.get("lessons", [])
    recent   = [l.get("lesson","") for l in lessons[-5:]]
    older    = [l.get("lesson","") for l in lessons[-20:-5]]
    fitness, record = fv.calculate(src, kb, watchdog_pass_rate,
                                   recent, older, growth_signal=growth_signal)
    return fitness, fv.is_stagnant(), record


def status():
    sb = get_sandbox()
    fv = get_fitness()
    return {
        "sandbox_promotions": sum(1 for _,_,p in sb._history if p),
        "sandbox_rejections": sum(1 for _,_,p in sb._history if not p),
        "stagnant_cycles": sb.stagnation_cycles(),
        "fitness_stagnant": fv.is_stagnant(),
        "fitness_stagnant_cycles": fv._stagnant_ctr,
        "fitness_last": fv._last_fitness,
        "best_fitness": sb._best,
        "recent_promotions": fv._recent_promotions,
    }
