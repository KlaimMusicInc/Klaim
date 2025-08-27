from django.contrib import admin
from django.urls import path, reverse_lazy
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import user_passes_test
from django.conf import settings


from accounts.views import (
    portal_cliente_home, reporte_avance_view, lyricfind_records, lyricfind_pendientes,
    lyricfind_guardar, lyricfind_omitir, generar_reporte_pdf, eliminar_isrc,
    obtener_info_isrc, guardar_match, login_view, actualizar_estado_obra,
    guardar_match_isrc, update_estado_isrc, matching_tool_table_titulo_autor,
    matching_tool_table_isrc, matching_tool_list, codigos_isrc_list,
    insertar_isrc_view, index_view, logout_view, update_estado, conflictos_view,
    matching_tool_view, actualizar_conflicto, eliminar_conflicto,
    insertar_informacion_conflicto, liberadas_view, eliminar_liberaciones,
    cliente_statements_admin, cliente_statements_panel,
    charts_portal_cliente_admin, charts_portal_cliente_panel,
    cliente_download_statements,           # NUEVA (ya la tenías importada)
    admin_download_statements,             # NUEVA
    is_admin_or_superstaff, is_cliente,    # tests de acceso
)

STAFF_LOGIN = reverse_lazy('portal_cliente_home')

urlpatterns = [
    # ========= Panel ADMIN (deben ir ANTES de 'admin/') =========
    path(
        'admin/panel/charts/',
        staff_member_required(charts_portal_cliente_admin, login_url=STAFF_LOGIN),
        name='charts_portal_cliente_admin'
    ),
    path(
        'admin/panel/download/',
        user_passes_test(is_admin_or_superstaff, login_url=STAFF_LOGIN)(admin_download_statements),
        name='admin_download_statements',
    ),

    # ========= Admin site y auth =========
    path(f"{settings.ADMIN_URL.strip('/')}/", admin.site.urls),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('', login_view, name='home'),

    # ========= Portal cliente =========
    path('portal-cliente/', portal_cliente_home, name='portal_cliente_home'),
    path('portal-cliente/download/', cliente_download_statements, name='cliente_download_statements'),

    # ===== Statements =====
    path('portal-cliente/statements/', cliente_statements_admin, name='cliente_statements'),
    path('portal-cliente/panel/statements/', cliente_statements_panel, name='cliente_statements_panel'),

    # ===== Gráficas =====
    path(
        'portal-cliente/charts/',
        staff_member_required(charts_portal_cliente_admin, login_url=STAFF_LOGIN),
        name='charts_portal_cliente'
    ),
    path('portal-cliente/panel/charts/', charts_portal_cliente_panel, name='charts_portal_cliente_panel'),

    # ===== Back-office (staff_member_required) =====
    path('index/', staff_member_required(index_view, login_url=STAFF_LOGIN), name='index'),
    path('update-estado/', staff_member_required(update_estado, login_url=STAFF_LOGIN), name='update-estado'),

    path('conflictos/', staff_member_required(conflictos_view, login_url=STAFF_LOGIN), name='conflictos'),
    path('actualizar-conflicto/', staff_member_required(actualizar_conflicto, login_url=STAFF_LOGIN), name='actualizar-conflicto'),
    path('eliminar-conflicto/', staff_member_required(eliminar_conflicto, login_url=STAFF_LOGIN), name='eliminar_conflicto'),
    path('insertar-informacion-conflicto/', staff_member_required(insertar_informacion_conflicto, login_url=STAFF_LOGIN), name='insertar_informacion_conflicto'),
    path('update-estado-conflicto/', staff_member_required(actualizar_estado_obra, login_url=STAFF_LOGIN), name='actualizar_estado_obra'),

    path('liberadas/', staff_member_required(liberadas_view, login_url=STAFF_LOGIN), name='liberadas'),
    path('eliminar-liberaciones/', staff_member_required(eliminar_liberaciones, login_url=STAFF_LOGIN), name='eliminar_liberaciones'),

    path('matching-tool/', staff_member_required(matching_tool_view, login_url=STAFF_LOGIN), name='matching_tool'),
    path('guardar-match/', staff_member_required(guardar_match, login_url=STAFF_LOGIN), name='guardar_match'),
    path('insertar-isrc/', staff_member_required(insertar_isrc_view, login_url=STAFF_LOGIN), name='insertar_isrc'),
    path('guardar-match-isrc/', staff_member_required(guardar_match_isrc, login_url=STAFF_LOGIN), name='guardar_match_isrc'),
    path('matching-tool-list/', staff_member_required(matching_tool_list, login_url=STAFF_LOGIN), name='matching_tool_list'),
    path('matching-tool/titulo-autor/', staff_member_required(matching_tool_table_titulo_autor, login_url=STAFF_LOGIN), name='matching_tool_table_titulo_autor'),
    path('matching-tool/isrc/', staff_member_required(matching_tool_table_isrc, login_url=STAFF_LOGIN), name='matching_tool_table_isrc'),
    path('update-estado-isrc/', staff_member_required(update_estado_isrc, login_url=STAFF_LOGIN), name='update_estado_isrc'),

    path('obtener-info-isrc/<int:id_isrc>/', staff_member_required(obtener_info_isrc, login_url=STAFF_LOGIN), name='obtener_info_isrc'),
    path('eliminar-isrc/<int:id_isrc>/', staff_member_required(eliminar_isrc, login_url=STAFF_LOGIN), name='eliminar_isrc'),

    path('reporte-pdf/', staff_member_required(generar_reporte_pdf, login_url=STAFF_LOGIN), name='generar_reporte_pdf'),
    path('reporte-avance/', staff_member_required(reporte_avance_view, login_url=STAFF_LOGIN), name='reporte_avance'),

    path('lyricfind/pendientes/', staff_member_required(lyricfind_pendientes, login_url=STAFF_LOGIN), name='lyricfind_pendientes'),
    path('lyricfind/guardar/<int:audio_id>/', staff_member_required(lyricfind_guardar, login_url=STAFF_LOGIN), name='lyricfind_guardar'),
    path('lyricfind/omitir/<int:audio_id>/', staff_member_required(lyricfind_omitir, login_url=STAFF_LOGIN), name='lyricfind_omitir'),
    path('lyricfind/records/', staff_member_required(lyricfind_records, login_url=STAFF_LOGIN), name='lyricfind_records'),
    path('codigos-isrc/', staff_member_required(codigos_isrc_list, login_url=STAFF_LOGIN), name='codigos_isrc_list'),
]
