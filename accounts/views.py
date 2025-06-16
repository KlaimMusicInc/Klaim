from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth import authenticate, login  # Asegúrate de importar authenticate y login
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import connection  # Conexión a la base de datos para consultas directas
from django.middleware.csrf import get_token  # Para generar el token CSRF
from django.db import connections
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from datetime import datetime, timezone, date, timedelta
from django.conf import settings
from django.core.mail import send_mail
from django.db import models
from django.db import transaction
from django.db.models import Prefetch, Exists, OuterRef, Value, Q, F, Count, Subquery, OuterRef, Exists, FloatField
from django.db.models.functions import Concat
from django.core.cache import cache
from django.shortcuts import redirect
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib import colors
from django.http import HttpResponse
from reportlab.lib.styles import getSampleStyleSheet
from datetime import datetime
from django.db.models import F, Value
from django.db.models.functions import Coalesce
from django.http import JsonResponse, Http404
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, HttpResponseNotAllowed
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.db.models import Count
from .models import LegacyUser, Obras, Artistas, MatchingToolTituloAutor,MatchingToolISRC, CodigosISRC, ArtistasUnicos, Catalogos, SubidasPlataforma, ConflictosPlataforma, ObrasLiberadas, MovimientoUsuario, ObrasAutores, AutoresUnicos, Clientes, IsrcLinksAudios, LyricfindRegistro
@csrf_exempt
def generar_reporte_pdf(request):
    # Crear la respuesta con tipo de contenido PDF
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'inline; filename="reporte.pdf"'
    
    # Crear el documento PDF
    doc = SimpleDocTemplate(response, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()
    
    # Agregar la fecha al encabezado del reporte
    fecha_actual = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    titulo = Paragraph(f"<b>Reporte de Base de Datos KLAIM</b><br/><br/>Generado el: {fecha_actual}", styles['Title'])
    elements.append(titulo)
    
    # Obtener datos
    total_obras = Obras.objects.count()
    obras_por_cliente = (
        Catalogos.objects
        .values("cliente__nombre_cliente")
        .annotate(total_obras=Count("obras"))
    )
    
    total_isrc = CodigosISRC.objects.count()
    isrc_por_cliente = (
        CodigosISRC.objects
        .values("obra__catalogo__cliente__nombre_cliente")
        .annotate(total_isrc=Count("id_isrc"))
    )
    
    total_conflictos = ConflictosPlataforma.objects.count()
    conflictos_por_cliente = (
        ConflictosPlataforma.objects
        .values("obra__catalogo__cliente__nombre_cliente")
        .annotate(total_conflictos=Count("id_conflicto"))
    )
    
    total_matching_isrc = MatchingToolISRC.objects.filter(usos__gt=0).count()
    matching_isrc_por_cliente = (
        MatchingToolISRC.objects.filter(usos__gt=0)
        .values("obra__catalogo__cliente__nombre_cliente")
        .annotate(total_matching_isrc=Count("id"))
    )
    
    # Crear la tabla
    data = [["Categoría", "Total"]]  # Encabezados
    data.append(["Total de Obras", total_obras])
    data.append(["Total de ISRCs", total_isrc])
    data.append(["Total de Conflictos", total_conflictos])
    data.append(["Total de Matching Tool ISRC", total_matching_isrc])
    
    data.append(["\nObras por Cliente:", "\n"])
    for item in obras_por_cliente:
        data.append([item["cliente__nombre_cliente"], item["total_obras"]])
    
    data.append(["\nISRCs por Cliente:", "\n"])
    for item in isrc_por_cliente:
        data.append([item["obra__catalogo__cliente__nombre_cliente"], item["total_isrc"]])
    
    data.append(["\nConflictos por Cliente:", "\n"])
    for item in conflictos_por_cliente:
        data.append([item["obra__catalogo__cliente__nombre_cliente"], item["total_conflictos"]])
    
    data.append(["\nMatching Tool ISRC por Cliente:", "\n"])
    for item in matching_isrc_por_cliente:
        data.append([item["obra__catalogo__cliente__nombre_cliente"], item["total_matching_isrc"]])
    
    table = Table(data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkgrey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 14),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('LEFTPADDING', (0, 0), (-1, -1), 50),
        ('RIGHTPADDING', (0, 0), (-1, -1), 50),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),

        # **Estilos para los subencabezados**
        ('BACKGROUND', (0, 5), (-1, 5), colors.lightgrey),  # "Obras por Cliente"
        ('FONTNAME', (0, 5), (-1, 5), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 5), (-1, 5), 12),

        ('BACKGROUND', (0, 10), (-1, 10), colors.lightgrey),  # "ISRCs por Cliente"
        ('FONTNAME', (0, 10), (-1, 10), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 10), (-1, 10), 12),

        ('BACKGROUND', (0, 13), (-1, 13), colors.lightgrey),  # "Conflictos por Cliente"
        ('FONTNAME', (0, 13), (-1, 13), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 13), (-1, 13), 12),

        ('BACKGROUND', (0, 17), (-1, 17), colors.lightgrey),  # "Matching Tool ISRC por Cliente"
        ('FONTNAME', (0, 17), (-1, 17), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 17), (-1, 17), 12),
    ]))
    
    elements.append(table)
    doc.build(elements)
    return response

# Vista de login
def login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']

        # Autenticar al usuario usando el sistema de autenticación de Django
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)  # Inicia sesión en Django
            return redirect('index')  # Redirige al index después del login exitoso
        else:
            messages.error(request, 'Usuario o contraseña incorrectos.')

    return render(request, 'login.html')

@login_required(login_url='login')
def index_view(request):
    # Obtener parámetros de búsqueda
    titulo = request.GET.get('titulo', '').strip()
    codigo_sgs = request.GET.get('codigo_sgs', '').strip()
    codigo_iswc = request.GET.get('codigo_iswc', '').strip()
    id_catalogo = request.GET.get('id_catalogo', '').strip()
    codigo_klaim = request.GET.get('codigo_klaim', '').strip()
    autor = request.GET.get('autor', '').strip()  # Obtener parámetro 'autor'
    incluir_liberadas = request.GET.get('incluir_liberadas', '') == 'on'

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
        filtros &= Q(obrasautores__autor__nombre_autor__icontains=autor)  # Filtrar por autor
    if not incluir_liberadas:
        filtros &= ~Q(subidasplataforma__estado_MLC='LIBERADA')

    # Configurar relaciones prefetch
    prefetch_autores = Prefetch(
        'obrasautores_set',
        queryset=ObrasAutores.objects.select_related('autor'),
        to_attr='autores_prefetched'
    )

    prefetch_artistas = Prefetch(
        'artistas_set',
        queryset=Artistas.objects.select_related('artista_unico'),
        to_attr='artistas_prefetched'
    )

    # Query principal
    obras = (
        Obras.objects.filter(filtros)
        .select_related('catalogo', 'catalogo__cliente')
        .prefetch_related(
            prefetch_autores,
            prefetch_artistas,
            'subidasplataforma_set'
        )
        .distinct()
    )

    # Paginación
    paginator = Paginator(obras, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Contexto para la plantilla
    context = {
        'page_obj': page_obj,
        'obras': page_obj.object_list,
        'incluir_liberadas': incluir_liberadas,
    }
    return render(request, 'index.html', context)

@csrf_exempt
def update_estado(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        obra_id = data.get('obra_id')
        campo = data.get('campo')
        estado = data.get('estado')

        try:
            # Obtener la obra correspondiente
            obra = Obras.objects.using('default').get(cod_klaim=obra_id)
            
            # Verificar si se intenta modificar el estado de una obra que está "LIBERADA"
            subida = SubidasPlataforma.objects.using('default').filter(obra=obra).first()
            if subida and (subida.estado_MLC == 'LIBERADA' or subida.estado_ADREV == 'LIBERADA'):
                # Comprobar si existe un registro en ObrasLiberadas
                if ObrasLiberadas.objects.using('default').filter(cod_klaim=obra).exists():
                    return JsonResponse({
                        'success': False,
                        'error': "Actualmente existe un registro de liberacion de la obra asociada, si está seguro de que desea modificar este estado, por favor comuníquese con ADMINISTRADOR."
                    })

            # Buscar o crear la fila en SubidasPlataforma
            subida, created = SubidasPlataforma.objects.using('default').get_or_create(
                obra=obra,
                defaults={
                    'estado_MLC': None,
                    'estado_ADREV': None
                }
            )

            # Actualizar ambos campos si el estado es "LIBERADA"
            tipo_movimiento = "LIBERADA" if estado == "LIBERADA" else f"Estado {campo} actualizado" 
            if estado == 'LIBERADA':
                subida.estado_MLC = 'LIBERADA'
                subida.estado_ADREV = 'LIBERADA'

                # Crear el registro en `ObrasLiberadas`
                autores_relacionados = obra.obrasautores_set.all()
                for relacion in autores_relacionados:
                    autor = relacion.autor
                    ObrasLiberadas.objects.using('default').create(
                        cod_klaim=obra,
                        titulo=obra.titulo,
                        codigo_sgs=obra.codigo_sgs,
                        codigo_iswc=obra.codigo_iswc,
                        id_cliente=obra.catalogo.cliente,
                        nombre_autor=autor.nombre_autor,
                        porcentaje_autor=relacion.porcentaje_autor,
                        fecha_creacion=date.today()
                    )
            else:
                # Actualizar el campo correspondiente (estado_MLC o estado_ADREV)
                if campo == 'estado_MLC':
                    subida.estado_MLC = estado
                elif campo == 'estado_ADREV':
                    subida.estado_ADREV = estado

            # Guardar cambios en la base de datos
            subida.save()

            MovimientoUsuario.objects.create(
                usuario=request.user,
                obra=obra,
                tipo_movimiento=estado  # Guarda el estado seleccionado ("LIBERADA", "OK", "NO CARGADA", "CONFLICTO")
            )

            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    return JsonResponse({'success': False, 'error': 'Método no permitido'})


@login_required(login_url='login')
def conflictos_view(request):
    # Obtener las obras que tienen estado 'Conflicto' en MLC o ADREV en la tabla subidas_plataforma
    conflictos_mlc = Obras.objects.using('default').filter(
        subidasplataforma__estado_MLC='Conflicto'
    ).select_related('catalogo__cliente').prefetch_related(
        'obrasautores_set__autor', 
        'subidasplataforma_set',
        'conflictos'  # Usar el related_name para acceder a los conflictos
    )

    conflictos_adrev = Obras.objects.using('default').filter(
        subidasplataforma__estado_ADREV='Conflicto'
    ).select_related('catalogo__cliente').prefetch_related(
        'obrasautores_set__autor', 
        'subidasplataforma_set',
        'conflictos'  # Usar el related_name para acceder a los conflictos
    )

    context = {
        'conflictos_mlc': conflictos_mlc,
        'conflictos_adrev': conflictos_adrev
    }

    return render(request, 'conflictos.html', context)



@csrf_exempt
def actualizar_conflicto(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            obras_ids = data.get('obras')
            nombre_contraparte = data.get('nombre_contraparte')
            porcentaje_contraparte = data.get('porcentaje_contraparte')
            informacion_adicional = data.get('informacion_adicional')
            plataforma = data.get('plataforma')
            enviar_correo = data.get('enviar_correo', False)  # Nuevo parámetro para decidir si se envía el correo

            if not obras_ids:
                return JsonResponse({'success': False, 'error': 'No se seleccionaron obras.'})

            for obra_id in obras_ids:
                obra = Obras.objects.using('default').get(cod_klaim=obra_id)
                cliente = obra.catalogo.cliente

                conflicto_vigente = ConflictosPlataforma.objects.using('default').filter(
                    obra=obra, plataforma=plataforma, estado_conflicto='vigente'
                ).exists()

                if conflicto_vigente:
                    return JsonResponse({'success': False, 'error': f'Ya existe un conflicto vigente para la obra "{obra.titulo}" en la plataforma "{plataforma}". Debe finalizar el conflicto vigente antes de crear uno nuevo.'})

                nuevo_conflicto = ConflictosPlataforma.objects.using('default').create(
                    obra=obra,
                    nombre_contraparte=nombre_contraparte if nombre_contraparte else None,
                    porcentaje_contraparte=porcentaje_contraparte if porcentaje_contraparte else None,
                    informacion_adicional=informacion_adicional if informacion_adicional else None,
                    fecha_conflicto=datetime.now(),
                    plataforma=plataforma,
                    estado_conflicto='vigente'
                )

                MovimientoUsuario.objects.create(
                    usuario=request.user,
                    obra=obra,
                    tipo_movimiento="CONFLICTO CREADO"
                )

                if enviar_correo:
                    destinatarios = [email_obj.email for email_obj in cliente.emails.all()]

                    if not destinatarios:
                        return JsonResponse({'success': False, 'error': f'El cliente "{cliente.nombre_cliente}" no tiene correos registrados.'})

                    codigo_sgs = obra.codigo_sgs
                    asunto = "OBRA EN CONFLICTO"
                    mensaje = f"""
Estimado equipo {cliente.nombre_cliente},

Se ha registrado un nuevo conflicto en la plataforma {plataforma}.

Detalles del Conflicto:
- Código SGS: {codigo_sgs}
- Nombre de la Contraparte: {nombre_contraparte or "N/A"}
- Porcentaje de la Contraparte: {porcentaje_contraparte or "N/A"}%
- Información Adicional: {informacion_adicional or "N/A"}
- Fecha de Conflicto: {nuevo_conflicto.fecha_conflicto.strftime('%Y-%m-%d')}
- Estado del Conflicto: {nuevo_conflicto.estado_conflicto}
                    """

                    send_mail(
                        asunto,
                        mensaje,
                        settings.EMAIL_HOST_USER,
                        destinatarios,
                        fail_silently=False
                    )

            return JsonResponse({'success': True})
        except Exception as e:
            print(f"Error al actualizar conflicto: {e}")
            return JsonResponse({'success': False, 'error': str(e)})

    return JsonResponse({'success': False, 'error': 'Método no permitido'})

@csrf_exempt
def insertar_informacion_conflicto(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            obras_ids = data.get('obras')
            informacion_adicional = data.get('informacion_adicional')

            # Verificar que se recibieron obras
            if not obras_ids:
                return JsonResponse({'success': False, 'error': 'No se seleccionaron obras.'})

            # Recorrer cada obra seleccionada
            for obra_id in obras_ids:
                # Obtener el conflicto correspondiente
                conflicto = ConflictosPlataforma.objects.using('default').filter(obra__cod_klaim=obra_id).first()

                if conflicto:
                    # Agregar nueva información a la existente
                    if conflicto.informacion_adicional:
                        conflicto.informacion_adicional += f' | {informacion_adicional}'  # Concatenar con el separador
                    else:
                        conflicto.informacion_adicional = informacion_adicional  # Si está vacío, solo asignar
                    
                    conflicto.save()  # Guardar los cambios

                    # Registrar el movimiento del usuario
                    MovimientoUsuario.objects.create(
                        usuario=request.user,
                        obra=conflicto.obra,
                        tipo_movimiento="INSERTÓ ACCIONES"
                    )

            return JsonResponse({'success': True})
        except Exception as e:
            print(f"Error al insertar información en conflicto: {e}")
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Método no permitido'})


@csrf_exempt
def eliminar_conflicto(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            obras_ids = data.get('obras')

            if not obras_ids:
                return JsonResponse({'success': False, 'error': 'No se seleccionaron obras.'})

            for obra_id in obras_ids:
                # Filtrar conflictos activos
                conflictos = ConflictosPlataforma.objects.using('default').filter(
                    obra__cod_klaim=obra_id, estado_conflicto='vigente'
                )

                for conflicto in conflictos:
                    conflicto.estado_conflicto = 'finalizado'
                    conflicto.save()

            return JsonResponse({'success': True})
        except Exception as e:
            print(f"Error al actualizar estado de conflicto: {e}")
            return JsonResponse({'success': False, 'error': str(e)})

    return JsonResponse({'success': False, 'error': 'Método no permitido'})


@csrf_exempt
def actualizar_estado_obra(request):
    if request.method == 'POST':
        try:
            print("Entró a la función `actualizar_estado_obra`")  # Confirmar entrada a la función
            
            # Obtener los datos enviados desde el frontend
            data = json.loads(request.body)
            obra_id = data.get('obra_id')
            estado = data.get('estado')
            plataforma = data.get('plataforma')  # Plataforma: MLC o ADREV
            informacion_adicional = data.get('informacion_adicional')  # Mensaje adicional

            print(f"Datos recibidos: obra_id={obra_id}, estado={estado}, plataforma={plataforma}, informacion_adicional={informacion_adicional}")

            # Validar los datos
            if not obra_id or not estado or not plataforma or not informacion_adicional:
                print("Error: Datos incompletos.")
                return JsonResponse({'success': False, 'error': 'Datos incompletos.'})

            # Obtener la obra
            obra = Obras.objects.using('default').filter(cod_klaim=obra_id).first()
            if not obra:
                print(f"Error: No se encontró la obra con ID {obra_id}.")
                return JsonResponse({'success': False, 'error': 'No se encontró la obra.'})

            print(f"Obra encontrada: {obra.titulo}")

            # Obtener la plataforma asociada y actualizar su estado
            if plataforma == 'MLC':
                subidas_plataforma = obra.subidasplataforma_set.filter(estado_MLC='Conflicto').first()
                if subidas_plataforma:
                    subidas_plataforma.estado_MLC = estado
                    subidas_plataforma.save()
                    print(f"Estado de la plataforma MLC actualizado a: {estado}")
                else:
                    print(f"No se encontró registro de estado_MLC en conflicto para la obra {obra.titulo}.")
                    return JsonResponse({'success': False, 'error': 'No se encontró un registro de MLC en conflicto.'})
            elif plataforma == 'ADREV':
                subidas_plataforma = obra.subidasplataforma_set.filter(estado_ADREV='Conflicto').first()
                if subidas_plataforma:
                    subidas_plataforma.estado_ADREV = estado
                    subidas_plataforma.save()
                    print(f"Estado de la plataforma ADREV actualizado a: {estado}")
                else:
                    print(f"No se encontró registro de estado_ADREV en conflicto para la obra {obra.titulo}.")
                    return JsonResponse({'success': False, 'error': 'No se encontró un registro de ADREV en conflicto.'})
            else:
                print(f"Plataforma {plataforma} no válida.")
                return JsonResponse({'success': False, 'error': 'Plataforma no válida.'})

            # Actualizar la información adicional en el último conflicto con estado "finalizado"
            conflicto = ConflictosPlataforma.objects.using('default').filter(
                obra=obra, estado_conflicto='finalizado'
            ).order_by('-fecha_conflicto').first()  # Obtener el último conflicto por fecha

            if conflicto:
                print(f"Último conflicto encontrado: {conflicto.id_conflicto}")
                if conflicto.informacion_adicional:
                    conflicto.informacion_adicional += f" | {informacion_adicional}"  # Concatenar mensaje
                else:
                    conflicto.informacion_adicional = informacion_adicional
                conflicto.save()
                print(f"Información adicional actualizada: {conflicto.informacion_adicional}")
            else:
                print("No se encontró un conflicto finalizado asociado.")

            return JsonResponse({'success': True})
        except Exception as e:
            print(f"Error en `actualizar_estado_obra`: {e}")
            return JsonResponse({'success': False, 'error': str(e)})

    print("Método no permitido.")
    return JsonResponse({'success': False, 'error': 'Método no permitido'})


@login_required(login_url='login')
def liberadas_view(request):
    # Obtener los parámetros de búsqueda de la URL
    titulo = request.GET.get('titulo', '')
    codigo_iswc = request.GET.get('codigo_iswc', '')
    nombre_autor = request.GET.get('nombre_autor', '')
    id_cliente = request.GET.get('id_cliente', '')

    # Iniciar la consulta base para la tabla ObrasLiberadas
    liberadas_list = ObrasLiberadas.objects.using('default').filter(estado_liberacion='vigente')

    # Aplicar filtros
    if titulo:
        liberadas_list = liberadas_list.filter(titulo__icontains=titulo)
    if codigo_iswc:
        liberadas_list = liberadas_list.filter(codigo_iswc=codigo_iswc)
    if nombre_autor:
        liberadas_list = liberadas_list.filter(nombre_autor__icontains=nombre_autor)
    if id_cliente:
        liberadas_list = liberadas_list.filter(id_cliente__nombre_cliente__icontains=id_cliente)

    # Paginación
    paginator = Paginator(liberadas_list, 10)  # Muestra 10 resultados por página
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'liberadas': page_obj.object_list,
    }

    return render(request, 'liberadas.html', context)

@csrf_exempt
def eliminar_liberaciones(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            obras_ids = data.get('obras')

            if not obras_ids:
                return JsonResponse({'success': False, 'error': 'No se seleccionaron obras.'})

            # Cambiar el estado de liberación a "finalizado" en lugar de eliminar
            ObrasLiberadas.objects.using('default').filter(id_liberada__in=obras_ids).update(estado_liberacion='finalizado')

            # Obtener los cod_klaim correspondientes a los registros seleccionados
            obras = ObrasLiberadas.objects.using('default').filter(id_liberada__in=obras_ids).values_list('cod_klaim', flat=True)

            # Actualizar el estado_MLC y estado_ADREV a "OK" en la tabla SubidasPlataforma
            SubidasPlataforma.objects.using('default').filter(obra_id__in=obras).update(estado_MLC='OK', estado_ADREV='OK')

            # Registrar el movimiento del usuario para cada obra reingresada
            usuario = request.user  # Obtener el usuario actual
            for obra_id in obras:
                MovimientoUsuario.objects.using('default').create(
                    usuario=usuario,
                    obra_id=obra_id,
                    tipo_movimiento="REINGRESO DE OBRA"
                )

            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    return JsonResponse({'success': False, 'error': 'Método no permitido'})

@login_required(login_url='login')
def matching_tool_view(request):
    import time
    start_time = time.time()

    # Parámetros de paginación
    page = int(request.GET.get('page', 1))
    per_page = 10

    # Subconsulta para verificar si existen códigos ISRC asociados
    isrc_exists = CodigosISRC.objects.filter(obra_id=OuterRef('obra_id'))

    # Consulta optimizada con filtro para excluir obras con ISRC
    subidas = (
        SubidasPlataforma.objects
        .filter(codigo_MLC__isnull=False)
        .exclude(codigo_MLC__exact='')
        .exclude(Exists(isrc_exists))  # Excluir registros con ISRC asociados
        .select_related('obra')
        .only('codigo_MLC', 'obra__titulo', 'obra__cod_klaim', 'matching_tool')  # Incluye la nueva columna
        .prefetch_related(
            Prefetch(
                'obra__obrasautores_set',
                queryset=ObrasAutores.objects.select_related('autor').only('autor__id_autor', 'autor__nombre_autor'),
                to_attr='prefetched_autores'
            ),
            Prefetch(
                'obra__artistas_set',
                queryset=Artistas.objects.only('id_artista', 'nombre_artista'),
                to_attr='prefetched_artistas'
            )
        )
    )

    paginator = Paginator(subidas, per_page)
    page_obj = paginator.get_page(page)

    # Expandir subidas con autores, artistas y el nuevo campo matching_tool
    expanded_subidas = []
    for subida in page_obj.object_list:
        obra = subida.obra
        autores = [autor.autor.nombre_autor for autor in obra.prefetched_autores]
        
        artistas = [
            {
                'nombre_artista': artista.nombre_artista,
                'id_artista_unico': getattr(artista.artista_unico, 'id_artista_unico', None)
            }
            for artista in Artistas.objects.filter(obra_id=obra.cod_klaim).select_related('artista_unico')
        ]
        
        if not artistas:  # Si no hay artistas asociados
            artistas_nombres = "No artistas"
            artistas_ids = ""
        else:
            artistas_nombres = ', '.join([artista['nombre_artista'] for artista in artistas])
            artistas_ids = ','.join([str(artista['id_artista_unico']) for artista in artistas if artista['id_artista_unico']])

        expanded_subidas.append({
            'obra': obra.titulo,
            'obra_id': obra.cod_klaim,
            'codigo_MLC': subida.codigo_MLC,  # Código alfanumérico
            'id_subida': subida.id_subida,  # ID entero
            'autor': ', '.join(autores) if autores else "No autores",
            'autor_id': obra.prefetched_autores[0].autor.id_autor if obra.prefetched_autores else None,
            'artistas': artistas_nombres,
            'artistas_ids': artistas_ids,
            'matching_tool': subida.matching_tool,  # Añadido
        })

    context = {
        'subidas': expanded_subidas,
        'page_obj': page_obj,
    }

    print(f"Tiempo total para procesar: {time.time() - start_time}s")
    return render(request, 'matching_tool.html', context)

@csrf_exempt
def guardar_match(request):
    if request.method == 'POST':
        try:
            # Parsear los datos recibidos
            data = json.loads(request.body)
            obra_id = data.get('obra_id')
            autor_id = data.get('autor_id')
            codigo_mlc_id = data.get('codigo_mlc_id')
            artista_ids = data.get('artista_ids', [])  # Puede estar vacío
            usos = data.get('usos')

            # Validar que los datos requeridos existen
            if not (obra_id and autor_id and codigo_mlc_id and usos is not None):
                return JsonResponse({'error': 'Datos incompletos'}, status=400)

            # Actualizar la base de datos dentro de una transacción
            with transaction.atomic():
                # Si no hay artistas, insertar registro con artista_id como NULL
                if not artista_ids:
                    MatchingToolTituloAutor.objects.create(
                        obra_id=obra_id,
                        autor_id=autor_id,
                        codigo_mlc_id=codigo_mlc_id,
                        artista_id=None,  # Campo nulo
                        usos=usos,
                        estado='Enviado',  # Valor por defecto
                    )
                else:
                    # Crear un registro para cada artista
                    for artista_id in artista_ids:
                        MatchingToolTituloAutor.objects.create(
                            obra_id=obra_id,
                            autor_id=autor_id,
                            codigo_mlc_id=codigo_mlc_id,
                            artista_id=artista_id,
                            usos=usos,
                            estado='Enviado',  # Valor por defecto
                        )

                # Actualizar el valor de `matching_tool` en la tabla `subidas_plataforma`
                SubidasPlataforma.objects.filter(id_subida=codigo_mlc_id).update(matching_tool=True)

            return JsonResponse({'message': 'Registro guardado exitosamente'}, status=201)

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({'error': 'Método no permitido'}, status=405)
@csrf_exempt
def insertar_isrc_view(request):
    if request.method == 'POST':
        try:
            # Parsear los datos recibidos
            data = json.loads(request.body)
            isrc = data.get('isrc')  # Código ISRC ingresado por el usuario
            artista = data.get('artista')  # Nombre del artista ingresado
            cod_klaim = data.get('cod_klaim')  # Código de la obra (cod_klaim)

            if not (isrc and artista and cod_klaim):
                return JsonResponse({'error': 'Datos incompletos'}, status=400)

            # Verificar si el artista ya existe en artistas_unicos
            artista_unico, created_unico = ArtistasUnicos.objects.get_or_create(nombre_artista=artista)

            # Verificar si el artista ya está asociado a la obra
            artista_asociado = Artistas.objects.filter(obra_id=cod_klaim, artista_unico_id=artista_unico.id_artista_unico).exists()

            if not artista_asociado:
                # Si el artista no está asociado a la obra, asociarlo
                Artistas.objects.create(
                    nombre_artista=artista,
                    obra_id=cod_klaim,
                    artista_unico_id=artista_unico.id_artista_unico  # Updated field
                )

            # Insertar el ISRC en la tabla codigos_isrc
            CodigosISRC.objects.create(
                codigo_isrc=isrc,
                obra_id=cod_klaim,
                id_artista_unico=artista_unico,  # Se pasa la instancia en lugar del ID
                name_artista_alternativo=artista
            )
            return JsonResponse({'message': 'ISRC registrado exitosamente'}, status=201)

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({'error': 'Método no permitido'}, status=405)

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
                return JsonResponse({"message": "Código ISRC no encontrado."}, status=404)

            # Validar que el `id_subida` esté asociado correctamente
            try:
                subida = SubidasPlataforma.objects.get(id_subida=id_subida, obra_id=codigo_isrc.obra_id)
            except SubidasPlataforma.DoesNotExist:
                return JsonResponse({"message": "Subida no encontrada o no asociada a esta obra."}, status=404)

            # Crear el registro en MatchingToolISRC
            MatchingToolISRC.objects.create(
                obra=codigo_isrc.obra,
                codigo_mlc=subida,
                id_isrc=codigo_isrc,
                usos=usos
            )

            # Actualizar el valor de matching_tool_isrc de 0 a 1
            codigo_isrc.matching_tool_isrc = 1
            codigo_isrc.save()

            return JsonResponse({"message": "Match guardado correctamente."}, status=200)

        except Exception as e:
            return JsonResponse({"message": f"Error: {str(e)}"}, status=500)

    return JsonResponse({"message": "Método no permitido."}, status=405)


@csrf_exempt
def obtener_info_isrc(request, id_isrc):
    if request.method != 'GET':
        return HttpResponseNotAllowed(['GET'])

    try:
        print(f"🔍 Buscando ISRC con ID: {id_isrc}")  # <--- LOG
        isrc = CodigosISRC.objects.select_related('obra').get(id_isrc=id_isrc)
        print("✅ ISRC encontrado:", isrc.codigo_isrc)

        titulo = isrc.obra.titulo
        autores_qs = ObrasAutores.objects.filter(obra=isrc.obra).select_related('autor')
        autores = ', '.join([a.autor.nombre_autor for a in autores_qs])
        artistas_qs = Artistas.objects.filter(obra=isrc.obra).select_related('artista_unico')
        artistas = ', '.join([a.artista_unico.nombre_artista for a in artistas_qs if a.artista_unico])

        return JsonResponse({
            'codigo_isrc': isrc.codigo_isrc,
            'titulo': titulo,
            'autores': autores or 'Sin autores',
            'artistas': artistas or 'Sin artistas'
        })

    except CodigosISRC.DoesNotExist:
        print("❌ ISRC no encontrado")  # <--- LOG
        return JsonResponse({'success': False, 'message': 'ISRC no encontrado.'}, status=404)
@csrf_exempt
def eliminar_isrc(request, id_isrc):
    if request.method != 'DELETE':
        return HttpResponseNotAllowed(['DELETE'])

    try:
        isrc = CodigosISRC.objects.get(id_isrc=id_isrc)
        isrc.delete()
        return JsonResponse({'success': True, 'message': 'ISRC eliminado correctamente.'})
    except CodigosISRC.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'ISRC no encontrado.'}, status=404)
    
@login_required(login_url='login')
def redirect_to_matching_tool(request):
    return redirect('matching_tool')


@login_required(login_url='login')
def codigos_isrc_list(request):
    cliente_id    = request.GET.get('cliente')
    cod_klaim_id  = request.GET.get('cod_klaim')

    # Subconsultas para traer id_subida y código MLC
    subquery_id_subida = SubidasPlataforma.objects.filter(
        obra_id=OuterRef('obra_id')
    ).values('id_subida')[:1]
    subquery_codigo_mlc = SubidasPlataforma.objects.filter(
        obra_id=OuterRef('obra_id')
    ).values('codigo_MLC')[:1]

    # Prefetch para autores relacionados
    autores_prefetch = Prefetch(
        'obra__obrasautores_set',
        queryset=ObrasAutores.objects.select_related('autor'),
        to_attr='autores_prefetched'
    )

    # Base queryset de ISRCs
    codigos_isrc = CodigosISRC.objects.filter(
        obra__subidasplataforma__codigo_MLC__isnull=False
    ).exclude(
        obra__subidasplataforma__codigo_MLC=''
    ).exclude(
        matching_tool_isrc=True
    ).select_related(
        'obra', 'id_artista_unico', 'obra__catalogo__cliente'
    ).prefetch_related(
        autores_prefetch
    ).annotate(
        codigo_mlc_id=Subquery(subquery_id_subida),
        codigo_mlc=Subquery(subquery_codigo_mlc),
        rating_val=Coalesce(F('rating'), Value(-1.0), output_field=FloatField())
    ).distinct().order_by('-rating_val')

    # Filtro por cod_klaim si se proporcionó
    if cod_klaim_id and cod_klaim_id.isdigit():
        codigos_isrc = codigos_isrc.filter(obra__cod_klaim=int(cod_klaim_id))
    # Si no se filtró por cod_klaim, aplicamos filtro por cliente si se proporcionó
    elif cliente_id and cliente_id.isdigit():
        codigos_isrc = codigos_isrc.filter(
            obra__catalogo__cliente__id_cliente=int(cliente_id)
        )

    # Lista de todos los clientes para el selector
    clientes = Clientes.objects.filter(
        catalogos__obras__codigos_isrc__isnull=False
    ).distinct()

    # Paginación
    paginator = Paginator(codigos_isrc, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'clientes': clientes,
        'cliente_seleccionado': int(cliente_id) if cliente_id and cliente_id.isdigit() else None,
        'cod_klaim_seleccionado': int(cod_klaim_id) if cod_klaim_id and cod_klaim_id.isdigit() else None,
    }

    return render(request, 'codigos_isrc_list.html', context)


@login_required(login_url='login')
def matching_tool_list(request):
    # Datos para la tabla de Títulos y Autores
    titulo_autor_records = MatchingToolTituloAutor.objects.all()
    titulo_autor_paginator = Paginator(titulo_autor_records, 10)
    titulo_autor_page_number = request.GET.get('page_titulo_autor')
    titulo_autor_page_obj = titulo_autor_paginator.get_page(titulo_autor_page_number)

    # Datos para la tabla de ISRC
    isrc_records = MatchingToolISRC.objects.all()
    isrc_paginator = Paginator(isrc_records, 10)
    isrc_page_number = request.GET.get('page_isrc')
    isrc_page_obj = isrc_paginator.get_page(isrc_page_number)

    return render(request, 'matching_tool_list.html', {
        'titulo_autor_page_obj': titulo_autor_page_obj,
        'isrc_page_obj': isrc_page_obj
    })



def matching_tool_table_titulo_autor(request):
    records = MatchingToolTituloAutor.objects.select_related(
        'obra', 'autor', 'codigo_mlc'
    ).all()

    creation_date = request.GET.get('creation_date', '').strip()

    if creation_date:
        try:
            # Convierte la fecha a un objeto datetime
            creation_date_obj = datetime.strptime(creation_date, '%Y-%m-%d')

            # Define el rango del día (inicio y fin)
            start_of_day = creation_date_obj
            end_of_day = creation_date_obj + timedelta(days=1) - timedelta(seconds=1)

            # Aplica el filtro entre inicio y fin del día
            records = records.filter(fecha_creacion__gte=start_of_day, fecha_creacion__lte=end_of_day)

            print(f"Filtro aplicado - Inicio del día: {start_of_day}, Fin del día: {end_of_day}")
        except ValueError:
            print("Error: Fecha no válida")

    print(f"Total registros después del filtro de fecha: {records.count()}")

    paginator = Paginator(records, 10)  # 10 registros por página
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'matching_tool_table_partial.html', {
        'page_obj': page_obj,
        'records': page_obj.object_list
    })

def matching_tool_table_isrc(request):
    records = MatchingToolISRC.objects.select_related(
        'obra', 'codigo_mlc', 'id_isrc'
    ).all()

    # Filtros de búsqueda
    work_title = request.GET.get('work_title', '').strip()
    mlc_code = request.GET.get('mlc_code', '').strip()
    creation_date = request.GET.get('creation_date', '').strip()
    status = request.GET.get('status', '').strip()

    print(f"Filtros recibidos - Work Title: {work_title}, MLC Code: {mlc_code}, Creation Date: {creation_date}, Status: {status}")
    print(f"Total registros antes del filtro: {records.count()}")

    if work_title:
        records = records.filter(obra__titulo__icontains=work_title)
    if mlc_code:
        records = records.filter(codigo_mlc__codigo_MLC__icontains=mlc_code)
    if creation_date:
        try:
            # Convierte la fecha de entrada al formato datetime
            creation_date_obj = datetime.strptime(creation_date, '%Y-%m-%d')

            # Define el inicio y fin del día
            start_of_day = creation_date_obj
            end_of_day = creation_date_obj + timedelta(days=1) - timedelta(seconds=1)

            # Aplica el filtro entre el inicio y el fin del día
            records = records.filter(fecha_creacion__gte=start_of_day, fecha_creacion__lte=end_of_day)

            print(f"Filtro aplicado - Inicio del día: {start_of_day}, Fin del día: {end_of_day}")
        except ValueError:
            print("Error: Fecha no válida")
    if status:
        records = records.filter(estado=status)

    print(f"Total registros después del filtro: {records.count()}")

    paginator = Paginator(records, 10)  # 10 registros por página
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'matching_tool_isrc_table_partial.html', {
        'page_obj': page_obj,
        'records': page_obj.object_list
    })


@csrf_exempt
def update_estado_isrc(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)  # Parsear los datos enviados en la solicitud
            record_id = data.get('id')  # ID del registro
            table = data.get('table')  # Nombre de la tabla
            estado = data.get('estado')  # Nuevo estado

            # Verificar si la tabla es válida y buscar el registro
            if table == 'matching_tool_titulo_autor':
                record = MatchingToolTituloAutor.objects.get(id=record_id)
            elif table == 'matching_tool_isrc':
                record = MatchingToolISRC.objects.get(id=record_id)
            else:
                return JsonResponse({'success': False, 'error': 'Invalid table name.'})

            # Actualizar el estado y guardar el registro
            record.estado = estado
            record.save()

            return JsonResponse({'success': True})
        except MatchingToolTituloAutor.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Record in matching_tool_titulo_autor not found.'})
        except MatchingToolISRC.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Record in matching_tool_isrc not found.'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    return JsonResponse({'success': False, 'error': 'Invalid request method.'})



def lyricfind_pendientes(request):
    # Filtra links que aún NO tienen registro LyricFind
    pendientes_qs = IsrcLinksAudios.objects.annotate(
        ya_procesado=Exists(
            LyricfindRegistro.objects.filter(isrc=OuterRef("id_isrc"))
        )
    ).filter(ya_procesado=False, activo=True).select_related(
        "obra", "obra__catalogo__cliente", "id_isrc__id_artista_unico"
    ).order_by("-fecha_creacion")

    return render(
        request,
        "lyricfind_pendientes.html",
        {"pendientes": pendientes_qs}
    )


# ► Guardar la letra y crear registro
def lyricfind_guardar(request, link_id):
    if request.method == "POST":
        link = get_object_or_404(IsrcLinksAudios, pk=link_id)

        letra = request.POST.get("lyric_text", "").strip()
        if not letra:
            messages.error(request, "La letra no puede estar vacía.")
            return redirect("lyricfind_pendientes")

        # Crear registro
        LyricfindRegistro.objects.create(
            obra_id=link.obra_id,
            isrc_id=link.id_isrc_id,
            artista_unico_id = link.id_isrc.id_artista_unico_id,
            lyric_text=letra,
            estado="Procesado"
        )

        # Eliminar link procesado
        link.delete()

        messages.success(request, "Letra guardada y audio procesado.")
    return redirect("lyricfind_pendientes")


# ► Omitir / eliminar audio erróneo
def lyricfind_omitir(request, link_id):
    link = get_object_or_404(IsrcLinksAudios, pk=link_id)
    link.activo = False
    link.save()
    return redirect('lyricfind_pendientes')

def lyricfind_records(request):
    # --- filtros por fecha ---
    date_from = request.GET.get("from")
    date_to   = request.GET.get("to")

    registros_qs = LyricfindRegistro.objects.select_related(
        "obra", "isrc", "artista_unico"
    ).order_by("-fecha_proceso")

    # aplicar filtro si hay fechas
    if date_from:
        registros_qs = registros_qs.filter(fecha_proceso__date__gte=date_from)
    if date_to:
        registros_qs = registros_qs.filter(fecha_proceso__date__lte=date_to)

    # paginación simple 50 por página
    paginator  = Paginator(registros_qs, 50)
    page_num   = request.GET.get('page')
    page_obj   = paginator.get_page(page_num)

    context = {
        "page_obj": page_obj,
        "total_registros": LyricfindRegistro.objects.count(),
        "from": date_from or "",
        "to": date_to or "",
    }
    return render(request, "lyricfind_records.html", context)

# Cerrar sesión
def logout_view(request):
    logout(request)
    print("Sesión cerrada, redirigiendo a login")
    return redirect('login')
