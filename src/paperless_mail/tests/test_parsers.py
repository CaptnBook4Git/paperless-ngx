import datetime
import logging
from pathlib import Path
from unittest import mock

import httpx
import pytest
from django.test.html import parse_html
from django.utils import timezone
from pytest_django.fixtures import SettingsWrapper
from pytest_httpx import HTTPXMock
from pytest_mock import MockerFixture

from documents.parsers import ParseError
from paperless_mail.parsers import MailDocumentParser


class TestEmailFileParsing:
    """
    Tests around reading a file and parsing it into a
    MailMessage
    """

    def test_parse_error_missing_file(
        self,
        mail_parser: MailDocumentParser,
        sample_dir: Path,
    ) -> None:
        """
        GIVEN:
            - Fresh parser
        WHEN:
            - A nonexistent file should be parsed
        THEN:
            - An Exception is thrown
        """
        # Check if exception is raised when parsing fails.
        test_file = sample_dir / "doesntexist.eml"

        assert not test_file.exists()

        with pytest.raises(ParseError):
            mail_parser.parse(test_file, "messages/rfc822")

    def test_parse_error_invalid_email(
        self,
        mail_parser: MailDocumentParser,
        broken_email_file: Path,
    ) -> None:
        """
        GIVEN:
            - Fresh parser
        WHEN:
            - A faulty file should be parsed
        THEN:
            - An Exception is thrown
        """
        # Check if exception is raised when the mail is faulty.

        with pytest.raises(ParseError):
            mail_parser.parse(broken_email_file, "messages/rfc822")

    def test_parse_simple_text_email_file(
        self,
        mail_parser: MailDocumentParser,
        simple_txt_email_file: Path,
    ) -> None:
        """
        GIVEN:
            - Fresh parser
        WHEN:
            - A .eml file should be parsed
        THEN:
            - The content of the mail should be available in the parse result.
        """
        # Parse Test file and check relevant content
        parsed_msg = mail_parser.parse_file_to_message(simple_txt_email_file)

        assert parsed_msg.date.year == 2022
        assert parsed_msg.date.month == 10
        assert parsed_msg.date.day == 12
        assert parsed_msg.date.hour == 21
        assert parsed_msg.date.minute == 40
        assert parsed_msg.date.second == 43
        assert parsed_msg.date.tzname() == "UTC+02:00"
        assert parsed_msg.from_ == "mail@someserver.de"
        assert parsed_msg.subject == "Simple Text Mail"
        assert parsed_msg.text == "This is just a simple Text Mail.\n"
        assert parsed_msg.to == ("some@one.de",)


class TestEmailMetadataExtraction:
    """
    Tests extraction of metadata from an email
    """

    def test_extract_metadata_fail(
        self,
        caplog: pytest.LogCaptureFixture,
        mail_parser: MailDocumentParser,
    ) -> None:
        """
        GIVEN:
            - Fresh start
        WHEN:
            - Metadata extraction is triggered for nonexistent file
        THEN:
            - A log warning should be generated
        """
        # Validate if warning is logged when parsing fails
        assert mail_parser.extract_metadata("na", "message/rfc822") == []

        assert len(caplog.records) == 1
        record = caplog.records[0]

        assert record.levelno == logging.WARNING
        assert record.name == "paperless.parsing.mail"
        assert "Error while fetching document metadata for na" in record.message

    def test_extract_metadata(
        self,
        mail_parser: MailDocumentParser,
        simple_txt_email_file: Path,
    ) -> None:
        """
        GIVEN:
            - Fresh start
        WHEN:
            - Metadata extraction is triggered
        THEN:
            - metadata is returned
        """
        # Validate Metadata parsing returns the expected results
        metadata = mail_parser.extract_metadata(simple_txt_email_file, "message/rfc822")

        assert {
            "namespace": "",
            "prefix": "",
            "key": "attachments",
            "value": "",
        } in metadata
        assert {
            "namespace": "",
            "prefix": "",
            "key": "date",
            "value": "2022-10-12 21:40:43 UTC+02:00",
        } in metadata
        assert {
            "namespace": "",
            "prefix": "header",
            "key": "content-language",
            "value": "en-US",
        } in metadata
        assert {
            "namespace": "",
            "prefix": "header",
            "key": "content-type",
            "value": "text/plain; charset=UTF-8; format=flowed",
        } in metadata
        assert {
            "namespace": "",
            "prefix": "header",
            "key": "date",
            "value": "Wed, 12 Oct 2022 21:40:43 +0200",
        } in metadata
        assert {
            "namespace": "",
            "prefix": "header",
            "key": "delivered-to",
            "value": "mail@someserver.de",
        } in metadata
        assert {
            "namespace": "",
            "prefix": "header",
            "key": "from",
            "value": "Some One <mail@someserver.de>",
        } in metadata
        assert {
            "namespace": "",
            "prefix": "header",
            "key": "message-id",
            "value": "<6e99e34d-e20a-80c4-ea61-d8234b612be9@someserver.de>",
        } in metadata
        assert {
            "namespace": "",
            "prefix": "header",
            "key": "mime-version",
            "value": "1.0",
        } in metadata
        assert {
            "namespace": "",
            "prefix": "header",
            "key": "received",
            "value": "from mail.someserver.org ([::1])\n\tby e1acdba3bd07 with LMTP\n\tid KBKZGD2YR2NTCgQAjubtDA\n\t(envelope-from <mail@someserver.de>)\n\tfor <mail@someserver.de>; Wed, 10 Oct 2022 11:40:46 +0200, from [127.0.0.1] (localhost [127.0.0.1]) by localhost (Mailerdaemon) with ESMTPSA id 2BC9064C1616\n\tfor <some@one.de>; Wed, 12 Oct 2022 21:40:46 +0200 (CEST)",
        } in metadata
        assert {
            "namespace": "",
            "prefix": "header",
            "key": "return-path",
            "value": "<mail@someserver.de>",
        } in metadata
        assert {
            "namespace": "",
            "prefix": "header",
            "key": "subject",
            "value": "Simple Text Mail",
        } in metadata
        assert {
            "namespace": "",
            "prefix": "header",
            "key": "to",
            "value": "some@one.de",
        } in metadata
        assert {
            "namespace": "",
            "prefix": "header",
            "key": "user-agent",
            "value": "Mozilla/5.0 (X11; Linux x86_64; rv:102.0) Gecko/20100101\n Thunderbird/102.3.1",
        } in metadata
        assert {
            "namespace": "",
            "prefix": "header",
            "key": "x-last-tls-session-version",
            "value": "TLSv1.3",
        } in metadata


class TestEmailThumbnailGenerate:
    """
    Tests the correct generation of an thumbnail for an email
    """

    def test_get_thumbnail(
        self,
        mocker: MockerFixture,
        mail_parser: MailDocumentParser,
        simple_txt_email_file: Path,
    ) -> None:
        """
        GIVEN:
            - An E-Mail was parsed
        WHEN:
            - The Thumbnail is requested
        THEN:
            - The parser should call the functions which generate the thumbnail
        """
        mocked_return = "Passing the return value through.."
        mock_make_thumbnail_from_pdf = mocker.patch(
            "paperless_mail.parsers.make_thumbnail_from_pdf",
        )
        mock_make_thumbnail_from_pdf.return_value = mocked_return

        mock_generate_pdf = mocker.patch(
            "paperless_mail.parsers.MailDocumentParser.generate_pdf",
        )
        mock_generate_pdf.return_value = "Mocked return value.."

        thumb = mail_parser.get_thumbnail(simple_txt_email_file, "message/rfc822")

        mock_generate_pdf.assert_called_once()
        mock_make_thumbnail_from_pdf.assert_called_once_with(
            "Mocked return value..",
            mail_parser.tempdir,
            None,
        )

        assert mocked_return == thumb


class TestTikaHtmlParse:
    def test_tika_parse_unsuccessful(
        self,
        httpx_mock: HTTPXMock,
        mail_parser: MailDocumentParser,
    ) -> None:
        """
        GIVEN:
            - Fresh start
        WHEN:
            - tika parsing fails
        THEN:
            - the parser should return an empty string
        """
        # Check unsuccessful parsing
        httpx_mock.add_response(
            json={"Content-Type": "text/html", "X-TIKA:Parsed-By": []},
        )
        parsed = mail_parser.tika_parse("None")
        assert parsed == ""

    def test_tika_parse(
        self,
        httpx_mock: HTTPXMock,
        mail_parser: MailDocumentParser,
    ) -> None:
        """
        GIVEN:
            - Fresh start
        WHEN:
            - tika parsing is called
        THEN:
            - a web request to tika shall be done and the reply es returned
        """
        html = '<html><head><meta http-equiv="content-type" content="text/html; charset=UTF-8"></head><body><p>Some Text</p></body></html>'
        expected_text = "Some Text"

        httpx_mock.add_response(
            json={
                "Content-Type": "text/html",
                "X-TIKA:Parsed-By": [],
                "X-TIKA:content": expected_text,
            },
        )
        parsed = mail_parser.tika_parse(html)
        assert expected_text == parsed.strip()
        assert "http://localhost:9998" in str(httpx_mock.get_request().url)

    def test_tika_parse_exception(
        self,
        httpx_mock: HTTPXMock,
        mail_parser: MailDocumentParser,
    ) -> None:
        """
        GIVEN:
            - Fresh start
        WHEN:
            - tika parsing is called and an exception is thrown on the request
        THEN:
            - a ParseError Exception is thrown
        """
        html = '<html><head><meta http-equiv="content-type" content="text/html; charset=UTF-8"></head><body><p>Some Text</p></body></html>'

        httpx_mock.add_response(status_code=httpx.codes.INTERNAL_SERVER_ERROR)

        with pytest.raises(ParseError):
            mail_parser.tika_parse(html)

    def test_tika_parse_unreachable(
        self,
        settings: SettingsWrapper,
        mail_parser: MailDocumentParser,
    ) -> None:
        """
        GIVEN:
            - Fresh start
        WHEN:
            - tika parsing is called but tika is not available
        THEN:
            - a ParseError Exception is thrown
        """
        html = '<html><head><meta http-equiv="content-type" content="text/html; charset=UTF-8"></head><body><p>Some Text</p></body></html>'

        # Check if exception is raised when Tika cannot be reached.
        with pytest.raises(ParseError):
            settings.TIKA_ENDPOINT = "http://does-not-exist:9998"
            mail_parser.tika_parse(html)


class TestParser:
    def test_parse_eml_simple(
        self,
        mocker: MockerFixture,
        mail_parser: MailDocumentParser,
        simple_txt_email_file: Path,
    ) -> None:
        """
        GIVEN:
            - Fresh start
        WHEN:
            - parsing is done with non html mail
        THEN:
            - parsed information is available
        """
        # Validate parsing returns the expected results
        mock_generate_pdf = mocker.patch(
            "paperless_mail.parsers.MailDocumentParser.generate_pdf",
        )

        mail_parser.parse(simple_txt_email_file, "message/rfc822")
        text_expected = (
            "Subject: Simple Text Mail\n\n"
            "From: Some One <mail@someserver.de>\n\n"
            "To: some@one.de\n\n"
            "CC: asdasd@æsdasd.de, asdadasdasdasda.asdasd@æsdasd.de\n\n"
            "BCC: fdf@fvf.de\n\n"
            "\n\nThis is just a simple Text Mail."
        )
        assert text_expected == mail_parser.text
        assert (
            datetime.datetime(
                2022,
                10,
                12,
                21,
                40,
                43,
                tzinfo=datetime.timezone(datetime.timedelta(seconds=7200)),
            )
            == mail_parser.date
        )

        # Just check if tried to generate archive, the unittest for generate_pdf() goes deeper.
        mock_generate_pdf.assert_called()

    def test_parse_eml_html(
        self,
        mocker: MockerFixture,
        httpx_mock: HTTPXMock,
        mail_parser: MailDocumentParser,
        html_email_file: Path,
    ) -> None:
        """
        GIVEN:
            - Fresh start
        WHEN:
            - parsing is done with html mail
        THEN:
            - Tika is called, parsed information from non html parts is available
        """

        mock_generate_pdf = mocker.patch(
            "paperless_mail.parsers.MailDocumentParser.generate_pdf",
        )

        # Validate parsing returns the expected results
        text_expected = (
            "Subject: HTML Message\n\n"
            "From: Name <someone@example.de>\n\n"
            "To: someone@example.de\n\n"
            "Attachments: IntM6gnXFm00FEV5.png (6.89 KiB), 600+kbfile.txt (600.24 KiB)\n\n"
            "HTML content: tika return\n\n"
            "Some Text and an embedded image."
        )

        httpx_mock.add_response(
            json={
                "Content-Type": "text/html",
                "X-TIKA:Parsed-By": [],
                "X-TIKA:content": "tika return",
            },
        )

        mail_parser.parse(html_email_file, "message/rfc822")

        mock_generate_pdf.assert_called_once()
        assert text_expected == mail_parser.text
        assert (
            datetime.datetime(
                2022,
                10,
                15,
                11,
                23,
                19,
                tzinfo=datetime.timezone(datetime.timedelta(seconds=7200)),
            )
            == mail_parser.date
        )

    def test_generate_pdf_parse_error(
        self,
        httpx_mock: HTTPXMock,
        mail_parser: MailDocumentParser,
        simple_txt_email_file: Path,
    ) -> None:
        """
        GIVEN:
            - Fresh start
        WHEN:
            - pdf generation is requested but gotenberg fails
        THEN:
            - a ParseError Exception is thrown
        """
        httpx_mock.add_response(status_code=httpx.codes.INTERNAL_SERVER_ERROR)

        with pytest.raises(ParseError):
            mail_parser.parse(simple_txt_email_file, "message/rfc822")

    def test_generate_pdf_simple_email(
        self,
        httpx_mock: HTTPXMock,
        mail_parser: MailDocumentParser,
        simple_txt_email_file: Path,
        simple_txt_email_pdf_file: Path,
    ) -> None:
        """
        GIVEN:
            - Simple text email with no HTML content
        WHEN:
            - Email is parsed
        THEN:
            - Gotenberg is called to generate a PDF from HTML
            - Archive file is generated
        """

        httpx_mock.add_response(
            url="http://localhost:3000/forms/chromium/convert/html",
            method="POST",
            content=simple_txt_email_pdf_file.read_bytes(),
        )

        mail_parser.parse(simple_txt_email_file, "message/rfc822")

        assert mail_parser.archive_path is not None

    @pytest.mark.httpx_mock(can_send_already_matched_responses=True)
    def test_generate_pdf_html_email(
        self,
        httpx_mock: HTTPXMock,
        mail_parser: MailDocumentParser,
        html_email_file: Path,
        html_email_pdf_file: Path,
    ) -> None:
        """
        GIVEN:
            - email with HTML content
        WHEN:
            - Email is parsed
        THEN:
            - Gotenberg is called to generate a PDF from HTML
            - Gotenberg is used to merge the two PDFs
            - Archive file is generated
        """
        httpx_mock.add_response(
            url="http://localhost:9998/tika/text",
            method="PUT",
            json={
                "Content-Type": "text/html",
                "X-TIKA:Parsed-By": [],
                "X-TIKA:content": "This is some Tika HTML text",
            },
        )
        httpx_mock.add_response(
            url="http://localhost:3000/forms/chromium/convert/html",
            method="POST",
            content=html_email_pdf_file.read_bytes(),
        )
        httpx_mock.add_response(
            url="http://localhost:3000/forms/pdfengines/merge",
            method="POST",
            content=b"Pretend merged PDF content",
        )
        mail_parser.parse(html_email_file, "message/rfc822")

        assert mail_parser.archive_path is not None

    def test_generate_pdf_html_email_html_to_pdf_failure(
        self,
        httpx_mock: HTTPXMock,
        mail_parser: MailDocumentParser,
        html_email_file: Path,
        html_email_pdf_file: Path,
    ) -> None:
        """
        GIVEN:
            - email with HTML content
        WHEN:
            - Email is parsed
            - Conversion of email HTML content to PDF fails
        THEN:
            - ParseError is raised
        """
        httpx_mock.add_response(
            url="http://localhost:9998/tika/text",
            method="PUT",
            json={
                "Content-Type": "text/html",
                "X-TIKA:Parsed-By": [],
                "X-TIKA:content": "This is some Tika HTML text",
            },
        )
        httpx_mock.add_response(
            url="http://localhost:3000/forms/chromium/convert/html",
            method="POST",
            content=html_email_pdf_file.read_bytes(),
        )
        httpx_mock.add_response(
            url="http://localhost:3000/forms/chromium/convert/html",
            method="POST",
            status_code=httpx.codes.INTERNAL_SERVER_ERROR,
        )
        with pytest.raises(ParseError):
            mail_parser.parse(html_email_file, "message/rfc822")

    @pytest.mark.httpx_mock(can_send_already_matched_responses=True)
    def test_generate_pdf_html_email_merge_failure(
        self,
        httpx_mock: HTTPXMock,
        mail_parser: MailDocumentParser,
        html_email_file: Path,
        html_email_pdf_file: Path,
    ) -> None:
        """
        GIVEN:
            - email with HTML content
        WHEN:
            - Email is parsed
            - Merging of PDFs fails
        THEN:
            - ParseError is raised
        """
        httpx_mock.add_response(
            url="http://localhost:9998/tika/text",
            method="PUT",
            json={
                "Content-Type": "text/html",
                "X-TIKA:Parsed-By": [],
                "X-TIKA:content": "This is some Tika HTML text",
            },
        )
        httpx_mock.add_response(
            url="http://localhost:3000/forms/chromium/convert/html",
            method="POST",
            content=html_email_pdf_file.read_bytes(),
        )
        httpx_mock.add_response(
            url="http://localhost:3000/forms/pdfengines/merge",
            method="POST",
            status_code=httpx.codes.INTERNAL_SERVER_ERROR,
        )
        with pytest.raises(ParseError):
            mail_parser.parse(html_email_file, "message/rfc822")

    def test_mail_to_html(
        self,
        mail_parser: MailDocumentParser,
        html_email_file: Path,
        html_email_html_file: Path,
    ) -> None:
        """
        GIVEN:
            - Email message with HTML content
        WHEN:
            - Email is parsed
        THEN:
            - Resulting HTML is as expected
        """
        with timezone.override("UTC"):
            mail = mail_parser.parse_file_to_message(html_email_file)
            html_file = mail_parser.mail_to_html(mail)

            expected_html = parse_html(html_email_html_file.read_text())
            actual_html = parse_html(html_file.read_text())

            assert expected_html == actual_html

    def test_generate_pdf_from_mail(
        self,
        httpx_mock: HTTPXMock,
        mail_parser: MailDocumentParser,
        html_email_file: Path,
    ) -> None:
        """
        GIVEN:
            - Email message with HTML content
        WHEN:
            - Email is parsed
        THEN:
            - Gotenberg is used to convert HTML to PDF
        """

        httpx_mock.add_response(content=b"Content")

        mail = mail_parser.parse_file_to_message(html_email_file)

        retval = mail_parser.generate_pdf_from_mail(mail)
        assert retval.read_bytes() == b"Content"

        request = httpx_mock.get_request()

        assert str(request.url) == "http://localhost:3000/forms/chromium/convert/html"

    def test_merge_pdfs(
        self,
        httpx_mock: HTTPXMock,
        mail_parser: MailDocumentParser,
        merged_pdf_first: Path,
        merged_pdf_second: Path,
    ) -> None:
        """
        GIVEN:
            - Two source PDFs
        WHEN:
            - A merge is requested
        THEN:
            - Gotenberg merges the PDFs and returns the merged file path
        """

        httpx_mock.add_response(
            url="http://localhost:3000/forms/pdfengines/merge",
            method="POST",
            content=b"Pretend merged PDF content",
        )

        retval = mail_parser.merge_pdfs([merged_pdf_first, merged_pdf_second])

        assert retval.read_bytes() == b"Pretend merged PDF content"
        request = httpx_mock.get_request()

        assert str(request.url) == "http://localhost:3000/forms/pdfengines/merge"

    @pytest.mark.httpx_mock(can_send_already_matched_responses=True)
    @mock.patch("gotenberg_client._merge.routes.SyncMergePdfsRoute.merge")
    @mock.patch("paperless_mail.models.MailRule.objects.get")
    def test_generate_pdf_layout_options(
        self,
        mock_mailrule_get: mock.Mock,
        mock_merge_route: mock.Mock,
        httpx_mock: HTTPXMock,
        mail_parser: MailDocumentParser,
        html_email_file: Path,
        html_email_pdf_file: Path,
    ) -> None:
        """
        GIVEN:
            - Email message
        WHEN:
            - Email is parsed with different layout options
        THEN:
            - Gotenberg is called with the correct layout option
        """
        httpx_mock.add_response(
            url="http://localhost:9998/tika/text",
            method="PUT",
            json={
                "Content-Type": "text/html",
                "X-TIKA:Parsed-By": [],
                "X-TIKA:content": "This is some Tika HTML text",
            },
        )
        httpx_mock.add_response(
            url="http://localhost:3000/forms/chromium/convert/html",
            method="POST",
            content=html_email_pdf_file.read_bytes(),
        )
        httpx_mock.add_response(
            url="http://localhost:3000/forms/pdfengines/merge",
            method="POST",
            content=b"Pretend merged PDF content",
        )

        def test_layout_option(layout_option, expected_calls, expected_pdf_names):
            mock_mailrule_get.return_value = mock.Mock(pdf_layout=layout_option)
            mail_parser.parse(
                document_path=html_email_file,
                mime_type="message/rfc822",
                mailrule_id=1,
            )
            args, _ = mock_merge_route.call_args
            assert len(args[0]) == expected_calls
            for i, pdf in enumerate(expected_pdf_names):
                assert args[0][i].name == pdf

        # 1 = MailRule.PdfLayout.TEXT_HTML
        test_layout_option(1, 2, ["email_as_pdf.pdf", "html.pdf"])

        # 2 = MailRule.PdfLayout.HTML_TEXT
        test_layout_option(2, 2, ["html.pdf", "email_as_pdf.pdf"])

        # 3 = MailRule.PdfLayout.HTML_ONLY
        test_layout_option(3, 1, ["html.pdf"])

        # 4 = MailRule.PdfLayout.TEXT_ONLY
        test_layout_option(4, 1, ["email_as_pdf.pdf"])

    def test_stage_cid_resources_and_rewrite_html_variants(
        self,
        mail_parser: MailDocumentParser,
        html_email_file: Path,
    ) -> None:
        """
        GIVEN:
            - HTML with multiple CID variants pointing to the same inline attachment
        WHEN:
            - CID resources are staged and HTML is rewritten
        THEN:
            - All CID variants resolve to a local staged resource name
        """
        msg = mail_parser.parse_file_to_message(html_email_file)
        route = mock.Mock()
        tempdir = Path(mail_parser.tempdir)

        html_with_variants = (
            '<img src="CID:part1.pNdUSz0s.D3NqVtPg@example.de">'
            '<img src="cid:<part1.pNdUSz0s.D3NqVtPg@example.de>">'
            '<img src="cid:part1.pNdUSz0s.D3NqVtPg%40example.de">'
        )

        rewritten = mail_parser._stage_cid_resources_and_rewrite_html(
            route,
            tempdir,
            html_with_variants,
            msg.attachments,
        )

        expected_resource_name = "part1pNdUSz0sD3NqVtPgexamplede"
        assert f'src="{expected_resource_name}"' in rewritten
        assert "CID:part1.pNdUSz0s.D3NqVtPg@example.de" not in rewritten
        assert "cid:<part1.pNdUSz0s.D3NqVtPg@example.de>" not in rewritten
        assert "cid:part1.pNdUSz0s.D3NqVtPg%40example.de" not in rewritten

        route.resource.assert_called_once()
        staged_resource = route.resource.call_args.args[0]
        assert staged_resource.name == expected_resource_name
        assert staged_resource.exists()

    def test_stage_cid_resources_ignores_non_matching_cids(
        self,
        mail_parser: MailDocumentParser,
        html_email_file: Path,
    ) -> None:
        """
        GIVEN:
            - HTML with CID references not present in attachments
        WHEN:
            - CID resources are staged and HTML is rewritten
        THEN:
            - Non-matching references are unchanged
        """
        msg = mail_parser.parse_file_to_message(html_email_file)
        route = mock.Mock()
        tempdir = Path(mail_parser.tempdir)

        original_html = '<img src="cid:not-found@example.de">'

        rewritten = mail_parser._stage_cid_resources_and_rewrite_html(
            route,
            tempdir,
            original_html,
            msg.attachments,
        )

        assert rewritten == original_html
        route.resource.assert_called_once()

    def test_stage_resources_rewrites_content_location_reference(
        self,
        mail_parser: MailDocumentParser,
    ) -> None:
        """
        GIVEN:
            - Attachment with a content-location
        WHEN:
            - HTML src references that content-location path
        THEN:
            - The src URL is rewritten to the staged local resource name
        """
        route = mock.Mock()
        tempdir = Path(mail_parser.tempdir)

        attachment = mock.Mock(
            content_id=None,
            content_location="https://example.invalid/assets/mail/logo.png",
            filename="logo.png",
            payload=b"inline-image",
        )

        rewritten = mail_parser._stage_cid_resources_and_rewrite_html(
            route,
            tempdir,
            '<img src="https://example.invalid/assets/mail/logo.png">',
            [attachment],
        )

        staged_resource = route.resource.call_args.args[0]
        assert rewritten == f'<img src="{staged_resource.name}">'
        route.resource.assert_called_once()

    def test_stage_resources_rewrites_filename_reference(
        self,
        mail_parser: MailDocumentParser,
    ) -> None:
        """
        GIVEN:
            - Attachment with a filename alias
        WHEN:
            - HTML src references the filename
        THEN:
            - The src URL is rewritten to the staged local resource name
        """
        route = mock.Mock()
        tempdir = Path(mail_parser.tempdir)

        attachment = mock.Mock(
            content_id=None,
            content_location=None,
            filename="signature-image.jpg",
            payload=b"inline-image",
        )

        rewritten = mail_parser._stage_cid_resources_and_rewrite_html(
            route,
            tempdir,
            '<img src="signature-image.jpg">',
            [attachment],
        )

        staged_resource = route.resource.call_args.args[0]
        assert rewritten == f'<img src="{staged_resource.name}">'
        route.resource.assert_called_once()

    def test_stage_resources_rewrites_srcset_candidates(
        self,
        mail_parser: MailDocumentParser,
    ) -> None:
        """
        GIVEN:
            - Attachment aliases present in srcset candidates
        WHEN:
            - HTML srcset contains matching and non-matching candidates
        THEN:
            - Only matching srcset candidates are rewritten
        """
        route = mock.Mock()
        tempdir = Path(mail_parser.tempdir)

        attachment = mock.Mock(
            content_id=None,
            content_location="/assets/banner@2x.png",
            filename="banner@2x.png",
            payload=b"inline-image",
        )

        rewritten = mail_parser._stage_cid_resources_and_rewrite_html(
            route,
            tempdir,
            '<img srcset="banner@2x.png 2x, https://cdn.example.invalid/banner@3x.png 3x">',
            [attachment],
        )

        staged_resource = route.resource.call_args.args[0]
        expected = (
            f'<img srcset="{staged_resource.name} 2x, '
            'https://cdn.example.invalid/banner@3x.png 3x">'
        )
        assert rewritten == expected
        route.resource.assert_called_once()

    def test_stage_resources_non_match_safety_keeps_external_links(
        self,
        mail_parser: MailDocumentParser,
    ) -> None:
        """
        GIVEN:
            - Attachment aliases that do not match external URLs
        WHEN:
            - HTML contains external src and srcset references
        THEN:
            - Non-matching references remain unchanged
        """
        route = mock.Mock()
        tempdir = Path(mail_parser.tempdir)

        attachment = mock.Mock(
            content_id=None,
            content_location="/assets/local-only.png",
            filename="local-only.png",
            payload=b"inline-image",
        )

        original_html = (
            '<img src="https://example.invalid/unrelated.png" '
            'srcset="https://example.invalid/unrelated.png 1x, '
            'https://example.invalid/unrelated@2x.png 2x">'
        )

        rewritten = mail_parser._stage_cid_resources_and_rewrite_html(
            route,
            tempdir,
            original_html,
            [attachment],
        )

        assert rewritten == original_html
        route.resource.assert_called_once()
