from marshmallow import Schema, fields, validate, validates, ValidationError


class RegisterSchema(Schema):
    email = fields.Email(required=True)
    username = fields.Str(required=True, validate=validate.Length(min=3, max=50))
    password = fields.Str(required=True, validate=validate.Length(min=8), load_only=True)
    first_name = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    last_name = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    phone = fields.Str(validate=validate.Length(max=20))
    department = fields.Str(validate=validate.Length(max=100))
    staff_id = fields.Str(validate=validate.Length(max=50))
    role_name = fields.Str(load_default="student")

    @validates("password")
    def validate_password(self, value):
        if not any(c.isupper() for c in value):
            raise ValidationError("Password must contain at least one uppercase letter.")
        if not any(c.isdigit() for c in value):
            raise ValidationError("Password must contain at least one digit.")


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
    first_name = fields.Str(validate=validate.Length(min=1, max=100))
    last_name = fields.Str(validate=validate.Length(min=1, max=100))
    phone = fields.Str(validate=validate.Length(max=20))
    department = fields.Str(validate=validate.Length(max=100))
