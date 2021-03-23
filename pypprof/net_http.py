"""Handle pprof endpoint requests a la Go's net/http/pprof.

The following endpoints are implemented:
    - /debug/pprof: List the available profiles.
    - /debug/pprof/profile: Collect a CPU profile.
    - /debug/pprof/wall: Collect a wall-clock profile.
    - /debug/pprof/heap: Get snapshot of current heap profile.
    - /debug/pprof/cmdline: The running program's command line.
    - /debug/pprof/thread: Currently running threads.
"""
from __future__ import print_function

import gc
import pkg_resources
import sys
import threading
import time
import traceback

try:
    import mprofile

    has_mprofile = True
except ImportError:
    has_mprofile = False

from zprofile.cpu_profiler import CPUProfiler
from zprofile.wall_profiler import WallProfiler
from pypprof.builder import Builder
from pypprof import thread_profiler


_wall_profiler = WallProfiler()


def start_pprof():
    # WallProfiler's registers a Python signal handler, which must be done
    # on the main thread. So do it now before spawning the background thread.
    # As a result, starting the pprof server has the side effect of registering the
    # wall-clock profiler's SIGALRM handler, which may conflict with other uses.
    _wall_profiler.register_handler()


def index() -> str:
    """/debug/pprof"""
    template = pkg_resources.resource_string(__name__, "index.html").decode("utf-8")
    body = template.format(num_threads=threading.active_count())
    return body.encode("utf-8")


def profile(self, duration_secs: int = 30) -> bytes:
    """/debug/pprof/profile"""
    cpu_profiler = CPUProfiler()
    pprof = cpu_profiler.profile(duration_secs)
    return pprof


def wall(self, duration_secs: int = 30) -> bytes:
    """/debug/pprof/wall"""
    pprof = _wall_profiler.profile(duration_secs)
    return pprof


def heap(self, run_gc: bool = False) -> bytes:
    """/debug/pprof/heap"""
    if run_gc:
        gc.collect()
    if not has_mprofile:
        return self.send_error(
            412, "mprofile must be installed to enable heap profiling"
        )
    if not mprofile.is_tracing():
        return self.send_error(412, "Heap profiling is not enabled")
    snap = mprofile.take_snapshot()
    pprof = build_heap_pprof(snap)
    return pprof


def thread(self, debug: bool = False) -> bytes:
    """/debug/pprof/thread"""
    pprof = thread_profiler.take_snapshot()
    return pprof


def cmdline(self) -> str:
    """/debug/pprof/cmdline"""
    body = "\0".join(sys.argv)
    return body.encode("utf-8")


def build_heap_pprof(snap):
    profile_builder = Builder()
    samples = {}  # trace => (count, measurement)
    for stat in snap.statistics("traceback"):
        trace = tuple(
            (frame.name, frame.filename, frame.firstlineno, frame.lineno)
            for frame in stat.traceback
        )
        try:
            samples[trace][0] += stat.count
            samples[trace][1] += stat.size
        except KeyError:
            samples[trace] = (stat.count, stat.size)
    profile_builder.populate_profile(samples, "HEAP", "bytes", snap.sample_rate, 1)
    return profile_builder.emit()
