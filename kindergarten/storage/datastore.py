"""T30 - DataStore: save_all(), load_all() bằng module json.

Mỗi danh sách được lưu thành một file .json riêng trong thư mục dữ liệu (dễ xem, dễ sao lưu).
Các bảo vệ đã bổ sung sau rà soát:
- L01: lưu bộ đếm mã trong meta.json, nạp lại không bao giờ cho bộ đếm lùi.
- L02: thiếu users.json trong khi còn file khác -> báo lỗi, không coi là "lần chạy đầu";
  tự sao lưu trước khi ghi nếu số bản ghi sắp giảm mạnh.
- L21: ghi các file thay đổi vào thư mục tạm `.saving/` (fsync) rồi mới thay thế; bắt đủ loại lỗi
  khi đọc; kiểm tra phiên bản và tự chuyển đổi dữ liệu cũ.
- P01: chỉ ghi file có nội dung thay đổi.  P02: điểm danh lưu dạng mảng gọn, file lớn không thụt lề.
- P07: sao lưu nén .zip, giữ số bản giới hạn, có chức năng khôi phục.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from ..attendance.records import AttendanceRecord, LeaveRequest
from ..auth.user import User
from ..classroom.classroom import Classroom
from ..classroom.timetable import TimeSlot
from ..core.base_manager import BaseManager
from ..core.base_model import BaseModel
from ..core.person import Employee
from ..exceptions import DataStoreError, KindergartenError
from ..finance.invoice import Invoice
from ..finance.settings import FeeSettings
from ..daily.records import DailyLog, Message
from ..reports.submissions import SubmittedReport
from ..health.records import Allergy, HealthRecord
from ..nutrition.meal import Meal, Menu
from ..people.child import Child
from ..people.parent import Parent
from ..teaching.lesson_log import LessonLog
from ..school_calendar import SchoolCalendar

if TYPE_CHECKING:
    from ..system import KindergartenSystem

LOAD_ERRORS = (OSError, KeyError, TypeError, ValueError, AttributeError, IndexError, KindergartenError)


class DataStore:
    VERSION = 2
    PRETTY_FILES = {"settings", "calendar", "meta", "users", "classes", "employees"}  # file nhỏ: thụt lề cho dễ đọc
    KEEP_BACKUPS = 10
    SHRINK_RATIO = 0.5   # số bản ghi giảm quá một nửa -> tự sao lưu trước khi ghi

    def __init__(self, data_dir: str | Path = "data") -> None:
        self.data_dir = Path(data_dir)
        self.backup_dir = self.data_dir / "backups"
        self._digests: dict[str, str] = {}

    # ------------------------------------------------------------------ cấu hình file
    @staticmethod
    def collections(system: "KindergartenSystem") -> dict[str, tuple[BaseManager, Callable[[Any], Any]]]:
        """Tên file -> (manager, hàm tạo đối tượng). Thứ tự = thứ tự nạp."""
        return {
            "users": (system.auth, User.from_dict),
            "employees": (system.employees, Employee.from_dict),
            "children": (system.children, Child.from_dict),
            "parents": (system.parents, Parent.from_dict),
            "classes": (system.classes, Classroom.from_dict),
            "timetable": (system.timetable, TimeSlot.from_dict),
            "health_records": (system.health.records, HealthRecord.from_dict),
            "allergies": (system.health.allergies, Allergy.from_dict),
            "attendance": (system.attendance, AttendanceRecord.from_storage),
            "leave_requests": (system.attendance.leave_requests, LeaveRequest.from_dict),
            "invoices": (system.invoices, Invoice.from_dict),
            "meals": (system.menus.meals, Meal.from_dict),
            "menus": (system.menus, Menu.from_dict),
            "daily_logs": (system.daily.logs, DailyLog.from_dict),
            "messages": (system.daily.messages, Message.from_dict),
            "reports": (system.reports, SubmittedReport.from_dict),
            "lesson_logs": (system.lessons, LessonLog.from_dict),
        }

    def path_of(self, name: str) -> Path:
        return self.data_dir / f"{name}.json"

    def has_data(self) -> bool:
        """Có BẤT KỲ file dữ liệu nào thì coi như đã có dữ liệu (L02)."""
        return self.data_dir.exists() and any(self.data_dir.glob("*.json"))

    # ------------------------------------------------------------------ ghi
    def _payload(self, system: "KindergartenSystem") -> dict[str, Any]:
        payload: dict[str, Any] = {"settings": system.settings.to_dict(), "calendar": system.calendar.to_dict(),
                                   "payroll": system.employees.closed_payrolls_to_dict()}
        for name, (manager, _factory) in self.collections(system).items():
            payload[name] = [r.to_row() for r in manager] if name == "attendance" else manager.to_list()
        return payload

    def _dump(self, name: str, data: Any) -> str:
        if name in self.PRETTY_FILES:
            return json.dumps(data, ensure_ascii=False, indent=2)
        return json.dumps(data, ensure_ascii=False, separators=(",", ":"))

    @staticmethod
    def _digest(text: str) -> str:
        return hashlib.sha1(text.encode("utf-8")).hexdigest()

    def save_all(self, system: "KindergartenSystem") -> Path:
        try:
            payload = self._payload(system)
            counts = {name: len(payload[name]) for name in self.collections(system)}
            texts = {name: self._dump(name, data) for name, data in payload.items()}
            meta_core = {"version": self.VERSION, "counts": counts, "counters": BaseModel.counters()}
            meta_text = self._dump("meta", meta_core)
            changed = {name: text for name, text in texts.items()
                       if self._digests.get(name) != self._digest(text) or not self.path_of(name).exists()}
            if not changed and self._digests.get("meta") == self._digest(meta_text):
                return self.data_dir                      # P01: không có gì thay đổi -> không đụng tới đĩa
            self.data_dir.mkdir(parents=True, exist_ok=True)
            self._protect_before_write(counts)
            meta = dict(meta_core, saved_at=datetime.now().isoformat(timespec="seconds"))
            changed["meta"] = self._dump("meta", meta)
            self._write_files(changed)
            for name, text in changed.items():
                self._digests[name] = self._digest(text)
            self._digests["meta"] = self._digest(meta_text)
        except OSError as exc:
            raise DataStoreError(f"Không ghi được dữ liệu vào '{self.data_dir}': {exc}") from exc
        return self.data_dir

    def _protect_before_write(self, counts: dict[str, int]) -> None:
        """Tự sao lưu mỗi ngày ở lần lưu đầu tiên, và trước khi ghi nếu dữ liệu sắp giảm mạnh (L02)."""
        if not any(self.data_dir.glob("*.json")):
            return
        old_total = sum(self.read_meta().get("counts", {}).values())
        new_total = sum(counts.values())
        today = datetime.now().strftime("%Y%m%d")
        has_today = any(p.name.startswith(today) for p in self.list_backup_paths())
        if (old_total >= 10 and new_total < old_total * self.SHRINK_RATIO) or not has_today:
            self.backup(label="tu_dong")

    def _write_files(self, files: dict[str, str]) -> None:
        """Ghi tất cả vào `.saving/` (có fsync) rồi mới đổi tên vào chỗ -> không còn trạng thái nửa cũ nửa mới
        nếu lỗi xảy ra trong lúc ghi (L21)."""
        staging = self.data_dir / ".saving"
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
        staging.mkdir(parents=True)
        try:
            for name, text in files.items():
                with open(staging / f"{name}.json", "w", encoding="utf-8") as file:
                    file.write(text)
                    file.flush()
                    os.fsync(file.fileno())
            for name in files:
                os.replace(staging / f"{name}.json", self.path_of(name))
        finally:
            shutil.rmtree(staging, ignore_errors=True)
        for leftover in self.data_dir.glob("*.json.tmp"):  # file tạm mồ côi của phiên bản cũ
            leftover.unlink(missing_ok=True)

    # ------------------------------------------------------------------ đọc
    def load_all(self, system: "KindergartenSystem") -> bool:
        """Đọc toàn bộ dữ liệu. Trả về False nếu thư mục chưa có file dữ liệu nào."""
        if not self.has_data():
            return False
        if not self.path_of("users").exists():
            raise DataStoreError(f"Thiếu file users.json trong '{self.data_dir}' trong khi các file dữ liệu khác "
                                 "vẫn còn. Hãy khôi phục từ thư mục data/backups/ trước khi chạy tiếp.")
        try:
            meta = self._read_json("meta", {}) or {}
            version = int(meta.get("version", 1))
            if version > self.VERSION:
                raise DataStoreError(f"Dữ liệu được tạo bởi phiên bản mới hơn (định dạng {version}); "
                                     "hãy cập nhật chương trình.")
            settings = self._read_json("settings", None)
            system.reset(FeeSettings.from_dict(settings) if settings else None)
            system.calendar = SchoolCalendar.from_dict(self._read_json("calendar", None))
            system.attendance.calendar = system.calendar
            system.menus.calendar = system.calendar
            for name, (manager, factory) in self.collections(system).items():
                manager.load_list(self._read_json(name, []), factory)
            system.employees.load_closed_payrolls(self._read_json("payroll", {}))
            BaseModel.restore_counters(meta.get("counters", {}))   # L01
            system.after_load()
        except DataStoreError:
            system.reset()
            raise
        except LOAD_ERRORS as exc:
            system.reset()
            raise DataStoreError(f"Dữ liệu trong '{self.data_dir}' bị lỗi, không đọc được: {exc!r}") from exc
        self._digests = {}  # lần lưu đầu sau khi nạp sẽ ghi lại theo định dạng mới nhất
        return True

    def _read_json(self, name: str, default: Any) -> Any:
        path = self.path_of(name)
        if not path.exists():
            return default
        with open(path, encoding="utf-8") as file:
            return json.load(file)

    def read_meta(self) -> dict[str, Any]:
        try:
            return self._read_json("meta", {}) or {}
        except (OSError, ValueError):
            return {}

    # ------------------------------------------------------------------ sao lưu / khôi phục (P07)
    def list_backup_paths(self) -> list[Path]:
        if not self.backup_dir.exists():
            return []
        return sorted(self.backup_dir.glob("*.zip"), reverse=True)

    def list_backups(self) -> list[str]:
        return [p.name for p in self.list_backup_paths()]

    def backup(self, label: str = "") -> Path:
        """Nén các file dữ liệu hiện có thành data/backups/<thời điểm>.zip."""
        files = sorted(self.data_dir.glob("*.json")) + sorted(self.data_dir.glob("*.jsonl"))
        if not files:
            raise DataStoreError("Chưa có dữ liệu để sao lưu.")
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        target = self.backup_dir / f"{stamp}{'_' + label if label else ''}.zip"
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for file in files:
                archive.write(file, file.name)
        self._prune_backups()
        return target

    def _prune_backups(self) -> None:
        """Giữ KEEP_BACKUPS bản mới nhất + bản mới nhất của mỗi tháng cũ hơn."""
        paths = self.list_backup_paths()
        keep = set(paths[: self.KEEP_BACKUPS])
        seen_months: set[str] = set()
        for path in paths:
            month = path.name[:6]
            if month not in seen_months:
                seen_months.add(month)
                keep.add(path)
        for path in paths:
            if path not in keep:
                path.unlink(missing_ok=True)

    def restore(self, name: str, system: "KindergartenSystem") -> Path:
        """Khôi phục từ một bản sao lưu (tự sao lưu hiện trạng trước khi khôi phục)."""
        source = self.backup_dir / name
        if not source.exists():
            raise DataStoreError(f"Không có bản sao lưu '{name}'.")
        current = self.backup(label="truoc_khoi_phuc") if self.has_data() else None
        try:
            with zipfile.ZipFile(source) as archive:
                names = [n for n in archive.namelist() if n.endswith((".json", ".jsonl")) and "/" not in n]
                if "users.json" not in names:
                    raise DataStoreError(f"Bản sao lưu '{name}' không hợp lệ (thiếu users.json).")
                for old in self.data_dir.glob("*.json"):
                    old.unlink()
                for member in names:
                    archive.extract(member, self.data_dir)
        except (OSError, zipfile.BadZipFile) as exc:
            raise DataStoreError(f"Không khôi phục được '{name}': {exc}") from exc
        self.load_all(system)
        return current or source
