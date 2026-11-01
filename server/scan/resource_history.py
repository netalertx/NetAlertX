"""
resource_history.py - tick-scoped resource sampling and persistence.

Called from __main__.py at the top and bottom of the schedule-tick block, so
its window covers run_plugin_scripts("schedule")/process_scan() together -
the two calls that actually cost CPU/IO each cycle. Pure, stateless psutil
reads - safe to call from a fresh Process() each time, no shared state with
health_endpoint.py's live /health gauge at all (see health_endpoint.py).
"""

import psutil

from logger import mylog
from utils.datetime_utils import timeNowUTC


def get_process_cpu_times_and_io():
    """
    (user+system+children CPU seconds, read_bytes, write_bytes) for the current
    process, as of right now - stateless cumulative reads, meant to be called
    twice (before/after a tick) and diffed by the caller, not used as a
    standalone live value. Includes children_user/children_system so a
    scanning plugin's own subprocess CPU time (reaped into the parent's
    cpu_times() by the kernel) is captured - io_counters() has no equivalent
    children field, so IO here only ever reflects NetAlertX's own direct I/O,
    never a plugin subprocess's.

    CPU and IO are sampled independently, each falling back to zeros on
    psutil.Error/AttributeError, so sampling never breaks the scan tick. A
    non-dumpable process (e.g. python3 carrying file capabilities) can't read
    /proc/self/io, so IO may be zero while CPU, read from /proc/self/stat,
    stays accurate.
    """
    cpu_time_s = 0.0
    read_bytes = 0
    write_bytes = 0

    try:
        p = psutil.Process()
        t = p.cpu_times()
        cpu_time_s = t.user + t.system + t.children_user + t.children_system
    except (psutil.Error, AttributeError) as e:
        mylog("verbose", [f"[resource_history] CPU sampling failed, using zero: {e!r}"])

    try:
        io = psutil.Process().io_counters()
        read_bytes = io.read_bytes
        write_bytes = io.write_bytes
    except (psutil.Error, AttributeError) as e:
        mylog("verbose", [f"[resource_history] IO sampling failed, using zeros: {e!r}"])

    return cpu_time_s, read_bytes, write_bytes


def insert_resource_history(db, pre, post, duration_ms, tick_failed=False):
    """
    Insert one Resource_History row from before/after tick-scoped samples.

    Args:
        db: open DB instance (db.sql.execute()).
        pre: get_process_cpu_times_and_io() result taken before the tick.
        post: get_process_cpu_times_and_io() result taken after the tick.
        duration_ms: wall-clock duration of the bracketed tick, in milliseconds.
        tick_failed: True if the tick raised and this row was written from the
            `finally` clause - lets a later viewer distinguish a truncated,
            crash-adjacent sample from an ordinary short tick.

    A history-write failure (locked DB, schema drift after a bad migration)
    must never take down the real scan tick's own commit - log and move on.
    """
    cpu_time_delta_s = post[0] - pre[0]

    if duration_ms <= 0:
        # Guard the actual edge case only - not an arbitrary "under Nms treat
        # as zero" cutoff, which would also zero out a genuinely fast-but-real
        # tick's true cost.
        resCpuPercent = 0.0
    else:
        resCpuPercent = (cpu_time_delta_s / (duration_ms / 1000)) * 100

    resIoReadBytes = post[1] - pre[1]
    resIoWriteBytes = post[2] - pre[2]

    # Sampled independently of the INSERT's own try/except below - a psutil
    # failure here must zero this one field, not get misreported as an
    # "insert failed" and skip the whole row (CPU/IO were already computed
    # successfully at this point).
    try:
        resRssMb = round(psutil.Process().memory_info().rss / (1024 * 1024), 2)
    except (psutil.Error, AttributeError) as e:
        mylog("verbose", [f"[resource_history] RSS sampling failed, using 0.0: {e}"])
        resRssMb = 0.0

    try:
        db.sql.execute(
            """
            INSERT INTO Resource_History
                (resDateTime, resCpuPercent, resRssMb, resIoReadBytes,
                 resIoWriteBytes, resScanDurationMs, resTickFailed)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                timeNowUTC(),
                resCpuPercent,
                resRssMb,
                resIoReadBytes,
                resIoWriteBytes,
                duration_ms,
                int(tick_failed),
            ),
        )
    except Exception as e:
        mylog("verbose", [f"[resource_history] insert failed, skipping this cycle: {e}"])
