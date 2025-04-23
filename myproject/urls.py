from django.contrib import admin
from django.urls import path
from accounts.views import generar_reporte_pdf, eliminar_isrc, obtener_info_isrc, guardar_match,login_view, redirect_to_matching_tool, actualizar_estado_obra, guardar_match_isrc, update_estado_isrc, matching_tool_table_titulo_autor, matching_tool_table_isrc, matching_tool_list, codigos_isrc_list, insertar_isrc_view, index_view, logout_view, update_estado, conflictos_view, matching_tool_view, actualizar_conflicto, eliminar_conflicto, insertar_informacion_conflicto, liberadas_view, eliminar_liberaciones

urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('', login_view, name='home'),  # Página de inicio redirige al login si no está autenticado
    path('index/', index_view, name='index'),  # Redirige al index si el usuario está autenticado
    path('update-estado/', update_estado, name='update-estado'),
    path('conflictos/', conflictos_view, name='conflictos'),  # Nueva ruta para actualizar estado
    path('actualizar-conflicto/', actualizar_conflicto, name='actualizar-conflicto'),
    path('eliminar-conflicto/', eliminar_conflicto, name='eliminar_conflicto'),
    path('update-estado-conflicto/', actualizar_estado_obra, name='actualizar_estado_obra'),
    path('insertar-informacion-conflicto/', insertar_informacion_conflicto, name='insertar_informacion_conflicto'),
    path('liberadas/', liberadas_view, name='liberadas'),
    path('eliminar-liberaciones/', eliminar_liberaciones, name='eliminar_liberaciones'),
    path('matching-tool/', matching_tool_view, name='matching_tool'),
    path('guardar-match/', guardar_match, name='guardar_match'),
    path('insertar-isrc/', insertar_isrc_view, name='insertar_isrc'),
    #path('codigos-isrc/', redirect_to_matching_tool, name='codigos_isrc_list'),
    path('codigos-isrc/', codigos_isrc_list, name='codigos_isrc_list'),
    path('guardar-match-isrc/', guardar_match_isrc, name='guardar_match_isrc'),
    path('matching-tool-list/', matching_tool_list, name='matching_tool_list'),
    path('matching-tool/titulo-autor/', matching_tool_table_titulo_autor, name='matching_tool_table_titulo_autor'),
    path('matching-tool/isrc/', matching_tool_table_isrc, name='matching_tool_table_isrc'),
    path('update-estado-isrc/', update_estado_isrc, name='update_estado_isrc'),
    path('reporte/', generar_reporte_pdf, name='reporte'),
    path('obtener-info-isrc/<int:id_isrc>/', obtener_info_isrc, name='obtener_info_isrc'),
    path('eliminar-isrc/<int:id_isrc>/', eliminar_isrc, name='eliminar_isrc'),
]




