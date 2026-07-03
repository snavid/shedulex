from app.services.sms_service import _format_beem_error


class TestFormatBeemError:
    def test_parses_json_error_body(self):
        detail = _format_beem_error(
            401,
            '{"code":120,"message":"Invalid Authentication Parameters"}',
        )
        assert detail == "Beem: Invalid Authentication Parameters (401, code 120)"

    def test_parses_nested_data_error_body(self):
        detail = _format_beem_error(
            400,
            '{"data":{"error_code":"API_INVALID_PARAMETER","message":"Invalid Sender ID."}}',
        )
        assert detail == "Beem: Invalid Sender ID. (400, API_INVALID_PARAMETER)"

    def test_falls_back_for_non_json(self):
        detail = _format_beem_error(500, "Internal Server Error")
        assert detail == "Beem SMS failed (HTTP 500)"

    def test_handles_empty_body(self):
        detail = _format_beem_error(401, "")
        assert detail == "Beem SMS failed (HTTP 401)"
