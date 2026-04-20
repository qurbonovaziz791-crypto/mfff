from django import forms

from .models import CharityCase, CharityComplaint


class CharityCaseForm(forms.ModelForm):
    class Meta:
        model = CharityCase
        fields = (
            "title",
            "slug",
            "status",
            "category",
            "teaser",
            "body",
            "video",
            "poster",
            "region",
            "district",
            "latitude",
            "longitude",
            "address",
            "contact_phone",
            "payment_info",
            "payment_click_url",
            "payment_payme_url",
            "payment_other_label",
            "payment_other_url",
            "goal_amount",
            "collected_amount",
            "is_publicly_verified",
            "sort_order",
            "verified_note",
        )
        widgets = {
            "title": forms.TextInput(
                attrs={"class": "mf-field-input", "autocomplete": "off", "maxlength": "200"}
            ),
            "slug": forms.TextInput(
                attrs={
                    "class": "mf-field-input",
                    "autocomplete": "off",
                    "placeholder": "Bo‘sh qoldiring — URL avtomatik",
                }
            ),
            "status": forms.Select(attrs={"class": "mf-field-select"}),
            "category": forms.Select(attrs={"class": "mf-field-select"}),
            "teaser": forms.TextInput(attrs={"class": "mf-field-input", "maxlength": "280"}),
            "body": forms.Textarea(attrs={"class": "mf-field-textarea", "rows": 10}),
            "video": forms.ClearableFileInput(
                attrs={"class": "hy-charity-form__file", "accept": "video/*"}
            ),
            "poster": forms.ClearableFileInput(
                attrs={"class": "hy-charity-form__file", "accept": "image/*"}
            ),
            "region": forms.Select(attrs={"class": "mf-field-select"}),
            "district": forms.TextInput(attrs={"class": "mf-field-input", "maxlength": "120"}),
            "latitude": forms.HiddenInput(),
            "longitude": forms.HiddenInput(),
            "address": forms.Textarea(attrs={"class": "mf-field-textarea", "rows": 3, "id": "id_address"}),
            "contact_phone": forms.TextInput(
                attrs={"class": "mf-field-input", "autocomplete": "tel", "maxlength": "32"}
            ),
            "payment_info": forms.Textarea(attrs={"class": "mf-field-textarea", "rows": 3}),
            "payment_click_url": forms.URLInput(
                attrs={
                    "class": "mf-field-input",
                    "placeholder": "https://my.click.uz/...",
                    "autocomplete": "off",
                }
            ),
            "payment_payme_url": forms.URLInput(
                attrs={
                    "class": "mf-field-input",
                    "placeholder": "https://payme.uz/...",
                    "autocomplete": "off",
                }
            ),
            "payment_other_label": forms.TextInput(
                attrs={"class": "mf-field-input", "maxlength": "60", "placeholder": "Masalan: Paynet"}
            ),
            "payment_other_url": forms.URLInput(
                attrs={"class": "mf-field-input", "placeholder": "https://...", "autocomplete": "off"}
            ),
            "goal_amount": forms.NumberInput(
                attrs={"class": "mf-field-input", "min": "0", "step": "1", "placeholder": "Masalan: 5000000"}
            ),
            "collected_amount": forms.NumberInput(
                attrs={"class": "mf-field-input", "min": "0", "step": "1", "placeholder": "Hozirgi yig‘im"}
            ),
            "is_publicly_verified": forms.CheckboxInput(attrs={"class": "hy-charity-form__check"}),
            "sort_order": forms.NumberInput(attrs={"class": "mf-field-input", "min": "0"}),
            "verified_note": forms.TextInput(attrs={"class": "mf-field-input", "maxlength": "200"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["slug"].required = False
        self.fields["video"].required = False
        self.fields["poster"].required = False
        self.fields["payment_info"].required = False
        self.fields["payment_click_url"].required = False
        self.fields["payment_payme_url"].required = False
        self.fields["payment_other_label"].required = False
        self.fields["payment_other_url"].required = False
        self.fields["verified_note"].required = False
        self.fields["goal_amount"].required = False
        self.fields["collected_amount"].required = False
        self.fields["latitude"].required = False
        self.fields["longitude"].required = False


class CharityComplaintForm(forms.ModelForm):
    class Meta:
        model = CharityComplaint
        fields = ("message",)
        widgets = {
            "message": forms.Textarea(
                attrs={
                    "id": "id_complaint_message",
                    "class": "hy-charity-complaint__textarea",
                    "rows": 5,
                    "placeholder": "Qisqa yozing…",
                    "maxlength": "2000",
                    "autocomplete": "off",
                }
            ),
        }

    def clean_message(self):
        text = (self.cleaned_data.get("message") or "").strip()
        if len(text) < 12:
            raise forms.ValidationError("Kamida 12 ta belgi yozing.")
        return text
