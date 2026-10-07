from django import forms
from django.contrib.auth.forms import PasswordChangeForm


class PortalPasswordChangeForm(PasswordChangeForm):
    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("new_password2")
        if password and self.user.check_password(password):
            self.add_error(
                "new_password2",
                forms.ValidationError("新密碼不可與目前密碼相同。", code="password_unchanged"),
            )
        return cleaned_data
