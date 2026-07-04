from marshmallow import Schema, fields, validate, validates, validates_schema, ValidationError


class RegisterSchema(Schema):
    email = fields.Email(required=True)
    username = fields.Str(required=True, validate=validate.Length(min=3, max=50))
    password = fields.Str(required=True, validate=validate.Length(min=8), load_only=True)
    first_name = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    last_name = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    phone = fields.Str(required=True, validate=validate.Length(min=10, max=20))
    department = fields.Str(validate=validate.Length(max=100))
    department_id = fields.Str(allow_none=True, load_default=None)
    program_id = fields.Str(allow_none=True, load_default=None)
    student_group_id = fields.Str(allow_none=True, load_default=None)
    staff_id = fields.Str(validate=validate.Length(max=50))
    role_name = fields.Str(load_default="student")
    # University association — provide either university_id OR university_name+code to create
    university_id = fields.Str(allow_none=True, load_default=None)
    university_name = fields.Str(validate=validate.Length(max=200), load_default=None)
    university_code = fields.Str(validate=validate.Length(max=20), load_default=None)

    @validates("password")
    def validate_password(self, value):
        if not any(c.isupper() for c in value):
            raise ValidationError("Password must contain at least one uppercase letter.")
        if not any(c.isdigit() for c in value):
            raise ValidationError("Password must contain at least one digit.")

    @validates_schema
    def validate_registration(self, data, **kwargs):
        if not data.get("phone"):
            raise ValidationError({"phone": ["Phone number is required for all accounts."]})
        if data.get("role_name") == "student" and not data.get("program_id"):
            raise ValidationError(
                {"program_id": ["Program is required for student accounts."]}
            )


class LoginSchema(Schema):
    email = fields.Email(required=True)
    password = fields.Str(required=True, load_only=True)


class TokenSchema(Schema):
    access_token = fields.Str()
    refresh_token = fields.Str()
    token_type = fields.Str()
    expires_in = fields.Int()
    user = fields.Dict()


class RefreshSchema(Schema):
    access_token = fields.Str()
    token_type = fields.Str()
    expires_in = fields.Int()


class PasswordResetRequestSchema(Schema):
    email = fields.Email(required=True)


class PasswordResetSchema(Schema):
    token = fields.Str(required=True)
    password = fields.Str(required=True, validate=validate.Length(min=8), load_only=True)

    @validates("password")
    def validate_password(self, value):
        if not any(c.isupper() for c in value):
            raise ValidationError("Password must contain at least one uppercase letter.")
        if not any(c.isdigit() for c in value):
            raise ValidationError("Password must contain at least one digit.")


class ChangePasswordSchema(Schema):
    current_password = fields.Str(required=True, load_only=True)
    new_password = fields.Str(required=True, validate=validate.Length(min=8), load_only=True)

    @validates("new_password")
    def validate_new_password(self, value):
        if not any(c.isupper() for c in value):
            raise ValidationError("Password must contain at least one uppercase letter.")
        if not any(c.isdigit() for c in value):
            raise ValidationError("Password must contain at least one digit.")


class UserUpdateSchema(Schema):
    email = fields.Email(allow_none=True)
    first_name = fields.Str(validate=validate.Length(min=1, max=100))
    last_name = fields.Str(validate=validate.Length(min=1, max=100))
    phone = fields.Str(validate=validate.Length(min=10, max=25), allow_none=True)
    department = fields.Str(validate=validate.Length(max=100))
    department_id = fields.Str(allow_none=True)
    program_id = fields.Str(allow_none=True)
    student_group_id = fields.Str(allow_none=True)
    registration_number = fields.Str(validate=validate.Length(max=50), allow_none=True)

    @validates("phone")
    def validate_phone(self, value):
        if value and "@" in value:
            raise ValidationError("Phone number cannot contain '@'.")


class StudentCreateSchema(Schema):
    first_name = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    last_name = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    registration_number = fields.Str(required=True, validate=validate.Length(min=2, max=50))
    phone = fields.Str(required=True, validate=validate.Length(min=10, max=25))
    email = fields.Email(allow_none=True)
    department_id = fields.Str(required=True)
    program_id = fields.Str(required=True)
    student_group_id = fields.Str(required=True)

    @validates("phone")
    def validate_phone(self, value):
        if value and "@" in value:
            raise ValidationError("Phone number cannot contain '@'.")


class PortalSessionSchema(Schema):
    university_code = fields.Str(required=True, validate=validate.Length(min=1, max=20))
    registration_number = fields.Str(required=True, validate=validate.Length(min=2, max=50))
    phone_last4 = fields.Str(required=True, validate=validate.Length(equal=4))


class PortalSubscribeSchema(Schema):
    phone = fields.Str(validate=validate.Length(min=10, max=25), allow_none=True)
    email = fields.Email(allow_none=True)

    @validates("phone")
    def validate_phone(self, value):
        if value and "@" in value:
            raise ValidationError("Phone number cannot contain '@'.")
