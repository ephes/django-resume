from django_resume.plugins.tokens import TokenPlugin


def test_tokens_check_permissions_request_authenticated(resume, rf):
    # Given a request with a authenticated user
    request = rf.get("/")
    request.user = resume.owner

    # When we call the check_permissions method
    permitted_if_none = TokenPlugin.check_permissions(
        request, {"flat": {"token_required": True}}
    )

    # Then the method should return None
    assert permitted_if_none is None
