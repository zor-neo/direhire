from direhire.ai.sanitizer import sanitize_public_job_description


def test_public_jd_sanitizer_removes_markup_scripts_and_contact_details() -> None:
    result = sanitize_public_job_description(
        """
        <article><h1>Backend Engineer</h1><script>secretNavigation()</script>
        <p>Build APIs with Python.</p><p>Contact jobs@example.com or +66 81 234 5678.</p></article>
        """
    )

    assert "Backend Engineer" in result
    assert "Build APIs with Python." in result
    assert "secretNavigation" not in result
    assert "jobs@example.com" not in result
    assert "+66 81 234 5678" not in result
    assert "[contact email removed]" in result
    assert "[contact phone removed]" in result
