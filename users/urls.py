from django.urls import path
from django.views.generic import RedirectView
from . import views

urlpatterns = [
    path("sw.js", views.service_worker_js, name="service_worker_js"),
    path('', views.login_view, name='login'),
    path('auth/<str:lk_uuid>/', views.magic_link_auth, name='magic_link_auth'),
    path('feed/', views.home_feed_view, name='home_feed'),
    path('feed/mark-seen/', views.mark_feed_post_seen_view, name='mark_feed_seen'),
    path("feed/hx/interaction/", views.feed_hx_interaction_view, name="feed_hx_interaction"),
    path("yaqin/action/", views.yaqin_action_view, name="yaqin_action"),
    path("activity/", views.notifications_view, name="activity"),
    path(
        "notifications/",
        RedirectView.as_view(pattern_name="activity", permanent=False),
        name="notifications",
    ),
    path('profile/settings/', views.profile_settings_view, name='profile_settings'),
    path('profile/edit/', views.profile_edit_view, name='profile_edit'),
    path('profile/<str:username>/recap/', views.recap_view, name='recap'),
    path('profile/<str:username>/export/', views.recap_export_txt, name='recap_export'),
    path('tag/<str:tag>/', views.hashtag_explore_view, name='hashtag_explore'),
    path("compose/", views.compose_view, name="compose"),
    path("archive/", views.archive_view, name="archive"),
    path("stats/", views.stats_view, name="stats"),
    path("search/", views.user_search_view, name="user_search"),
    path("xabarlar/", views.dm_inbox_view, name="dm_inbox"),
    path("xabarlar/<str:username>/poll/", views.dm_thread_poll_view, name="dm_thread_poll"),
    path("xabarlar/<str:username>/", views.dm_thread_view, name="dm_thread"),
    path('p/<str:username>/<int:post_id>/', views.post_detail_view, name='post_detail'),
    path('profile/<str:username>/yaqinlar/', views.yaqin_list_view, name='yaqin_list'),
    path('profile/<str:username>/', views.profile_view, name='profile'),
    path('logout/', views.logout_view, name='logout'),
]
