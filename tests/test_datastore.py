"""Kiểm thử DataStore lưu/đọc JSON (T30) và dữ liệu mẫu (T31)."""
import pytest

from kindergarten.auth.user import Role
from kindergarten.exceptions import DataStoreError
from kindergarten.people.child import Child
from kindergarten.storage.datastore import DataStore
from kindergarten.system import KindergartenSystem


def test_seed_data_matches_requirements(seeded):
    assert len(seeded.children) == 20 and len(seeded.employees.teachers()) == 5 and len(seeded.classes) == 3
    assert all(1 <= c.age <= 6 for c in seeded.children)
    assert seeded.auth.find_by_username("admin").role is Role.ADMIN


def test_save_and_load_roundtrip(seeded):
    data_dir = seeded.save()
    files = {p.name for p in data_dir.glob("*.json")}
    assert {"children.json", "invoices.json", "settings.json", "meta.json"} <= files
    other = KindergartenSystem(data_dir)
    assert other.load() is True
    for name, (manager, _factory) in DataStore.collections(seeded).items():
        assert len(DataStore.collections(other)[name][0]) == len(manager), name
    child = other.children.get("C001")
    assert child.class_id and other.classes.get(child.class_id).has_child("C001")
    assert other.parents.parents_of("C001")
    assert other.employees.get("T001").calculate_salary() == seeded.employees.get("T001").calculate_salary()
    assert other.invoices.total_debt() == seeded.invoices.total_debt()
    assert other.auth.login("admin", "admin123").role is Role.ADMIN


def test_ids_continue_after_load(seeded, dob_for):
    seeded.save()
    other = KindergartenSystem(seeded.store.data_dir)
    other.load()
    assert other.children.add(Child("Bé Mới Vào", dob_for(3), "Nam")).id == "C021"


def test_load_empty_and_corrupt(tmp_path):
    assert KindergartenSystem(tmp_path / "empty").load() is False
    broken = tmp_path / "broken"
    broken.mkdir()
    (broken / "users.json").write_text("{không phải json", encoding="utf-8")
    with pytest.raises(DataStoreError):
        KindergartenSystem(broken).load()
