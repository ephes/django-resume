from resume.models import Person


def test_person_name():
    person = Person(name="John Doe")
    assert str(person) == "John Doe"
