from django.db import connections


def test_sqlite_test_database_uses_django_in_memory_default():
    creation = connections["default"].creation
    test_database_name = creation._get_test_db_name()

    assert creation.is_in_memory_db(test_database_name)
    assert test_database_name != "tests/test_database.sqlite3"
