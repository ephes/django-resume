from django_resume.timelines import TimelineItemForm


def test_initial_position(person):
    # Given a person and existing items with positions 0 and 1
    existing_items = [{"position": 0}, {"position": 1}]
    # When we create a new form
    form = TimelineItemForm(person=person, existing_items=existing_items)
    # Then the initial position should be 2 for the next new item
    assert form.initial["position"] == 2


def test_already_set_initial_position(person):
    # Given a person and existing items with positions 0 and 1
    existing_items = [{"position": 0}, {"position": 1}]
    # When we create a new form with an initial position
    form = TimelineItemForm(
        initial={"position": 3}, person=person, existing_items=existing_items
    )
    # Then the initial position should be 3 for the next new item
    assert form.initial["position"] == 3


def test_invalid_on_taken_position(person, timeline_item_data):
    # Given a person and existing items with positions 0 and 1
    existing_items = [{"position": 0}, {"position": 1}]
    # When we try to create a new item with position 1
    timeline_item_data["position"] = 1
    form = TimelineItemForm(
        timeline_item_data, person=person, existing_items=existing_items
    )
    # Then the form should be invalid
    assert not form.is_valid()
    assert "position" in form.errors
