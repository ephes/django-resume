from django_resume.plugins.tokens import (
    TOKEN_ALPHABET,
    TokenPlugin,
    generate_random_string,
)


def test_generate_random_string_has_requested_length_and_uses_expected_charset():
    generated = generate_random_string(10)

    assert len(generated) == 10
    assert all(character in TOKEN_ALPHABET for character in generated)


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
