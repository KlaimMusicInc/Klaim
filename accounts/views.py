# ───────────────────────────────────────────────────────────────
# 0. Typing helper para evitar F401 de imports "de referencia"
# ───────────────────────────────────────────────────────────────
# ───────────────────────────────────────────────────────────────
# 1. Librerías estándar
# ───────────────────────────────────────────────────────────────
import json
import logging
import re
import time as _t  # módulo estándar (`_t.time()`)
from collections import defaultdict
from datetime import datetime  # clase `time` → time.min / time.max
from datetime import date, time, timedelta
from decimal import Decimal, InvalidOperation
from functools import wraps
from typing import TYPE_CHECKING

# ───────────────────────────────────────────────────────────────
# 2. Django
# ───────────────────────────────────────────────────────────────
from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.core.mail import send_mail
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db import IntegrityError, transaction
from django.db.models import (
    Count,
    Exists,
    F,
    FloatField,
    OuterRef,
    Prefetch,
    Q,
    Subquery,
    Value,
)
from django.db.models.functions import Coalesce
from django.http import Http404, HttpResponse, HttpResponseNotAllowed, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import NoReverseMatch, reverse, reverse_lazy
from django.utils import timezone
from django.utils.timezone import now
from django.views.decorators.csrf import csrf_exempt

# ───────────────────────────────────────────────────────────────
# 3. ReportLab (PDF generation)
# ───────────────────────────────────────────────────────────────
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

# ───────────────────────────────────────────────────────────────
# 4. Modelos locales
# ───────────────────────────────────────────────────────────────
from .models import (
    Artistas,
    ArtistasUnicos,
    AudiosISRC,
    Catalogos,
    ClienteAccount,
    Clientes,
    CodigosISRC,
    ConflictosPlataforma,
    IsrcLinksAudios,
    LyricfindRegistro,
    MatchingToolISRC,
    MatchingToolTituloAutor,
    MovimientoUsuario,
    Obras,
    ObrasAutores,
    ObrasLiberadas,
    SubidasPlataforma,
)

logger = logging.getLogger(__name__)
# ───────────────────────────────────────────────────────────────
# 2.b Imports SOLO para type hints / referencia (evita F401)
# ───────────────────────────────────────────────────────────────
if TYPE_CHECKING:
    # Django – objetos/módulos que hoy no se usan en tiempo de ejecución
    from django.contrib.auth.models import Group, Permission  # noqa: F401
    from django.core.cache import cache  # noqa: F401
    from django.db import connection, connections, models  # noqa: F401
    from django.db.models.functions import Concat, TruncDate  # noqa: F401
    from django.middleware.csrf import get_token  # noqa: F401
    from django.views.decorators.http import require_GET  # noqa: F401
    from reportlab.pdfgen import canvas  # noqa: F401

    # Modelos locales que hoy no se usan en estas views
    from .models import AutoresUnicos  # noqa: F401
    from .models import LegacyStatementExcel  # noqa: F401
    from .models import RoyaltyStatement  # noqa: F401
    from .models import StatementFile  # noqa: F401


@staff_member_required(login_url=reverse_lazy("portal_cliente_home"))
def reporte_avance_view(request):
    """Dashboard-resumen por cliente."""
    # ────── MÉTRICAS GLOBALES ──────────────────────────────────────────
    totales = {
        "obras": Obras.objects.count(),
        "isrc": CodigosISRC.objects.count(),
        "conflictos": ConflictosPlataforma.objects.count(),
        "matching_isrc": MatchingToolISRC.objects.filter(usos__gt=0).count(),
        "matching_ta": MatchingToolTituloAutor.objects.count(),
        "audio_links": IsrcLinksAudios.objects.filter(activo=True).count(),
    }

    # helper para agrupar <cliente, total>
    def agrupar(qs, campo):
        return (
            qs.values(nombre_cliente=F("obra__catalogo__cliente__nombre_cliente"))
            .annotate(total=Count(campo))
            .order_by("nombre_cliente")
        )

    # ────── POR CLIENTE ────────────────────────────────────────────────
    resumen = defaultdict(
        lambda: {
            "obras": 0,
            "isrc": 0,
            "conflictos": 0,
            "matching_isrc": 0,
            "matching_ta": 0,
            "audio_links": 0,
        }
    )

    # Obras (vía Catálogos)
    for row in Catalogos.objects.values(
        nombre_cliente=F("cliente__nombre_cliente")
    ).annotate(total=Count("obras")):
        resumen[row["nombre_cliente"]]["obras"] = row["total"]

    for qs, campo, key in [
        (CodigosISRC.objects, "id_isrc", "isrc"),
        (ConflictosPlataforma.objects, "id_conflicto", "conflictos"),
        (MatchingToolISRC.objects.filter(usos__gt=0), "id", "matching_isrc"),
        (MatchingToolTituloAutor.objects, "id", "matching_ta"),
        (IsrcLinksAudios.objects.filter(activo=True), "id_isrc_link", "audio_links"),
    ]:
        for row in agrupar(qs, campo):
            resumen[row["nombre_cliente"]][key] = row["total"]

    clientes_stats = [{"cliente": cli, **stats} for cli, stats in resumen.items()]
    clientes_stats.sort(key=lambda d: d["cliente"].lower())

    context = {
        "hoy": timezone.now(),  # ⇒ datetime, ya puedes usar {{ hoy|date:"d/m/Y H:i" }}
        "totales": totales,
        "clientes": clientes_stats,
    }
    return render(request, "reporte_avance.html", context)


@staff_member_required(login_url=reverse_lazy("portal_cliente_home"))
@csrf_exempt
def generar_reporte_pdf(request):
    # ── cabecera del PDF ────────────────────────────────────────────────
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = 'inline; filename="reporte.pdf"'
    doc = SimpleDocTemplate(response, pagesize=letter)
    styles = getSampleStyleSheet()
    elements = []

    fecha_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    elements.append(
        Paragraph(
            f"<b>Reporte de Base de Datos KLAIM</b><br/>Generado el {fecha_str}",
            styles["Title"],
        )
    )
    elements.append(Spacer(1, 18))

    # ── métricas globales ───────────────────────────────────────────────
    total_obras = Obras.objects.count()
    total_isrc = CodigosISRC.objects.count()
    total_conflictos = ConflictosPlataforma.objects.count()
    total_matching_isrc = MatchingToolISRC.objects.filter(usos__gt=0).count()
    total_audio_links = IsrcLinksAudios.objects.filter(activo=True).count()

    # ── métricas por cliente (alias “nombre_cliente” para evitar choques) ─
    def por_cliente(qs, campo_contador):
        return (
            qs.values(nombre_cliente=F("obra__catalogo__cliente__nombre_cliente"))
            .annotate(total=Count(campo_contador))
            .order_by("nombre_cliente")
        )

    obras_por_cliente = por_cliente(
        CodigosISRC.objects.none().values("obra"), "obra"
    )  # truco p/rows vacías
    # realmente Obras→Catalogos es 1-N; usamos Catalogos
    obras_por_cliente = (
        Catalogos.objects.values(nombre_cliente=F("cliente__nombre_cliente"))
        .annotate(total=Count("obras"))
        .order_by("nombre_cliente")
    )

    isrc_por_cliente = por_cliente(CodigosISRC.objects, "id_isrc")
    conflictos_por_cliente = por_cliente(ConflictosPlataforma.objects, "id_conflicto")
    matching_isrc_por_cliente = por_cliente(
        MatchingToolISRC.objects.filter(usos__gt=0), "id"
    )
    audio_links_por_cliente = (
        IsrcLinksAudios.objects.filter(activo=True)
        .values(nombre_cliente=F("obra__catalogo__cliente__nombre_cliente"))
        .annotate(total=Count("id_isrc_link"))
        .order_by("nombre_cliente")
    )

    # ── helper para secciones por cliente ───────────────────────────────
    def bloque(titulo, qs):
        filas = [[f"<b>{titulo}</b>", ""]]
        filas += [[item["nombre_cliente"], item["total"]] for item in qs]
        return filas

    # ── tabla final (una sola) ──────────────────────────────────────────
    data = [
        ["Categoría", "Total"],
        ["Total de obras", total_obras],
        ["Total de ISRC", total_isrc],
        ["Total de conflictos", total_conflictos],
        ["Total matching-ISRC", total_matching_isrc],
        ["Total audio-links activos", total_audio_links],
    ]
    data += bloque("Obras por cliente", obras_por_cliente)
    data += bloque("ISRC por cliente", isrc_por_cliente)
    data += bloque("Conflictos por cliente", conflictos_por_cliente)
    data += bloque("Matching-ISRC por cliente", matching_isrc_por_cliente)
    data += bloque("Audio-links por cliente", audio_links_por_cliente)

    # convertir posibles strings con <b> en Paragraphs
    data = [
        [Paragraph(str(c), styles["BodyText"]) if "<b>" in str(c) else c for c in row]
        for row in data
    ]

    table = Table(data, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#444")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.beige]),
            ]
        )
    )

    elements.append(table)
    doc.build(elements)
    return response


def _post_login_redirect(user, request):
    # respeta ?next=... si venía de @login_required
    nxt = request.GET.get("next") or request.POST.get("next")
    if nxt:
        return nxt
    # clientes (no-staff) -> portal cliente
    if user.groups.filter(name="Cliente").exists() and not user.is_staff:
        try:
            return reverse("portal_cliente_home")
        except NoReverseMatch:
            return "/portal-cliente/"  # fallback si aún no tienes la URL nombrada
    # staff / superstaff / admin -> back-office
    return reverse("index")


def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username", "")
        password = request.POST.get("password", "")
        user = authenticate(request, username=username, password=password)
        if user is not None:
            if not user.is_active:
                messages.error(request, "Tu cuenta está inactiva.")
            else:
                login(request, user)
                return redirect(_post_login_redirect(user, request))
        else:
            messages.error(request, "Usuario o contraseña incorrectos.")
    return render(request, "login.html")


@login_required
def portal_cliente_home(request):
    # Si por error un staff entra aquí, lo enviamos al back-office
    if request.user.is_staff:
        return redirect("index")

    try:
        link = ClienteAccount.objects.select_related("cliente").get(user=request.user)
    except ClienteAccount.DoesNotExist:
        messages.error(
            request, "Tu usuario no está asociado a un cliente. Contacta soporte."
        )
        return redirect("logout")

    # Defaults seguros
    y = now().year
    m = now().month
    q_default = ((m - 1) // 3) + 1  # 1..4

    context = {
        "cliente": link.cliente,
        "anio": int(request.GET.get("anio", y)),
        "q": int(request.GET.get("q", q_default)),
        "derecho": request.GET.get("derecho", "Mecanico"),
        "page_size": int(request.GET.get("page_size", 100)),
    }
    return render(request, "portal_cliente_home.html", context)


@staff_member_required(login_url=reverse_lazy("portal_cliente_home"))
def index_view(request):
    # Obtener parámetros de búsqueda
    titulo = request.GET.get("titulo", "").strip()
    codigo_sgs = request.GET.get("codigo_sgs", "").strip()
    codigo_iswc = request.GET.get("codigo_iswc", "").strip()
    id_catalogo = request.GET.get("id_catalogo", "").strip()
    codigo_klaim = request.GET.get("codigo_klaim", "").strip()
    autor = request.GET.get("autor", "").strip()  # Obtener parámetro 'autor'
    incluir_liberadas = request.GET.get("incluir_liberadas", "") == "on"

    # Filtros dinámicos
    filtros = Q()
    if titulo:
        filtros &= Q(titulo__icontains=titulo)
    if codigo_sgs:
        filtros &= Q(codigo_sgs__icontains=codigo_sgs)
    if codigo_iswc:
        filtros &= Q(codigo_iswc__icontains=codigo_iswc)
    if id_catalogo:
        filtros &= Q(catalogo__id_catalogo=id_catalogo)
    if codigo_klaim:
        filtros &= Q(cod_klaim=codigo_klaim)
    if autor:
        filtros &= Q(
            obrasautores__autor__nombre_autor__icontains=autor
        )  # Filtrar por autor
    if not incluir_liberadas:
        filtros &= ~Q(subidasplataforma__estado_MLC="LIBERADA")

    # Configurar relaciones prefetch
    prefetch_autores = Prefetch(
        "obrasautores_set",
        queryset=ObrasAutores.objects.select_related("autor"),
        to_attr="autores_prefetched",
    )

    prefetch_artistas = Prefetch(
        "artistas_set",
        queryset=Artistas.objects.select_related("artista_unico"),
        to_attr="artistas_prefetched",
    )

    # Query principal
    obras = (
        Obras.objects.filter(filtros)
        .select_related("catalogo", "catalogo__cliente")
        .prefetch_related(prefetch_autores, prefetch_artistas, "subidasplataforma_set")
        .distinct()
    )

    # Paginación
    paginator = Paginator(obras, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # Contexto para la plantilla
    context = {
        "page_obj": page_obj,
        "obras": page_obj.object_list,
        "incluir_liberadas": incluir_liberadas,
    }
    return render(request, "index.html", context)


@staff_member_required(login_url=reverse_lazy("portal_cliente_home"))
@csrf_exempt
def update_estado(request):
    if request.method == "POST":
        data = json.loads(request.body)
        obra_id = data.get("obra_id")
        campo = data.get("campo")
        estado = data.get("estado")

        try:
            # Obtener la obra correspondiente
            obra = Obras.objects.using("default").get(cod_klaim=obra_id)

            # Verificar si se intenta modificar el estado de una obra que está "LIBERADA"
            subida = (
                SubidasPlataforma.objects.using("default").filter(obra=obra).first()
            )
            if subida and (
                subida.estado_MLC == "LIBERADA" or subida.estado_ADREV == "LIBERADA"
            ):
                # Comprobar si existe un registro en ObrasLiberadas
                if (
                    ObrasLiberadas.objects.using("default")
                    .filter(cod_klaim=obra)
                    .exists()
                ):
                    return JsonResponse(
                        {
                            "success": False,
                            "error": "Actualmente existe un registro de liberacion de la obra asociada, si está seguro de que desea modificar este estado, por favor comuníquese con ADMINISTRADOR.",
                        }
                    )

            # Buscar o crear la fila en SubidasPlataforma
            subida, created = SubidasPlataforma.objects.using("default").get_or_create(
                obra=obra, defaults={"estado_MLC": None, "estado_ADREV": None}
            )

            # Actualizar ambos campos si el estado es "LIBERADA"
            tipo_movimiento = (
                "LIBERADA" if estado == "LIBERADA" else f"Estado {campo} actualizado"
            )
            if estado == "LIBERADA":
                subida.estado_MLC = "LIBERADA"
                subida.estado_ADREV = "LIBERADA"

                # Crear el registro en `ObrasLiberadas`
                autores_relacionados = obra.obrasautores_set.all()
                for relacion in autores_relacionados:
                    autor = relacion.autor
                    ObrasLiberadas.objects.using("default").create(
                        cod_klaim=obra,
                        titulo=obra.titulo,
                        codigo_sgs=obra.codigo_sgs,
                        codigo_iswc=obra.codigo_iswc,
                        id_cliente=obra.catalogo.cliente,
                        nombre_autor=autor.nombre_autor,
                        porcentaje_autor=relacion.porcentaje_autor,
                        fecha_creacion=date.today(),
                    )
            else:
                # Actualizar el campo correspondiente (estado_MLC o estado_ADREV)
                if campo == "estado_MLC":
                    subida.estado_MLC = estado
                elif campo == "estado_ADREV":
                    subida.estado_ADREV = estado

            # Guardar cambios en la base de datos
            subida.save()
            logger.debug("Movimiento detectado: %s", tipo_movimiento)
            MovimientoUsuario.objects.create(
                usuario=request.user,
                obra=obra,
                tipo_movimiento=estado,  # Guarda el estado seleccionado ("LIBERADA", "OK", "NO CARGADA", "CONFLICTO")
            )

            return JsonResponse({"success": True})
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})

    return JsonResponse({"success": False, "error": "Método no permitido"})


@staff_member_required(login_url=reverse_lazy("portal_cliente_home"))
def conflictos_view(request):
    # ───── Querysets base ─────────────────────────────────────────────
    qs_mlc = (
        Obras.objects.filter(subidasplataforma__estado_MLC="Conflicto")
        .select_related("catalogo__cliente")
        .prefetch_related(
            "obrasautores_set__autor", "subidasplataforma_set", "conflictos"
        )
        .distinct()
    )

    qs_adrev = (
        Obras.objects.filter(subidasplataforma__estado_ADREV="Conflicto")
        .select_related("catalogo__cliente")
        .prefetch_related(
            "obrasautores_set__autor", "subidasplataforma_set", "conflictos"
        )
        .distinct()
    )

    # ───── Paginadores (20 registros) ─────────────────────────────────
    pag_mlc = Paginator(qs_mlc, 20)
    pag_adrev = Paginator(qs_adrev, 20)

    num_mlc = request.GET.get("page_mlc")
    num_adrev = request.GET.get("page_adrev")

    page_obj_mlc = pag_mlc.get_page(num_mlc)
    page_obj_adrev = pag_adrev.get_page(num_adrev)

    context = {
        "conflictos_mlc": page_obj_mlc.object_list,
        "conflictos_adrev": page_obj_adrev.object_list,
        "page_obj_mlc": page_obj_mlc,
        "page_obj_adrev": page_obj_adrev,
    }
    return render(request, "conflictos.html", context)


@staff_member_required(login_url=reverse_lazy("portal_cliente_home"))
@csrf_exempt
def actualizar_conflicto(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Método no permitido"})

    try:
        data = json.loads(request.body)

        obras_ids = data.get("obras")
        nombre_contraparte = (data.get("nombre_contraparte") or "").strip()
        porcentaje_contraparte = (data.get("porcentaje_contraparte") or "").strip()
        informacion_adicional = (data.get("informacion_adicional") or "").strip()
        plataforma = data.get("plataforma")
        enviar_correo = data.get("enviar_correo", False)

        # ---------  VALIDACIÓN DE CAMPOS  ---------
        if (
            not obras_ids
            or not nombre_contraparte
            or not porcentaje_contraparte
            or not informacion_adicional
            or not plataforma
        ):
            return JsonResponse(
                {
                    "success": False,
                    "error": "Todos los campos (obras, contraparte, porcentaje, acciones y plataforma) son obligatorios.",
                }
            )

        for obra_id in obras_ids:
            obra = Obras.objects.using("default").get(cod_klaim=obra_id)
            cliente = obra.catalogo.cliente

            # No permitir más de un conflicto vigente por plataforma
            if (
                ConflictosPlataforma.objects.using("default")
                .filter(obra=obra, plataforma=plataforma, estado_conflicto="vigente")
                .exists()
            ):
                return JsonResponse(
                    {
                        "success": False,
                        "error": f'Ya existe un conflicto vigente para "{obra.titulo}" en {plataforma}. Finalícelo antes de crear uno nuevo.',
                    }
                )

            nuevo_conflicto = ConflictosPlataforma.objects.using("default").create(
                obra=obra,
                nombre_contraparte=nombre_contraparte,
                porcentaje_contraparte=porcentaje_contraparte,
                informacion_adicional=informacion_adicional,
                fecha_conflicto=datetime.now(),
                plataforma=plataforma,
                estado_conflicto="vigente",
            )

            # Registrar movimiento
            MovimientoUsuario.objects.create(
                usuario=request.user, obra=obra, tipo_movimiento="CONFLICTO CREADO"
            )

            # ---------  ENVÍO DE CORREO OPCIONAL  ---------
            if enviar_correo:
                destinatarios = [e.email for e in cliente.emails.all()]
                if not destinatarios:
                    return JsonResponse(
                        {
                            "success": False,
                            "error": f'El cliente "{cliente.nombre_cliente}" no tiene correos registrados.',
                        }
                    )

                codigo_sgs = obra.codigo_sgs
                asunto = "OBRA EN CONFLICTO"
                mensaje = f"""Estimado equipo {cliente.nombre_cliente},

Se ha registrado un nuevo conflicto en la plataforma {plataforma}.

Detalles:
- Código SGS: {codigo_sgs}
- Contraparte: {nombre_contraparte}
- Participación: {porcentaje_contraparte}%
- Acciones tomadas: {informacion_adicional}
- Fecha: {nuevo_conflicto.fecha_conflicto:%Y-%m-%d}

Estado actual: {nuevo_conflicto.estado_conflicto}
"""

                send_mail(
                    asunto,
                    mensaje,
                    settings.EMAIL_HOST_USER,
                    destinatarios,
                    fail_silently=False,
                )

        return JsonResponse({"success": True})

    except Exception as e:
        print(f"Error al crear conflicto: {e}")
        return JsonResponse({"success": False, "error": str(e)})


@staff_member_required(login_url=reverse_lazy("portal_cliente_home"))
@csrf_exempt
def insertar_informacion_conflicto(request):
    """
    Agrega texto extra al conflicto VIGENTE más reciente de cada obra seleccionada.
    (Es el mismo conflicto que luego pintas en el template con
     `{% with ultimo_conflicto = obra.conflictos.last %}`).
    """
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Método no permitido"})

    try:
        data = json.loads(request.body)
        obras_ids = data.get("obras") or []
        informacion_adicional = data.get("informacion_adicional", "").strip()

        if not obras_ids:
            return JsonResponse(
                {"success": False, "error": "No se seleccionaron obras."}
            )
        if not informacion_adicional:
            return JsonResponse(
                {"success": False, "error": "El texto no puede estar vacío."}
            )

        for obra_id in obras_ids:
            # ⇒ el último conflicto VIGENTE de esa obra
            conflicto = (
                ConflictosPlataforma.objects.using("default")
                .filter(obra__cod_klaim=obra_id, estado_conflicto="vigente")
                .order_by("-fecha_conflicto", "-id_conflicto")  # el más reciente
                .first()
            )

            if not conflicto:
                continue  # no hay un conflicto vigente: nada que actualizar

            # Concatenar el nuevo mensaje con separador “ | ”
            if conflicto.informacion_adicional:
                conflicto.informacion_adicional += f" | {informacion_adicional}"
            else:
                conflicto.informacion_adicional = informacion_adicional
            conflicto.save()

            # Guardar el movimiento
            MovimientoUsuario.objects.create(
                usuario=request.user,
                obra=conflicto.obra,
                tipo_movimiento="INSERTÓ ACCIONES",
            )

        return JsonResponse({"success": True})

    except Exception as e:
        print(f"[insertar_informacion_conflicto] {e}")
        return JsonResponse({"success": False, "error": str(e)})


@staff_member_required(login_url=reverse_lazy("portal_cliente_home"))
@csrf_exempt
def eliminar_conflicto(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            obras_ids = data.get("obras")

            if not obras_ids:
                return JsonResponse(
                    {"success": False, "error": "No se seleccionaron obras."}
                )

            for obra_id in obras_ids:
                # Filtrar conflictos activos
                conflictos = ConflictosPlataforma.objects.using("default").filter(
                    obra__cod_klaim=obra_id, estado_conflicto="vigente"
                )

                for conflicto in conflictos:
                    conflicto.estado_conflicto = "finalizado"
                    conflicto.save()

            return JsonResponse({"success": True})
        except Exception as e:
            print(f"Error al actualizar estado de conflicto: {e}")
            return JsonResponse({"success": False, "error": str(e)})

    return JsonResponse({"success": False, "error": "Método no permitido"})


@staff_member_required(login_url=reverse_lazy("portal_cliente_home"))
@csrf_exempt
def actualizar_estado_obra(request):
    """
    • Finaliza el conflicto vigente (ya lo hizo eliminar_conflicto).
    • Actualiza el estado_MLC / estado_ADREV según corresponda.
    • Si el estado elegido es LIBERADA → crea el registro en obras_liberadas.
    • Registra siempre el movimiento del usuario en movimientos_usuario.
    """
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Método no permitido"})

    try:
        data = json.loads(request.body)
        obra_id = data.get("obra_id")
        estado = data.get("estado")  # «OK» o «LIBERADA»
        plataforma = data.get("plataforma")  # «MLC» o «ADREV»
        info_extra = data.get("informacion_adicional")

        if not all([obra_id, estado, plataforma, info_extra]):
            return JsonResponse({"success": False, "error": "Datos incompletos."})

        obra = Obras.objects.using("default").filter(cod_klaim=obra_id).first()
        if not obra:
            return JsonResponse({"success": False, "error": "No se encontró la obra."})

        # ---------- 1. Actualizar estado en subidas_plataforma ----------
        if plataforma == "MLC":
            subida = obra.subidasplataforma_set.filter(estado_MLC="Conflicto").first()
            if not subida:
                return JsonResponse(
                    {
                        "success": False,
                        "error": "No se encontró un registro MLC en conflicto.",
                    }
                )
            subida.estado_MLC = estado
            subida.save()

        elif plataforma == "ADREV":
            subida = obra.subidasplataforma_set.filter(estado_ADREV="Conflicto").first()
            if not subida:
                return JsonResponse(
                    {
                        "success": False,
                        "error": "No se encontró un registro ADREV en conflicto.",
                    }
                )
            subida.estado_ADREV = estado
            subida.save()
        else:
            return JsonResponse({"success": False, "error": "Plataforma no válida."})

        # ---------- 2. Añadir información al último conflicto finalizado ----------
        conflicto = (
            ConflictosPlataforma.objects.using("default")
            .filter(obra=obra, estado_conflicto="finalizado")
            .order_by("-fecha_conflicto")
            .first()
        )
        if conflicto:
            conflicto.informacion_adicional = (
                f"{conflicto.informacion_adicional + ' | ' if conflicto.informacion_adicional else ''}"
                f"{info_extra}"
            )
            conflicto.save()

        # ---------- 3. Si el estado es LIBERADA → insertar en obras_liberadas ----------
        if estado == "LIBERADA":
            from datetime import date

            # Evitar duplicados si ya existe una liberación vigente
            liberada, created = ObrasLiberadas.objects.using("default").get_or_create(
                cod_klaim=obra,  # FK
                defaults={
                    "titulo": obra.titulo,
                    "codigo_sgs": obra.codigo_sgs,
                    "codigo_iswc": obra.codigo_iswc,
                    "id_cliente": obra.catalogo.cliente if obra.catalogo else None,
                    "nombre_autor": ", ".join(
                        oa.autor.nombre_autor for oa in obra.obrasautores_set.all()
                    )
                    or "N/A",
                    "porcentaje_autor": ", ".join(
                        str(oa.porcentaje_autor) for oa in obra.obrasautores_set.all()
                    )
                    or None,
                    "fecha_creacion": date.today(),
                    "estado_liberacion": "vigente",
                },
            )
            # Si ya existía y estaba finalizada, re-activamos
            if not created and liberada.estado_liberacion == "finalizado":
                liberada.estado_liberacion = "vigente"
                liberada.save()

        # ---------- 4. Registrar movimiento del usuario ----------
        MovimientoUsuario.objects.using("default").create(
            usuario=request.user,
            obra=obra,
            tipo_movimiento=f"ESTADO {'LIBERADA' if estado == 'LIBERADA' else 'OK'}",
        )

        return JsonResponse({"success": True})

    except Exception as e:
        print(f"[actualizar_estado_obra] {e}")
        return JsonResponse({"success": False, "error": str(e)})


@staff_member_required(login_url=reverse_lazy("portal_cliente_home"))
def liberadas_view(request):
    # Obtener los parámetros de búsqueda de la URL
    titulo = request.GET.get("titulo", "")
    codigo_iswc = request.GET.get("codigo_iswc", "")
    nombre_autor = request.GET.get("nombre_autor", "")
    id_cliente = request.GET.get("id_cliente", "")

    # Iniciar la consulta base para la tabla ObrasLiberadas
    liberadas_list = ObrasLiberadas.objects.using("default").filter(
        estado_liberacion="vigente"
    )

    # Aplicar filtros
    if titulo:
        liberadas_list = liberadas_list.filter(titulo__icontains=titulo)
    if codigo_iswc:
        liberadas_list = liberadas_list.filter(codigo_iswc=codigo_iswc)
    if nombre_autor:
        liberadas_list = liberadas_list.filter(nombre_autor__icontains=nombre_autor)
    if id_cliente:
        liberadas_list = liberadas_list.filter(
            id_cliente__nombre_cliente__icontains=id_cliente
        )

    # Paginación
    paginator = Paginator(liberadas_list, 10)  # Muestra 10 resultados por página
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # ── NUEVO: preparar listas para la vista (autores y porcentajes) ──
    def _split_sc(s):
        # Solo separa por ';' para no romper decimales con coma.
        return [
            x.strip()
            for x in (s or "").replace("\n", ";").replace("|", ";").split(";")
            if x.strip()
        ]

    for obra in page_obj.object_list:
        obra.autores_list = _split_sc(getattr(obra, "nombre_autor", ""))
        raw_porc = getattr(obra, "porcentaje_autor", "")
        raw_porc = str(raw_porc) if raw_porc is not None else ""
        obra.porcentajes_list = (
            _split_sc(raw_porc)
            if ";" in raw_porc or "|" in raw_porc or "\n" in raw_porc
            else []
        )

    context = {
        "page_obj": page_obj,
        "liberadas": page_obj.object_list,
    }
    return render(request, "liberadas.html", context)


@staff_member_required(login_url=reverse_lazy("portal_cliente_home"))
@csrf_exempt
def eliminar_liberaciones(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            obras_ids = data.get("obras")

            if not obras_ids:
                return JsonResponse(
                    {"success": False, "error": "No se seleccionaron obras."}
                )

            # Cambiar el estado de liberación a "finalizado" en lugar de eliminar
            ObrasLiberadas.objects.using("default").filter(
                id_liberada__in=obras_ids
            ).update(estado_liberacion="finalizado")

            # Obtener los cod_klaim correspondientes a los registros seleccionados
            obras = (
                ObrasLiberadas.objects.using("default")
                .filter(id_liberada__in=obras_ids)
                .values_list("cod_klaim", flat=True)
            )

            # Actualizar el estado_MLC y estado_ADREV a "OK" en la tabla SubidasPlataforma
            SubidasPlataforma.objects.using("default").filter(obra_id__in=obras).update(
                estado_MLC="OK", estado_ADREV="OK"
            )

            # Registrar el movimiento del usuario para cada obra reingresada
            usuario = request.user  # Obtener el usuario actual
            for obra_id in obras:
                MovimientoUsuario.objects.using("default").create(
                    usuario=usuario,
                    obra_id=obra_id,
                    tipo_movimiento="REINGRESO DE OBRA",
                )

            return JsonResponse({"success": True})
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})

    return JsonResponse({"success": False, "error": "Método no permitido"})


@staff_member_required(login_url=reverse_lazy("portal_cliente_home"))
def matching_tool_view(request):
    start_time = _t.time()

    page = int(request.GET.get("page", 1))
    per_page = 10

    subidas = (
        SubidasPlataforma.objects.filter(codigo_MLC__isnull=False)
        .exclude(codigo_MLC__exact="")
        .filter(matching_tool=False)  # ← solo las que SIGUEN pendientes
        .select_related("obra")
        .only("codigo_MLC", "obra__titulo", "obra__cod_klaim", "matching_tool")
        .prefetch_related(
            Prefetch(
                "obra__obrasautores_set",
                queryset=ObrasAutores.objects.select_related("autor").only(
                    "autor__id_autor", "autor__nombre_autor"
                ),
                to_attr="prefetched_autores",
            ),
            Prefetch(
                "obra__artistas_set",
                queryset=Artistas.objects.only("id_artista", "nombre_artista"),
                to_attr="prefetched_artistas",
            ),
        )
    )

    paginator = Paginator(subidas, per_page)
    page_obj = paginator.get_page(page)

    expanded_subidas = []
    for subida in page_obj.object_list:
        obra = subida.obra

        # Autores como LISTA (sin comas)
        autores = [a.autor.nombre_autor for a in obra.prefetched_autores]

        # Artistas: necesitamos también ids únicos → usamos un QS con select_related
        artists_qs = Artistas.objects.filter(obra_id=obra.cod_klaim).select_related(
            "artista_unico"
        )
        artistas_nombres = [a.nombre_artista for a in artists_qs]
        artistas_ids = ",".join(
            str(a.artista_unico.id_artista_unico)
            for a in artists_qs
            if getattr(a.artista_unico, "id_artista_unico", None)
        )

        expanded_subidas.append(
            {
                "obra": obra.titulo,
                "obra_id": obra.cod_klaim,
                "codigo_MLC": subida.codigo_MLC,
                "id_subida": subida.id_subida,
                # ↓ ahora listas
                "autores": autores,
                "autor_id": (
                    obra.prefetched_autores[0].autor.id_autor
                    if obra.prefetched_autores
                    else None
                ),
                "artistas": artistas_nombres,
                "artistas_ids": artistas_ids,
                "matching_tool": subida.matching_tool,
            }
        )

    print("matching_tool_view →", _t.time() - start_time, "s")

    return render(
        request,
        "matching_tool.html",
        {"subidas": expanded_subidas, "page_obj": page_obj},
    )


# ╔════════════════════════════════════════════════════════════╗
# ║ 2.  GUARDAR MATCH  (Título-Autor)                          ║
# ╚════════════════════════════════════════════════════════════╝
@staff_member_required(login_url=reverse_lazy("portal_cliente_home"))
@csrf_exempt
def guardar_match(request):
    if request.method != "POST":
        return JsonResponse({"error": "Método no permitido"}, status=405)

    try:
        data = json.loads(request.body)
        obra_id = data.get("obra_id")
        autor_id = data.get("autor_id")
        codigo_mlc_id = data.get("codigo_mlc_id")
        artista_ids = data.get("artista_ids", [])
        usos = data.get("usos")

        if not (obra_id and autor_id and codigo_mlc_id and usos is not None):
            return JsonResponse({"error": "Datos incompletos"}, status=400)

        with transaction.atomic():
            if not artista_ids:  # sin artistas
                MatchingToolTituloAutor.objects.create(
                    obra_id=obra_id,
                    autor_id=autor_id,
                    codigo_mlc_id=codigo_mlc_id,
                    artista_id=None,
                    usos=usos,
                    estado="Enviado",
                )
            else:  # uno por cada artista
                for art_id in artista_ids:
                    MatchingToolTituloAutor.objects.create(
                        obra_id=obra_id,
                        autor_id=autor_id,
                        codigo_mlc_id=codigo_mlc_id,
                        artista_id=art_id,
                        usos=usos,
                        estado="Enviado",
                    )

            # ⇒ marcar la subida como YA procesada
            SubidasPlataforma.objects.filter(id_subida=codigo_mlc_id).update(
                matching_tool=True
            )

        return JsonResponse({"message": "Registro guardado exitosamente"}, status=201)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


# ╔════════════════════════════════════════════════════════════╗
# ║ 3.  INSERTAR ISRC  (solo añade ISRC, no cierra la subida) ║
# ╚════════════════════════════════════════════════════════════╝
@staff_member_required(login_url=reverse_lazy("portal_cliente_home"))
@csrf_exempt
def insertar_isrc_view(request):
    """
    Inserta un nuevo ISRC y asocia (o crea) el artista único:
    * No genera duplicados en `artistas_unicos` (normaliza y compara `iexact`).
    * No duplica ISRC ya existentes.
    * Si el artista ya está vinculado a la obra, no vuelve a crearlo en `artistas`.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Método no permitido"}, status=405)

    try:
        data = json.loads(request.body)
        isrc_raw = (data.get("isrc") or "").strip().upper()
        artista_raw = (data.get("artista") or "").strip()
        cod_klaim = data.get("cod_klaim")

        if not (isrc_raw and artista_raw and cod_klaim):
            return JsonResponse({"error": "Datos incompletos"}, status=400)

        # Normaliza el nombre del artista (quita espacios extra)
        artista_norm = " ".join(artista_raw.split())

        with transaction.atomic():
            # 1) Buscar artista único sin diferenciar mayúsc./minúsc.
            artista_unico = ArtistasUnicos.objects.filter(
                nombre_artista__iexact=artista_norm
            ).first()
            if not artista_unico:
                artista_unico = ArtistasUnicos.objects.create(
                    nombre_artista=artista_norm
                )

            # 2) Asegurar vínculo obra-artista (tabla `artistas`)
            Artistas.objects.get_or_create(
                obra_id=cod_klaim,
                artista_unico_id=artista_unico.id_artista_unico,
                defaults={"nombre_artista": artista_unico.nombre_artista},
            )

            # 3) Verificar que el ISRC no exista
            if CodigosISRC.objects.filter(codigo_isrc=isrc_raw).exists():
                return JsonResponse(
                    {"error": "Ese ISRC ya está registrado."}, status=400
                )

            # 4) Crear el ISRC
            CodigosISRC.objects.create(
                codigo_isrc=isrc_raw,
                obra_id=cod_klaim,
                id_artista_unico=artista_unico,
                name_artista_alternativo=artista_unico.nombre_artista,
            )

        return JsonResponse({"message": "ISRC registrado exitosamente"}, status=201)

    except IntegrityError as e:
        # Uso mínimo de 'e' para evitar F841 y dejar trazabilidad
        logger.warning("insertar_isrc_view: IntegrityError al crear ISRC: %s", e)
        return JsonResponse({"error": "Registro duplicado."}, status=400)

    except Exception as e:
        # Aquí ya lo estabas usando; mejor aún, deja constancia con traceback
        logger.exception("insertar_isrc_view: error inesperado: %s", e)
        return JsonResponse({"error": str(e)}, status=500)


@staff_member_required(login_url=reverse_lazy("portal_cliente_home"))
@csrf_exempt
def guardar_match_isrc(request):
    if request.method == "POST":
        try:
            # Parsear los datos enviados desde el frontend
            data = json.loads(request.body)
            id_isrc = data.get("id_isrc")
            usos = data.get("usos")
            id_subida = data.get("id_subida")  # Nuevo dato recibido

            # Validar los datos
            if not id_isrc or usos is None or not id_subida:
                return JsonResponse({"message": "Datos inválidos."}, status=400)

            # Validar que el registro exista
            try:
                codigo_isrc = CodigosISRC.objects.get(id_isrc=id_isrc)
            except CodigosISRC.DoesNotExist:
                return JsonResponse(
                    {"message": "Código ISRC no encontrado."}, status=404
                )

            # Validar que el `id_subida` esté asociado correctamente
            try:
                subida = SubidasPlataforma.objects.get(
                    id_subida=id_subida, obra_id=codigo_isrc.obra_id
                )
            except SubidasPlataforma.DoesNotExist:
                return JsonResponse(
                    {"message": "Subida no encontrada o no asociada a esta obra."},
                    status=404,
                )

            # Crear el registro en MatchingToolISRC
            MatchingToolISRC.objects.create(
                obra=codigo_isrc.obra, codigo_mlc=subida, id_isrc=codigo_isrc, usos=usos
            )

            # Actualizar el valor de matching_tool_isrc de 0 a 1
            codigo_isrc.matching_tool_isrc = 1
            codigo_isrc.save()

            return JsonResponse(
                {"message": "Match guardado correctamente."}, status=200
            )

        except Exception as e:
            return JsonResponse({"message": f"Error: {str(e)}"}, status=500)

    return JsonResponse({"message": "Método no permitido."}, status=405)


@staff_member_required(login_url=reverse_lazy("portal_cliente_home"))
@csrf_exempt
def obtener_info_isrc(request, id_isrc):
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])

    try:
        print(f"🔍 Buscando ISRC con ID: {id_isrc}")  # <--- LOG
        isrc = CodigosISRC.objects.select_related("obra").get(id_isrc=id_isrc)
        print("✅ ISRC encontrado:", isrc.codigo_isrc)

        titulo = isrc.obra.titulo
        autores_qs = ObrasAutores.objects.filter(obra=isrc.obra).select_related("autor")
        autores = ", ".join([a.autor.nombre_autor for a in autores_qs])
        artistas_qs = Artistas.objects.filter(obra=isrc.obra).select_related(
            "artista_unico"
        )
        artistas = ", ".join(
            [a.artista_unico.nombre_artista for a in artistas_qs if a.artista_unico]
        )

        return JsonResponse(
            {
                "codigo_isrc": isrc.codigo_isrc,
                "titulo": titulo,
                "autores": autores or "Sin autores",
                "artistas": artistas or "Sin artistas",
            }
        )

    except CodigosISRC.DoesNotExist:
        print("❌ ISRC no encontrado")  # <--- LOG
        return JsonResponse(
            {"success": False, "message": "ISRC no encontrado."}, status=404
        )


@staff_member_required(login_url=reverse_lazy("portal_cliente_home"))
@csrf_exempt
def eliminar_isrc(request, id_isrc):
    if request.method != "DELETE":
        return HttpResponseNotAllowed(["DELETE"])

    try:
        isrc = CodigosISRC.objects.get(id_isrc=id_isrc)
        isrc.delete()
        return JsonResponse(
            {"success": True, "message": "ISRC eliminado correctamente."}
        )
    except CodigosISRC.DoesNotExist:
        return JsonResponse(
            {"success": False, "message": "ISRC no encontrado."}, status=404
        )


@staff_member_required(login_url=reverse_lazy("portal_cliente_home"))
def redirect_to_matching_tool(request):
    return redirect("matching_tool")


@staff_member_required(login_url=reverse_lazy("portal_cliente_home"))
def codigos_isrc_list(request):
    """
    Lista de ISRC pendientes de ‘matching tool’.
    Ahora el parámetro GET ?cliente= funciona tanto si recibe el **id**
    como si recibe el **nombre** (parcial o completo) del cliente.
    """
    cliente_param = request.GET.get("cliente", "").strip()
    cod_klaim_param = request.GET.get("cod_klaim", "").strip()

    # ────────────  Sub-consultas  ────────────
    sub_id_subida = SubidasPlataforma.objects.filter(
        obra_id=OuterRef("obra_id")
    ).values("id_subida")[:1]

    sub_codigo_mlc = SubidasPlataforma.objects.filter(
        obra_id=OuterRef("obra_id")
    ).values("codigo_MLC")[:1]

    autores_prefetch = Prefetch(
        "obra__obrasautores_set",
        queryset=ObrasAutores.objects.select_related("autor"),
        to_attr="autores_prefetched",
    )

    # ────────────  Query base  ────────────
    codigos_isrc = (
        CodigosISRC.objects.filter(obra__subidasplataforma__codigo_MLC__isnull=False)
        .exclude(obra__subidasplataforma__codigo_MLC="")
        .exclude(matching_tool_isrc=True)  # aún sin procesar
        .select_related("obra", "id_artista_unico", "obra__catalogo__cliente")
        .prefetch_related(autores_prefetch)
        .annotate(
            codigo_mlc_id=Subquery(sub_id_subida),
            codigo_mlc=Subquery(sub_codigo_mlc),
            rating_val=Coalesce(F("rating"), Value(-1.0), output_field=FloatField()),
        )
        .distinct()
        .order_by("-rating_val")
    )

    # ────────────  Filtros dinámicos  ────────────
    # 1) por obra (cod_klaim) – tiene prioridad
    if cod_klaim_param.isdigit():
        codigos_isrc = codigos_isrc.filter(obra__cod_klaim=int(cod_klaim_param))

    # 2) por cliente (id numérico o texto con el nombre)
    elif cliente_param:
        if cliente_param.isdigit():
            codigos_isrc = codigos_isrc.filter(
                obra__catalogo__cliente__id_cliente=int(cliente_param)
            )
        else:
            codigos_isrc = codigos_isrc.filter(
                obra__catalogo__cliente__nombre_cliente__icontains=cliente_param
            )

    # ────────────  Selector de clientes para el <select> del template  ────────────
    clientes = Clientes.objects.filter(
        catalogos__obras__codigos_isrc__isnull=False
    ).distinct()

    # ────────────  Paginación  ────────────
    paginator = Paginator(codigos_isrc, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "codigos_isrc_list.html",
        {
            "page_obj": page_obj,
            "clientes": clientes,
            "cliente_seleccionado": cliente_param or None,
            "cod_klaim_seleccionado": cod_klaim_param or None,
        },
    )


@staff_member_required(login_url=reverse_lazy("portal_cliente_home"))
def matching_tool_list(request):
    # Datos para la tabla de Títulos y Autores
    titulo_autor_records = MatchingToolTituloAutor.objects.all()
    titulo_autor_paginator = Paginator(titulo_autor_records, 10)
    titulo_autor_page_number = request.GET.get("page_titulo_autor")
    titulo_autor_page_obj = titulo_autor_paginator.get_page(titulo_autor_page_number)

    # Datos para la tabla de ISRC
    isrc_records = MatchingToolISRC.objects.all()
    isrc_paginator = Paginator(isrc_records, 10)
    isrc_page_number = request.GET.get("page_isrc")
    isrc_page_obj = isrc_paginator.get_page(isrc_page_number)

    return render(
        request,
        "matching_tool_list.html",
        {
            "titulo_autor_page_obj": titulo_autor_page_obj,
            "isrc_page_obj": isrc_page_obj,
        },
    )


@staff_member_required(login_url=reverse_lazy("portal_cliente_home"))
def matching_tool_table_titulo_autor(request):
    records = MatchingToolTituloAutor.objects.select_related(
        "obra", "autor", "codigo_mlc"
    ).all()

    # ───── Filtros GET ─────────────────────────────────────────
    work_title = request.GET.get("work_title", "").strip()
    mlc_code = request.GET.get("mlc_code", "").strip()
    creation_date = request.GET.get("creation_date", "").strip()
    status = request.GET.get("status", "").strip()

    if work_title:
        records = records.filter(obra__titulo__icontains=work_title)

    if mlc_code:
        records = records.filter(codigo_mlc__codigo_MLC__icontains=mlc_code)

    if creation_date:
        try:
            date_obj = datetime.strptime(creation_date, "%Y-%m-%d")
            start_of_day = date_obj
            end_of_day = date_obj + timedelta(days=1) - timedelta(seconds=1)
            records = records.filter(fecha_creacion__range=(start_of_day, end_of_day))
        except ValueError:
            print("Fecha no válida:", creation_date)

    if status:
        records = records.filter(estado=status)

    # ───── Paginación / render ────────────────────────────────
    page_obj = Paginator(records, 10).get_page(request.GET.get("page"))
    return render(
        request,
        "matching_tool_table_partial.html",
        {"page_obj": page_obj, "records": page_obj.object_list},
    )


@staff_member_required(login_url=reverse_lazy("portal_cliente_home"))
def matching_tool_table_isrc(request):
    records = MatchingToolISRC.objects.select_related(
        "obra", "codigo_mlc", "id_isrc"
    ).all()

    # Filtros de búsqueda
    work_title = request.GET.get("work_title", "").strip()
    mlc_code = request.GET.get("mlc_code", "").strip()
    creation_date = request.GET.get("creation_date", "").strip()
    status = request.GET.get("status", "").strip()

    print(
        f"Filtros recibidos - Work Title: {work_title}, MLC Code: {mlc_code}, Creation Date: {creation_date}, Status: {status}"
    )
    print(f"Total registros antes del filtro: {records.count()}")

    if work_title:
        records = records.filter(obra__titulo__icontains=work_title)
    if mlc_code:
        records = records.filter(codigo_mlc__codigo_MLC__icontains=mlc_code)
    if creation_date:
        try:
            # Convierte la fecha de entrada al formato datetime
            creation_date_obj = datetime.strptime(creation_date, "%Y-%m-%d")

            # Define el inicio y fin del día
            start_of_day = creation_date_obj
            end_of_day = creation_date_obj + timedelta(days=1) - timedelta(seconds=1)

            # Aplica el filtro entre el inicio y el fin del día
            records = records.filter(
                fecha_creacion__gte=start_of_day, fecha_creacion__lte=end_of_day
            )

            print(
                f"Filtro aplicado - Inicio del día: {start_of_day}, Fin del día: {end_of_day}"
            )
        except ValueError:
            print("Error: Fecha no válida")
    if status:
        records = records.filter(estado=status)

    print(f"Total registros después del filtro: {records.count()}")

    paginator = Paginator(records, 10)  # 10 registros por página
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "matching_tool_isrc_table_partial.html",
        {"page_obj": page_obj, "records": page_obj.object_list},
    )


@staff_member_required(login_url=reverse_lazy("portal_cliente_home"))
@csrf_exempt
def update_estado_isrc(request):
    if request.method == "POST":
        try:
            data = json.loads(
                request.body
            )  # Parsear los datos enviados en la solicitud
            record_id = data.get("id")  # ID del registro
            table = data.get("table")  # Nombre de la tabla
            estado = data.get("estado")  # Nuevo estado

            # Verificar si la tabla es válida y buscar el registro
            if table == "matching_tool_titulo_autor":
                record = MatchingToolTituloAutor.objects.get(id=record_id)
            elif table == "matching_tool_isrc":
                record = MatchingToolISRC.objects.get(id=record_id)
            else:
                return JsonResponse({"success": False, "error": "Invalid table name."})

            # Actualizar el estado y guardar el registro
            record.estado = estado
            record.save()

            return JsonResponse({"success": True})
        except MatchingToolTituloAutor.DoesNotExist:
            return JsonResponse(
                {
                    "success": False,
                    "error": "Record in matching_tool_titulo_autor not found.",
                }
            )
        except MatchingToolISRC.DoesNotExist:
            return JsonResponse(
                {"success": False, "error": "Record in matching_tool_isrc not found."}
            )
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})

    return JsonResponse({"success": False, "error": "Invalid request method."})


@staff_member_required(login_url=reverse_lazy("portal_cliente_home"))
def lyricfind_pendientes(request):
    """
    Lista audios descargados con éxito y sin letra procesada.
    Permite filtrar por id_isrc pasado como parámetro GET (?id_isrc=12345).
    """
    pendientes_qs = (
        AudiosISRC.objects.filter(exito_descarga=True)
        .annotate(
            ya_procesado=Exists(
                LyricfindRegistro.objects.filter(isrc_id=OuterRef("id_isrc_id"))
            )
        )
        .filter(ya_procesado=False)
        .select_related(
            "obra",
            "obra__catalogo__cliente",
            "id_isrc__id_artista_unico",
        )
        .order_by("-id_audio")
    )

    # -------- filtro por id_isrc (si llega desde el drop-zone) ----------
    id_isrc_param = request.GET.get("id_isrc")
    if id_isrc_param and id_isrc_param.isdigit():
        pendientes_qs = pendientes_qs.filter(id_isrc_id=id_isrc_param)

    paginator = Paginator(pendientes_qs, 30)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "lyricfind_pendientes.html",
        {"pendientes": page_obj.object_list, "page_obj": page_obj},
    )


# ──────────────────────────────────────────────────────────────────────────────
#  GUARDAR LETRA
# ──────────────────────────────────────────────────────────────────────────────
def lyricfind_guardar(request, audio_id: int):
    """
    Guarda la letra pegada en el modal y crea LyricfindRegistro.
    Luego elimina el registro en AudiosISRC (ya procesado).
    """
    if request.method != "POST":
        return redirect("lyricfind_pendientes")

    audio = get_object_or_404(AudiosISRC, pk=audio_id)

    lyric_text = request.POST.get("lyric_text", "").strip()
    if not lyric_text:
        messages.error(request, "La letra no puede estar vacía.")
        return redirect("lyricfind_pendientes")

    # Registro en lyricfind_registros
    LyricfindRegistro.objects.create(
        obra_id=audio.obra_id,
        isrc_id=audio.id_isrc_id,
        artista_unico_id=audio.id_isrc.id_artista_unico_id,
        lyric_text=lyric_text,
        estado="Procesado",
    )

    # Audio ya procesado → lo quitamos de la cola
    audio.delete()

    messages.success(request, "Letra guardada y audio marcado como procesado.")
    return redirect("lyricfind_pendientes")


# ──────────────────────────────────────────────────────────────────────────────
#  OMITIR AUDIO
# ──────────────────────────────────────────────────────────────────────────────
@staff_member_required(login_url=reverse_lazy("portal_cliente_home"))
def lyricfind_omitir(request, audio_id):  # <— renombrado aquí
    audio = get_object_or_404(AudiosISRC, pk=audio_id)
    audio.activo = False
    audio.save()
    messages.info(request, "Audio omitido.")
    return redirect("lyricfind_pendientes")


@staff_member_required(login_url=reverse_lazy("portal_cliente_home"))
def lyricfind_records(request):
    # ── 1) Parsear los parámetros GET ───────────────────────────────────
    def to_date(value: str | None):
        try:
            return datetime.strptime(value, "%Y-%m-%d").date() if value else None
        except (TypeError, ValueError):
            return None

    d_from = to_date(request.GET.get("from"))
    d_to = to_date(request.GET.get("to"))

    # ── 2) Query base ───────────────────────────────────────────────────
    qs = LyricfindRegistro.objects.select_related(
        "obra", "isrc", "artista_unico"
    ).order_by("-fecha_proceso")

    # ── 3) Aplicar el rango únicamente si se suministra alguna fecha ────
    if d_from or d_to:
        if not d_to:  # solo “from” ⇒ hasta el final de ese día
            d_to = d_from
        elif not d_from:  # solo “to”   ⇒ desde el inicio de ese día
            d_from = d_to

        start_dt = datetime.combine(d_from, time.min)  # 00:00:00
        end_dt = datetime.combine(d_to, time.max)  # 23:59:59.999999
        qs = qs.filter(fecha_proceso__range=(start_dt, end_dt))

    # ── 4) Paginación ──────────────────────────────────────────────────
    page_obj = Paginator(qs, 30).get_page(request.GET.get("page"))

    return render(
        request,
        "lyricfind_records.html",
        {
            "page_obj": page_obj,
            "total_registros": qs.count(),
            "from": d_from.isoformat() if d_from else "",
            "to": d_to.isoformat() if d_to else "",
        },
    )


# --- GUARD DE ACCESO ---
def is_admin_or_superstaff(user) -> bool:
    """Admin total o miembro de grupos privilegiados."""
    if user.is_superuser:
        return True
    # grupos: 'Administrador' o 'SuperStaff'
    try:
        return user.groups.filter(name__in=["Administrador", "SuperStaff"]).exists()
    except Exception:
        return False


def is_cliente(user) -> bool:
    """Tiene vínculo con un cliente."""
    return (
        hasattr(user, "cliente_account")
        and getattr(user.cliente_account, "cliente_id", None) is not None
    )


def is_portal_authorized(user) -> bool:
    """
    Permitidos:
      - is_superuser
      - grupos 'Administrador' o 'SuperStaff'
      - usuarios cliente (tienen cliente_account)
    Excluidos:
      - usuarios 'staff' comunes (is_staff=True) que no sean admin/superstaff ni cliente.
    """
    if not user.is_authenticated:
        return False

    if is_admin_or_superstaff(user):
        return True

    if is_cliente(user):
        return True

    # si llega aquí y es staff común → denegado
    if getattr(user, "is_staff", False):
        return False

    return False


def portal_required(view_func):
    """Decorator: requiere login y autorización especial (excluye staff común)."""

    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        user = request.user
        if not user.is_authenticated:
            # <<--- usa la URL nombrada 'login' que ya tienes en tus urls ('/login/')
            return redirect_to_login(
                request.get_full_path(), login_url=reverse_lazy("login")
            )
        if not is_portal_authorized(user):
            # Usuario autenticado pero no autorizado (por ej., staff común) -> 403
            raise PermissionDenied("No autorizado para el portal de clientes.")
        return view_func(request, *args, **kwargs)

    return _wrapped


# --- VIEW PRINCIPAL (UN SOLO DIV, PAGINADA) ---
# ====== ADMIN / SUPERSTAFF (página completa) ======

# ======== VISTAS EXISTENTES: ADMIN PAGE COMPLETA (se mantiene lógica) ========


# =========================
# ======================================================
#  VISTA ADMIN (PÁGINA FULL)
# ======================================================
@user_passes_test(is_admin_or_superstaff, login_url=reverse_lazy("login"))
def cliente_statements_admin(request):
    """
    Página completa de statements:
      - SOLO Admin/SuperStaff
      - Requiere ?cliente_id=<id> para listar; si falta, muestra formulario con error.
    """
    from django.db.models import F, Func  # TRIM en filtros
    from django.utils.timezone import now

    from accounts.models import MicroSyncMarketShare  # noqa: F401
    from accounts.models import (
        LegacyStatementExcel,
        MicroSyncStatement,
        RoyaltyStatement,
        StatementFile,
    )

    # === Lista de clientes para el desplegable (id_cliente, nombre_cliente)
    try:
        from accounts.models import Clientes  # ajusta si tu modelo se llama distinto

        clientes_qs = Clientes.objects.order_by("nombre_cliente").values(
            "id_cliente", "nombre_cliente"
        )
        clientes = list(clientes_qs)
    except Exception:
        # Fallback: cliente_id disponibles en StatementFile
        ids = (
            StatementFile.objects.values_list("cliente_id", flat=True)
            .distinct()
            .order_by("cliente_id")
        )
        clientes = [
            {"id_cliente": cid, "nombre_cliente": f"Cliente {cid}"} for cid in ids
        ]

    # === Lista de AÑOS para el desplegable (2022..año actual)
    years = list(range(2022, now().year + 1))

    # Valores SEGUROS para el template (evita MultiValueDictKeyError)
    cliente_id_value = request.GET.get("cliente_id", "")
    page_size_value = request.GET.get("page_size", "")

    cid = request.GET.get("cliente_id")
    if not cid:
        # Render inicial sin cliente: deja el formulario utilizable
        return render(
            request,
            "cliente_statements.html",
            {
                "mode": None,
                "error": "Debe seleccionar un cliente para visualizar los statements.",
                "cliente_id_value": cliente_id_value,
                "page_size_value": page_size_value or 100,
                "anio": _int_or_default(request.GET.get("anio"), now().year),
                "q": _int_or_default(request.GET.get("q"), 1),
                "derecho": _str_or_default(request.GET.get("derecho"), "Mecanico"),
                "columns": [],
                "page_obj": None,
                "paginates": True,
                "clientes": clientes,  # para el select de clientes
                "years": years,  # para el select de años
            },
        )

    try:
        cliente_id = int(cid)
    except ValueError:
        raise PermissionDenied("cliente_id inválido.")

    # Filtros con parseo robusto
    anio = _int_or_default(request.GET.get("anio"), now().year)
    q_ui = _int_or_default(request.GET.get("q"), 1)  # visible para usuario
    derecho = _str_or_default(request.GET.get("derecho"), "Mecanico")
    page = _int_or_default(request.GET.get("page"), 1)
    page_size = _int_or_default(request.GET.get("page_size"), 30)

    # Contexto base (incluye valores seguros para el template)
    context = {
        "anio": anio,
        "q": q_ui,
        "derecho": derecho,
        "mode": None,
        "columns": [],
        "page_obj": None,
        "paginates": True,
        "cliente_id": cliente_id,
        "cliente_id_value": str(cliente_id),
        "page_size_value": page_size,
        "clientes": clientes,  # select de clientes
        "years": years,  # select de años
    }

    # ========== MICROSYNC (tabla dinámica) ==========
    if derecho == "MicroSync":
        ms_qs = (
            StatementFile.objects.filter(
                cliente_id=cliente_id, anio=anio, periodo_q=q_ui
            )
            .annotate(
                derecho_t=Func(F("derecho"), function="TRIM"),
                file_type_t=Func(F("file_type"), function="TRIM"),
            )
            .filter(derecho_t__iexact="MicroSync", file_type_t__iexact="XLSX")
            .order_by("-id_file")
        )
        ms_file = ms_qs.first()

        if not ms_file:
            ms_file = (
                StatementFile.objects.filter(
                    cliente_id=cliente_id, anio=anio, periodo_q=0
                )
                .annotate(
                    derecho_t=Func(F("derecho"), function="TRIM"),
                    file_type_t=Func(F("file_type"), function="TRIM"),
                )
                .filter(derecho_t__iexact="MicroSync", file_type_t__iexact="XLSX")
                .order_by("-id_file")
                .first()
            )

        if ms_file:
            columns = [
                ("asset_title", "Asset Title"),
                ("asset_type", "Asset Type"),
                ("track_code", "Track Code"),
                ("artist", "Artist"),
                ("type", "Type"),
                ("country", "Country"),
                ("ad_total_views", "Ad Total Views"),
                ("amount_payable_usd", "Amount Payable (USD)"),
            ]
            qs = (
                MicroSyncStatement.objects.filter(id_file=ms_file.id_file)
                .order_by("id_ms")
                .values(*[c[0] for c in columns])
            )
            paginator = Paginator(qs, page_size)
            try:
                page_obj = paginator.page(page)
            except PageNotAnInteger:
                page_obj = paginator.page(1)
            except EmptyPage:
                page_obj = paginator.page(paginator.num_pages)

            context.update(
                {"mode": "MICROSYNC", "columns": columns, "page_obj": page_obj}
            )
            return render(request, "cliente_statements.html", context)

        return render(request, "cliente_statements.html", context)

    # ========== MECÁNICO ==========
    # TSV
    tsv_file = (
        StatementFile.objects.filter(cliente_id=cliente_id, anio=anio, periodo_q=q_ui)
        .annotate(
            derecho_t=Func(F("derecho"), function="TRIM"),
            file_type_t=Func(F("file_type"), function="TRIM"),
        )
        .filter(derecho_t__iexact=derecho, file_type_t__iexact="TSV")
        .order_by("-id_file")
        .first()
    )

    if tsv_file:
        columns = [
            ("work_writer_list", "Work Writer List"),
            ("work_primary_title", "Work Primary Title"),
            ("iswc", "ISWC"),
            ("usage_period_start", "Usage Period Start Date"),
            ("usage_period_end", "Usage Period End Date"),
            ("use_type", "Use Type"),
            ("processing_type", "Processing Type"),
            ("dsp_name", "DSP Name"),
            ("number_of_usages", "Number of Usages"),
            ("distributed_amount_usd", "Distributed Amount"),
            ("codigo_sgs", "Código SGS"),
            ("obra_id", "cod_klaim"),
        ]
        qs = (
            RoyaltyStatement.objects.filter(id_file=tsv_file.id_file)
            .order_by("id_statement")
            .values(*[c[0] for c in columns])
        )
        paginator = Paginator(qs, page_size)
        try:
            page_obj = paginator.page(page)
        except PageNotAnInteger:
            page_obj = paginator.page(1)
        except EmptyPage:
            page_obj = paginator.page(paginator.num_pages)

        context.update({"mode": "TSV", "columns": columns, "page_obj": page_obj})
        return render(request, "cliente_statements.html", context)

    # XLSX legado
    xlsx_file = (
        StatementFile.objects.filter(cliente_id=cliente_id, anio=anio, periodo_q=q_ui)
        .annotate(
            derecho_t=Func(F("derecho"), function="TRIM"),
            file_type_t=Func(F("file_type"), function="TRIM"),
        )
        .filter(derecho_t__iexact=derecho, file_type_t__iexact="XLSX")
        .order_by("-id_file")
        .first()
    )

    if xlsx_file:
        columns = [
            ("work_writer_list", "Work Writer List"),
            ("work_primary_title", "Work Primary Title"),
            ("iswc", "ISWC"),
            ("usage_period_start", "Usage Period Start Date"),
            ("usage_period_end", "Usage Period End Date"),
            ("use_type", "Use Type"),
            ("processing_type", "Processing Type"),
            ("dsp_name", "DSP Name"),
            ("number_of_usages", "Number of Usages"),
            ("distributed_amount_usd", "Distributed Amount"),
        ]
        qs = (
            LegacyStatementExcel.objects.filter(id_file=xlsx_file.id_file)
            .order_by("id_legacy")
            .values(*[c[0] for c in columns])
        )
        paginator = Paginator(qs, page_size)
        try:
            page_obj = paginator.page(page)
        except PageNotAnInteger:
            page_obj = paginator.page(1)
        except EmptyPage:
            page_obj = paginator.page(paginator.num_pages)

        context.update({"mode": "XLSX", "columns": columns, "page_obj": page_obj})
        return render(request, "cliente_statements.html", context)

    return render(request, "cliente_statements.html", context)


# ======================================================
#  PANEL PORTAL (FRAGMENTO CON HTMX) — SOLO CLIENTES
# ======================================================
@login_required
def cliente_statements_panel(request):
    """
    Fragmento/página que usaremos desde el portal del cliente.
    - Fuerza cliente_id = request.user.cliente_account.cliente_id
    - Ignora cualquier cliente_id de la query (evita spoofing)
    - El portal lo llama con HTMX + hx-select para extraer #results
    """
    if not is_cliente(request.user):
        raise PermissionDenied("Solo clientes pueden acceder a este panel.")

    from django.db.models import F, Func  # <-- para TRIM en filtros

    from accounts.models import MicroSyncMarketShare  # noqa: F401
    from accounts.models import (
        LegacyStatementExcel,
        MicroSyncStatement,
        RoyaltyStatement,
        StatementFile,
    )

    # Forzar cliente del usuario logueado
    cliente_id = request.user.cliente_account.cliente_id

    # Filtros con parseo robusto
    anio = _int_or_default(request.GET.get("anio"), now().year)
    q_ui = _int_or_default(request.GET.get("q"), 1)
    derecho = _str_or_default(request.GET.get("derecho"), "Mecanico")
    page = _int_or_default(request.GET.get("page"), 1)
    page_size = 30  # Fijo a 30 por página (se elimina el filtro en el template)

    # Contexto base (incluye el fallback requerido por el template)
    context = {
        "anio": anio,
        "q": q_ui,
        "derecho": derecho,
        "mode": None,
        "columns": [],
        "page_obj": None,
        "paginates": True,
        "cliente_id": cliente_id,
        "cliente_id_value": str(cliente_id),  # <-- necesario para el template
    }

    # ========== MICROSYNC (tabla dinámica) ==========
    if derecho == "MicroSync":
        # 1) Intentar con el Q elegido
        ms_qs = (
            StatementFile.objects.filter(
                cliente_id=cliente_id, anio=anio, periodo_q=q_ui
            )
            .annotate(
                derecho_t=Func(F("derecho"), function="TRIM"),
                file_type_t=Func(F("file_type"), function="TRIM"),
            )
            .filter(derecho_t__iexact="MicroSync", file_type_t__iexact="XLSX")
            .order_by("-id_file")
        )
        ms_file = ms_qs.first()

        # 2) Fallback a Q=0
        if not ms_file:
            ms_qs_fallback = (
                StatementFile.objects.filter(
                    cliente_id=cliente_id, anio=anio, periodo_q=0
                )
                .annotate(
                    derecho_t=Func(F("derecho"), function="TRIM"),
                    file_type_t=Func(F("file_type"), function="TRIM"),
                )
                .filter(derecho_t__iexact="MicroSync", file_type_t__iexact="XLSX")
                .order_by("-id_file")
            )
            ms_file = ms_qs_fallback.first()

        if ms_file:
            columns = [
                ("asset_title", "Asset Title"),
                ("asset_type", "Asset Type"),
                ("track_code", "Track Code"),
                ("artist", "Artist"),
                ("type", "Type"),
                ("country", "Country"),
                ("ad_total_views", "Ad Total Views"),
                ("amount_payable_usd", "Amount Payable (USD)"),
            ]
            qs = (
                MicroSyncStatement.objects.filter(id_file=ms_file.id_file)
                .order_by("id_ms")
                .values(*[c[0] for c in columns])
            )
            paginator = Paginator(qs, page_size)
            try:
                page_obj = paginator.page(page)
            except PageNotAnInteger:
                page_obj = paginator.page(1)
            except EmptyPage:
                page_obj = paginator.page(paginator.num_pages)

            context.update(
                {"mode": "MICROSYNC", "columns": columns, "page_obj": page_obj}
            )
            return render(request, "cliente_statements.html", context)

        # Si no hay archivo MicroSync, devolvemos vacío (con el contexto base)
        return render(request, "cliente_statements.html", context)

    # ========== MECÁNICO (igual que hoy, pero con TRIM en filtros) ==========
    # TSV primero
    tsv_file = (
        StatementFile.objects.filter(cliente_id=cliente_id, anio=anio, periodo_q=q_ui)
        .annotate(
            derecho_t=Func(F("derecho"), function="TRIM"),
            file_type_t=Func(F("file_type"), function="TRIM"),
        )
        .filter(derecho_t__iexact=derecho, file_type_t__iexact="TSV")
        .order_by("-id_file")
        .first()
    )

    if tsv_file:
        columns = [
            ("work_writer_list", "Work Writer List"),
            ("work_primary_title", "Work Primary Title"),
            ("iswc", "ISWC"),
            ("usage_period_start", "Usage Period Start Date"),
            ("usage_period_end", "Usage Period End Date"),
            ("use_type", "Use Type"),
            ("processing_type", "Processing Type"),
            ("dsp_name", "DSP Name"),
            ("number_of_usages", "Number of Usages"),
            ("distributed_amount_usd", "Distributed Amount"),
            ("codigo_sgs", "Código SGS"),
            ("obra_id", "cod_klaim"),
        ]
        qs = (
            RoyaltyStatement.objects.filter(id_file=tsv_file.id_file)
            .order_by("id_statement")
            .values(*[c[0] for c in columns])
        )
        paginator = Paginator(qs, page_size)
        try:
            page_obj = paginator.page(page)
        except PageNotAnInteger:
            page_obj = paginator.page(1)
        except EmptyPage:
            page_obj = paginator.page(paginator.num_pages)
        context.update({"mode": "TSV", "columns": columns, "page_obj": page_obj})
        return render(request, "cliente_statements.html", context)

    # XLSX legado
    xlsx_file = (
        StatementFile.objects.filter(cliente_id=cliente_id, anio=anio, periodo_q=q_ui)
        .annotate(
            derecho_t=Func(F("derecho"), function="TRIM"),
            file_type_t=Func(F("file_type"), function="TRIM"),
        )
        .filter(derecho_t__iexact=derecho, file_type_t__iexact="XLSX")
        .order_by("-id_file")
        .first()
    )

    if xlsx_file:
        columns = [
            ("work_writer_list", "Work Writer List"),
            ("work_primary_title", "Work Primary Title"),
            ("iswc", "ISWC"),
            ("usage_period_start", "Usage Period Start Date"),
            ("usage_period_end", "Usage Period End Date"),
            ("use_type", "Use Type"),
            ("processing_type", "Processing Type"),
            ("dsp_name", "DSP Name"),
            ("number_of_usages", "Number of Usages"),
            ("distributed_amount_usd", "Distributed Amount"),
        ]
        qs = (
            LegacyStatementExcel.objects.filter(id_file=xlsx_file.id_file)
            .order_by("id_legacy")
            .values(*[c[0] for c in columns])
        )
        paginator = Paginator(qs, page_size)
        try:
            page_obj = paginator.page(page)
        except PageNotAnInteger:
            page_obj = paginator.page(1)
        except EmptyPage:
            page_obj = paginator.page(paginator.num_pages)
        context.update({"mode": "XLSX", "columns": columns, "page_obj": page_obj})
        return render(request, "cliente_statements.html", context)

    # vacío
    return render(request, "cliente_statements.html", context)


# ======================================================
#  Helpers de parseo seguros
# ======================================================
def _int_or_default(val, default):
    try:
        if val is None or val == "":
            return default
        return int(val)
    except (ValueError, TypeError):
        return default


def _str_or_default(val, default):
    return default if val is None or val == "" else val


# ======================================================
#  Utilidades para las GRÁFICAS
# ======================================================
def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _guess_key(keys, candidates):
    norm = {_norm(k): k for k in keys}
    for c in candidates:
        if c in norm:
            return norm[c]
    for nk, orig in norm.items():
        if any(c in nk for c in candidates):
            return orig
    return None


def _to_decimal(x):
    try:
        if x is None:
            return Decimal("0")
        if isinstance(x, (int, float, Decimal)):
            return Decimal(str(x))
        s = str(x).strip().replace(",", "")
        return Decimal(s or "0")
    except (InvalidOperation, ValueError):
        return Decimal("0")


def _topn_dict(d, n=10):
    items = sorted(d.items(), key=lambda x: x[1], reverse=True)
    if len(items) <= n:
        return [{"label": k, "value": float(v)} for k, v in items]
    head = [{"label": k, "value": float(v)} for k, v in items[:n]]
    tail = sum(v for _, v in items[n:])
    head.append({"label": "Otros", "value": float(tail)})
    return head


def _aggregate_for_charts(rows, kind="mecanico"):
    """
    Agregador para gráficas.
    - kind='mecanico': devuelve (total, by_dsp, by_processing_type)
    - kind='microsync': devuelve (total, by_country, by_asset_title)
    """
    if not rows:
        return 0.0, [], []

    keys = rows[0].keys()

    if kind == "microsync":
        amount_key = _guess_key(
            keys, ["amountpayableusd", "amount_payable_usd", "amount", "monto"]
        )
        country_key = _guess_key(keys, ["country", "pais"])
        asset_key = _guess_key(keys, ["assettitle", "asset_title", "title", "titulo"])

        total = Decimal("0")
        by_country = defaultdict(Decimal)
        by_asset = defaultdict(Decimal)

        for r in rows:
            v = _to_decimal(r.get(amount_key))
            total += v
            if country_key:
                by_country[r.get(country_key) or "N/D"] += v
            if asset_key:
                by_asset[r.get(asset_key) or "N/D"] += v

        return float(total), _topn_dict(by_country), _topn_dict(by_asset)

    # kind == 'mecanico'
    amount_key = _guess_key(
        keys,
        [
            "distributedamount",
            "distribuitedamount",
            "amountdistributed",
            "distributedamountusd",
            "amount",
            "monto",
        ],
    )
    dsp_key = _guess_key(
        keys, ["dspname", "dsp", "platform", "retailer", "service", "partner"]
    )
    proc_key = _guess_key(
        keys, ["processingtype", "processtype", "processing", "status"]
    )

    total = Decimal("0")
    by_dsp = defaultdict(Decimal)
    by_proc = defaultdict(Decimal)

    for r in rows:
        v = _to_decimal(r.get(amount_key))
        total += v
        if dsp_key:
            by_dsp[r.get(dsp_key) or "N/D"] += v
        if proc_key:
            by_proc[r.get(proc_key) or "N/D"] += v

    return float(total), _topn_dict(by_dsp), _topn_dict(by_proc)


def _fetch_rows_for_filters(request, cliente_id, anio, q, derecho):
    """
    Devuelve filas SIN paginar para alimentar las gráficas.
    - Si Mecánico: fields -> distributed_amount_usd, dsp_name, processing_type
    - Si MicroSync: fields -> amount_payable_usd, country, asset_title
    """
    from django.db.models import F, Func  # <-- para TRIM en filtros

    from accounts.models import (
        LegacyStatementExcel,
        MicroSyncStatement,
        RoyaltyStatement,
        StatementFile,
    )

    # Normaliza filtros
    anio = _int_or_default(anio, now().year)
    q_ui = _int_or_default(q, 1)
    derecho = _str_or_default(derecho, "Mecanico")

    if not cliente_id:
        return []
    try:
        cliente_id = int(cliente_id)
    except (ValueError, TypeError):
        return []

    if derecho == "MicroSync":
        # 1) Q elegido
        ms_qs = (
            StatementFile.objects.filter(
                cliente_id=cliente_id, anio=anio, periodo_q=q_ui
            )
            .annotate(
                derecho_t=Func(F("derecho"), function="TRIM"),
                file_type_t=Func(F("file_type"), function="TRIM"),
            )
            .filter(derecho_t__iexact="MicroSync", file_type_t__iexact="XLSX")
            .order_by("-id_file")
        )
        ms_file = ms_qs.first()

        # 2) Fallback Q=0
        if not ms_file:
            ms_qs_fallback = (
                StatementFile.objects.filter(
                    cliente_id=cliente_id, anio=anio, periodo_q=0
                )
                .annotate(
                    derecho_t=Func(F("derecho"), function="TRIM"),
                    file_type_t=Func(F("file_type"), function="TRIM"),
                )
                .filter(derecho_t__iexact="MicroSync", file_type_t__iexact="XLSX")
                .order_by("-id_file")
            )
            ms_file = ms_qs_fallback.first()

        if not ms_file:
            return []

        return list(
            MicroSyncStatement.objects.filter(id_file=ms_file.id_file).values(
                "amount_payable_usd", "country", "asset_title"
            )
        )

    # ===== MECÁNICO =====
    # TSV
    tsv = (
        StatementFile.objects.filter(cliente_id=cliente_id, anio=anio, periodo_q=q_ui)
        .annotate(
            derecho_t=Func(F("derecho"), function="TRIM"),
            file_type_t=Func(F("file_type"), function="TRIM"),
        )
        .filter(derecho_t__iexact=derecho, file_type_t__iexact="TSV")
        .order_by("-id_file")
        .first()
    )
    if tsv:
        return list(
            RoyaltyStatement.objects.filter(id_file=tsv.id_file).values(
                "distributed_amount_usd", "dsp_name", "processing_type"
            )
        )

    # XLSX
    xlsx = (
        StatementFile.objects.filter(cliente_id=cliente_id, anio=anio, periodo_q=q_ui)
        .annotate(
            derecho_t=Func(F("derecho"), function="TRIM"),
            file_type_t=Func(F("file_type"), function="TRIM"),
        )
        .filter(derecho_t__iexact=derecho, file_type_t__iexact="XLSX")
        .order_by("-id_file")
        .first()
    )
    if xlsx:
        return list(
            LegacyStatementExcel.objects.filter(id_file=xlsx.id_file).values(
                "distributed_amount_usd", "dsp_name", "processing_type"
            )
        )

    return []


# ======================================================
#  VISTAS DE LAS GRÁFICAS
# ======================================================
def _safe_int(v, default=None):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


@staff_member_required
def charts_portal_cliente_admin(request):
    """
    Página de GRÁFICAS para ADMIN/SUPERSTAFF.
    Toma cliente_id desde la query (?cliente_id=...) y arma el payload
    que consume el parcial `charts_portal_cliente.html`.
    - Mecánico: 2 donuts + tarjeta total distributed
    - MicroSync: 2 tarjetas (amount payable + market share) + 2 donuts (country, asset title)
    """
    from django.db.models import F, Func  # <-- para TRIM en filtros

    from accounts.models import (  # noqa: F401
        MicroSyncMarketShare,
        MicroSyncStatement,
        StatementFile,
    )

    cliente_id = request.GET.get("cliente_id") or None
    anio = _safe_int(request.GET.get("anio"), None)
    q_ui = _safe_int(request.GET.get("q"), None)
    derecho = request.GET.get("derecho") or "Mecanico"

    # Filas para agregados (usa la misma lógica ya corregida)
    rows = _fetch_rows_for_filters(request, cliente_id, anio, q_ui, derecho)

    if derecho == "MicroSync":
        # Resolver el StatementFile: primero Q elegido, luego fallback Q=0
        ms_file = None
        if cliente_id and anio is not None and q_ui is not None:
            ms_qs = (
                StatementFile.objects.filter(
                    cliente_id=int(cliente_id), anio=anio, periodo_q=q_ui
                )
                .annotate(
                    derecho_t=Func(F("derecho"), function="TRIM"),
                    file_type_t=Func(F("file_type"), function="TRIM"),
                )
                .filter(derecho_t__iexact="MicroSync", file_type_t__iexact="XLSX")
                .order_by("-id_file")
            )
            ms_file = ms_qs.first()
            if not ms_file:
                ms_qs_fb = (
                    StatementFile.objects.filter(
                        cliente_id=int(cliente_id), anio=anio, periodo_q=0
                    )
                    .annotate(
                        derecho_t=Func(F("derecho"), function="TRIM"),
                        file_type_t=Func(F("file_type"), function="TRIM"),
                    )
                    .filter(derecho_t__iexact="MicroSync", file_type_t__iexact="XLSX")
                    .order_by("-id_file")
                )
                ms_file = ms_qs_fb.first()

        # Donuts (country / asset title) + total detalle
        total_det, by_country, by_asset = _aggregate_for_charts(rows, kind="microsync")

        # Total Market Share (otra tabla)
        total_share = 0.0
        if ms_file:
            agg_share = MicroSyncMarketShare.objects.filter(
                id_file=ms_file.id_file
            ).aggregate(total=SumDecimal("amount_payable_usd"))
            total_share = float(agg_share.get("total") or 0)

        ctx = {
            "cliente_id": cliente_id,
            "anio": anio,
            "q": q_ui,
            "derecho": "MicroSync",
            "payload": {
                "derecho": "MicroSync",
                "microsync": {
                    "total_amount_payable": float(total_det),  # total del detalle
                    "total_market_share": float(total_share),  # total de cuota
                    "by_country": by_country,
                    "by_asset_title": by_asset,
                },
            },
        }
        return render(request, "charts_portal_cliente.html", ctx)

    # ===== Mecánico =====
    total, by_dsp, by_processing = _aggregate_for_charts(rows, kind="mecanico")
    ctx = {
        "cliente_id": cliente_id,
        "anio": anio,
        "q": q_ui,
        "derecho": "Mecanico",
        "payload": {
            "derecho": "Mecanico",
            "mecanico": {
                "total_distributed_amount": total,
                "by_dsp": by_dsp,
                "by_processing_type": by_processing,
            },
        },
    }
    return render(request, "charts_portal_cliente.html", ctx)


@login_required
def charts_portal_cliente_panel(request):
    """
    Fragmento HTMX de GRÁFICAS para el PORTAL DEL CLIENTE.
    Fuerza cliente_id desde la sesión.
    - Mecánico: 2 donuts + tarjeta total distributed
    - MicroSync: 2 tarjetas (amount payable + market share) + 2 donuts (country, asset title)
    """
    from django.db.models import F, Func  # <-- para TRIM en filtros

    from accounts.models import MicroSyncMarketShare, StatementFile  # noqa: F401

    # Forzar cliente_id desde el usuario autenticado
    try:
        cliente_id = request.user.cliente_account.cliente_id
    except Exception:
        raise PermissionDenied("No se pudo determinar el cliente de la sesión.")

    anio = _safe_int(request.GET.get("anio"), None)
    q_ui = _safe_int(request.GET.get("q"), None)
    derecho = request.GET.get("derecho") or "Mecanico"

    rows = _fetch_rows_for_filters(request, cliente_id, anio, q_ui, derecho)

    if derecho == "MicroSync":
        # Resolver StatementFile para cuota de mercado (Q elegido -> fallback Q0)
        ms_file = None
        if cliente_id and anio is not None and q_ui is not None:
            ms_qs = (
                StatementFile.objects.filter(
                    cliente_id=int(cliente_id), anio=anio, periodo_q=q_ui
                )
                .annotate(
                    derecho_t=Func(F("derecho"), function="TRIM"),
                    file_type_t=Func(F("file_type"), function="TRIM"),
                )
                .filter(derecho_t__iexact="MicroSync", file_type_t__iexact="XLSX")
                .order_by("-id_file")
            )
            ms_file = ms_qs.first()
            if not ms_file:
                ms_qs_fb = (
                    StatementFile.objects.filter(
                        cliente_id=int(cliente_id), anio=anio, periodo_q=0
                    )
                    .annotate(
                        derecho_t=Func(F("derecho"), function="TRIM"),
                        file_type_t=Func(F("file_type"), function="TRIM"),
                    )
                    .filter(derecho_t__iexact="MicroSync", file_type_t__iexact="XLSX")
                    .order_by("-id_file")
                )
                ms_file = ms_qs_fb.first()

        total_det, by_country, by_asset = _aggregate_for_charts(rows, kind="microsync")

        total_share = 0.0
        if ms_file:
            agg_share = MicroSyncMarketShare.objects.filter(
                id_file=ms_file.id_file
            ).aggregate(total=SumDecimal("amount_payable_usd"))
            total_share = float(agg_share.get("total") or 0)

        payload = {
            "derecho": "MicroSync",
            "microsync": {
                "total_amount_payable": float(total_det),
                "total_market_share": float(total_share),
                "by_country": by_country,
                "by_asset_title": by_asset,
            },
        }
        return render(request, "charts_portal_cliente.html", {"payload": payload})

    # Mecánico
    total, by_dsp, by_processing = _aggregate_for_charts(rows, kind="mecanico")
    payload = {
        "derecho": "Mecanico",
        "mecanico": {
            "total_distributed_amount": total,
            "by_dsp": by_dsp,
            "by_processing_type": by_processing,
        },
    }
    return render(request, "charts_portal_cliente.html", {"payload": payload})


# ======================================================
#  Utilidades específicas (aggregations)
# ======================================================
from django.db.models import DecimalField, F, Sum, Value
from django.db.models.functions import Coalesce


def SumDecimal(field_name, max_digits=18, decimal_places=10):
    """
    SUM seguro para campos monetarios (Decimal) con fallback a 0 en Decimal.
    Evita 'Expression contains mixed types: DecimalField, IntegerField'.
    """
    dec_field = DecimalField(max_digits=max_digits, decimal_places=decimal_places)
    return Coalesce(
        Sum(field_name, output_field=dec_field),
        Value(Decimal("0"), output_field=dec_field),
        output_field=dec_field,
    )


import logging
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

# DESCARGA DE ARCHIVOS
from django.http import Http404, HttpResponse

logger = logging.getLogger(__name__)

# ====== constantes y helpers ======
DERECHO_MAP = {"Mecanico": "MECANICO", "MicroSync": "MICROSINC"}
DATA_ROOT = Path(
    getattr(
        settings, "STATEMENTS_DATA_ROOT", Path(settings.BASE_DIR) / "static" / "data"
    )
)


def _folder_name(q: int, cliente: str, derecho_ui: str, anio: int) -> str:
    return f"Q{int(q)}_{cliente.upper()}_{DERECHO_MAP.get(derecho_ui, derecho_ui).upper()}_{int(anio)}"


def _folder_path(q: int, cliente: str, derecho_ui: str, anio: int) -> Path:
    return DATA_ROOT / _folder_name(q, cliente, derecho_ui, anio)


def _zip_folder(folder: Path, zip_name: str) -> HttpResponse:
    if not folder.exists() or not folder.is_dir():
        raise Http404("No se encontró la carpeta del período seleccionado.")
    buf = BytesIO()
    with ZipFile(buf, "w", ZIP_DEFLATED) as zf:
        for f in sorted(folder.glob("*")):
            if f.is_file():
                zf.write(f, arcname=f.name)
    buf.seek(0)
    resp = HttpResponse(buf.getvalue(), content_type="application/zip")
    resp["Content-Disposition"] = f'attachment; filename="{zip_name}.zip"'
    return resp


# ====== vistas ======


# Solo CLIENTES (si prefieres, puedes dejar @login_required y el check interno)
@user_passes_test(is_cliente, login_url="login")
def cliente_download_statements(request):
    try:
        anio = int(request.GET.get("anio"))
        q = int(request.GET.get("q"))
        derecho_ui = (request.GET.get("derecho") or "Mecanico").strip()
    except (TypeError, ValueError):
        raise Http404("Parámetros inválidos.")

    cliente_nombre = request.user.cliente_account.cliente.nombre_cliente.strip().upper()
    folder = _folder_path(q, cliente_nombre, derecho_ui, anio)

    if not folder.exists():
        folder0 = _folder_path(0, cliente_nombre, derecho_ui, anio)  # fallback Q0
        if not folder0.exists():
            logger.info(
                "Folder no encontrado (cliente=%s, q=%s, anio=%s, derecho=%s). DATA_ROOT=%s",
                cliente_nombre,
                q,
                anio,
                derecho_ui,
                DATA_ROOT,
            )
            raise Http404(
                "No hay carpeta de descarga para los filtros seleccionados (ni Q ni consolidado anual)."
            )
        folder = folder0

    zip_name = folder.name
    logger.info("Descarga CLIENTE: user=%s, folder=%s", request.user.username, folder)
    return _zip_folder(folder, zip_name)


# Solo ADMIN/SUPERSTAFF
@user_passes_test(is_admin_or_superstaff, login_url="login")
def admin_download_statements(request):
    cliente = (request.GET.get("cliente") or "").strip().upper()
    cliente_id = request.GET.get("cliente_id")

    if not cliente and cliente_id:
        from accounts.models import Clientes

        try:
            obj = Clientes.objects.only("nombre_cliente").get(
                id_cliente=int(cliente_id)
            )
            cliente = (obj.nombre_cliente or "").strip().upper()
        except Exception:
            raise Http404("cliente_id inválido o no encontrado.")

    if not cliente:
        raise Http404("Debe indicar cliente o cliente_id.")

    try:
        anio = int(request.GET.get("anio"))
        q = int(request.GET.get("q"))
        derecho_ui = (request.GET.get("derecho") or "Mecanico").strip()
    except (TypeError, ValueError):
        raise Http404("Parámetros inválidos.")

    folder = _folder_path(q, cliente, derecho_ui, anio)
    if not folder.exists():
        folder0 = _folder_path(0, cliente, derecho_ui, anio)  # fallback Q0
        if not folder0.exists():
            logger.info(
                "Folder no encontrado (ADMIN): cliente=%s q=%s anio=%s derecho=%s. DATA_ROOT=%s",
                cliente,
                q,
                anio,
                derecho_ui,
                DATA_ROOT,
            )
            raise Http404(
                "No hay carpeta de descarga para esos filtros (ni Q ni consolidado anual)."
            )
        folder = folder0

    zip_name = folder.name
    logger.info("Descarga ADMIN: user=%s, folder=%s", request.user.username, folder)
    return _zip_folder(folder, zip_name)


# Cerrar sesión
def logout_view(request):
    logout(request)
    print("Sesión cerrada, redirigiendo a login")
    return redirect("login")
