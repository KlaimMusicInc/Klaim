from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
import bcrypt
from datetime import date
from django.utils import timezone
from django.conf import settings

class Clientes(models.Model):
    id_cliente = models.AutoField(primary_key=True)
    nombre_cliente = models.CharField(max_length=255)
    tipo_cliente = models.CharField(max_length=50)

    class Meta:
        db_table = 'clientes'

class ClienteEmails(models.Model):
    cliente = models.ForeignKey(Clientes, on_delete=models.CASCADE, related_name='emails')
    email = models.EmailField(max_length=255)

    class Meta:
        db_table = 'cliente_emails'


# Tabla Catalogos
class Catalogos(models.Model):
    id_catalogo = models.AutoField(primary_key=True)
    cliente = models.ForeignKey(Clientes, on_delete=models.CASCADE, db_column='id_cliente')
    fecha_recibido = models.DateField()
    estado = models.CharField(max_length=10)

    class Meta:
        db_table = 'catalogos'

# Modelo de Obras
class Obras(models.Model):
    cod_klaim = models.AutoField(primary_key=True)
    titulo = models.CharField(max_length=255)
    codigo_sgs = models.CharField(max_length=100)
    codigo_iswc = models.CharField(max_length=100, null=True, blank=True)
    catalogo = models.ForeignKey(Catalogos, on_delete=models.CASCADE)

    class Meta:
        db_table = 'obras'

# Tabla AutoresUnicos
class AutoresUnicos(models.Model):
    id_autor = models.AutoField(primary_key=True)
    nombre_autor = models.CharField(max_length=255)
    codigo_ipi = models.CharField(max_length=100, null=True, blank=True)
    tipo_autor = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        db_table = 'autoresunicos'
        unique_together = ('nombre_autor', 'codigo_ipi', 'tipo_autor')  # Restricción de unicidad

# Tabla intermedia ObrasAutores para asociar Obras con AutoresUnicos y guardar porcentaje_autor
class ObrasAutores(models.Model):
    obra = models.ForeignKey(Obras, on_delete=models.CASCADE, db_column='obra_id')
    autor = models.ForeignKey(AutoresUnicos, on_delete=models.CASCADE, db_column='autor_id')
    porcentaje_autor = models.DecimalField(max_digits=5, decimal_places=2)

    class Meta:
        db_table = 'obrasautores'
class ArtistasUnicos(models.Model):
    id_artista_unico = models.AutoField(primary_key=True)
    nombre_artista = models.CharField(max_length=255)

    class Meta:
        db_table = 'artistas_unicos'
        unique_together = ('nombre_artista',)  # Basado en el índice único del dump
class Artistas(models.Model):
    id_artista = models.AutoField(primary_key=True)
    nombre_artista = models.CharField(max_length=255)
    obra = models.ForeignKey(Obras, on_delete=models.CASCADE)
    artista_unico = models.ForeignKey(ArtistasUnicos, on_delete=models.CASCADE, db_column='id_artista_unico')

    class Meta:
        db_table = 'artistas'

# Subidas a plataformas
class SubidasPlataforma(models.Model):
    id_subida = models.AutoField(primary_key=True)
    obra = models.ForeignKey(Obras, on_delete=models.CASCADE, db_column='obra_id')
    codigo_MLC = models.CharField(max_length=100, null=True, blank=True, db_index=True)  # Índice para consultas rápidas
    codigo_ADREV = models.CharField(max_length=100, null=True, blank=True)
    estado_MLC = models.CharField(
        max_length=50,
        choices=[
            ('OK', 'OK'),
            ('Conflicto', 'Conflicto'),
            ('NO CARGADA', 'NO CARGADA'),
            ('LIBERADA', 'LIBERADA')
        ],
        null=True,
        blank=True
    )
    estado_ADREV = models.CharField(
        max_length=50,
        choices=[
            ('OK', 'OK'),
            ('Conflicto', 'Conflicto'),
            ('NO CARGADA', 'NO CARGADA'),
            ('LIBERADA', 'LIBERADA')
        ],
        null=True,
        blank=True
    )
    fecha_subida = models.DateField()
    matching_tool = models.BooleanField(default=False)  # Nueva columna

    class Meta:
        db_table = 'subidas_plataforma'

class ConflictosPlataforma(models.Model):
    id_conflicto = models.AutoField(primary_key=True)
    obra = models.ForeignKey(Obras, on_delete=models.CASCADE, related_name='conflictos')
    nombre_contraparte = models.CharField(max_length=255, null=True)
    porcentaje_contraparte = models.DecimalField(max_digits=5, decimal_places=2, null=True)
    informacion_adicional = models.TextField(blank=True, null=True)
    fecha_conflicto = models.DateField(auto_now_add=True)
    plataforma = models.CharField(max_length=50, choices=[('MLC', 'MLC'), ('ADREV', 'ADREV')])
    estado_conflicto = models.CharField(max_length=50, choices=[('vigente', 'vigente'), ('finalizado', 'finalizado')], default=None, null=True)

    class Meta:
        db_table = 'conflictos_plataforma'

class ObrasLiberadas(models.Model):
    id_liberada = models.AutoField(primary_key=True)
    cod_klaim = models.ForeignKey(Obras, on_delete=models.CASCADE, db_column='cod_klaim')
    titulo = models.CharField(max_length=255)
    codigo_sgs = models.CharField(max_length=100)
    codigo_iswc = models.CharField(max_length=100, null=True, blank=True)
    id_cliente = models.ForeignKey(Clientes, on_delete=models.CASCADE, db_column='id_cliente', null=True)
    nombre_autor = models.CharField(max_length=255)
    porcentaje_autor = models.DecimalField(max_digits=5, decimal_places=2)
    fecha_creacion = models.DateField(default=date.today)
    estado_liberacion = models.CharField(max_length=10, choices=[('vigente', 'vigente'), ('finalizado', 'finalizado')], default='vigente')

    class Meta:
        db_table = 'obras_liberadas'

class CodigosISRC(models.Model):
    id_isrc = models.AutoField(primary_key=True)
    codigo_isrc = models.CharField(max_length=100)
    obra = models.ForeignKey(
        Obras, 
        on_delete=models.CASCADE, 
        db_column='obra_id', 
        related_name='codigos_isrc'
    )
    id_artista_unico = models.ForeignKey(
        ArtistasUnicos, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True, 
        db_column='id_artista_unico'
    )
    name_artista_alternativo = models.CharField(max_length=255, null=True, blank=True)
    titulo_alternativo = models.CharField(max_length=255, null=True, blank=True)
    matching_tool_isrc = models.BooleanField(default=False)
    
    # 👉 Agrega este campo:
    rating = models.FloatField(null=True, blank=True)

    class Meta:
        db_table = 'codigos_isrc'


class MatchingToolTituloAutor(models.Model):
    obra = models.ForeignKey('Obras', on_delete=models.CASCADE, db_column='obra_id')
    autor = models.ForeignKey('AutoresUnicos', on_delete=models.CASCADE, db_column='autor_id')
    codigo_mlc = models.ForeignKey('SubidasPlataforma', on_delete=models.CASCADE, db_column='codigo_mlc_id')
    artista = models.ForeignKey('ArtistasUnicos', on_delete=models.CASCADE, db_column='artista_id', null=True, blank=True)  # Modificado
    usos = models.PositiveSmallIntegerField()  # Máximo 3 cifras
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(
        max_length=10,
        choices=[
            ('Enviado', 'Enviado'),
            ('Aceptada', 'Aceptada'),
            ('Rechazada', 'Rechazada')
        ],
        default='Enviado'
    )

    class Meta:
        db_table = 'matching_tool_titulo_autor'




class MatchingToolISRC(models.Model):
    obra = models.ForeignKey(
        'Obras',
        on_delete=models.CASCADE,
        db_column='obra_id'
    )
    codigo_mlc = models.ForeignKey(
        'SubidasPlataforma',
        on_delete=models.CASCADE,
        db_column='codigo_mlc_id'
    )
    id_isrc = models.ForeignKey(
        'CodigosISRC',
        on_delete=models.CASCADE,
        db_column='id_isrc'
    )
    usos = models.PositiveSmallIntegerField()  # Máximo 3 cifras
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(
        max_length=10,
        choices=[
            ('Enviado', 'Enviado'),
            ('Aceptada', 'Aceptada'),
            ('Rechazada', 'Rechazada')
        ],
        default='Enviado'
    )

    class Meta:
        db_table = 'matching_tool_isrc'

class LyricfindRegistro(models.Model):
    id_lyricfind = models.AutoField(primary_key=True, db_column='id_lyricfind')

    obra = models.ForeignKey(
        Obras,
        on_delete=models.CASCADE,
        db_column='obra_id',
        related_name='lyricfind_registros'
    )
    isrc = models.ForeignKey(
        CodigosISRC,
        on_delete=models.CASCADE,
        db_column='id_isrc',
        related_name='lyricfind_registros'
    )
    artista_unico = models.ForeignKey(
        ArtistasUnicos,
        on_delete=models.CASCADE,
        db_column='id_artista_unico',
        related_name='lyricfind_registros'
    )

    lyric_text = models.TextField()

    ESTADO_CHOICES = (
        ('Pendiente',  'Pendiente'),
        ('Procesado',  'Procesado'),
        ('Error',      'Error'),
    )
    estado = models.CharField(
        max_length=10,
        choices=ESTADO_CHOICES,
        default='Pendiente'
    )

    motivo_error = models.TextField(null=True, blank=True)

    fecha_proceso = models.DateTimeField(
        auto_now_add=True,
        db_column='fecha_proceso'
    )
    fecha_actualizacion = models.DateTimeField(
        auto_now=True,
        db_column='fecha_actualizacion'
    )

    class Meta:
        db_table = 'lyricfind_registros'
        unique_together = ('obra', 'isrc', 'artista_unico')
        verbose_name = 'Registro LyricFind'
        verbose_name_plural = 'Registros LyricFind'
        managed = True     

class IsrcLinksAudios(models.Model):
    id_isrc_link = models.AutoField(primary_key=True, db_column='id_isrc_link')

    id_isrc = models.ForeignKey(
        CodigosISRC,
        on_delete=models.CASCADE,
        db_column='id_isrc',
        related_name='links_audio'
    )
    obra = models.ForeignKey(
        Obras,
        on_delete=models.CASCADE,
        db_column='obra_id',
        related_name='links_audio'
    )

    codigo_isrc = models.CharField(max_length=100)          # redundante, pero está en la tabla
    spotify_link = models.URLField(max_length=255, null=True, blank=True)
    deezer_link  = models.URLField(max_length=255, null=True, blank=True)
    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'isrc_links_audios'
        unique_together = ('id_isrc',)      # igual que el UNIQUE KEY uq_isrc
        managed = True
        verbose_name = 'Link de Audio (ISRC)'
        verbose_name_plural = 'Links de Audio (ISRC)'



class AudiosISRC(models.Model):
    id_audio = models.AutoField(primary_key=True)

    id_isrc = models.ForeignKey(
        'CodigosISRC',
        on_delete=models.CASCADE,
        db_column='id_isrc',
        related_name='audios'
    )

    obra = models.ForeignKey(
        'Obras',
        on_delete=models.CASCADE,
        db_column='obra_id',
        related_name='audios_isrc'
    )

    link_utilizado = models.URLField(max_length=255)
    
    fuente = models.CharField(
        max_length=10,
        choices=[('Spotify', 'Spotify'), ('Deezer', 'Deezer')]
    )

    exito_descarga = models.BooleanField()
    
    nombre_archivo = models.CharField(max_length=255, null=True, blank=True)
    
    mensaje_error = models.TextField(null=True, blank=True)

    # ─── Nuevo campo para soft-delete ─────────────────────────────────────
    activo = models.BooleanField(
        default=True,
        help_text="Marca si este audio sigue pendiente (True) o fue omitido (False)."
    )

    class Meta:
        db_table = 'audios_isrc'
        verbose_name = "Audio descargado"
        verbose_name_plural = "Audios descargados"
        ordering = ['-id_audio']

    def __str__(self):
        return f"{self.id_audio} – {self.id_isrc.codigo_isrc if self.id_isrc else 'N/A'}"


class MovimientoUsuario(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, db_column='usuario_id')  # Ajuste para el modelo correcto
    obra = models.ForeignKey(Obras, on_delete=models.CASCADE, db_column='obra_id')
    tipo_movimiento = models.CharField(max_length=50)
    fecha_hora = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'movimientos_usuario'

class UserManager(BaseUserManager):
    """
    Manager para el modelo User.
    Crea usuarios normales y superusuarios.
    """
    def create_user(self, username, password=None, **extra_fields):
        if not username:
            raise ValueError('El usuario debe tener un username')
        username = self.model.normalize_username(username)
        user = self.model(username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if not extra_fields.get('is_staff'):
            raise ValueError('Superuser must have is_staff=True.')
        if not extra_fields.get('is_superuser'):
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(username, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Modelo único de usuario para toda la app.
    Mapea a la tabla `accounts_user` existente. 
    Campos heredados de archivos de volcado:
      - id
      - username
      - password
      - last_login
      - name
      - is_active
      - is_admin (se renombrará internamente a is_staff)
    Campos nuevos (para compatibilidad con el auth de Django):
      - is_staff
      - is_superuser
      - date_joined
    """
    id = models.AutoField(primary_key=True)
    username = models.CharField(max_length=150, unique=True)
    name = models.CharField(max_length=150, null=True, blank=True)

    # Para AbstractBaseUser
    password = models.CharField(max_length=128)
    last_login = models.DateTimeField(null=True, blank=True)

    # Volcado legados
    is_active = models.BooleanField(default=True)

    # Se renombra el campo legadado `is_admin` a `is_staff`
    is_admin = models.BooleanField(
        default=False,
        db_column='is_admin',
        help_text='Indica si este usuario tiene permisos de administrador (staff).'
    )

    # Campos nuevos requeridos por PermissionsMixin y admin
    is_staff = models.BooleanField(
        default=False,
        help_text='Puede acceder al sitio de administración.'
    )
    is_superuser = models.BooleanField(
        default=False,
        help_text='Para permisos totales, ignorando restricciones de grupos.'
    )
    date_joined = models.DateTimeField(
        default=timezone.now,
        help_text='Fecha en que se creó esta cuenta.'
    )

    objects = UserManager()

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = []  # sólo username es obligatorio

    class Meta:
        db_table = 'accounts_user'
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'

    def __str__(self):
        return self.username
    # Modelo de usuario
