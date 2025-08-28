from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

# Importa tu modelo legado (tabla accounts_user NO gestionada)
from accounts.models import LegacyAccountUser


class Command(BaseCommand):
    help = "Migra usuarios desde accounts_user (legado) hacia auth_user, preservando hashes y asignando grupos."

    def add_arguments(self, parser):
        parser.add_argument(
            "--purge-auth-users",
            action="store_true",
            help="Borra todos los auth_user antes de migrar (¡cuidado!).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="No guarda cambios; solo muestra lo que haría.",
        )

    def handle(self, *args, **options):
        dry = options["dry_run"]
        purge = options["purge_auth_users"]

        User = get_user_model()
        # Debe ser el built-in
        if User._meta.db_table != "auth_user":
            raise CommandError(
                f"AUTH_USER_MODEL no es auth.User (actual: {User._meta.label}). Ajusta settings primero."
            )

        # --- Configuración por IDs (ajústala si quieres) ---
        ADMIN_IDS = [1]  # administrador
        STAFF_IDS = [8, 12]  # staff/operarios
        CLIENTE_IDS = []  # por ahora ninguno
        # lo que no esté arriba será SuperStaff por defecto

        # Grupos (se crean si no existen)
        g_admin, _ = Group.objects.get_or_create(name="Administrador")
        g_staff, _ = Group.objects.get_or_create(name="Staff")
        g_super, _ = Group.objects.get_or_create(name="SuperStaff")
        g_cliente, _ = Group.objects.get_or_create(name="Cliente")

        self.stdout.write(
            self.style.NOTICE(
                f"Usuarios legados a procesar: {LegacyAccountUser.objects.count()}"
            )
        )

        with transaction.atomic():
            if purge:
                if dry:
                    self.stdout.write(
                        self.style.WARNING(
                            "[dry-run] Se borrarían TODOS los auth_user (y relaciones M2M por cascada)."
                        )
                    )
                else:
                    deleted, _ = User.objects.all().delete()
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Borrados auth_user (filas totales afectadas, incl. M2M/logs): {deleted}"
                        )
                    )

            migrados = 0
            for leg in LegacyAccountUser.objects.all().order_by("id"):
                data = {
                    "id": leg.id,  # conservamos el id
                    "username": leg.username,
                    "password": leg.password,  # preserva hash tal cual
                    "is_active": bool(leg.is_active),
                    "is_staff": False,  # set abajo
                    "is_superuser": False,  # set abajo
                    "date_joined": leg.date_joined or timezone.now(),
                    "last_login": leg.last_login,
                    "first_name": "",
                    "last_name": "",
                    "email": "",
                }

                # Mapear 'name' a first/last (rápido)
                if getattr(leg, "name", None):
                    parts = (leg.name or "").strip().split(" ", 1)
                    data["first_name"] = (parts[0][:150]) if parts else ""
                    data["last_name"] = (parts[1][:150]) if len(parts) > 1 else ""

                # Flags por listas
                if leg.id in ADMIN_IDS:
                    data["is_superuser"] = True
                    data["is_staff"] = True
                elif leg.id in STAFF_IDS:
                    data["is_superuser"] = False
                    data["is_staff"] = True
                elif leg.id in CLIENTE_IDS:
                    data["is_superuser"] = False
                    data["is_staff"] = False
                else:
                    # por defecto: SuperStaff interno
                    data["is_superuser"] = False
                    data["is_staff"] = True

                if dry:
                    self.stdout.write(
                        f"[dry-run] crearía auth_user id={data['id']} user={data['username']} "
                        f"staff={data['is_staff']} superuser={data['is_superuser']}"
                    )
                    continue

                # Crea el auth_user con el id legado (MySQL lo permite)
                u = User.objects.create(**data)

                # Asignar grupo según flags / listas
                if data["is_superuser"]:
                    u.groups.set([g_admin])
                else:
                    if leg.id in STAFF_IDS:
                        u.groups.set([g_staff])
                    elif leg.id in CLIENTE_IDS:
                        u.groups.set([g_cliente])
                    else:
                        u.groups.set([g_super])  # por defecto SuperStaff

                migrados += 1

            if dry:
                self.stdout.write(
                    self.style.WARNING("[dry-run] No se aplicaron cambios.")
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Migración completada. Usuarios creados en auth_user: {migrados}"
                    )
                )
