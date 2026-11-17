"""Nhật ký lỗi (có thời điểm, tự xoay vòng file - P07, U19) và nhật ký thao tác (K06)."""
from __future__ import annotations

import json
import logging
import logging.handlers
from datetime import datetime
from pathlib import Path
from typing import Any


def error_logger(log_dir: str | Path) -> logging.Logger:
    """Logger ghi lỗi ngoài dự kiến vào logs/error.log, tối đa 5 file x 1 MB."""
    path = Path(log_dir) / "error.log"
    name = f"kindergarten.errors.{path.resolve()}"
    logger = logging.getLogger(name)
    if not logger.handlers:
        path.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.handlers.RotatingFileHandler(path, maxBytes=1_000_000, backupCount=5, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger


def log_exception(log_dir: str | Path, exc: BaseException) -> Path:
    error_logger(log_dir).error("Lỗi ngoài dự kiến: %r", exc, exc_info=(type(exc), exc, exc.__traceback__))
    return Path(log_dir) / "error.log"


class AuditLog:
    """K06 - Nhật ký thao tác: mỗi dòng một sự kiện JSON (thời điểm, người dùng, hành động, đối tượng, chi tiết).

    File chỉ ghi nối thêm, không bao giờ sửa lại dòng cũ.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def write(self, user: str, action: str, target: str = "", detail: Any = None) -> None:
        entry = {"at": datetime.now().isoformat(timespec="seconds"), "user": user or "(hệ thống)",
                 "action": action, "target": target, "detail": detail}
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "a", encoding="utf-8") as file:
                file.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
        except OSError:
            pass  # không để lỗi ghi nhật ký làm hỏng thao tác chính

    def read(self, limit: int = 200) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        lines = self.path.read_text(encoding="utf-8").splitlines()[-limit:]
        result = []
        for line in reversed(lines):
            try:
                result.append(json.loads(line))
            except ValueError:
                continue
        return result
