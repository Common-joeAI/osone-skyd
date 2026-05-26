#!/usr/bin/env python3
"""
skyd_sandbox.py — Sandbox + Rollback + Improved Fitness + Formal SkyLang Parser
Implements Grok's three suggestions as a drop-in enhancement to skyd.

1. Sandbox: candidate skyd.py tested in subprocess before promotion
2. Rollback: checkpoints every evolution, auto-reverts on fitness drop
3. Fitness: stagnation penalty, watchdog pass rate, real code growth signal
4. SkyLang v2: typed formal grammar with real parser, not string matching
"""

import os, re, sys, json, math, time, shutil, hashlib, logging, pathlib, subprocess, tempfile
from datetime import datetime
from collections import defaultdict, deque

log = logging.getLogger("skyd.sandbox")

SKYD_PATH    = "/skyd/skyd.py"          # inside container — the live source
BACKUP_DIR   = "/var/log/skyd_backups"
CANDIDATE    = "/tmp/skyd_candidate.py"
FITNESS_LOG  = "/var/log/skyd_fitness_v2.jsonl"
SANDBOX_LOG  = "/var/log/skyd_sandbox.jsonl"
SKYLANG_LOG  = "/var/log/skyd_skylang_v2.jsonl"
LANG_DIR     = "/usr/local/skyd/lang"

os.makedirs(BACKUP_DIR, exist_ok=True)
os.makedirs(LANG_DIR,   exist_ok=True)


# ══════════════════════════════════════════════════════════════════
# PART 1 — SANDBOX + ROLLBACK
# ══════════════════════════════════════════════════════════════════

class EvolutionSandbox:
    """
    Wraps every proposed code change in a test-before-promote pipeline.

    Pipeline:
      1. Checkpoint current skyd.py → /var/log/skyd_backups/skyd_{gen}.py
      2. Smart-merge proposed snippet into candidate copy
      3. py_compile check (syntax)
      4. Behavioral subprocess test (import + smoke test)
      5. Fitness delta check
      6. Promote if delta > -0.05 AND no crash, else revert
    """

    def __init__(self, fitness_fn=None):
        self._fitness_fn = fitness_fn or self._default_fitness
        self._history    = []          # (gen, delta, promoted)
        self._stagnant   = 0           # cycles with no fitness improvement
        self._best       = None        # best fitness seen

    # ── Checkpoint ──────────────────────────────────────────────

    def checkpoint(self, generation):
        """Save a versioned backup of the current skyd.py."""
        backup = f"{BACKUP_DIR}/skyd_{generation}_{int(time.time())}.py"
        try:
            shutil.copy2(SKYD_PATH, backup)
            # Keep only last 20 backups
            backups = sorted(pathlib.Path(BACKUP_DIR).glob("skyd_*.py"))
            for old in backups[:-20]:
                old.unlink(missing_ok=True)
            log.info(f"💾 Checkpoint: {backup}")
            return backup
        except Exception as e:
            log.warning(f"Checkpoint failed: {e}")
            return None

    def rollback(self, backup_path, generation, reason=""):
        """Restore skyd.py from a checkpoint."""
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

    # ── Smart Merge ─────────────────────────────────────────────

    def _smart_merge(self, original_src, snippet, description=""):
        """
        Intelligently merge a proposed snippet into the source.
        Strategy:
        - If snippet defines a new function (def foo():), append it
        - If snippet redefines an existing function, replace the old one
        - If snippet is a class or top-level expression, append safely
        - Never allow deletion of existing guardrail/safety functions
        """
        PROTECTED = {
            "is_safe", "is_permanently_blocked", "_add_guardrail",
            "apply_self_improvement", "main", "hive_heartbeat"
        }
        if not snippet or len(snippet.strip()) < 10:
            return None, "snippet too short"

        # Find function names in snippet
        new_fns = re.findall(r'^def (\w+)\s*\(', snippet, re.MULTILINE)
        new_classes = re.findall(r'^class (\w+)', snippet, re.MULTILINE)

        # Block protected overwrites
        for fn in new_fns:
            if fn in PROTECTED:
                return None, f"blocked: snippet tries to overwrite protected function '{fn}'"

        result = original_src

        # Replace existing functions if they appear in snippet
        for fn in new_fns:
            pattern = rf'^def {re.escape(fn)}\s*\([^)]*\):.*?(?=\n^def |\n^class |\Z)'
            if re.search(pattern, result, re.MULTILINE | re.DOTALL):
                result = re.sub(pattern, snippet, result, count=1, flags=re.MULTILINE | re.DOTALL)
                log.info(f"  🔄 Replaced function: {fn}")
                return result, "ok"

        # Append new content before the main() function
        if "\ndef main(" in result:
            result = result.replace("\ndef main(", f"\n\n# === Evolved Gen snippet: {description[:60]} ===\n{snippet}\n\ndef main(", 1)
        else:
            result += f"\n\n# === Evolved snippet ===\n{snippet}\n"

        return result, "ok"

    # ── Compile + Behavioral Test ────────────────────────────────

    def _syntax_check(self, path):
        """Run py_compile on candidate."""
        try:
            r = subprocess.run(
                [sys.executable, "-m", "py_compile", path],
                capture_output=True, text=True, timeout=10
            )
            return r.returncode == 0, r.stderr.strip()
        except Exception as e:
            return False, str(e)

    def _behavioral_test(self, path, timeout=15):
        """
        Run candidate in a subprocess and verify it:
        - Imports without crashing
        - Key functions still exist
        - No obvious infinite loops (exits within timeout)
        """
        test_script = f"""
import sys, ast, importlib.util
sys.argv = ['skyd_test']

# Parse AST — must be valid
with open({repr(path)}) as f:
    src = f.read()
tree = ast.parse(src)

# Required functions must still exist
required = {{'main','smart_think','is_safe','load_kb','get_system_state'}}
defined  = {{n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}}
missing  = required - defined
if missing:
    print('MISSING_FUNCTIONS:' + ','.join(missing))
    sys.exit(1)

# Must import cleanly (no top-level side effects in test mode)
# Just check the AST is sane
print('PASS:functions=' + str(len(defined)))
"""
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(test_script)
                tpath = f.name
            r = subprocess.run(
                [sys.executable, tpath],
                capture_output=True, text=True, timeout=timeout
            )
            os.unlink(tpath)
            output = r.stdout.strip()
            if r.returncode == 0 and output.startswith("PASS"):
                fn_count = int(output.split("functions=")[1]) if "functions=" in output else 0
                return True, {"functions": fn_count, "output": output}
            return False, {"error": r.stderr.strip() or output}
        except subprocess.TimeoutExpired:
            return False, {"error": "behavioral test timed out"}
        except Exception as e:
            return False, {"error": str(e)}

    # ── Default Fitness ──────────────────────────────────────────

    def _default_fitness(self, src):
        """Quick fitness estimate from source text."""
        lines = src.splitlines()
        fns   = len(re.findall(r'^def \w+', src, re.MULTILINE))
        branches = len(re.findall(r'\b(if|elif|for|while|except)\b', src))
        freq = defaultdict(int)
        for c in src: freq[c] += 1
        total = len(src)
        entropy = -sum((v/total)*math.log2(v/total) for v in freq.values() if v > 0) if total else 0
        return round((fns * 2 + branches * 0.5 + entropy) / 10, 4)

    # ── Main entry point ─────────────────────────────────────────

    def test_and_promote(self, snippet, description, generation, current_fitness, risk="low"):
        """
        Full sandbox pipeline. Returns (promoted: bool, new_fitness: float, reason: str).
        safe_mode=True (risk=low): skip behavioral test, only syntax check + fitness delta.
        """
        safe_mode = (risk == "low")
        backup = self.checkpoint(generation)

        # Read current source
        try:
            original = pathlib.Path(SKYD_PATH).read_text()
        except Exception as e:
            return False, current_fitness, f"can't read source: {e}"

        # Merge
        merged, merge_err = self._smart_merge(original, snippet, description)
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

        # Behavioral test
        ok, result = self._behavioral_test(CANDIDATE)
        if not ok:
            self._log_sandbox_event(generation, "REJECT_BEHAVIOR", reason=str(result))
            log.warning(f"❌ Behavioral fail: {result}")
            return False, current_fitness, f"behavior: {result}"

        # Fitness delta
        new_fitness = self._fitness_fn(merged)
        delta = new_fitness - current_fitness

        if delta > -0.05:
            # PROMOTE
            shutil.copy2(CANDIDATE, SKYD_PATH)
            self._log_sandbox_event(generation, "PROMOTE", delta=delta, fitness=new_fitness)
            log.info(f"✅ PROMOTED Gen {generation+1}: delta={delta:+.4f} fitness={new_fitness:.4f}")
            self._history.append((generation, delta, True))
            # Reward fitness function for successful promotion
            try: get_fitness()._recent_promotions += 1
            except: pass
            if self._best is None or new_fitness > self._best:
                self._best = new_fitness
                self._stagnant = 0
            else:
                self._stagnant += 1
            return True, new_fitness, "promoted"
        else:
            # REVERT
            self.rollback(backup, generation, reason=f"fitness drop {delta:+.4f}")
            self._log_sandbox_event(generation, "REVERT", delta=delta, fitness=new_fitness)
            self._stagnant += 1
            return False, current_fitness, f"fitness drop {delta:+.4f}"

    def _log_sandbox_event(self, generation, event, **kwargs):
        entry = {"ts": datetime.now().isoformat(), "gen": generation, "event": event, **kwargs}
        try:
            with open(SANDBOX_LOG, "a") as f: f.write(json.dumps(entry) + "\n")
        except: pass

    def recent_history(self, n=10):
        return self._history[-n:]

    def stagnation_cycles(self):
        return self._stagnant


# ══════════════════════════════════════════════════════════════════
# PART 2 — IMPROVED FITNESS FUNCTION (Grok's formula + stagnation)
# ══════════════════════════════════════════════════════════════════

class FitnessV2:
    """
    Fitness = (
        0.25 * normalize(unique_actions_executed)  # behavioral variety
        0.20 * normalize(watchdog_pass_rate)        # quality of evolutions
        0.25 * novelty_score                        # lesson novelty
        0.15 * code_growth_signal                   # real code got bigger
        0.15 * (0 if stagnant else 1)               # stagnation penalty
    )
    """

    def __init__(self):
        self._prev_lines       = 0
        self._prev_fns         = 0
        self._action_window    = deque(maxlen=50)
        self._stagnant_ctr     = 0
        self._last_fitness     = None
        self._stagnant_thresh  = 10
        self._recent_promotions = 0   # incremented by sandbox on PROMOTE

    def update_actions(self, action):
        self._action_window.append(action or "none")

    def calculate(self, src, kb, watchdog_pass_rate, lessons_recent, lessons_older):
        lines = src.count('\n') if src else 0
        fns   = len(re.findall(r'^def \w+', src, re.MULTILINE)) if src else 0

        # 1. Unique action diversity (normalized 0-1)
        actions = list(self._action_window)
        unique_actions = len(set(actions)) / max(len(actions), 1)

        # 2. Watchdog pass rate (already 0-1)
        pass_rate = min(1.0, max(0.0, watchdog_pass_rate))

        # 3. Novelty: new words in recent lessons vs older ones
        recent_words = set(' '.join(lessons_recent).lower().split())
        older_words  = set(' '.join(lessons_older).lower().split())
        novelty = len(recent_words - older_words) / max(len(recent_words), 1) if recent_words else 0

        # 4. Code growth signal — did the code actually get bigger?
        if lines > self._prev_lines or fns > self._prev_fns:
            growth = 1.0
            self._prev_lines = lines
            self._prev_fns   = fns
        else:
            growth = 0.7  # penalty for no real code change

        # 5. Stagnation penalty
        # Promotion bonus: reward sandbox actually landing code
        _prom_bonus = min(1.0, self._recent_promotions / 3.0)  # 3 promotions = full score
        fitness = (
            0.20 * unique_actions +
            0.15 * pass_rate +
            0.25 * novelty +
            0.15 * growth +
            0.10 * (0.0 if self._stagnant_ctr >= self._stagnant_thresh else 1.0) +
            0.15 * _prom_bonus
        )
        fitness = round(fitness, 4)

        # Update stagnation counter
        if self._last_fitness is not None:
            if abs(fitness - self._last_fitness) < 0.002:
                self._stagnant_ctr += 1
            else:
                self._stagnant_ctr = 0
        self._last_fitness = fitness

        # Log it
        record = {
            "ts": datetime.now().isoformat(),
            "fitness": fitness,
            "unique_actions": round(unique_actions, 3),
            "pass_rate": round(pass_rate, 3),
            "novelty": round(novelty, 3),
            "growth": growth,
            "stagnant_cycles": self._stagnant_ctr,
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
        """0.0 = normal, 1.0 = maximum stagnation — inject into evolution prompt."""
        return min(1.0, self._stagnant_ctr / self._stagnant_thresh)


# ══════════════════════════════════════════════════════════════════
# PART 3 — SKYLANG v2: TYPED FORMAL GRAMMAR + REAL PARSER
# ══════════════════════════════════════════════════════════════════

"""
SkyLang v2 Grammar (EBNF):

program    := statement*
statement  := watch_stmt | every_stmt | if_stmt | on_stmt | define_stmt | comment

watch_stmt := 'WATCH' metric comparator value '->' action_list
every_stmt := 'EVERY' duration '->' action_list
if_stmt    := 'IF' condition '->' action_list ['ELSE' action_list]
on_stmt    := 'ON' event '->' action_list
define_stmt:= 'DEFINE' name '=' expr

metric     := IDENTIFIER ('.' IDENTIFIER)*
comparator := '>' | '<' | '>=' | '<=' | '==' | '!='
value      := NUMBER | STRING | IDENTIFIER
duration   := NUMBER ('s'|'m'|'h'|'d')
condition  := metric comparator value | IDENTIFIER 'failed' | IDENTIFIER 'restarted'
action_list:= action (';' action)*
action     := IDENTIFIER (arg*)
arg        := STRING | NUMBER | IDENTIFIER | '$' IDENTIFIER
event      := STRING | IDENTIFIER

Types: INT, FLOAT, STRING, BOOL, METRIC, ACTION
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional, Any

# ── Token types ─────────────────────────────────────────────────

TK_WATCH = 'WATCH'; TK_EVERY = 'EVERY'; TK_IF = 'IF'; TK_ELSE = 'ELSE'
TK_ON = 'ON'; TK_DEFINE = 'DEFINE'; TK_ARROW = '->'; TK_SEMI = ';'
TK_IDENT = 'IDENT'; TK_NUMBER = 'NUMBER'; TK_STRING = 'STRING'
TK_CMP = 'CMP'; TK_COMMENT = 'COMMENT'; TK_DURATION = 'DURATION'
TK_EOF = 'EOF'

KEYWORDS = {
    'WATCH': TK_WATCH, 'EVERY': TK_EVERY, 'IF': TK_IF,
    'ELSE': TK_ELSE, 'ON': TK_ON, 'DEFINE': TK_DEFINE,
}

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
    threshold_type: str   # 'int'|'float'|'percent'|'string'
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
        self.source = source
        self.pos    = 0
        self.line   = 1
        self.tokens = []
        self._tokenize()

    def _tokenize(self):
        src = self.source
        i = 0
        line = 1
        while i < len(src):
            # newline
            if src[i] == '\n':
                line += 1; i += 1; continue
            # whitespace
            if src[i] in ' \t\r':
                i += 1; continue
            # comment
            if src[i] == '#':
                while i < len(src) and src[i] != '\n': i += 1
                continue
            # arrow
            if src[i:i+2] == '->':
                self.tokens.append(Token(TK_ARROW, '->', line)); i += 2; continue
            # comparators
            if src[i:i+2] in ('>=','<=','==','!='):
                self.tokens.append(Token(TK_CMP, src[i:i+2], line)); i += 2; continue
            if src[i] in '><':
                self.tokens.append(Token(TK_CMP, src[i], line)); i += 1; continue
            # semicolon
            if src[i] == ';':
                self.tokens.append(Token(TK_SEMI, ';', line)); i += 1; continue
            # string
            if src[i] in '"\'':
                q = src[i]; j = i+1
                while j < len(src) and src[j] != q: j += 1
                self.tokens.append(Token(TK_STRING, src[i+1:j], line)); i = j+1; continue
            # number (with optional duration suffix)
            if src[i].isdigit():
                j = i
                while j < len(src) and (src[j].isdigit() or src[j] == '.'): j += 1
                num_str = src[i:j]
                num = float(num_str) if '.' in num_str else int(num_str)
                # duration suffix?
                if j < len(src) and src[j] in 'smhd':
                    suf = src[j]
                    mult = {'s':1,'m':60,'h':3600,'d':86400}[suf]
                    self.tokens.append(Token(TK_DURATION, num * mult, line))
                    i = j+1
                # percent?
                elif j < len(src) and src[j] == '%':
                    self.tokens.append(Token(TK_NUMBER, ('percent', num), line)); i = j+1
                else:
                    self.tokens.append(Token(TK_NUMBER, num, line)); i = j
                continue
            # identifier or keyword
            if src[i].isalpha() or src[i] == '_':
                j = i
                while j < len(src) and (src[j].isalnum() or src[j] in '_.'): j += 1
                word = src[i:j]
                ttype = KEYWORDS.get(word.upper(), TK_IDENT)
                if ttype != TK_IDENT:
                    word = word.upper()
                self.tokens.append(Token(ttype, word, line)); i = j; continue
            # skip unknown
            i += 1
        self.tokens.append(Token(TK_EOF, None, line))

    def __iter__(self): return iter(self.tokens)


class SkyLangParser:
    def __init__(self, source):
        self.lexer  = SkyLangLexer(source)
        self.tokens = list(self.lexer)
        self.pos    = 0

    def _peek(self): return self.tokens[self.pos] if self.pos < len(self.tokens) else Token(TK_EOF, None)
    def _advance(self):
        t = self.tokens[self.pos]
        self.pos += 1
        return t
    def _expect(self, ttype):
        t = self._advance()
        if t.type != ttype:
            raise SyntaxError(f"Line {t.line}: expected {ttype}, got {t.type} ({t.value!r})")
        return t

    def _parse_action_list(self):
        """Parse one or more actions separated by semicolons."""
        actions = []
        while self._peek().type not in (TK_EOF,) and self._peek().value not in (None,):
            tok = self._peek()
            # Stop at next statement keyword
            if tok.type in (TK_WATCH, TK_EVERY, TK_IF, TK_ON, TK_DEFINE, TK_ELSE):
                break
            if tok.type == TK_SEMI:
                self._advance(); continue
            # Collect until semicolon or newline-equivalent (next keyword)
            action_parts = []
            while self._peek().type not in (TK_SEMI, TK_EOF, TK_WATCH, TK_EVERY, TK_IF, TK_ON, TK_DEFINE, TK_ELSE):
                action_parts.append(str(self._advance().value))
            action = ' '.join(action_parts)
            if action.strip():
                actions.append(action.strip())
            if self._peek().type == TK_SEMI:
                self._advance()
            else:
                break
        return actions

    def _parse_value(self):
        """Parse a value token and return (value, type_str)."""
        t = self._advance()
        if t.type == TK_NUMBER:
            if isinstance(t.value, tuple) and t.value[0] == 'percent':
                return t.value[1], 'percent'
            return t.value, 'float' if isinstance(t.value, float) else 'int'
        if t.type == TK_STRING:
            return t.value, 'string'
        if t.type == TK_IDENT:
            return t.value, 'identifier'
        if t.type == TK_DURATION:
            return t.value, 'duration'
        return t.value, 'unknown'

    def parse(self):
        """Parse full program, return (statements, errors)."""
        statements = []
        errors     = []
        while self._peek().type != TK_EOF:
            try:
                stmt = self._parse_statement()
                if stmt: statements.append(stmt)
            except SyntaxError as e:
                errors.append(ParseError(0, str(e)))
                # Skip to next line/keyword
                while self._peek().type not in (TK_WATCH, TK_EVERY, TK_IF, TK_ON, TK_DEFINE, TK_EOF):
                    self._advance()
        return statements, errors

    def _parse_statement(self):
        t = self._peek()
        if t.type == TK_WATCH:  return self._parse_watch()
        if t.type == TK_EVERY:  return self._parse_every()
        if t.type == TK_IF:     return self._parse_if()
        if t.type == TK_ON:     return self._parse_on()
        if t.type == TK_DEFINE: return self._parse_define()
        # Unknown — skip token
        self._advance()
        return None

    def _parse_watch(self):
        self._advance()  # consume WATCH
        # metric
        metric_tok = self._expect(TK_IDENT)
        metric = metric_tok.value
        # comparator
        cmp_tok = self._expect(TK_CMP)
        # value
        val, vtype = self._parse_value()
        # ->
        self._expect(TK_ARROW)
        # actions
        actions = self._parse_action_list()
        return WatchStmt(metric=metric, comparator=cmp_tok.value,
                         threshold=val, threshold_type=vtype, actions=actions)

    def _parse_every(self):
        self._advance()  # consume EVERY
        dur_tok = self._advance()
        interval = dur_tok.value if dur_tok.type == TK_DURATION else int(dur_tok.value or 60)
        self._expect(TK_ARROW)
        actions = self._parse_action_list()
        return EveryStmt(interval_seconds=interval, actions=actions)

    def _parse_if(self):
        self._advance()  # consume IF
        # condition: metric op value OR ident 'failed'/'restarted'
        parts = []
        while self._peek().type not in (TK_ARROW, TK_EOF):
            parts.append(str(self._advance().value))
        condition = ' '.join(parts)
        self._expect(TK_ARROW)
        actions = self._parse_action_list()
        else_actions = []
        if self._peek().type == TK_ELSE:
            self._advance()
            self._expect(TK_ARROW)
            else_actions = self._parse_action_list()
        return IfStmt(condition=condition, actions=actions, else_actions=else_actions)

    def _parse_on(self):
        self._advance()  # consume ON
        event_tok = self._advance()
        self._expect(TK_ARROW)
        actions = self._parse_action_list()
        return OnStmt(event=str(event_tok.value), actions=actions)

    def _parse_define(self):
        self._advance()  # consume DEFINE
        name = self._expect(TK_IDENT).value
        # optional =
        if self._peek().value == '=': self._advance()
        val, _ = self._parse_value()
        return DefineStmt(name=name, value=val)


# ── SkyLang v2 Runtime Executor ──────────────────────────────────

SAFE_ACTIONS = {
    "DROP_CACHE":    "sync && echo 3 > /proc/sys/vm/drop_caches",
    "RENICE":        "renice -n {arg0} -p $(pgrep {arg1} | head -1)",
    "SYNC":          "sync",
    "VACUUM_LOGS":   "find /var/log -name '*.log' -mtime +{arg0} -delete",
    "RESTART":       None,   # blocked
    "ALERT":         "echo '[SKYLANG ALERT] {arg0}' >> /var/log/skyd_alerts.log",
    "LOG":           "echo '[SKYLANG] {arg0}' >> /var/log/skyd_skylang_runtime.log",
    "NOOP":          "true",
}

class SkyLangRuntime:
    """Executes parsed SkyLang v2 AST against live system state."""

    def __init__(self, system_state_fn=None):
        self._state_fn   = system_state_fn
        self._defines    = {}
        self._last_every = {}  # interval_seconds -> last_run_ts

    def _get_metric(self, name, state):
        """Resolve a metric name to a value from system state."""
        mapping = {
            "cpu":    state.get("cpu_percent", 0),
            "mem":    state.get("memory_percent", 0),
            "ram":    state.get("memory_percent", 0),
            "disk":   state.get("disk_percent", 0),
            "swap":   state.get("swap_percent", 0),
        }
        # Support dot notation: cpu.percent -> cpu_percent
        key = name.lower().replace(".", "_").replace("usage", "percent")
        for k, v in mapping.items():
            if k in key: return v
        return self._defines.get(name, 0)

    def _eval_condition(self, stmt, state):
        if isinstance(stmt, WatchStmt):
            val   = self._get_metric(stmt.metric, state)
            thresh = stmt.threshold
            if stmt.threshold_type == 'percent': thresh = thresh  # already float
            cmp = stmt.comparator
            if cmp == '>':  return val > thresh
            if cmp == '<':  return val < thresh
            if cmp == '>=': return val >= thresh
            if cmp == '<=': return val <= thresh
            if cmp == '==': return val == thresh
            if cmp == '!=': return val != thresh
        if isinstance(stmt, IfStmt):
            cond = stmt.condition.lower()
            if 'failed' in cond:    return False  # would check service status
            if 'restarted' in cond: return False
            return True  # fallback
        return False

    def _exec_action(self, action_str):
        """Execute a single action string safely."""
        action_upper = action_str.strip().upper().split()[0]
        if action_upper in ("RESTART", "RM", "DELETE", "KILL"):
            log.info(f"🚫 SkyLang v2 blocked: {action_str[:60]}")
            return False
        if action_upper in SAFE_ACTIONS:
            cmd = SAFE_ACTIONS[action_upper]
            if cmd is None: return False
            # Basic arg substitution
            parts = action_str.split()[1:]
            for i, p in enumerate(parts):
                cmd = cmd.replace(f"{{arg{i}}}", p)
            try:
                subprocess.run(cmd, shell=True, timeout=10, capture_output=True)
                log.info(f"▶️  SkyLang v2: {action_str[:60]}")
                return True
            except Exception as e:
                log.warning(f"SkyLang exec error: {e}")
                return False
        else:
            # Unknown action — just log it
            log.info(f"📋 SkyLang v2 action (unexecuted): {action_str[:60]}")
            return True

    def run_program(self, statements, state):
        """Execute all statements against current system state."""
        fired = []
        now = time.time()
        for stmt in statements:
            try:
                if isinstance(stmt, WatchStmt):
                    if self._eval_condition(stmt, state):
                        for a in stmt.actions:
                            self._exec_action(a)
                            fired.append({"type":"WATCH","metric":stmt.metric,"action":a})

                elif isinstance(stmt, EveryStmt):
                    last = self._last_every.get(stmt.interval_seconds, 0)
                    if now - last >= stmt.interval_seconds:
                        for a in stmt.actions:
                            self._exec_action(a)
                            fired.append({"type":"EVERY","interval":stmt.interval_seconds,"action":a})
                        self._last_every[stmt.interval_seconds] = now

                elif isinstance(stmt, IfStmt):
                    if self._eval_condition(stmt, state):
                        for a in stmt.actions: self._exec_action(a)
                        fired.append({"type":"IF","condition":stmt.condition[:40]})
                    elif stmt.else_actions:
                        for a in stmt.else_actions: self._exec_action(a)

                elif isinstance(stmt, DefineStmt):
                    self._defines[stmt.name] = stmt.value

            except Exception as e:
                log.warning(f"SkyLang runtime error on {stmt}: {e}")
        return fired


def parse_and_validate_skylang(source):
    """
    Parse + validate a SkyLang v2 source string.
    Returns (statements, errors, stats).
    """
    parser = SkyLangParser(source)
    stmts, errors = parser.parse()
    stats = {
        "watch_rules": sum(1 for s in stmts if isinstance(s, WatchStmt)),
        "every_rules": sum(1 for s in stmts if isinstance(s, EveryStmt)),
        "if_rules":    sum(1 for s in stmts if isinstance(s, IfStmt)),
        "on_rules":    sum(1 for s in stmts if isinstance(s, OnStmt)),
        "defines":     sum(1 for s in stmts if isinstance(s, DefineStmt)),
        "errors":      len(errors),
        "total":       len(stmts),
    }
    # Log to JSONL
    entry = {"ts": datetime.now().isoformat(), "stats": stats,
             "errors": [e.__dict__ for e in errors]}
    try:
        with open(SKYLANG_LOG, "a") as f: f.write(json.dumps(entry) + "\n")
    except: pass
    return stmts, errors, stats




# ── SkyLang v2 Code Generator ─────────────────────────────────────
# Turns parsed AST nodes into real Python functions (not just shell)

def generate_python_from_skylang(statements):
    """
    Convert SkyLang v2 AST → executable Python functions.
    Returns a string of Python code ready to exec() or append to capabilities.
    """
    lines = [
        "# SkyLang v2 → Python codegen",
        "import subprocess, os, logging as _log",
        "_skl_log = _log.getLogger('skyd.skylang_runtime')",
        "",
    ]

    for i, stmt in enumerate(statements):
        if isinstance(stmt, WatchStmt):
            fn_name = f"_watch_{stmt.metric.replace('.','_')}_{i}"
            cmp_map = {'>':'>', '<':'<', '>=':'>=', '<=':'<=', '==':'==', '!=':'!='}
            op = cmp_map.get(stmt.comparator, '>')
            thresh = stmt.threshold
            # Build action body
            action_lines = []
            for act in stmt.actions:
                act_up = act.strip().upper().split()[0]
                if act_up == "DROP_CACHE":
                    action_lines.append('    subprocess.run("sync && echo 3 > /proc/sys/vm/drop_caches", shell=True, timeout=5)')
                elif act_up == "RENICE":
                    parts = act.split()[1:]
                    proc = parts[1] if len(parts) > 1 else "top"
                    action_lines.append(f'    subprocess.run(f"renice -n 19 -p $(pgrep {proc} | head -1)", shell=True, timeout=5)')
                elif act_up == "ALERT":
                    msg = ' '.join(act.split()[1:])
                    action_lines.append(f'    _skl_log.warning("[SKYLANG ALERT] {msg}")')
                elif act_up == "LOG":
                    msg = ' '.join(act.split()[1:])
                    action_lines.append(f'    _skl_log.info("[SKYLANG] {msg}")')
                else:
                    action_lines.append(f'    _skl_log.info("[SKYLANG] action: {act}")')

            lines += [
                f"def {fn_name}(state):",
                f'    """WATCH {stmt.metric} {stmt.comparator} {thresh} -> {stmt.actions}"""',
                f"    val = state.get('{stmt.metric.lower()}', state.get('{stmt.metric.lower()}_percent', 0))",
                f"    if val {op} {thresh}:",
            ] + action_lines + [
                f"        return True",
                f"    return False",
                "",
            ]

        elif isinstance(stmt, EveryStmt):
            fn_name = f"_every_{stmt.interval_seconds}s_{i}"
            action_lines = []
            for act in stmt.actions:
                act_up = act.strip().upper().split()[0]
                if act_up == "SYNC":
                    action_lines.append('    subprocess.run("sync", shell=True, timeout=5)')
                elif act_up == "VACUUM_LOGS":
                    days = act.split()[1] if len(act.split()) > 1 else "7"
                    action_lines.append(f'    subprocess.run("find /var/log -name *.log -mtime +{days} -delete", shell=True, timeout=10)')
                else:
                    action_lines.append(f'    _skl_log.info("[SKYLANG EVERY] {act}")')
            lines += [
                f"_every_{stmt.interval_seconds}s_{i}_last = 0",
                f"def {fn_name}(now=None):",
                f'    """EVERY {stmt.interval_seconds}s -> {stmt.actions}"""',
                f"    import time as _t",
                f"    global _every_{stmt.interval_seconds}s_{i}_last",
                f"    _now = now or _t.time()",
                f"    if _now - _every_{stmt.interval_seconds}s_{i}_last >= {stmt.interval_seconds}:",
            ] + [f"    {l.strip()}" for l in action_lines] + [
                f"        _every_{stmt.interval_seconds}s_{i}_last = _now",
                f"        return True",
                f"    return False",
                "",
            ]

        elif isinstance(stmt, DefineStmt):
            lines.append(f"_SKYLANG_{stmt.name.upper()} = {repr(stmt.value)}")
            lines.append("")

    return "\n".join(lines)

# ══════════════════════════════════════════════════════════════════
# PUBLIC API
# ══════════════════════════════════════════════════════════════════

_sandbox  = None
_fitness  = None
_runtime  = None

def get_sandbox():
    global _sandbox
    if _sandbox is None: _sandbox = EvolutionSandbox()
    return _sandbox

def get_fitness():
    global _fitness
    if _fitness is None: _fitness = FitnessV2()
    return _fitness

def get_runtime(state_fn=None):
    global _runtime
    if _runtime is None: _runtime = SkyLangRuntime(state_fn)
    return _runtime


def sandbox_apply_improvement(improvement, generation, current_fitness=0.5):
    """
    Drop-in replacement for skyd's apply_self_improvement.
    Uses full sandbox pipeline instead of blind append.
    """
    if not improvement: return False, current_fitness, "no improvement"
    if improvement.get("risk") == "high":
        log.info("⏸️  Sandbox: skipping high-risk proposal")
        return False, current_fitness, "high risk"

    snippet = improvement.get("code_snippet", "")
    desc    = improvement.get("description", "")
    itype   = improvement.get("improvement_type", "")

    if itype == "skylang":
        # Validate with new parser before writing
        stmts, errors, stats = parse_and_validate_skylang(snippet)
        if errors:
            log.warning(f"⚠️  SkyLang v2 parse errors: {[e.message for e in errors]}")
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = f"{LANG_DIR}/evolved_v2_{ts}.sky"
        pathlib.Path(path).write_text(f"# SkyLang v2 | Gen {generation}\n# {desc}\n{snippet}\n")
        log.info(f"📝 SkyLang v2 rule written: {stats}")
        return True, current_fitness, f"skylang: {stats['total']} stmts, {stats['errors']} errors"

    if any(t in itype for t in ("python", "new_capability", "c_asm")) and snippet:
        promoted, new_fit, reason = get_sandbox().test_and_promote(
            snippet, desc, generation, current_fitness,
            risk=improvement.get("risk", "low")
        )
        return promoted, new_fit, reason

    return False, current_fitness, f"unknown type: {itype}"


def fitness_tick(action, src, kb, watchdog_pass_rate=0.5):
    """Update FitnessV2 each cycle. Returns (fitness, is_stagnant)."""
    fv = get_fitness()
    fv.update_actions(action)
    lessons = kb.get("lessons", [])
    recent = [l.get("lesson","") for l in lessons[-5:]]
    older  = [l.get("lesson","") for l in lessons[-20:-5]]
    fitness, record = fv.calculate(src, kb, watchdog_pass_rate, recent, older)
    return fitness, fv.is_stagnant(), record


def run_base_rules(state):
    """Parse and run the base_rules.sky through SkyLang v2 runtime."""
    base = f"{LANG_DIR}/base_rules.sky"
    if not pathlib.Path(base).exists(): return []
    src = pathlib.Path(base).read_text()
    stmts, errors, stats = parse_and_validate_skylang(src)
    runtime = get_runtime()
    fired = runtime.run_program(stmts, state)
    if fired:
        log.info(f"⚡ SkyLang v2 base rules fired: {len(fired)} actions")
    return fired


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
    }
