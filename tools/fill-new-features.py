"""
Fill new corpus fields for programs already in the corpus, running up to
BATCH_SIZE programs in parallel.

Specify which features to fill with --features (default: all).  Multiple
identity.* paths collapse to a single reconsider-node identity call.

Usage (from repo root, with venv active or full path to peer-atlas):
    python3 tools/fill-new-features.py
    python3 tools/fill-new-features.py --features identity.cip_code identity.first_degree_granted_year
    python3 tools/fill-new-features.py --features historical
    python3 tools/fill-new-features.py --features identity.cip_code --batch-size 1
    python3 tools/fill-new-features.py berkeley_mdes --features historical
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

IDENTITY_INSTRUCTION = (
    "find the first year this program granted a degree; "
    "assign the best CIP code from the cip_codes list"
)

DEFAULT_BATCH_SIZE = 4
DEFAULT_PEER_ATLAS = "peer-atlas-cli/.venv/bin/peer-atlas"
MAX_RATE_RETRIES   = 5
RATE_BACKOFF_S     = 60   # seconds between rate-limit retries (linear: 60, 120, 180 …)

# All supported feature paths and the CLI step they map to
_FEATURE_STEP_MAP = {
    "identity":                           "identity",
    "identity.institution_name":          "identity",
    "identity.first_degree_granted_year": "identity",
    "identity.cip_code":                  "cip_code",
    "identity.ipeds_unitid":              "identity",
    "historical":                         "historical",
    "freopp_roi":                         "freopp_roi",
}
_ALL_STEPS: tuple[str, ...] = ("identity", "cip_code", "historical", "freopp_roi")


def features_to_steps(features: list[str]) -> tuple[str, ...]:
    """Map a list of feature paths to an ordered, deduplicated list of CLI steps."""
    seen: set[str] = set()
    steps: list[str] = []
    for f in features:
        step = _FEATURE_STEP_MAP.get(f)
        if step is None:
            # Prefix match for identity.*
            if f.startswith("identity."):
                step = "identity"
            elif f.startswith("historical."):
                step = "historical"
            else:
                raise ValueError(f"Unknown feature path: {f!r}. Known: {sorted(_FEATURE_STEP_MAP)}")
        if step not in seen:
            seen.add(step)
            steps.append(step)
    # Preserve canonical order
    return tuple(s for s in _ALL_STEPS if s in seen)

_GRN = "\033[32m"
_RED = "\033[31m"
_YEL = "\033[33m"
_CYN = "\033[36m"
_DIM = "\033[2m"
_BLD = "\033[1m"
_RST = "\033[0m"
_EL  = "\033[2K"

_ANSI_RE = re.compile(r"\033\[[0-9;]*m")

def _fmt_dur(s: float) -> str:
    s = int(s)
    if s < 60:
        return f"{s}s"
    m, s = divmod(s, 60)
    if m < 60:
        return f"{m}m{s:02d}s"
    h, m = divmod(m, 60)
    return f"{h}h{m:02d}m"


def _vis(s: str) -> int:
    """Visible character count (strips ANSI codes)."""
    return len(_ANSI_RE.sub("", s))


def _ljust(s: str, w: int) -> str:
    return s + " " * max(0, w - _vis(s))


# ---------------------------------------------------------------------------
# Per-program state
# ---------------------------------------------------------------------------

class _Prog:
    __slots__ = ("steps", "node_idx", "steps_done", "last_action")

    def __init__(self, steps: tuple[str, ...]) -> None:
        self.steps      = steps
        self.node_idx   = 0
        self.steps_done = 0
        self.last_action = "starting…"

    @property
    def node(self) -> str:
        return self.steps[self.node_idx] if self.node_idx < len(self.steps) else "done"


# ---------------------------------------------------------------------------
# ProgressDisplay
# ---------------------------------------------------------------------------

class ProgressDisplay:
    """
    Draws a main progress bar and a per-program live table that animate in
    place using ANSI cursor-up. Log lines scroll above the live area.

    Cursor discipline:
      _drawn  = number of lines currently occupying the live area on screen.
      _redraw always moves up exactly _drawn lines before repainting.
      log()   moves up _drawn, writes one permanent line, resets _drawn=0,
              then calls _redraw() so the cursor ends up _drawn lines below
              the new permanent line — never overshooting.
    """

    BAR_W       = 24
    RATE_WIN    = 60.0   # seconds for rolling req/min
    MIN_FRAME_S = 0.05   # max ~20 fps for live redraws

    def __init__(self, total: int, steps_per_program: int = 2) -> None:
        self._lock              = threading.Lock()
        self._total             = total
        self._steps_per_program = steps_per_program
        self._completed         = 0
        self._start             = time.monotonic()
        self._step_ts:   deque[float] = deque()
        self._active:    dict[str, _Prog] = {}
        self._drawn      = 0
        self._last_frame = 0.0
        self._is_tty     = sys.stderr.isatty()

    # ── public API ──────────────────────────────────────────────────────────

    def program_start(self, pid: str, steps: tuple[str, ...]) -> None:
        with self._lock:
            self._active[pid] = _Prog(steps)
            self._redraw()

    def step_start(self, pid: str) -> None:
        with self._lock:
            p = self._active.get(pid)
            if p:
                p.steps_done += 1
                p.node_idx   += 1
                p.last_action = "starting…"
            self._redraw()

    def update_last_action(self, pid: str, line: str) -> None:
        with self._lock:
            p = self._active.get(pid)
            if p:
                p.last_action = line.strip()
            self._redraw(throttle=True)

    def program_done(self, pid: str) -> None:
        with self._lock:
            now = time.monotonic()
            self._step_ts.append(now)
            self._trim_window(now)
            self._completed += 1
            self._active.pop(pid, None)
            self._redraw()

    def log(self, msg: str, *, ok: bool | None = True) -> None:
        """Print a permanent timestamped line above the live area."""
        ts     = datetime.now().strftime("%H:%M:%S")
        colour = _GRN if ok is True else (_RED if ok is False else _DIM)
        with self._lock:
            # Move up to top of live area and overwrite first line with log msg.
            self._move_up(self._drawn)
            sys.stderr.write(f"\r{_EL}{_DIM}{ts}{_RST}  {colour}{msg}{_RST}\n")
            # Cursor is now 1 line below where it was; the rest of the old live
            # area is still on screen below. Reset _drawn so _redraw starts fresh.
            self._drawn = 0
            self._redraw()

    def error_block(self, lines: list[str]) -> None:
        """Print a traceback or multi-line error block, preceded by 4 blank lines.
        Lines are printed at full width — no truncation. The live display is
        redrawn below the block so progress continues normally."""
        with self._lock:
            self._move_up(self._drawn)
            self._drawn = 0
            if self._is_tty:
                for _ in range(4):
                    sys.stderr.write(f"\r{_EL}\n")
                for line in lines:
                    sys.stderr.write(f"\r{_EL}{line}\n")
            else:
                sys.stderr.write("\n" * 4)
                for line in lines:
                    sys.stderr.write(line + "\n")
            sys.stderr.flush()
            self._redraw()

    def finish(self) -> None:
        with self._lock:
            self._move_up(self._drawn)
            sys.stderr.write(f"\r{_EL}")
            self._drawn = 0

    # ── private ─────────────────────────────────────────────────────────────

    def _trim_window(self, now: float) -> None:
        cutoff = now - self.RATE_WIN
        while self._step_ts and self._step_ts[0] < cutoff:
            self._step_ts.popleft()

    def _rpm(self) -> float | None:
        n = len(self._step_ts)
        if n < 2:
            return None
        w = self._step_ts[-1] - self._step_ts[0]
        return None if w < 1.0 else (n - 1) / w * 60.0

    def _move_up(self, n: int) -> None:
        if self._is_tty and n > 0:
            sys.stderr.write(f"\033[{n}A")

    def _wline(self, content: str = "") -> None:
        sys.stderr.write(f"\r{_EL}{content}\n")

    def _main_bar(self) -> str:
        filled  = int(self.BAR_W * self._completed / max(self._total, 1))
        bar     = f"[{_GRN}{'█' * filled}{_DIM}{'░' * (self.BAR_W - filled)}{_RST}]"
        elapsed = time.monotonic() - self._start
        rpm     = self._rpm()
        parts   = [bar, f" {_BLD}{_CYN}{self._completed}/{self._total}{_RST}"]
        if self._active:
            parts.append(f"  {_YEL}▶ {len(self._active)} active{_RST}")
        if rpm is not None:
            parts.append(f"  {rpm:.1f} req/min")
            rem = self._total - self._completed
            if rem > 0:
                parts.append(f"  ETA ~{_DIM}{_fmt_dur(rem * self._steps_per_program / (rpm / 60))}{_RST}")
        parts.append(f"  elapsed {_DIM}{_fmt_dur(elapsed)}{_RST}")
        return "".join(parts)

    def _step_bar(self, p: _Prog) -> str:
        n     = len(p.steps)
        bps   = max(1, 4 // n)   # blocks per step, scaled to fill ~4 chars
        done  = p.steps_done * bps
        cur   = 1 if p.node_idx < len(p.steps) else 0
        total = n * bps
        empty = total - done - cur
        return (
            f"[{_GRN}{'█' * done}{_RST}"
            f"{_YEL}{'▓' * cur}{_RST}"
            f"{_DIM}{'░' * empty}{_RST}]"
        )

    def _redraw(self, *, throttle: bool = False) -> None:
        if not self._is_tty:
            return
        now = time.monotonic()
        if throttle and now - self._last_frame < self.MIN_FRAME_S:
            return
        self._last_frame = now

        self._move_up(self._drawn)

        lines: list[str] = [self._main_bar()]

        if self._active:
            W_PID  = 26
            W_NODE = 11
            lines.append("")
            lines.append(
                f"  {_DIM}"
                f"{'Program':<{W_PID}}  {'Step':<{W_NODE}}  {'Progress':<14}  Last action"
                f"{_RST}"
            )
            lines.append(f"  {_DIM}{'─' * 90}{_RST}")
            for pid, p in self._active.items():
                sbar  = self._step_bar(p)
                slbl  = f"{p.steps_done + (1 if p.node_idx < len(p.steps) else 0)}/{len(p.steps)}"
                last  = p.last_action[:54] + "…" if len(p.last_action) > 55 else p.last_action
                prog  = f"{sbar} {_DIM}{slbl}{_RST}"
                lines.append(
                    f"  {_ljust(pid[:W_PID], W_PID)}"
                    f"  {_ljust(_CYN + p.node + _RST, W_NODE + len(_CYN) + len(_RST))}"
                    f"  {_ljust(prog, 14 + 20)}"  # 20 = ANSI overhead in prog
                    f"  {_DIM}{last}{_RST}"
                )

        for line in lines:
            self._wline(line)
        sys.stderr.flush()
        self._drawn = len(lines)


# ---------------------------------------------------------------------------
# Subprocess helpers
# ---------------------------------------------------------------------------

class RateLimitError(Exception):
    """Raised when a subprocess output indicates an HTTP 429 rate-limit response."""
    def __init__(self, full_output: str) -> None:
        super().__init__("LLM provider returned HTTP 429 (rate limited)")
        self.full_output = full_output


def _is_429_line(line: str) -> bool:
    return "429" in line and ("HTTP" in line or "rate" in line.lower() or "returned" in line)


def _run_streaming(
    cmd: list[str], pid: str, display: ProgressDisplay,
) -> tuple[int, str]:
    out: list[str] = []
    with subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    ) as proc:
        assert proc.stdout
        for raw in proc.stdout:
            line = raw.rstrip()
            if line:
                out.append(line)
                display.update_last_action(pid, line)
                if _is_429_line(line):
                    proc.kill()
                    proc.wait()
                    raise RateLimitError("\n".join(out))
        proc.wait()
    return proc.returncode, "\n".join(out)


def _cmd_for_step(peer_atlas: str, pid: str, step: str) -> list[str]:
    if step == "identity":
        return [peer_atlas, "reconsider-node", pid, "identity", IDENTITY_INSTRUCTION]
    if step == "cip_code":
        return [peer_atlas, "classify-cip", pid]
    if step == "historical":
        return [peer_atlas, "research-node", pid, "historical"]
    if step == "freopp_roi":
        return [peer_atlas, "classify-freopp", pid]
    raise ValueError(f"Unknown step: {step!r}")


def process_program(
    pid: str, peer_atlas: str, display: ProgressDisplay, steps: tuple[str, ...],
) -> list[tuple[str, int]]:
    display.program_start(pid, steps)
    results: list[tuple[str, int]] = []

    step_cmds = [(s, _cmd_for_step(peer_atlas, pid, s)) for s in steps]

    for i, (node, cmd) in enumerate(step_cmds):
        if i > 0:
            display.step_start(pid)
        label = f"{pid}/{node}"
        for attempt in range(MAX_RATE_RETRIES + 1):
            t0 = time.monotonic()
            try:
                rc, out = _run_streaming(cmd, pid, display)
                break
            except RateLimitError as e:
                if attempt >= MAX_RATE_RETRIES:
                    raise
                wait = RATE_BACKOFF_S * (attempt + 1)
                display.log(
                    f"{_ljust(label, 44)}  {_YEL}HTTP 429 — retry {attempt + 1}/{MAX_RATE_RETRIES} in {wait}s{_RST}",
                    ok=None,
                )
                time.sleep(wait)
        dur    = time.monotonic() - t0
        ok     = rc == 0
        status = f"{_GRN}OK{_RST}" if ok else f"{_RED}FAILED (exit {rc}){_RST}"
        display.log(f"{_ljust(label, 44)}  {status}  {_DIM}{dur:.1f}s{_RST}", ok=ok)
        if not ok:
            display.error_block(out.splitlines())
        results.append((label, rc))

    display.program_done(pid)
    return results


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("program_ids", nargs="*", metavar="PROGRAM_ID",
                        help="Specific program IDs to process (default: all programs in corpus)")
    parser.add_argument(
        "--features", nargs="+", metavar="FEATURE_PATH",
        help=(
            "Feature paths to fill, e.g. identity.cip_code historical "
            "(default: all features). Multiple identity.* paths collapse to one "
            "reconsider-node identity call."
        ),
    )
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE,
                        help=f"Programs to process in parallel (default: {DEFAULT_BATCH_SIZE})")
    parser.add_argument("--peer-atlas", default=DEFAULT_PEER_ATLAS,
                        help=f"Path to peer-atlas binary (default: {DEFAULT_PEER_ATLAS})")
    args = parser.parse_args()

    repo_root  = Path(__file__).resolve().parent.parent
    pa_path    = Path(args.peer_atlas)
    peer_atlas = str(repo_root / pa_path) if not pa_path.is_absolute() else str(pa_path)

    data = json.loads((repo_root / "corpus" / "programs.json").read_text(encoding="utf-8"))
    corpus_pids = [p["program_id"] for p in data.get("programs", [])
                   if isinstance(p, dict) and p.get("program_id")]

    if args.program_ids:
        unknown = [pid for pid in args.program_ids if pid not in set(corpus_pids)]
        if unknown:
            sys.stderr.write(f"{_RED}Unknown program IDs:{_RST} {', '.join(unknown)}\n")
            sys.exit(1)
        pids = args.program_ids
    else:
        pids = corpus_pids

    try:
        steps = features_to_steps(args.features) if args.features else _ALL_STEPS
    except ValueError as e:
        sys.stderr.write(f"{_RED}Error:{_RST} {e}\n")
        sys.exit(1)

    if not steps:
        sys.stderr.write(f"{_RED}Error:{_RST} No valid steps derived from --features.\n")
        sys.exit(1)

    total = len(pids)

    sys.stderr.write(
        f"{_BLD}{_CYN}fill-new-features{_RST}  "
        f"{total} programs  steps={','.join(steps)}  batch={args.batch_size}  peer-atlas={peer_atlas}\n\n"
    )

    display  = ProgressDisplay(total, steps_per_program=len(steps))
    failures: list[str] = []

    with ThreadPoolExecutor(max_workers=args.batch_size) as executor:
        futures = {
            executor.submit(process_program, pid, peer_atlas, display, steps): pid
            for pid in pids
        }
        for future in as_completed(futures):
            pid = futures[future]
            try:
                for label, rc in future.result():
                    if rc != 0:
                        failures.append(label)
            except RateLimitError as e:
                display.finish()
                sys.stderr.write("\n" * 4)
                sys.stderr.write(f"{_RED}Rate limit (HTTP 429) — stopping.{_RST}\n\n")
                sys.stderr.write(e.full_output + "\n")
                os._exit(1)
            except Exception as e:
                display.log(f"{pid} — unexpected error: {e}", ok=False)
                failures.append(pid)

    display.finish()
    sys.stderr.write("\n")
    if failures:
        sys.stderr.write(f"{_RED}FAILED{_RST} ({len(failures)}): {', '.join(failures)}\n")
        sys.exit(1)
    else:
        sys.stderr.write(f"{_GRN}Done.{_RST} All {total} programs processed successfully.\n")


if __name__ == "__main__":
    main()
