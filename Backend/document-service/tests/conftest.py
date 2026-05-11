import sys
import types

import pytest
from flask_jwt_extended import create_access_token

# Some local environments may not have optional runtime deps installed.
# Provide a tiny httpx stub so route imports succeed during unit tests.
if "httpx" not in sys.modules:
    httpx_stub = types.ModuleType("httpx")

    class _StubClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, *args, **kwargs):
            raise RuntimeError("httpx client stub invoked in tests without monkeypatch.")

    httpx_stub.Client = _StubClient
    sys.modules["httpx"] = httpx_stub

if "openpyxl" not in sys.modules:
    openpyxl_stub = types.ModuleType("openpyxl")
    openpyxl_styles_stub = types.ModuleType("openpyxl.styles")
    openpyxl_utils_stub = types.ModuleType("openpyxl.utils")

    class _DummyCell:
        fill = None
        font = None
        alignment = None
        border = None

    class _DummySheet:
        title = "Sheet"
        max_row = 0
        column_dimensions = {}

        def append(self, _row):
            self.max_row += 1

        def cell(self, row=None, column=None):
            return _DummyCell()

    class _Workbook:
        def __init__(self):
            self.active = _DummySheet()

        def save(self, _buffer):
            return None

    class _Style:
        def __init__(self, *args, **kwargs):
            pass

    def _get_column_letter(_col):
        return "A"

    openpyxl_stub.Workbook = _Workbook
    openpyxl_styles_stub.Font = _Style
    openpyxl_styles_stub.PatternFill = _Style
    openpyxl_styles_stub.Alignment = _Style
    openpyxl_styles_stub.Border = _Style
    openpyxl_styles_stub.Side = _Style
    openpyxl_utils_stub.get_column_letter = _get_column_letter
    sys.modules["openpyxl"] = openpyxl_stub
    sys.modules["openpyxl.styles"] = openpyxl_styles_stub
    sys.modules["openpyxl.utils"] = openpyxl_utils_stub

if "qrcode" not in sys.modules:
    qrcode_stub = types.ModuleType("qrcode")

    class _DummyImage:
        def save(self, _buffer, format=None):
            return None

    class _QRCode:
        def __init__(self, *args, **kwargs):
            pass

        def add_data(self, _data):
            return None

        def make(self, fit=True):
            return None

        def make_image(self, fill_color=None, back_color=None):
            return _DummyImage()

    qrcode_stub.QRCode = _QRCode
    sys.modules["qrcode"] = qrcode_stub

if "reportlab" not in sys.modules:
    reportlab_stub = types.ModuleType("reportlab")
    reportlab_lib_stub = types.ModuleType("reportlab.lib")
    reportlab_pagesizes_stub = types.ModuleType("reportlab.lib.pagesizes")
    reportlab_colors_stub = types.ModuleType("reportlab.lib.colors")
    reportlab_styles_stub = types.ModuleType("reportlab.lib.styles")
    reportlab_units_stub = types.ModuleType("reportlab.lib.units")
    reportlab_enums_stub = types.ModuleType("reportlab.lib.enums")
    reportlab_platypus_stub = types.ModuleType("reportlab.platypus")

    def _landscape(value):
        return value

    class _HexColor:
        def __init__(self, _value):
            pass

    class _ParagraphStyle:
        def __init__(self, *args, **kwargs):
            pass

    class _SimpleDocTemplate:
        def __init__(self, *args, **kwargs):
            pass

        def build(self, _story):
            return None

    class _Element:
        def __init__(self, *args, **kwargs):
            pass

    def _get_sample_stylesheet():
        return {"Normal": object()}

    reportlab_pagesizes_stub.A4 = (842, 595)
    reportlab_pagesizes_stub.landscape = _landscape
    reportlab_colors_stub.HexColor = _HexColor
    reportlab_colors_stub.white = object()
    reportlab_colors_stub.lightgrey = object()
    reportlab_styles_stub.getSampleStyleSheet = _get_sample_stylesheet
    reportlab_styles_stub.ParagraphStyle = _ParagraphStyle
    reportlab_units_stub.cm = 1
    reportlab_enums_stub.TA_CENTER = 1
    reportlab_enums_stub.TA_LEFT = 0
    reportlab_platypus_stub.SimpleDocTemplate = _SimpleDocTemplate
    reportlab_platypus_stub.Table = _Element
    reportlab_platypus_stub.TableStyle = _Element
    reportlab_platypus_stub.Paragraph = _Element
    reportlab_platypus_stub.Spacer = _Element
    reportlab_platypus_stub.Image = _Element

    sys.modules["reportlab"] = reportlab_stub
    sys.modules["reportlab.lib"] = reportlab_lib_stub
    sys.modules["reportlab.lib.pagesizes"] = reportlab_pagesizes_stub
    sys.modules["reportlab.lib.colors"] = reportlab_colors_stub
    sys.modules["reportlab.lib.styles"] = reportlab_styles_stub
    sys.modules["reportlab.lib.units"] = reportlab_units_stub
    sys.modules["reportlab.lib.enums"] = reportlab_enums_stub
    sys.modules["reportlab.platypus"] = reportlab_platypus_stub

from app import create_app
from app.extensions import db as _db


@pytest.fixture(scope="session")
def app():
    app = create_app("testing")
    app.config.update(
        JWT_SECRET_KEY="test-jwt-secret-with-at-least-thirty-two-bytes",
        DOCUMENT_SHARE_SECRET="test-document-share-secret-with-at-least-thirty-two-bytes",
        DOCUMENT_SHARE_SALT="test-document-share-salt",
    )
    with app.app_context():
        _db.create_all()
        yield app
        _db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def db(app):
    yield _db
    _db.session.rollback()


@pytest.fixture()
def make_access_token(app):
    def _make(*, role="admin", roles=None, identity="test-user"):
        claims = {}
        if role is not None:
            claims["role"] = role
        if roles is not None:
            claims["roles"] = roles
        with app.app_context():
            return create_access_token(identity=identity, additional_claims=claims)

    return _make
