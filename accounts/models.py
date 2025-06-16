from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
import bcrypt
from datetime import date
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
        managed = False     

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
        managed = False
        verbose_name = 'Link de Audio (ISRC)'
        verbose_name_plural = 'Links de Audio (ISRC)'
class MovimientoUsuario(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, db_column='usuario_id')  # Ajuste para el modelo correcto
    obra = models.ForeignKey(Obras, on_delete=models.CASCADE, db_column='obra_id')
    tipo_movimiento = models.CharField(max_length=50)
    fecha_hora = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'movimientos_usuario'

# Gestión de usuarios
class UserManager(BaseUserManager):
    def create_user(self, username, password=None):
        if not username:
            raise ValueError('El usuario debe tener un nombre de usuario')
        user = self.model(username=username)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, password):
        user = self.create_user(username=username, password=password)
        user.is_admin = True
        user.save(using=self._db)
        return user

    def get_by_natural_key(self, username):
        return self.get(username=username)

# Modelo de usuario legado
class LegacyUser(AbstractBaseUser):
    id = models.AutoField(primary_key=True)
    username = models.CharField(max_length=100, unique=True, db_column='username')
    password = models.CharField(max_length=255, db_column='password')
    last_login = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = 'username'

    objects = UserManager()

    def check_password(self, password):
        if isinstance(self.password, str):
            stored_password = self.password.encode('utf-8')
        else:
            stored_password = self.password
        return bcrypt.checkpw(password.encode('utf-8'), stored_password)

    def __str__(self):
        return self.username

    class Meta:
        db_table = 'users'
        managed = False

# Modelo de usuario
class User(AbstractBaseUser):
    username = models.CharField(max_length=150, unique=True)
    name = models.CharField(max_length=150, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_admin = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD = 'username'

    def __str__(self):
        return self.username

    def has_perm(self, perm, obj=None):
        return True

    def has_module_perms(self, app_label):
        return True

    @property
    def is_staff(self):
        return self.is_admin
