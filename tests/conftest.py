"""T33 - Cấu hình chung cho pytest: hệ thống rỗng, hệ thống có dữ liệu mẫu, các hàm tạo dữ liệu nhanh."""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kindergarten.auth.user import User  # noqa: E402
from kindergarten.core.base_model import BaseModel  # noqa: E402
from kindergarten.hr.employees import Teacher  # noqa: E402
from kindergarten.people.child import Child  # noqa: E402
from kindergarten.people.parent import Parent  # noqa: E402
from kindergarten.system import KindergartenSystem  # noqa: E402
from kindergarten.utils import add_months  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_state():
    """Mỗi test bắt đầu với bộ đếm mã mới; giảm số vòng băm mật khẩu cho test chạy nhanh."""
    BaseModel.reset_counters()
    old_iterations = User.HASH_ITERATIONS
    User.HASH_ITERATIONS = 1_000
    yield
    User.HASH_ITERATIONS = old_iterations


@pytest.fixture
def dob_for():
    """Ngày sinh để trẻ/người đủ `years` tuổi `months` tháng tính đến hôm nay."""
    def factory(years: int, months: int = 2) -> date:
        return add_months(date.today(), -(years * 12 + months))
    return factory


@pytest.fixture
def system(tmp_path):
    return KindergartenSystem(tmp_path / "data")


@pytest.fixture
def seeded(system):
    from seed_data import seed
    seed(system)
    return system


@pytest.fixture
def make_child(system, dob_for):
    def factory(name: str = "Nguyễn Văn An", years: int = 4, months: int = 2, gender: str = "Nam", **kwargs) -> Child:
        dob = dob_for(years, months)
        kwargs.setdefault("enrollment_date", max(dob, date.today() - timedelta(days=300)))
        return system.children.add(Child(name, dob, gender, **kwargs))
    return factory


@pytest.fixture
def make_parent(system):
    def factory(name: str, phone: str, relationship: str = "Bố", **kwargs) -> Parent:
        return system.parents.add(Parent(name, "1988-01-15", phone, relationship=relationship, **kwargs))
    return factory


@pytest.fixture
def make_teacher(system):
    def factory(name: str, phone: str, **kwargs) -> Teacher:
        return system.employees.add(Teacher(name, "1990-05-20", phone, **kwargs))
    return factory
