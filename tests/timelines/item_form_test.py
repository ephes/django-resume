from django_resume.plugins.timelines import TimelineItemForm


def test_initial_position(resume):
    # Given a resume and existing items with positions 0 and 1
    existing_items = [{"position": 0}, {"position": 1}]
    # When we create a new form
    form = TimelineItemForm(resume=resume, existing_items=existing_items)
    # Then the initial position should be 2 for the next new item
    assert form.initial["position"] == 2


def test_timeline_item_form_position_invalid(resume):
    form = TimelineItemForm({"position": "invalid"}, resume=resume)
    assert not form.is_valid()
    assert "position" in form.errors


def test_already_set_initial_position(resume):
    # Given a resume and existing items with positions 0 and 1
    existing_items = [{"position": 0}, {"position": 1}]
    # When we create a new form with an initial position
    form = TimelineItemForm(
        initial={"position": 3}, resume=resume, existing_items=existing_items
    )
    # Then the initial position should be 3 for the next new item
    assert form.initial["position"] == 3


def test_invalid_on_taken_position(resume, timeline_item_data):
    # Given a resume and existing items with positions 0 and 1
    existing_items = [{"id": "1", "position": 0}, {"id": "2", "position": 1}]
    # When we try to create a new item with position 1
    timeline_item_data["id"] = "3"
    timeline_item_data["position"] = 1
    form = TimelineItemForm(
        timeline_item_data, resume=resume, existing_items=existing_items
    )
    # Then the form should be invalid
    assert not form.is_valid()
    assert "position" in form.errors


def test_valid_on_taken_position_if_update(resume, timeline_item_data):
    # Given a resume and existing items with positions 0 and 1
    existing_items = [{"id": "1", "position": 0}, {"id": "2", "position": 1}]
    # When we try to update the item with id "2" and same position 1
    timeline_item_data["id"] = "2"
    timeline_item_data["position"] = 1
    form = TimelineItemForm(
        timeline_item_data, resume=resume, existing_items=existing_items
    )
    # Then the form should be valid
    assert form.is_valid()
