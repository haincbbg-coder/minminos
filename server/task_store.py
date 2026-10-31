"""Durable SQLite store for the autonomous Javis task queue.

The queue is runtime state, so SQLite lives in JAVIS_STATE_DIR instead of inside a
brain that may be synchronized by Git. A JSON snapshot is still exported by
``tasks.py`` for portability and backwards compatibility with older Javis builds.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
import unicodedata
import re
import uuid
from pathlib import Path
from typing import Any, Iterable, Optional


VALID_STATUS = {
    "triage", "todo", "ready", "running", "review", "blocked", "done",
    "cancelled", "archived",
}
# Sổ hỏi đáp của một việc (`metadata.qa`, cổng từ Javis 0.235.0): giữ ngần này lượt gần nhất, mỗi
# câu tối đa QA_TEXT_MAX ký tự, phần "đã làm tới đâu" tối đa QA_PROGRESS_MAX. Đủ cho lần chạy sau
# hiểu chuyện, không đủ để phình kho hay prompt.
QA_KEEP = 8
QA_TEXT_MAX = 1000
QA_PROGRESS_MAX = 1500
TERMINAL_STATUS = {"done", "cancelled", "archived"}
# Điều kiện SQL "bước cha CHƯA cho qua" (alias cha = p). Bước thường qua khi done/archived như cũ.
# GATE chỉ qua khi chủ THẬT SỰ duyệt (`metadata.gate.duyet = 1`, do approve_gate ghi): nút cũ
# "Xoá khỏi bảng"/"Xoá tất cả" đẩy GATE sang archived, và nếu archived cũng tính là qua thì một
# cú dọn bảng lặng lẽ mở khoá bước chi tiền phía sau.
DEP_UNMET_SQL = (
    "(p.id IS NULL OR p.status NOT IN ('done','archived') OR "
    "(p.capability='gate' AND COALESCE(json_extract(p.metadata_json,'$.gate.duyet'),0) <> 1))"
)
ACTIVE_STATUS = {"triage", "todo", "ready", "running", "review", "blocked"}


def now() -> float:
    return time.time()


def norm_title(text: str) -> str:
    value = unicodedata.normalize("NFD", (text or "").lower())
    value = "".join(c for c in value if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", value)).strip()


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _loads(value: Any, fallback: Any) -> Any:
    try:
        parsed = json.loads(value or "")
        return parsed
    except Exception:
        return fallback


# Khoá metadata của bước job (Đội AI) phải sống qua mọi lần ghi đè: `prepared` và `_finish`
# ghi CẢ cột metadata bằng thứ worker trả về, nên không giữ lại là thứ tự bước và ghi chú
# "Chủ yêu cầu sửa" biến mất ngay lần chạy đầu tiên.
JOB_META_KEYS = ("job_step", "gate", "sua")


def _giu_meta_job(cu: Any, moi: Optional[dict]) -> dict:
    out = dict(moi or {})
    old = _loads(cu, {}) if not isinstance(cu, dict) else cu
    if isinstance(old, dict):
        for k in JOB_META_KEYS:
            if k in old and k not in out:
                out[k] = old[k]
    return out


class TaskStore:
    """Small transactional task database.

    All mutations use ``BEGIN IMMEDIATE`` and compare-and-set status transitions.
    This makes claiming safe even when the API and dispatcher race.
    """

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._db = sqlite3.connect(str(self.path), check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA synchronous=NORMAL")
        self._db.execute("PRAGMA busy_timeout=5000")
        self._schema()

    def close(self) -> None:
        with self._lock:
            self._db.close()

    def _schema(self) -> None:
        with self._lock:
            self._db.executescript(
                """
                CREATE TABLE IF NOT EXISTS boards (
                    brain_root TEXT PRIMARY KEY,
                    orchestration TEXT NOT NULL DEFAULT 'off',
                    paused_reason TEXT NOT NULL DEFAULT '',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    brain_root TEXT NOT NULL,
                    title TEXT NOT NULL,
                    normalized_title TEXT NOT NULL,
                    intent TEXT NOT NULL DEFAULT '',
                    route TEXT NOT NULL DEFAULT 'auto',
                    capability TEXT NOT NULL DEFAULT 'auto',
                    execution_mode TEXT NOT NULL DEFAULT 'auto',
                    priority INTEGER NOT NULL DEFAULT 2,
                    status TEXT NOT NULL DEFAULT 'triage',
                    needs_approval INTEGER NOT NULL DEFAULT 0,
                    block_kind TEXT NOT NULL DEFAULT '',
                    block_reason TEXT NOT NULL DEFAULT '',
                    created_by TEXT NOT NULL DEFAULT 'user',
                    chat_id TEXT NOT NULL DEFAULT '',
                    idempotency_key TEXT NOT NULL DEFAULT '',
                    attempts INTEGER NOT NULL DEFAULT 0,
                    max_attempts INTEGER NOT NULL DEFAULT 3,
                    claimed_by TEXT NOT NULL DEFAULT '',
                    claim_expires_at REAL NOT NULL DEFAULT 0,
                    not_before REAL NOT NULL DEFAULT 0,
                    last_heartbeat_at REAL NOT NULL DEFAULT 0,
                    current_run_id TEXT NOT NULL DEFAULT '',
                    result TEXT NOT NULL DEFAULT '',
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    artifacts_json TEXT NOT NULL DEFAULT '[]',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_tasks_board_status
                    ON tasks(brain_root, status, priority, created_at);
                CREATE INDEX IF NOT EXISTS idx_tasks_claim
                    ON tasks(status, claim_expires_at);
                CREATE UNIQUE INDEX IF NOT EXISTS idx_tasks_idempotency
                    ON tasks(brain_root, idempotency_key)
                    WHERE idempotency_key <> '';

                CREATE TABLE IF NOT EXISTS task_dependencies (
                    task_id TEXT NOT NULL,
                    depends_on_id TEXT NOT NULL,
                    PRIMARY KEY(task_id, depends_on_id)
                );

                CREATE TABLE IF NOT EXISTS task_runs (
                    id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    brain_root TEXT NOT NULL,
                    worker_id TEXT NOT NULL,
                    engine_provider TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL,
                    started_at REAL NOT NULL,
                    heartbeat_at REAL NOT NULL,
                    finished_at REAL NOT NULL DEFAULT 0,
                    error TEXT NOT NULL DEFAULT '',
                    result TEXT NOT NULL DEFAULT '',
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                );

                CREATE INDEX IF NOT EXISTS idx_runs_task
                    ON task_runs(task_id, started_at DESC);

                CREATE TABLE IF NOT EXISTS task_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    run_id TEXT NOT NULL DEFAULT '',
                    event_type TEXT NOT NULL,
                    message TEXT NOT NULL DEFAULT '',
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at REAL NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_events_task
                    ON task_events(task_id, created_at DESC);

                CREATE TABLE IF NOT EXISTS task_migrations (
                    migration_key TEXT PRIMARY KEY,
                    migrated_at REAL NOT NULL
                );
                """
            )
            # Cột thêm sau khi kho đã có trên máy người dùng. `not_before` (0.59.44): việc vấp
            # "gói thuê bao hết lượt" được hoãn tới mốc reset; dispatcher bỏ qua việc chưa tới
            # giờ thay vì nhặt lại sau 5 giây rồi đốt hết lượt thử trước khi hạn mức mở lại.
            cot = {r["name"] for r in self._db.execute("PRAGMA table_info(tasks)").fetchall()}
            if "not_before" not in cot:
                self._db.execute(
                    "ALTER TABLE tasks ADD COLUMN not_before REAL NOT NULL DEFAULT 0"
                )
            # `job_id` (26.10, Đội AI có GATE): việc thuộc một chuỗi bước của một đội. NULL với
            # mọi việc cũ, nên việc lẻ chạy y như trước.
            if "job_id" not in cot:
                self._db.execute("ALTER TABLE tasks ADD COLUMN job_id TEXT")
            self._db.executescript(
                """
                CREATE INDEX IF NOT EXISTS idx_tasks_job ON tasks(job_id);

                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    brain_root TEXT NOT NULL,
                    title TEXT NOT NULL,
                    doi TEXT NOT NULL DEFAULT 'khac',
                    status TEXT NOT NULL DEFAULT 'dang_chay',
                    chat_id TEXT NOT NULL DEFAULT '',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                );

                CREATE INDEX IF NOT EXISTS idx_jobs_board
                    ON jobs(brain_root, created_at DESC);

                -- 26.10.312: gợi ý "việc này bố giao tay hoài" mà bố đã bấm bỏ qua, theo từng brain.
                CREATE TABLE IF NOT EXISTS goi_y_lap_bo_qua (
                    brain_root TEXT NOT NULL,
                    hint_key TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    PRIMARY KEY(brain_root, hint_key)
                );
                """
            )
            self._db.commit()

    def _tx(self) -> None:
        self._db.execute("BEGIN IMMEDIATE")

    def ensure_board(self, brain_root: str, orchestration: str = "off") -> None:
        ts = now()
        with self._lock:
            self._db.execute(
                """INSERT OR IGNORE INTO boards
                   (brain_root, orchestration, created_at, updated_at)
                   VALUES (?, ?, ?, ?)""",
                (brain_root, orchestration, ts, ts),
            )
            self._db.commit()

    def set_orchestration(self, brain_root: str, mode: str) -> None:
        self.ensure_board(brain_root)
        with self._lock:
            self._db.execute(
                "UPDATE boards SET orchestration=?, updated_at=? WHERE brain_root=?",
                (mode, now(), brain_root),
            )
            self._db.commit()

    def board_mode(self, brain_root: str) -> str:
        self.ensure_board(brain_root)
        with self._lock:
            row = self._db.execute(
                "SELECT orchestration FROM boards WHERE brain_root=?", (brain_root,)
            ).fetchone()
        return str(row["orchestration"] if row else "off")

    def board_roots(self) -> list[str]:
        with self._lock:
            rows = self._db.execute(
                "SELECT brain_root FROM boards ORDER BY brain_root"
            ).fetchall()
        return [str(r["brain_root"]) for r in rows]

    def _event(
        self,
        task_id: str,
        event_type: str,
        message: str = "",
        run_id: str = "",
        metadata: Optional[dict] = None,
    ) -> None:
        self._db.execute(
            """INSERT INTO task_events
               (task_id, run_id, event_type, message, metadata_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (task_id, run_id, event_type, message, _json(metadata or {}), now()),
        )

    def enqueue(
        self,
        brain_root: str,
        title: str,
        intent: str,
        route: str = "auto",
        priority: int = 2,
        deps: Optional[Iterable[str]] = None,
        needs_approval: bool = False,
        created_by: str = "user",
        chat_id: str = "",
        capability: str = "auto",
        execution_mode: str = "auto",
        idempotency_key: str = "",
        status: str = "triage",
        max_attempts: int = 3,
        task_id: str = "",
        job_id: str = "",
        metadata: Optional[dict] = None,
        dedup_title: bool = True,
    ) -> str:
        """`job_id`/`metadata`/`dedup_title` dành cho bước của một job (Đội AI): bước job mang
        tiêu đề như "Viết content" rất dễ trùng một việc lẻ đang mở, mà gộp vào việc lẻ đó là
        nối nhầm chuỗi bước. Mặc định giữ nguyên hành vi cũ."""
        root = str(brain_root)
        self.ensure_board(root)
        title = (title or intent or "Task")[:160]
        normalized = norm_title(title)
        ts = now()
        with self._lock:
            self._tx()
            try:
                if idempotency_key:
                    row = self._db.execute(
                        """SELECT id FROM tasks
                           WHERE brain_root=? AND idempotency_key=? LIMIT 1""",
                        (root, idempotency_key),
                    ).fetchone()
                    if row:
                        self._db.commit()
                        return str(row["id"])
                if normalized and dedup_title:
                    row = self._db.execute(
                        f"""SELECT id FROM tasks
                            WHERE brain_root=? AND normalized_title=?
                              AND status IN ({','.join('?' for _ in ACTIVE_STATUS)})
                            ORDER BY created_at LIMIT 1""",
                        (root, normalized, *sorted(ACTIVE_STATUS)),
                    ).fetchone()
                    if row:
                        self._db.commit()
                        return str(row["id"])

                tid = task_id or ("t_" + uuid.uuid4().hex[:12])
                safe_status = status if status in VALID_STATUS else "triage"
                self._db.execute(
                    """INSERT INTO tasks (
                        id, brain_root, title, normalized_title, intent, route,
                        capability, execution_mode, priority, status, needs_approval,
                        created_by, chat_id, idempotency_key, max_attempts,
                        created_at, updated_at, job_id, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        tid, root, title, normalized, intent or title, route or "auto",
                        capability or "auto", execution_mode or "auto",
                        max(1, min(3, int(priority or 2))), safe_status,
                        int(bool(needs_approval)), created_by or "user", str(chat_id or ""),
                        idempotency_key or "", max(1, int(max_attempts or 3)), ts, ts,
                        (str(job_id) if job_id else None), _json(metadata or {}),
                    ),
                )
                for dep in dict.fromkeys(str(d) for d in (deps or []) if str(d)):
                    self._db.execute(
                        """INSERT OR IGNORE INTO task_dependencies(task_id, depends_on_id)
                           VALUES (?, ?)""",
                        (tid, dep),
                    )
                self._event(tid, "created", f"created by {created_by or 'user'}")
                self._db.commit()
                return tid
            except Exception:
                self._db.rollback()
                raise

    def _task_from_row(self, row: sqlite3.Row) -> dict:
        task = dict(row)
        task["needs_approval"] = bool(task.get("needs_approval"))
        task["metadata"] = _loads(task.pop("metadata_json", "{}"), {})
        task["artifacts"] = _loads(task.pop("artifacts_json", "[]"), [])
        with self._lock:
            deps = self._db.execute(
                "SELECT depends_on_id FROM task_dependencies WHERE task_id=? ORDER BY depends_on_id",
                (task["id"],),
            ).fetchall()
        task["deps"] = [str(d["depends_on_id"]) for d in deps]
        return task

    def get_task(self, task_id: str) -> Optional[dict]:
        with self._lock:
            row = self._db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        return self._task_from_row(row) if row else None

    def list_tasks(
        self,
        brain_root: str,
        include_archived: bool = False,
        limit: int = 500,
    ) -> list[dict]:
        sql = "SELECT * FROM tasks WHERE brain_root=?"
        args: list[Any] = [brain_root]
        if not include_archived:
            sql += " AND status <> 'archived'"
        sql += " ORDER BY priority, created_at LIMIT ?"
        args.append(max(1, min(5000, int(limit))))
        with self._lock:
            rows = self._db.execute(sql, args).fetchall()
        return [self._task_from_row(r) for r in rows]

    def list_events(self, task_id: str, limit: int = 100) -> list[dict]:
        with self._lock:
            rows = self._db.execute(
                """SELECT * FROM task_events WHERE task_id=?
                   ORDER BY id DESC LIMIT ?""",
                (task_id, max(1, min(500, int(limit)))),
            ).fetchall()
        out = []
        for row in reversed(rows):
            value = dict(row)
            value["metadata"] = _loads(value.pop("metadata_json", "{}"), {})
            out.append(value)
        return out

    def list_events_bulk(self, task_ids: list[str], limit: int = 20) -> dict[str, list[dict]]:
        """{task_id: [event, ...]} cho NHIỀU task trong một truy vấn thay vì N+1.

        _snapshot của Kanban trước đây lấy list_tasks(limit=5000) rồi gọi list_events cho
        TỪNG task - đúng khuôn N+1, chi phí tăng tuyến tính theo số việc trên bảng, mà nó
        chạy sau mỗi lần giao việc, mỗi lần worker xong và mỗi nhịp dọn dẹp.

        Cắt theo lô 500 id: SQLite bản mới cho tới 32.766 tham số nhưng bản cũ chỉ 999,
        mà kho này chạy trên cả máy người dùng lẫn image Docker nên đừng đoán.
        Thứ tự trong mỗi task giữ nguyên như list_events: cũ -> mới.
        """
        out: dict[str, list[dict]] = {tid: [] for tid in task_ids}
        if not task_ids:
            return out
        lim = max(1, min(500, int(limit)))
        with self._lock:
            for i in range(0, len(task_ids), 500):
                lo = task_ids[i:i + 500]
                marks = ",".join("?" * len(lo))
                rows = self._db.execute(
                    f"""SELECT * FROM (
                            SELECT *, ROW_NUMBER() OVER (PARTITION BY task_id ORDER BY id DESC) AS _rn
                            FROM task_events WHERE task_id IN ({marks})
                        ) WHERE _rn <= ?
                        ORDER BY task_id, id ASC""",
                    (*lo, lim),
                ).fetchall()
                for row in rows:
                    value = dict(row)
                    value.pop("_rn", None)
                    value["metadata"] = _loads(value.pop("metadata_json", "{}"), {})
                    out.setdefault(value["task_id"], []).append(value)
        return out

    def list_runs(self, task_id: str, limit: int = 20) -> list[dict]:
        with self._lock:
            rows = self._db.execute(
                """SELECT * FROM task_runs WHERE task_id=?
                   ORDER BY started_at DESC LIMIT ?""",
                (task_id, max(1, min(100, int(limit)))),
            ).fetchall()
        out = []
        for row in rows:
            value = dict(row)
            value["metadata"] = _loads(value.pop("metadata_json", "{}"), {})
            out.append(value)
        return out

    def promote_dependencies(self, brain_root: str) -> int:
        """Move dependency-waiting tasks to ready when every parent is terminal-successful."""
        with self._lock:
            self._tx()
            try:
                ids = [
                    str(r["id"])
                    for r in self._db.execute(
                        """
                        SELECT t.id
                        FROM tasks t
                        WHERE t.brain_root=? AND t.status='todo'
                          AND t.capability <> 'gate'
                          AND EXISTS (
                              SELECT 1 FROM task_dependencies d WHERE d.task_id=t.id
                          )
                          AND NOT EXISTS (
                              SELECT 1
                              FROM task_dependencies d
                              LEFT JOIN tasks p ON p.id=d.depends_on_id
                              WHERE d.task_id=t.id
                                AND """ + DEP_UNMET_SQL + """
                          )
                        """,
                        (brain_root,),
                    ).fetchall()
                ]
                ts = now()
                for tid in ids:
                    self._db.execute(
                        "UPDATE tasks SET status='ready', updated_at=? WHERE id=? AND status='todo'",
                        (ts, tid),
                    )
                    self._event(tid, "dependency_ready", "all dependencies completed")
                self._db.commit()
                return len(ids)
            except Exception:
                self._db.rollback()
                raise

    def reclaim_stale(self, brain_root: str, active_worker_ids: set[str]) -> int:
        ts = now()
        with self._lock:
            self._tx()
            try:
                rows = self._db.execute(
                    """SELECT id, claimed_by, current_run_id FROM tasks
                       WHERE brain_root=? AND status='running'
                         AND claim_expires_at > 0 AND claim_expires_at < ?""",
                    (brain_root, ts),
                ).fetchall()
                reclaimed = 0
                for row in rows:
                    if str(row["claimed_by"]) in active_worker_ids:
                        continue
                    tid = str(row["id"])
                    run_id = str(row["current_run_id"] or "")
                    self._db.execute(
                        """UPDATE tasks SET status='ready', claimed_by='',
                           claim_expires_at=0, current_run_id='', updated_at=?
                           WHERE id=? AND status='running'""",
                        (ts, tid),
                    )
                    if run_id:
                        self._db.execute(
                            """UPDATE task_runs SET status='stale', finished_at=?,
                               error='worker heartbeat expired'
                               WHERE id=? AND status='running'""",
                            (ts, run_id),
                        )
                    self._event(tid, "reclaimed", "worker heartbeat expired", run_id)
                    reclaimed += 1
                self._db.commit()
                return reclaimed
            except Exception:
                self._db.rollback()
                raise

    def archive_old_terminal(self, brain_root: str, age_days: float = 3.0) -> int:
        """Tự dọn bảng: task đã kết thúc (done/cancelled) quá age_days thì chuyển archived.

        Việc một-lần xong rồi không nằm mãi trên bảng Việc; archived chỉ bị ẨN
        (list_tasks mặc định lọc ra), lịch sử vẫn tra được với include_archived=True.
        Chạy trong housekeep mỗi vòng dispatch nên phải idempotent và rẻ."""
        ts = now()
        cutoff = ts - age_days * 86400
        with self._lock:
            self._tx()
            try:
                rows = self._db.execute(
                    """SELECT id, status FROM tasks
                       WHERE brain_root=? AND status IN ('done','cancelled')
                         AND updated_at < ?""",
                    (brain_root, cutoff),
                ).fetchall()
                for row in rows:
                    tid = str(row["id"])
                    self._db.execute(
                        "UPDATE tasks SET status='archived', updated_at=? WHERE id=?",
                        (ts, tid),
                    )
                    self._event(
                        tid, "auto_archive",
                        f"{row['status']} -> archived: đã kết thúc quá {age_days:g} ngày",
                    )
                self._db.commit()
                return len(rows)
            except Exception:
                self._db.rollback()
                raise

    # Chỉ những trạng thái đã KẾT THÚC mới được xoá. Whitelist cứng để một lời gọi sai
    # tham số không thể quét mất việc đang chờ hay đang chạy.
    _PURGEABLE = ("archived", "cancelled", "done")

    def purge_terminal(
        self, brain_root: str, statuses: tuple = ("archived", "cancelled")
    ) -> int:
        """XOÁ HẲN task đã kết thúc khỏi kho (kèm event/run/dependency). Trả số đã xoá.

        Khác archive_old_terminal (chỉ ẩn khỏi bảng, vẫn tra được): đây là dọn thật, dùng
        khi bảng đầy việc rác không còn giá trị tra cứu. Mặc định giữ 'done' vì đó là lịch
        sử việc Javis làm được; muốn dọn cả thì truyền statuses vào."""
        allowed = tuple(s for s in statuses if s in self._PURGEABLE)
        if not allowed:
            return 0
        marks = ",".join("?" for _ in allowed)
        with self._lock:
            self._tx()
            try:
                rows = self._db.execute(
                    f"SELECT id FROM tasks WHERE brain_root=? AND status IN ({marks})",
                    (brain_root, *allowed),
                ).fetchall()
                ids = [str(r["id"]) for r in rows]
                for tid in ids:
                    self._db.execute("DELETE FROM task_events WHERE task_id=?", (tid,))
                    self._db.execute("DELETE FROM task_runs WHERE task_id=?", (tid,))
                    self._db.execute(
                        "DELETE FROM task_dependencies WHERE task_id=? OR depends_on_id=?",
                        (tid, tid),
                    )
                    self._db.execute("DELETE FROM tasks WHERE id=?", (tid,))
                self._db.commit()
                return len(ids)
            except Exception:
                self._db.rollback()
                raise

    def clear_board(self, brain_root: str) -> int:
        """XOÁ TRẮNG bảng: mọi việc của brain này, TRỪ việc đang có worker cầm.

        Khác purge_terminal (chỉ đụng việc đã kết thúc): đây là lệnh dứt khoát của chủ khi
        cả bảng không còn giá trị. Giữ lại 'running' vì xoá task trong lúc worker còn chạy
        sẽ để lại worker mồ côi ghi vào một task không còn tồn tại."""
        with self._lock:
            self._tx()
            try:
                rows = self._db.execute(
                    "SELECT id FROM tasks WHERE brain_root=? AND status<>'running'",
                    (brain_root,),
                ).fetchall()
                ids = [str(r["id"]) for r in rows]
                for tid in ids:
                    self._db.execute("DELETE FROM task_events WHERE task_id=?", (tid,))
                    self._db.execute("DELETE FROM task_runs WHERE task_id=?", (tid,))
                    self._db.execute(
                        "DELETE FROM task_dependencies WHERE task_id=? OR depends_on_id=?",
                        (tid, tid),
                    )
                    self._db.execute("DELETE FROM tasks WHERE id=?", (tid,))
                self._db.commit()
                return len(ids)
            except Exception:
                self._db.rollback()
                raise

    def archive_by_status(self, brain_root: str, statuses: tuple) -> int:
        """Đẩy MỌI việc đang ở các trạng thái này sang `archived`. Trả số việc đã dọn.

        Dùng cho nút "Xoá tất cả" của bảng Cần bạn xử lý. Cố ý ARCHIVE chứ không xoá hẳn -
        giống hệt nút "Xoá khỏi bảng" của từng dòng, nên hai lối cùng một hậu quả và việc vẫn
        tra lại được. Việc đang chạy KHÔNG bị đụng: xoá task trong lúc worker còn cầm là để
        lại một worker mồ côi ghi vào bản ghi không còn tồn tại.
        """
        allowed = tuple(s for s in statuses if s in VALID_STATUS and s != "running")
        if not allowed:
            return 0
        marks = ",".join("?" for _ in allowed)
        with self._lock:
            self._tx()
            try:
                rows = self._db.execute(
                    f"SELECT id FROM tasks WHERE brain_root=? AND status IN ({marks})",
                    (brain_root, *allowed),
                ).fetchall()
                ids = [str(r["id"]) for r in rows]
                ts = now()
                for tid in ids:
                    self._db.execute(
                        """UPDATE tasks SET status='archived', block_kind='', block_reason='',
                           claimed_by='', claim_expires_at=0, current_run_id='', updated_at=?
                           WHERE id=?""",
                        (ts, tid),
                    )
                    self._event(tid, "operator_move", "-> archived: xoá tất cả")
                self._db.commit()
                return len(ids)
            except Exception:
                self._db.rollback()
                raise

    def grant_full(self, task_id: str, reason: str = "operator grant") -> bool:
        """Chủ CẤP QUYỀN toàn quyền cho một việc rồi đưa nó chạy lại. Trả False nếu không được.

        Đây là nửa còn thiếu của thiết kế cũ. Specifier được dặn thẳng trong prompt là gặp việc
        cần thao tác ra ngoài thì "để kernel chặn và xin quyền" - nhưng chưa từng có đường nào
        để XIN, nên việc nằm mãi ở cột Cần bạn xử lý với một câu tiếng máy, còn nút Thử lại thì
        chạy lại đúng nhánh chặn ấy rồi chặn lại y hệt.

        Ghi một sự kiện riêng (`operator_grant`) chứ không dùng chung `operator_move`: đây là
        lần một con người mở khoá cho việc tự thao tác thật ra ngoài, thứ không hoàn tác được,
        nên nó phải đọc ra được trong nhật ký vòng đời.
        """
        with self._lock:
            self._tx()
            try:
                row = self._db.execute(
                    "SELECT status FROM tasks WHERE id=?", (task_id,)
                ).fetchone()
                if not row or row["status"] == "running":
                    self._db.rollback()
                    return False
                self._db.execute(
                    """UPDATE tasks SET status='ready', execution_mode='full',
                       block_kind='', block_reason='', attempts=0,
                       claimed_by='', claim_expires_at=0, current_run_id='', updated_at=?
                       WHERE id=?""",
                    (now(), task_id),
                )
                self._event(task_id, "operator_grant",
                            f"{row['status']} -> ready, mức quyền = full: {reason}")
                self._db.commit()
                return True
            except Exception:
                self._db.rollback()
                raise

    def next_candidate(self, brain_root: str) -> Optional[dict]:
        with self._lock:
            # `not_before`: việc đang đợi gói thuê bao mở lại hạn mức chưa tới giờ thì
            # không phải ứng viên, dù status vẫn là ready.
            row = self._db.execute(
                """SELECT * FROM tasks
                   WHERE brain_root=? AND status IN ('triage','ready')
                     AND not_before <= ? AND capability <> 'gate'
                   ORDER BY CASE status WHEN 'triage' THEN 0 ELSE 1 END,
                            priority, created_at
                   LIMIT 1""",
                (brain_root, now()),
            ).fetchone()
        return self._task_from_row(row) if row else None

    def claim(
        self,
        task_id: str,
        worker_id: str,
        lease_seconds: int = 90,
        engine_provider: str = "",
    ) -> Optional[dict]:
        """Atomically claim exactly one selected task."""
        ts = now()
        run_id = "run_" + uuid.uuid4().hex[:14]
        with self._lock:
            self._tx()
            try:
                row = self._db.execute(
                    "SELECT * FROM tasks WHERE id=?", (task_id,)
                ).fetchone()
                if not row or row["status"] not in ("triage", "ready"):
                    self._db.rollback()
                    return None
                if str(row["capability"] or "") == "gate":
                    # GATE là chỗ CHỜ NGƯỜI, không phải việc để chạy. Chặn ở đây (chứ không chỉ ở
                    # next_candidate) vì /kanban/run và /kanban/nudge gọi claim thẳng theo mã.
                    self._db.rollback()
                    return None
                if row["status"] == "ready":
                    unfinished = self._db.execute(
                        """
                        SELECT COUNT(*) AS n
                        FROM task_dependencies d
                        LEFT JOIN tasks p ON p.id=d.depends_on_id
                        WHERE d.task_id=?
                          AND """ + DEP_UNMET_SQL + """
                        """,
                        (task_id,),
                    ).fetchone()["n"]
                    if unfinished:
                        self._db.execute(
                            "UPDATE tasks SET status='todo', updated_at=? WHERE id=?",
                            (ts, task_id),
                        )
                        self._event(task_id, "waiting_dependency", "unfinished dependency")
                        self._db.commit()
                        return None
                changed = self._db.execute(
                    """UPDATE tasks
                       SET status='running', attempts=attempts+1, claimed_by=?,
                           claim_expires_at=?, not_before=0, last_heartbeat_at=?,
                           current_run_id=?, block_kind='', block_reason='', updated_at=?
                       WHERE id=? AND status IN ('triage','ready')""",
                    (worker_id, ts + lease_seconds, ts, run_id, ts, task_id),
                ).rowcount
                if changed != 1:
                    self._db.rollback()
                    return None
                self._db.execute(
                    """INSERT INTO task_runs
                       (id, task_id, brain_root, worker_id, engine_provider, status,
                        started_at, heartbeat_at)
                       VALUES (?, ?, ?, ?, ?, 'running', ?, ?)""",
                    (
                        run_id, task_id, str(row["brain_root"]), worker_id,
                        engine_provider or "", ts, ts,
                    ),
                )
                self._event(task_id, "claimed", f"claimed by {worker_id}", run_id)
                self._db.commit()
            except Exception:
                self._db.rollback()
                raise
        return self.get_task(task_id)

    def heartbeat(self, task_id: str, worker_id: str, lease_seconds: int = 90) -> bool:
        ts = now()
        with self._lock:
            self._tx()
            try:
                row = self._db.execute(
                    "SELECT current_run_id FROM tasks WHERE id=? AND status='running' AND claimed_by=?",
                    (task_id, worker_id),
                ).fetchone()
                if not row:
                    self._db.rollback()
                    return False
                self._db.execute(
                    """UPDATE tasks SET last_heartbeat_at=?, claim_expires_at=?, updated_at=?
                       WHERE id=?""",
                    (ts, ts + lease_seconds, ts, task_id),
                )
                if row["current_run_id"]:
                    self._db.execute(
                        "UPDATE task_runs SET heartbeat_at=? WHERE id=?",
                        (ts, row["current_run_id"]),
                    )
                self._db.commit()
                return True
            except Exception:
                self._db.rollback()
                raise

    def _finish(
        self,
        task_id: str,
        worker_id: str,
        status: str,
        result: str = "",
        error: str = "",
        block_kind: str = "",
        block_reason: str = "",
        metadata: Optional[dict] = None,
        artifacts: Optional[list] = None,
        event_type: str = "completed",
        not_before: float = 0.0,
        keep_attempt: bool = False,
    ) -> Optional[dict]:
        """`not_before`: mốc epoch trước đó dispatcher không nhặt lại việc (hoãn vì hết hạn mức).
        `keep_attempt`: trả lại lượt thử mà `claim` vừa cộng - lượt vấp hạn mức không phải lỗi
        của việc, tính nó là ba lần vấp cùng một cửa sổ hết lượt là việc chết oan."""
        if status not in VALID_STATUS:
            raise ValueError("invalid task status")
        ts = now()
        with self._lock:
            self._tx()
            try:
                row = self._db.execute(
                    """SELECT current_run_id, metadata_json FROM tasks
                       WHERE id=? AND status='running' AND claimed_by=?""",
                    (task_id, worker_id),
                ).fetchone()
                if not row:
                    self._db.rollback()
                    return None
                run_id = str(row["current_run_id"] or "")
                metadata = _giu_meta_job(row["metadata_json"], metadata)
                self._db.execute(
                    """UPDATE tasks
                       SET status=?, result=?, block_kind=?, block_reason=?,
                           metadata_json=?, artifacts_json=?, claimed_by='',
                           claim_expires_at=0, not_before=?, last_heartbeat_at=?,
                           current_run_id='', updated_at=?
                       WHERE id=?""",
                    (
                        status, (result or "")[:20000], block_kind or "",
                        (block_reason or "")[:2000], _json(metadata or {}),
                        _json(artifacts or []), float(not_before or 0.0), ts, ts, task_id,
                    ),
                )
                if keep_attempt:
                    self._db.execute(
                        """UPDATE tasks
                           SET attempts=CASE WHEN attempts > 0 THEN attempts - 1 ELSE 0 END
                           WHERE id=?""",
                        (task_id,),
                    )
                if run_id:
                    run_status = "completed" if status in ("done", "review", "ready") else status
                    self._db.execute(
                        """UPDATE task_runs
                           SET status=?, finished_at=?, heartbeat_at=?, error=?,
                               result=?, metadata_json=?
                           WHERE id=?""",
                        (
                            run_status, ts, ts, (error or block_reason or "")[:4000],
                            (result or "")[:20000], _json(metadata or {}), run_id,
                        ),
                    )
                self._event(
                    task_id, event_type, block_reason or error or status, run_id, metadata
                )
                self._db.commit()
            except Exception:
                self._db.rollback()
                raise
        return self.get_task(task_id)

    def complete(
        self,
        task_id: str,
        worker_id: str,
        result: str,
        needs_approval: bool = False,
        metadata: Optional[dict] = None,
        artifacts: Optional[list] = None,
    ) -> Optional[dict]:
        return self._finish(
            task_id, worker_id, "review" if needs_approval else "done",
            result=result, metadata=metadata, artifacts=artifacts,
            event_type="completed",
        )

    def prepared(
        self,
        task_id: str,
        worker_id: str,
        intent: str,
        capability: str,
        execution_mode: str,
        metadata: Optional[dict] = None,
    ) -> Optional[dict]:
        ts = now()
        with self._lock:
            self._tx()
            try:
                row = self._db.execute(
                    """SELECT current_run_id, metadata_json FROM tasks
                       WHERE id=? AND status='running' AND claimed_by=?""",
                    (task_id, worker_id),
                ).fetchone()
                if not row:
                    self._db.rollback()
                    return None
                run_id = str(row["current_run_id"] or "")
                metadata = _giu_meta_job(row["metadata_json"], metadata)
                self._db.execute(
                    """UPDATE tasks
                       SET status='ready', attempts=CASE WHEN attempts > 0 THEN attempts - 1 ELSE 0 END,
                           intent=?, capability=?, execution_mode=?,
                           metadata_json=?, claimed_by='', claim_expires_at=0,
                           current_run_id='', updated_at=?
                       WHERE id=?""",
                    (
                        intent, capability or "files", execution_mode or "auto",
                        _json(metadata or {}), ts, task_id,
                    ),
                )
                if run_id:
                    self._db.execute(
                        """UPDATE task_runs SET status='specified', finished_at=?,
                           heartbeat_at=?, result=?, metadata_json=? WHERE id=?""",
                        (ts, ts, intent[:20000], _json(metadata or {}), run_id),
                    )
                self._event(
                    task_id, "specified", f"capability={capability}", run_id, metadata
                )
                self._db.commit()
            except Exception:
                self._db.rollback()
                raise
        return self.get_task(task_id)

    def block(
        self,
        task_id: str,
        worker_id: str,
        kind: str,
        reason: str,
        result: str = "",
        transient: bool = False,
        not_before: float = 0.0,
        keep_attempt: bool = False,
    ) -> Optional[dict]:
        """`transient=True` -> về ready để thử lại (còn lượt). `not_before` hoãn lần thử tới
        mốc đó; `keep_attempt` không tính lần vấp này vào `attempts` (hết hạn mức gói thuê bao
        đã biết giờ mở lại: đợi đúng giờ rồi thử là chắc ăn, không có lý do gì để đốt lượt)."""
        task = self.get_task(task_id)
        if not task:
            return None
        con_luot = keep_attempt or int(task["attempts"]) < int(task["max_attempts"])
        retry = bool(transient and con_luot)
        # GIỮ metadata (điều kiện hoàn thành do specifier viết) và artifacts: `_finish` ghi đè
        # cột bằng thứ được truyền, bản trước không truyền gì nên mỗi lần chặn/thử lại là việc
        # chạy lại với "ĐIỀU KIỆN HOÀN THÀNH: []".
        return self._finish(
            task_id, worker_id, "ready" if retry else "blocked",
            result=result, error=reason, block_kind=kind,
            block_reason=reason, event_type="retry_scheduled" if retry else "blocked",
            metadata=task.get("metadata") or {}, artifacts=task.get("artifacts") or [],
            not_before=float(not_before or 0.0) if retry else 0.0,
            keep_attempt=bool(keep_attempt and retry),
        )

    def ask(
        self, task_id: str, worker_id: str, question: str, result: str = "",
        extra_meta: Optional[dict] = None,
    ) -> Optional[dict]:
        """Chặn việc ở `needs_input` VÀ ghi câu hỏi vào `metadata.qa` (0.235.0).

        Trước đây câu hỏi chỉ nằm lẫn trong `block_reason`, và đường duy nhất để gỡ là Thử lại:
        việc chạy lại từ đầu mà không ai nói cho nó câu trả lời, nên nó hỏi lại y hệt. Giờ mỗi
        lần hỏi là một mục `{q, asked_at, progress}`; `answer` điền `a` vào mục đó, và lần chạy
        sau đọc cả sổ (ý tưởng `ask_user` của OpenMuse). `progress` là đầu bản tường thuật của
        lần chạy vừa dừng, để lần sau biết phần nào đã làm xong."""
        task = self.get_task(task_id)
        if not task:
            return None
        meta = dict(task.get("metadata") or {})
        qa = [x for x in (meta.get("qa") or []) if isinstance(x, dict)]
        qa.append({
            "q": (question or "").strip()[:QA_TEXT_MAX],
            "asked_at": now(),
            "progress": (result or "").strip()[:QA_PROGRESS_MAX],
        })
        meta["qa"] = qa[-QA_KEEP:]
        meta.update(extra_meta or {})
        return self._finish(
            task_id, worker_id, "blocked",
            result=result, error=question, block_kind="needs_input",
            block_reason=question, event_type="blocked",
            metadata=meta, artifacts=task.get("artifacts") or [],
        )

    def answer(self, task_id: str, text: str, by: str = "owner") -> tuple[Optional[dict], str]:
        """Chủ trả lời việc đang chờ ở `needs_input`: điền câu trả lời rồi đưa việc về `ready`.

        Trả (task, "") khi xong, (None, mã lỗi) khi không: "not_found", "empty", "not_waiting".
        TRẢ LẠI lượt thử mà lần chạy vừa hỏi đã tiêu: hỏi người không phải là việc hỏng, tính
        nó thì việc hỏi ba câu là chết vì hết lượt dù chưa hỏng lần nào."""
        text = (text or "").strip()
        if not text:
            return None, "empty"
        with self._lock:
            self._tx()
            try:
                row = self._db.execute(
                    "SELECT * FROM tasks WHERE id=?", (task_id,)
                ).fetchone()
                if not row:
                    self._db.rollback()
                    return None, "not_found"
                if row["status"] != "blocked" or row["block_kind"] != "needs_input":
                    self._db.rollback()
                    return None, "not_waiting"
                meta = _loads(row["metadata_json"], {})
                qa = [x for x in (meta.get("qa") or []) if isinstance(x, dict)]
                if not qa or qa[-1].get("a"):
                    # Việc kẹt từ trước bản này: câu hỏi chỉ còn trong block_reason.
                    qa.append({"q": str(row["block_reason"] or "")[:QA_TEXT_MAX],
                               "asked_at": float(row["updated_at"] or now())})
                qa[-1].update({"a": text[:QA_TEXT_MAX], "answered_at": now(), "by": by})
                meta["qa"] = qa[-QA_KEEP:]
                meta.pop("once_pending", None)     # câu hỏi "đã gửi chưa" (0.238.0) đã có lời đáp
                self._db.execute(
                    """UPDATE tasks SET status='ready', block_kind='', block_reason='',
                       attempts=CASE WHEN attempts > 0 THEN attempts - 1 ELSE 0 END,
                       metadata_json=?, claimed_by='', claim_expires_at=0, not_before=0,
                       current_run_id='', updated_at=?
                       WHERE id=?""",
                    (_json(meta), now(), task_id),
                )
                self._event(task_id, "answered", text[:500], metadata={"by": by})
                self._db.commit()
            except Exception:
                self._db.rollback()
                raise
        return self.get_task(task_id), ""

    # ------------------------------------------------------------------
    # 26.10.312: trang Công việc yên hơn (ý từ Javis 0.411, viết lại cho MinMin)
    # ------------------------------------------------------------------
    # Việc dừng lại mà CHỈ CHỦ gỡ được: một câu hỏi, một lần xin quyền thao tác ra ngoài, hoặc
    # kết quả chờ duyệt. Mọi kiểu dừng khác (lỗi tạm, hết lượt gói, máy AI chưa sẵn sàng) là
    # việc MinMin tự lo, bày vào "Cần bố xử lý" chỉ làm bố lo mà không làm gì được.
    OWNER_BLOCK_KINDS = ("needs_input", "capability")

    @classmethod
    def waits_for_owner(cls, task: dict) -> bool:
        st = str((task or {}).get("status") or "")
        if st == "review":
            return True
        return st == "blocked" and str(task.get("block_kind") or "") in cls.OWNER_BLOCK_KINDS

    def archive_stopped(self, brain_root: str, owner: bool) -> int:
        """Dọn một trong hai khu việc dừng: `owner=True` khu "Cần bố xử lý", False khu "MinMin
        đang tự xử lý". Cùng hậu quả với `archive_by_status` (archive, không xoá hẳn)."""
        with self._lock:
            rows = self._db.execute(
                "SELECT id, status, block_kind FROM tasks WHERE brain_root=? "
                "AND status IN ('blocked', 'review')", (brain_root,)).fetchall()
        ids = [str(r["id"]) for r in rows if self.waits_for_owner(dict(r)) == bool(owner)]
        if not ids:
            return 0
        with self._lock:
            self._tx()
            try:
                ts = now()
                for tid in ids:
                    self._db.execute(
                        """UPDATE tasks SET status='archived', block_kind='', block_reason='',
                           claimed_by='', claim_expires_at=0, current_run_id='', updated_at=?
                           WHERE id=? AND status IN ('blocked', 'review')""",
                        (ts, tid),
                    )
                    self._event(tid, "operator_move", "-> archived: xoá tất cả")
                self._db.commit()
            except Exception:
                self._db.rollback()
                raise
        return len(ids)

    # "Nhắn thêm" được cho mọi việc KHÔNG đang chạy và KHÔNG đang chờ câu trả lời (việc đó đi
    # đường `answer`). Việc đã xong cũng được: "viết ngắn lại đoạn 2" sau khi đọc kết quả là ca
    # hay gặp nhất.
    FOLLOWUP_STATUS = ("blocked", "review", "done", "cancelled", "triage", "todo", "ready")
    FOLLOWUP_Q = "Bố nhắn thêm cho việc này"

    def followup(self, task_id: str, text: str, by: str = "owner") -> tuple[Optional[dict], str]:
        """Lời dặn thêm của chủ cho một việc, rồi đưa việc về hàng đợi.

        Trước bản này cách duy nhất để đổi một việc đã dừng hay đã xong là Thử lại, chạy lại y
        nguyên. Lời dặn vào sổ hỏi đáp như một lượt ĐÃ có câu trả lời, kèm kết quả lần trước ở
        `progress`, nên lần chạy sau (`TasksFeature._hoi_dap`) đi tiếp từ kết quả cũ chứ không
        làm lại từ đầu, và không gửi lại thứ đã gửi. Số lần thử tính lại từ 0: đây là một yêu
        cầu mới chứ không phải thêm một lần thử cho yêu cầu cũ.
        Trả (task, "") hoặc (None, "empty" | "not_found" | "running" | "waiting" | "gate")."""
        text = (text or "").strip()
        if not text:
            return None, "empty"
        with self._lock:
            self._tx()
            try:
                row = self._db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
                if not row:
                    self._db.rollback()
                    return None, "not_found"
                if row["capability"] == "gate":
                    self._db.rollback()
                    return None, "gate"
                if row["status"] == "running":
                    self._db.rollback()
                    return None, "running"
                if row["status"] == "blocked" and row["block_kind"] == "needs_input":
                    self._db.rollback()
                    return None, "waiting"
                if row["status"] not in self.FOLLOWUP_STATUS:
                    self._db.rollback()
                    return None, "not_found"
                meta = _loads(row["metadata_json"], {})
                qa = [x for x in (meta.get("qa") or []) if isinstance(x, dict)]
                ts = now()
                qa.append({
                    "q": self.FOLLOWUP_Q, "a": text[:QA_TEXT_MAX], "kind": "followup", "by": by,
                    "asked_at": ts, "answered_at": ts,
                    "progress": str(row["result"] or "").strip()[:QA_PROGRESS_MAX],
                })
                meta["qa"] = qa[-QA_KEEP:]
                meta.pop("once_pending", None)
                meta.pop("kiem", None)          # kết quả sẽ khác, dấu đã kiểm của bản cũ không còn đúng
                self._db.execute(
                    """UPDATE tasks SET status='ready', block_kind='', block_reason='', attempts=0,
                       metadata_json=?, claimed_by='', claim_expires_at=0, not_before=0,
                       current_run_id='', updated_at=?
                       WHERE id=?""",
                    (_json(meta), ts, task_id),
                )
                self._event(task_id, "followup", text[:500], metadata={"by": by, "from": row["status"]})
                self._db.commit()
            except Exception:
                self._db.rollback()
                raise
        return self.get_task(task_id), ""

    def set_check(self, task_id: str, state: str, why: str = "") -> Optional[dict]:
        """Ghi kết quả lượt KIỂM một việc đã xong. `state`: "dang_kiem" lúc đang chạy, "dat" khi
        đạt, "chua_dat" khi chưa đạt (việc chuyển sang Cần bố xử lý với lý do làm câu hỏi, để ô
        trả lời dùng luôn được), "loi" khi lượt kiểm không chạy nổi (việc vẫn Xong, chỉ là chưa
        kiểm). Chỉ đụng việc đang done hoặc review."""
        if state not in ("dang_kiem", "dat", "chua_dat", "loi"):
            return None
        with self._lock:
            self._tx()
            try:
                row = self._db.execute(
                    "SELECT status, metadata_json FROM tasks WHERE id=?", (task_id,)).fetchone()
                if not row or row["status"] not in ("done", "review"):
                    self._db.rollback()
                    return None
                meta = _loads(row["metadata_json"], {})
                ts = now()
                meta["kiem"] = {"state": state, "why": str(why or "")[:QA_TEXT_MAX], "at": ts}
                if state == "chua_dat":
                    reason = ("Kiểm lại thấy chưa đạt: " + (why or "lượt kiểm không nói rõ chỗ nào.")
                              + " Bố muốn MinMin sửa thế nào?")[:QA_TEXT_MAX]
                    qa = [x for x in (meta.get("qa") or []) if isinstance(x, dict)]
                    qa.append({"q": reason, "asked_at": ts})
                    meta["qa"] = qa[-QA_KEEP:]
                    self._db.execute(
                        """UPDATE tasks SET status='blocked', block_kind='needs_input', block_reason=?,
                           metadata_json=?, updated_at=? WHERE id=?""",
                        (reason, _json(meta), ts, task_id),
                    )
                    self._event(task_id, "kiem_chua_dat", reason[:500])
                else:
                    self._db.execute("UPDATE tasks SET metadata_json=?, updated_at=? WHERE id=?",
                                     (_json(meta), ts, task_id))
                    if state != "dang_kiem":
                        self._event(task_id, "kiem_" + state, str(why or "")[:500])
                self._db.commit()
            except Exception:
                self._db.rollback()
                raise
        return self.get_task(task_id)

    # Gợi ý việc lặp: việc bố giao TAY (trang Công việc, chat, giọng nói) 3 lần trong 60 ngày,
    # so tên bỏ số, là một việc hằng ngày đang chờ được đặt lịch. Việc do loop, nhắc hẹn, trợ lý
    # sinh ra thì đã tự chạy rồi, không tính.
    HINT_SOURCES = ("user", "chat", "voice", "web", "telegram", "zalo")
    HINT_MIN_COUNT = 3
    HINT_WINDOW_DAYS = 60
    HINT_SCAN = 300

    @staticmethod
    def hint_words(title: str) -> frozenset:
        """Chữ của một tên việc, bỏ số: "Báo cáo doanh thu 28/10" và "... 4/11" là một việc."""
        return frozenset(w for w in norm_title(title).split()
                         if len(w) > 1 and not any(c.isdigit() for c in w))

    def repeat_hints(self, brain_root: str, limit: int = 3) -> list[dict]:
        root = str(brain_root)
        since = now() - self.HINT_WINDOW_DAYS * 86400
        marks = ",".join("?" for _ in self.HINT_SOURCES)
        with self._lock:
            rows = self._db.execute(
                f"""SELECT id, title, intent, created_at FROM tasks
                    WHERE brain_root=? AND created_at>=? AND job_id IS NULL
                      AND created_by IN ({marks})
                    ORDER BY created_at DESC LIMIT ?""",
                (root, since, *self.HINT_SOURCES, self.HINT_SCAN),
            ).fetchall()
            bo_qua = {r["hint_key"] for r in self._db.execute(
                "SELECT hint_key FROM goi_y_lap_bo_qua WHERE brain_root=?", (root,)).fetchall()}
        nhom: list[dict] = []
        for r in rows:
            words = self.hint_words(r["title"])
            if len(words) < 2:
                continue
            for g in nhom:
                chung = len(words & g["words"])
                if chung and chung / len(words | g["words"]) >= 0.7:
                    g["count"] += 1
                    break
            else:
                nhom.append({"words": words, "count": 1, "title": r["title"], "intent": r["intent"],
                             "task_id": r["id"], "last_at": float(r["created_at"])})
        out = []
        for g in nhom:
            key = " ".join(sorted(g["words"]))
            if g["count"] >= self.HINT_MIN_COUNT and key not in bo_qua:
                out.append({"key": key, "count": g["count"], "title": g["title"],
                            "intent": str(g["intent"] or "")[:600], "task_id": g["task_id"],
                            "last_at": g["last_at"]})
        out.sort(key=lambda h: (-h["count"], -h["last_at"]))
        return out[:max(1, int(limit))]

    def dismiss_hint(self, brain_root: str, hint_key: str) -> None:
        with self._lock:
            self._db.execute(
                "INSERT OR REPLACE INTO goi_y_lap_bo_qua(brain_root, hint_key, created_at) VALUES (?, ?, ?)",
                (str(brain_root), str(hint_key)[:500], now()))
            self._db.commit()

    def move(self, task_id: str, status: str, reason: str = "operator") -> bool:
        if status not in VALID_STATUS:
            return False
        with self._lock:
            self._tx()
            try:
                row = self._db.execute(
                    "SELECT status FROM tasks WHERE id=?", (task_id,)
                ).fetchone()
                if not row:
                    self._db.rollback()
                    return False
                if row["status"] == "running":
                    self._db.rollback()
                    return False
                # Người dùng tự kéo việc: bỏ luôn mốc hoãn (họ muốn chạy NGAY, kể cả khi
                # Javis đang đợi gói thuê bao mở lại).
                self._db.execute(
                    """UPDATE tasks SET status=?, block_kind='', block_reason='',
                       claimed_by='', claim_expires_at=0, not_before=0, current_run_id='',
                       updated_at=?
                       WHERE id=?""",
                    (status, now(), task_id),
                )
                self._event(task_id, "operator_move", f"{row['status']} -> {status}: {reason}")
                self._db.commit()
                return True
            except Exception:
                self._db.rollback()
                raise

    def recover_codex_global_flag_blocks(self, brain_root: str) -> int:
        """Retry tasks blocked by the v0.9.173 Codex argv ordering regression once.

        The match is intentionally narrow so operator/input blocks and unrelated
        Codex failures remain untouched.
        """
        key = "recovery:codex-global-flags-v1:" + str(brain_root)
        with self._lock:
            self._tx()
            try:
                seen = self._db.execute(
                    "SELECT 1 FROM task_migrations WHERE migration_key=?", (key,)
                ).fetchone()
                if seen:
                    self._db.rollback()
                    return 0
                rows = self._db.execute(
                    """SELECT id FROM tasks
                       WHERE brain_root=? AND status='blocked'
                         AND block_reason LIKE '%unexpected argument%'
                         AND block_reason LIKE '%--ask-for-approval%'""",
                    (brain_root,),
                ).fetchall()
                ts = now()
                for row in rows:
                    task_id = str(row["id"])
                    self._db.execute(
                        """UPDATE tasks
                           SET status='ready',
                               attempts=CASE WHEN attempts > 0 THEN attempts - 1 ELSE 0 END,
                               block_kind='', block_reason='', claimed_by='',
                               claim_expires_at=0, current_run_id='', updated_at=?
                           WHERE id=? AND status='blocked'""",
                        (ts, task_id),
                    )
                    self._event(
                        task_id,
                        "system_recovered",
                        "retry after Codex global flag ordering fix",
                    )
                self._db.execute(
                    """INSERT INTO task_migrations(migration_key, migrated_at)
                       VALUES (?, ?)""",
                    (key, ts),
                )
                self._db.commit()
                return len(rows)
            except Exception:
                self._db.rollback()
                raise

    def cancel_running(self, task_id: str, reason: str = "operator cancel") -> bool:
        ts = now()
        with self._lock:
            self._tx()
            try:
                row = self._db.execute(
                    "SELECT current_run_id FROM tasks WHERE id=? AND status='running'",
                    (task_id,),
                ).fetchone()
                if not row:
                    self._db.rollback()
                    return False
                self._db.execute(
                    """UPDATE tasks SET status='cancelled', block_kind='cancelled',
                       block_reason=?, claimed_by='', claim_expires_at=0,
                       current_run_id='', updated_at=? WHERE id=?""",
                    (reason, ts, task_id),
                )
                if row["current_run_id"]:
                    self._db.execute(
                        """UPDATE task_runs SET status='cancelled', finished_at=?, error=?
                           WHERE id=?""",
                        (ts, reason, row["current_run_id"]),
                    )
                self._event(task_id, "cancelled", reason, str(row["current_run_id"] or ""))
                self._db.commit()
                return True
            except Exception:
                self._db.rollback()
                raise

    # ------------------------------------------------------------------
    # Job của Đội AI: chuỗi bước chạy lần lượt, có bước GATE chờ chủ duyệt
    # ------------------------------------------------------------------
    @staticmethod
    def _job_from_row(row: sqlite3.Row) -> dict:
        job = dict(row)
        job["metadata"] = _loads(job.pop("metadata_json", "{}"), {})
        return job

    def create_job(
        self, brain_root: str, job_id: str, title: str, doi: str, chat_id: str = "",
        metadata: Optional[dict] = None,
    ) -> str:
        ts = now()
        self.ensure_board(str(brain_root))
        with self._lock:
            self._db.execute(
                """INSERT INTO jobs (id, brain_root, title, doi, status, chat_id,
                   created_at, updated_at, metadata_json)
                   VALUES (?, ?, ?, ?, 'dang_chay', ?, ?, ?, ?)""",
                (job_id, str(brain_root), (title or "Job")[:160], doi or "khac",
                 str(chat_id or ""), ts, ts, _json(metadata or {})),
            )
            self._db.commit()
        return job_id

    def get_job(self, job_id: str) -> Optional[dict]:
        with self._lock:
            row = self._db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        return self._job_from_row(row) if row else None

    def list_jobs(self, brain_root: str, limit: int = 50) -> list[dict]:
        with self._lock:
            rows = self._db.execute(
                """SELECT * FROM jobs WHERE brain_root=?
                   ORDER BY created_at DESC LIMIT ?""",
                (brain_root, max(1, min(500, int(limit)))),
            ).fetchall()
        return [self._job_from_row(r) for r in rows]

    def job_tasks(self, job_id: str) -> list[dict]:
        """Mọi bước của job, KỂ CẢ đã archived (housekeep tự archive việc xong quá 3 ngày)."""
        with self._lock:
            rows = self._db.execute(
                "SELECT * FROM tasks WHERE job_id=? ORDER BY created_at", (job_id,)
            ).fetchall()
        return [self._task_from_row(r) for r in rows]

    def set_job_status(self, job_id: str, status: str, meta_patch: Optional[dict] = None) -> None:
        with self._lock:
            row = self._db.execute(
                "SELECT status, metadata_json FROM jobs WHERE id=?", (job_id,)
            ).fetchone()
            if not row:
                return
            meta = _loads(row["metadata_json"], {})
            if meta_patch:
                meta.update(meta_patch)
            if row["status"] == status and not meta_patch:
                return
            self._db.execute(
                "UPDATE jobs SET status=?, metadata_json=?, updated_at=? WHERE id=?",
                (status, _json(meta), now(), job_id),
            )
            self._db.commit()

    def open_gates(self, brain_root: str) -> list[str]:
        """GATE đủ điều kiện (mọi bước nó phụ thuộc đã xong) -> `blocked` / `block_kind=gate`.

        Trả mã các GATE VỪA chuyển. Idempotent: GATE đã chờ thì không đụng lại."""
        with self._lock:
            self._tx()
            try:
                rows = self._db.execute(
                    """
                    SELECT t.id, t.intent, t.metadata_json FROM tasks t
                    WHERE t.brain_root=? AND t.capability='gate'
                      AND t.status IN ('triage','todo','ready')
                      AND NOT EXISTS (
                          SELECT 1 FROM task_dependencies d
                          LEFT JOIN tasks p ON p.id=d.depends_on_id
                          WHERE d.task_id=t.id
                            AND """ + DEP_UNMET_SQL + """
                      )
                    """,
                    (brain_root,),
                ).fetchall()
                ts = now()
                out = []
                for row in rows:
                    meta = _loads(row["metadata_json"], {})
                    gate = meta.get("gate") if isinstance(meta.get("gate"), dict) else {}
                    mo_ta = str(gate.get("mo_ta") or row["intent"] or "Chờ chủ duyệt")[:2000]
                    self._db.execute(
                        """UPDATE tasks SET status='blocked', block_kind='gate', block_reason=?,
                           claimed_by='', claim_expires_at=0, current_run_id='', updated_at=?
                           WHERE id=? AND status IN ('triage','todo','ready')""",
                        (mo_ta, ts, row["id"]),
                    )
                    self._event(str(row["id"]), "gate_cho", "GATE tới lượt, chờ chủ duyệt")
                    out.append(str(row["id"]))
                self._db.commit()
                return out
            except Exception:
                self._db.rollback()
                raise

    def gates_waiting(self, brain_root: str) -> list[dict]:
        with self._lock:
            rows = self._db.execute(
                """SELECT * FROM tasks WHERE brain_root=? AND capability='gate'
                   AND status='blocked' AND block_kind='gate'""",
                (brain_root,),
            ).fetchall()
        return [self._task_from_row(r) for r in rows]

    def mark_gate_notified(self, task_id: str) -> bool:
        """Đặt cờ "đã báo" cho LẦN CHỜ hiện tại của GATE. True = lời gọi này giành được quyền
        báo (cờ vừa bật), False = đã có người báo rồi. Compare-and-set trong một giao dịch nên
        dispatcher, tick và một lần đọc trang cùng lúc cũng chỉ báo một lần."""
        with self._lock:
            self._tx()
            try:
                row = self._db.execute(
                    "SELECT status, block_kind, metadata_json FROM tasks WHERE id=?", (task_id,)
                ).fetchone()
                if not row or row["status"] != "blocked" or row["block_kind"] != "gate":
                    self._db.rollback()
                    return False
                meta = _loads(row["metadata_json"], {})
                gate = dict(meta.get("gate") or {}) if isinstance(meta.get("gate"), dict) else {}
                if gate.get("da_bao"):
                    self._db.rollback()
                    return False
                gate["da_bao"] = True
                gate["bao_luc"] = now()
                meta["gate"] = gate
                self._db.execute(
                    "UPDATE tasks SET metadata_json=? WHERE id=?", (_json(meta), task_id)
                )
                self._db.commit()
                return True
            except Exception:
                self._db.rollback()
                raise

    def approve_gate(self, gate_id: str, unlock_ids: Iterable[str], source: str = "dashboard",
                     note: str = "") -> Optional[list[str]]:
        """Duyệt: GATE -> done và cấp `execution_mode=full` cho ĐÚNG các bước GATE mở khoá, trong
        MỘT giao dịch. Tách hai bước ra thì giữa chúng dispatcher kịp thăng bước sau lên ready ở
        mức auto, nhặt chạy, rồi chặn vì thiếu quyền. Trả mã các bước đã cấp quyền, None khi GATE
        không ở trạng thái chờ (đã duyệt/huỷ rồi: lời gọi lặp không cấp quyền lần nữa)."""
        with self._lock:
            self._tx()
            try:
                row = self._db.execute(
                    "SELECT status, block_kind, metadata_json FROM tasks WHERE id=?", (gate_id,)
                ).fetchone()
                if not row or row["status"] != "blocked" or row["block_kind"] != "gate":
                    self._db.rollback()
                    return None
                ts = now()
                gmeta = _loads(row["metadata_json"], {})
                gate = dict(gmeta.get("gate") or {}) if isinstance(gmeta.get("gate"), dict) else {}
                gate.update({"duyet": True, "duyet_luc": ts, "duyet_qua": source})
                gmeta["gate"] = gate
                self._db.execute(
                    """UPDATE tasks SET status='done', block_kind='', block_reason='',
                       result=?, metadata_json=?, updated_at=? WHERE id=?""",
                    ("Chủ đã duyệt" + (f": {note}" if note else ""), _json(gmeta), ts, gate_id),
                )
                self._event(gate_id, "gate_duyet", f"duyệt qua {source}",
                            metadata={"source": source, "note": note})
                granted = []
                for tid in dict.fromkeys(str(x) for x in unlock_ids if str(x)):
                    r = self._db.execute(
                        "SELECT status FROM tasks WHERE id=?", (tid,)
                    ).fetchone()
                    if not r or r["status"] in ("running",) or r["status"] in TERMINAL_STATUS:
                        continue
                    self._db.execute(
                        """UPDATE tasks SET status='ready', execution_mode='full',
                           block_kind='', block_reason='', attempts=0, not_before=0,
                           claimed_by='', claim_expires_at=0, current_run_id='', updated_at=?
                           WHERE id=?""",
                        (ts, tid),
                    )
                    self._event(tid, "operator_grant",
                                f"{r['status']} -> ready, mức quyền = full: GATE {gate_id} "
                                f"được duyệt qua {source}",
                                metadata={"source": source, "gate": gate_id})
                    granted.append(tid)
                self._db.commit()
                return granted
            except Exception:
                self._db.rollback()
                raise

    def revise_gate(self, gate_id: str, prev_id: str, note: str,
                    source: str = "dashboard") -> str:
        """Sửa lại: bước ngay trước GATE chạy lại với ghi chú của chủ, GATE về chờ (todo) và
        xoá cờ đã báo để lần chờ sau được báo lại. Trả "" khi xong, mã lỗi khi không."""
        with self._lock:
            self._tx()
            try:
                g = self._db.execute(
                    "SELECT status, block_kind, metadata_json FROM tasks WHERE id=?", (gate_id,)
                ).fetchone()
                if not g or g["status"] != "blocked" or g["block_kind"] != "gate":
                    self._db.rollback()
                    return "not_waiting"
                p = self._db.execute(
                    "SELECT status, intent, metadata_json FROM tasks WHERE id=?", (prev_id,)
                ).fetchone()
                if not p:
                    self._db.rollback()
                    return "no_prev"
                if p["status"] == "running":
                    self._db.rollback()
                    return "prev_running"
                ts = now()
                cau = f"Chủ yêu cầu sửa: {note}"
                pmeta = _loads(p["metadata_json"], {})
                sua = [x for x in (pmeta.get("sua") or []) if isinstance(x, dict)]
                sua.append({"note": note[:QA_TEXT_MAX], "luc": ts, "source": source})
                pmeta["sua"] = sua[-QA_KEEP:]
                intent = (str(p["intent"] or "").rstrip() + "\n\n" + cau)[:20000]
                self._db.execute(
                    """UPDATE tasks SET status='ready', intent=?, metadata_json=?, attempts=0,
                       block_kind='', block_reason='', not_before=0, claimed_by='',
                       claim_expires_at=0, current_run_id='', updated_at=? WHERE id=?""",
                    (intent, _json(pmeta), ts, prev_id),
                )
                self._event(prev_id, "rerun_with_note", cau[:500],
                            metadata={"source": source, "gate": gate_id})
                gmeta = _loads(g["metadata_json"], {})
                gate = dict(gmeta.get("gate") or {}) if isinstance(gmeta.get("gate"), dict) else {}
                gate["da_bao"] = False
                gate.pop("bao_luc", None)
                gmeta["gate"] = gate
                self._db.execute(
                    """UPDATE tasks SET status='todo', block_kind='', block_reason='',
                       metadata_json=?, updated_at=? WHERE id=?""",
                    (_json(gmeta), ts, gate_id),
                )
                self._event(gate_id, "gate_sua", cau[:500],
                            metadata={"source": source, "note": note[:QA_TEXT_MAX]})
                self._db.commit()
                return ""
            except Exception:
                self._db.rollback()
                raise

    def reject_job(self, job_id: str, gate_id: str, source: str = "dashboard",
                   note: str = "") -> list[str]:
        """Từ chối: GATE và mọi bước chưa xong của job -> cancelled. Bước đang chạy KHÔNG bị
        đụng ở đây (worker còn cầm); trả mã của chúng để tầng trên huỷ worker."""
        with self._lock:
            self._tx()
            try:
                rows = self._db.execute(
                    "SELECT id, status FROM tasks WHERE job_id=?", (job_id,)
                ).fetchall()
                ts = now()
                running = []
                for r in rows:
                    tid, st = str(r["id"]), str(r["status"])
                    if st in TERMINAL_STATUS:
                        continue
                    if st == "running":
                        running.append(tid)
                        continue
                    self._db.execute(
                        """UPDATE tasks SET status='cancelled', block_kind='cancelled',
                           block_reason=?, claimed_by='', claim_expires_at=0,
                           current_run_id='', updated_at=? WHERE id=?""",
                        ("Chủ từ chối ở GATE", ts, tid),
                    )
                    self._event(tid, "cancelled", f"job bị từ chối qua {source}")
                if gate_id:
                    self._event(gate_id, "gate_tu_choi", f"từ chối qua {source}",
                                metadata={"source": source, "note": note})
                self._db.commit()
                return running
            except Exception:
                self._db.rollback()
                raise

    def add_event(self, task_id: str, event_type: str, message: str = "",
                  metadata: Optional[dict] = None) -> None:
        with self._lock:
            self._event(task_id, event_type, message, metadata=metadata)
            self._db.commit()

    def health(self, brain_root: Optional[str] = None) -> dict:
        where = " WHERE brain_root=?" if brain_root else ""
        args = (brain_root,) if brain_root else ()
        with self._lock:
            rows = self._db.execute(
                f"SELECT status, COUNT(*) AS n FROM tasks{where} GROUP BY status", args
            ).fetchall()
            recent = self._db.execute(
                f"""SELECT COUNT(*) AS n FROM tasks{where}
                    {'AND' if where else 'WHERE'} status='done' AND updated_at>=?""",
                (*args, now() - 86400),
            ).fetchone()
        counts = {s: 0 for s in VALID_STATUS}
        counts.update({str(r["status"]): int(r["n"]) for r in rows})
        return {"counts": counts, "completed_24h": int(recent["n"] if recent else 0)}

    def import_legacy(self, brain_root: str, json_path: Path) -> int:
        """Import a legacy board once, preserving ids and terminal state."""
        key = "legacy-json:" + str(Path(json_path).resolve())
        with self._lock:
            seen = self._db.execute(
                "SELECT 1 FROM task_migrations WHERE migration_key=?", (key,)
            ).fetchone()
        if seen:
            return 0
        data: dict = {}
        try:
            if json_path.is_file():
                parsed = json.loads(json_path.read_text(encoding="utf-8"))
                if isinstance(parsed, dict):
                    data = parsed
        except Exception:
            data = {}
        self.ensure_board(brain_root, str(data.get("orchestration") or "off"))
        imported = 0
        for old in data.get("tasks", []) if isinstance(data.get("tasks"), list) else []:
            try:
                old_status = str(old.get("status") or "triage")
                if old_status not in VALID_STATUS:
                    old_status = "triage"
                # A process from the legacy in-memory dispatcher cannot still be
                # alive after migration/restart, so never import it as running.
                if old_status == "running":
                    old_status = "ready"
                created_by = str(old.get("created_by") or "legacy")
                self.enqueue(
                    brain_root=brain_root,
                    title=str(old.get("title") or old.get("intent") or "Task"),
                    intent=str(old.get("intent") or old.get("title") or ""),
                    route=str(old.get("route") or "auto"),
                    priority=int(old.get("priority") or 2),
                    deps=old.get("deps") or [],
                    # Old Learn tasks all forced review. The autonomous queue now
                    # reserves intervention for typed external-write/input blocks.
                    needs_approval=bool(old.get("needs_approval", False)) and created_by != "learn",
                    created_by=created_by,
                    chat_id=str(old.get("chat_id") or ""),
                    capability=str(old.get("capability") or "auto"),
                    execution_mode=str(old.get("execution_mode") or "auto"),
                    status=old_status,
                    task_id=str(old.get("id") or ""),
                )
                task = self.get_task(str(old.get("id") or ""))
                if task and (old.get("result") or old.get("block_reason")):
                    with self._lock:
                        self._db.execute(
                            """UPDATE tasks SET result=?, block_kind=?, block_reason=?,
                               created_at=?, updated_at=? WHERE id=?""",
                            (
                                str(old.get("result") or "")[:20000],
                                str(old.get("block_kind") or old.get("block_reason") or ""),
                                str(old.get("block_reason") or "")[:2000],
                                float(old.get("created_at") or now()),
                                float(old.get("updated_at") or now()),
                                task["id"],
                            ),
                        )
                        self._db.commit()
                imported += 1
            except Exception:
                continue
        with self._lock:
            self._db.execute(
                "INSERT OR REPLACE INTO task_migrations(migration_key, migrated_at) VALUES (?, ?)",
                (key, now()),
            )
            self._db.execute(
                "UPDATE boards SET orchestration=?, updated_at=? WHERE brain_root=?",
                (str(data.get("orchestration") or "off"), now(), brain_root),
            )
            self._db.commit()
        return imported
