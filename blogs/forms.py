from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils.html import strip_tags
import re
from .models import Kayfiyat
from .storage import VIS_PRIVATE, VIS_UNLISTED, VIS_FOLLOWERS, VIS_PUBLIC

User = get_user_model()

VISIBILITY_CHOICES = [
    (VIS_PRIVATE, "Faqat men"),
    (VIS_UNLISTED, "Faqat havola (profilda boshqalarga ko‘rinmasin)"),
    (VIS_FOLLOWERS, "Faqat yaqinlarim"),
    (VIS_PUBLIC, "Hammaga ochiq"),
]


class PostCreateForm(forms.Form):
    title = forms.CharField(
        max_length=50,
        widget=forms.TextInput(
            attrs={
                "class": "mf-field-input",
                "placeholder": "Masalan: Bugungi kunning eng yaxshi daqiqasi",
                "autocomplete": "off",
            }
        ),
    )
    mood = forms.CharField(
        widget=forms.HiddenInput(attrs={"id": "id_mood"}),
        required=True,
    )
    hashtag = forms.CharField(
        required=False,
        max_length=100,
        widget=forms.TextInput(
            attrs={
                "class": "mf-field-input",
                "placeholder": "#hashtag (ixtiyoriy)",
            }
        ),
    )
    body = forms.CharField(
        max_length=255,
        widget=forms.Textarea(
            attrs={
                "class": "mf-field-textarea",
                "placeholder": "Hozir nima his qilyapsiz? (255 belgigacha)",
                "rows": "4",
                "maxlength": "255",
                "oninput": "updateCharCount(this)",
            }
        ),
    )
    parent = forms.IntegerField(required=False, widget=forms.HiddenInput())
    post_id = forms.IntegerField(required=False, widget=forms.HiddenInput())
    visibility = forms.TypedChoiceField(
        choices=VISIBILITY_CHOICES,
        coerce=int,
        initial=VIS_PRIVATE,
        widget=forms.Select(attrs={"class": "mf-field-select"}),
    )
    collaborators = forms.ModelMultipleChoiceField(
        queryset=User.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={"class": "mf-collab-checkboxes space-y-1"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.is_bound:
            return
        first = (
            Kayfiyat.objects.filter(is_primary=True, is_active=True)
            .order_by("sort_order", "name")
            .values_list("slug", flat=True)
            .first()
        )
        if first and not self.initial.get("mood"):
            self.fields["mood"].initial = first

    def clean_mood(self):
        slug = (self.cleaned_data.get("mood") or "").strip()
        if not slug:
            raise ValidationError("Kayfiyat tanlang.")
        if not Kayfiyat.objects.filter(slug=slug, is_active=True).exists():
            raise ValidationError("Bu kayfiyat mavjud emas yoki o‘chirilgan.")
        return slug

    def clean_body(self):
        """Xavfsizlik va kontent nazorati"""
        body = self.cleaned_data.get('body')
        
        # 1. HTML teglarni tozalash (XSS hujumidan himoya)
        clean_text = strip_tags(body)
        
        # 2. Ortiqcha probellarni olib tashlash
        clean_text = " ".join(clean_text.split())
        
        # 3. Uzunlik tekshiruvi (Backend nazorati)
        if len(clean_text) > 255:
            raise ValidationError("Xabar 255 belgidan oshib ketdi!")
            
        return clean_text

    def clean_hashtag(self):
        """Hashtag formatini tekshirish"""
        hashtag = self.cleaned_data.get('hashtag')
        if hashtag:
            # Bo'shliqlar va maxsus belgilarni tekshirish (faqat # va so'zlar)
            if not re.match(r'^#[\w\d_]+$', hashtag):
                # Agar foydalanuvchi # belgisiz yozgan bo'lsa, o'zimiz qo'shib qo'yamiz
                if not hashtag.startswith('#'):
                    hashtag = f"#{hashtag}"
                # Yana bir bor tekshiramiz
                if " " in hashtag:
                    raise ValidationError("Hashtagda bo'shliq bo'lishi mumkin emas!")
        return hashtag

    def clean_title(self):
        """Sarlavhani tozalash"""
        title = self.cleaned_data.get('title')
        return strip_tags(title).strip()

    def clean_collaborators(self):
        collabs = list(self.cleaned_data.get("collaborators") or [])
        if len(collabs) > 3:
            raise ValidationError("Hammuallif ko‘pi bilan 3 kishi bo‘lishi mumkin.")
        return collabs