"""
💥 FAULT INJECTION — Document parser resilience tests.

Verifies the parser handles I/O failures gracefully:
- Missing files
- Permission denied
- Corrupt content
- Unsupported formats
"""

import pytest


@pytest.mark.asyncio
async def test_parse_nonexistent_file():
    """Parser raises clear error for missing file."""
    from app.ingestion.parser import parser

    with pytest.raises(ValueError) as exc:
        await parser.parse("/tmp/nonexistent_file_xyz.pdf")
    assert "No such file" in str(exc.value) or "not found" in str(exc.value).lower()


@pytest.mark.asyncio
async def test_parse_unsupported_extension():
    """Parser raises clear error for unsupported format."""
    from app.ingestion.parser import parser

    with pytest.raises(ValueError) as exc:
        await parser.parse("/tmp/test.xyz")
    assert "Unsupported" in str(exc.value)


@pytest.mark.asyncio
async def test_parse_empty_txt(tmp_path):
    """Parser handles empty text file."""
    from app.ingestion.parser import parser

    f = tmp_path / "empty.txt"
    f.write_text("")
    text = await parser.parse(str(f))
    assert text == ""


@pytest.mark.asyncio
async def test_parse_permission_denied(tmp_path):
    """Parser handles permission denied on file."""
    from app.ingestion.parser import parser
    import os

    f = tmp_path / "noaccess.txt"
    f.write_text("test content")
    os.chmod(str(f), 0o000)
    try:
        with pytest.raises(ValueError) as exc:
            await parser.parse(str(f))
        assert "Permission denied" in str(exc.value) or "denied" in str(exc.value).lower()
    finally:
        os.chmod(str(f), 0o644)


@pytest.mark.asyncio
async def test_parse_non_utf8_content(tmp_path):
    """Parser handles non-UTF-8 content gracefully."""
    from app.ingestion.parser import parser

    f = tmp_path / "binary.txt"
    f.write_bytes(b"\xff\xfe\x00\x01\x02\x03")
    text = await parser.parse(str(f))
    assert isinstance(text, str)


@pytest.mark.asyncio
async def test_file_signature_validation():
    """File signature validation rejects mismatched content."""
    from app.ingestion.parser import DocumentParser

    # PDF magic check
    assert DocumentParser.validate_file_signature(b"%PDF-1.4", ".pdf")
    assert not DocumentParser.validate_file_signature(b"not a pdf", ".pdf")

    # DOCX magic check
    assert DocumentParser.validate_file_signature(b"PK\x03\x04", ".docx")
    assert not DocumentParser.validate_file_signature(b"not docx", ".docx")

    # TXT check (rejects binary)
    assert DocumentParser.validate_file_signature(b"hello world", ".txt")
    assert not DocumentParser.validate_file_signature(b"hello\x00world", ".txt")


@pytest.mark.asyncio
async def test_validate_large_file_signature():
    """File signature validation works on large content."""
    from app.ingestion.parser import DocumentParser

    # PDF with extra data before header (some generators do this)
    large = b"\n\n\n\n" + b"%PDF-1.4" + b"x" * 1000
    assert DocumentParser.validate_file_signature(large, ".pdf")

    # PDF with header beyond scan limit
    too_far = b"x" * 200 + b"%PDF-1.4"
    assert not DocumentParser.validate_file_signature(too_far, ".pdf")
