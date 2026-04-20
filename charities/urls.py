from django.urls import path

from . import views

urlpatterns = [
    path("", views.charity_list_view, name="charity_list"),
    path("qoshish/", views.charity_create_view, name="charity_create"),
    path("<slug:slug>/yangilash/", views.charity_add_update_view, name="charity_add_update"),
    path("<slug:slug>/shikoyat/", views.charity_complaint_view, name="charity_complaint"),
    path("<slug:slug>/tahrirlash/", views.charity_edit_view, name="charity_edit"),
    path("<slug:slug>/", views.charity_detail_view, name="charity_detail"),
]
