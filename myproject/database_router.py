class UserDatabaseRouter:
    """
    A router to control database operations for user-related models in the 'default' database
    and all other models in the 'klaim_db' database.
    """

    def db_for_read(self, model, **hints):
        if model._meta.app_label == 'accounts' and model.__name__ == 'LegacyUser':
            return 'default'
        elif model._meta.app_label == 'accounts':
            return 'klaim_db'
        return 'default'

    def db_for_write(self, model, **hints):
        if model._meta.app_label == 'accounts' and model.__name__ == 'LegacyUser':
            return 'default'
        elif model._meta.app_label == 'accounts':
            return 'klaim_db'
        return 'default'

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        # Permitir migraciones de LegacyUser solo en 'default'
        if app_label == 'accounts' and model_name == 'legacyuser':
            return db == 'default'
        # Permitir migraciones de todos los demás modelos de accounts solo en 'klaim_db'
        elif app_label == 'accounts':
            return db == 'klaim_db'
        # Bloquear migraciones para aplicaciones de administración y autenticación en klaim_db
        elif app_label in {'admin', 'auth', 'contenttypes', 'sessions'}:
            return db == 'default'
        return None
