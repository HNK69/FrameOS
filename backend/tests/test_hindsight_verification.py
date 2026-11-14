from app.services.hindsight import _retained_content_matches


def test_hindsight_fact_is_verified_against_its_source_document():
    document_id = "frameops-retain-test"
    result = {"results": [{
        "document_id": document_id,
        "text": "The client prefers understated music and a warm natural opening for verification.",
    }]}

    assert _retained_content_matches(
        "For this verification, the client prefers understated music and a warm, natural opening.",
        result,
        document_id,
    )


def test_hindsight_fact_from_another_document_does_not_verify_retention():
    result = {"results": [{
        "document_id": "another-client-document",
        "text": "The client prefers understated music and a warm natural opening.",
    }]}

    assert not _retained_content_matches(
        "The client prefers understated music and a warm natural opening.",
        result,
        "frameops-retain-test",
    )
