from django.db import migrations

class Migration(migrations.Migration):
    # ⚠️ Usa la ÚLTIMA migración real que listaste
    dependencies = [
        ('accounts', '0008_alter_microsyncmarketshare_amount_payable_usd_and_more'),
    ]

    operations = [
        # 1) DROP FK antigua (si existe) que apunta a `users(id)`
        migrations.RunSQL(
            sql=r"""
                -- Elimina la FK antigua solo si existe
                SET @fk_name := (
                    SELECT rc.CONSTRAINT_NAME
                    FROM information_schema.REFERENTIAL_CONSTRAINTS rc
                    WHERE rc.CONSTRAINT_SCHEMA = DATABASE()
                      AND rc.TABLE_NAME = 'movimientos_usuario'
                      AND rc.CONSTRAINT_NAME = 'movimientos_usuario_ibfk_1'
                );
                SET @drop_sql := IF(@fk_name IS NOT NULL,
                    'ALTER TABLE `movimientos_usuario` DROP FOREIGN KEY `movimientos_usuario_ibfk_1`',
                    'SELECT 1');
                PREPARE stmt FROM @drop_sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;
            """,
            reverse_sql=r"""
                -- Reponer la FK antigua SOLO si no existe ya la nueva
                SET @has_new := (
                    SELECT COUNT(*)
                    FROM information_schema.REFERENTIAL_CONSTRAINTS rc
                    WHERE rc.CONSTRAINT_SCHEMA = DATABASE()
                      AND rc.TABLE_NAME = 'movimientos_usuario'
                      AND rc.CONSTRAINT_NAME = 'fk_movimientos_usuario_auth_user'
                );
                SET @add_old := IF(@has_new = 0,
                    'ALTER TABLE `movimientos_usuario` ADD CONSTRAINT `movimientos_usuario_ibfk_1` FOREIGN KEY (`usuario_id`) REFERENCES `users` (`id`) ON DELETE CASCADE',
                    'SELECT 1');
                PREPARE stmt FROM @add_old; EXECUTE stmt; DEALLOCATE PREPARE stmt;
            """,
        ),

        # 2) ADD FK nueva hacia `auth_user(id)` (si no existe)
        migrations.RunSQL(
            sql=r"""
                SET @has_new := (
                    SELECT COUNT(*)
                    FROM information_schema.REFERENTIAL_CONSTRAINTS rc
                    WHERE rc.CONSTRAINT_SCHEMA = DATABASE()
                      AND rc.TABLE_NAME = 'movimientos_usuario'
                      AND rc.CONSTRAINT_NAME = 'fk_movimientos_usuario_auth_user'
                );
                SET @add_new := IF(@has_new = 0,
                    'ALTER TABLE `movimientos_usuario` ADD CONSTRAINT `fk_movimientos_usuario_auth_user` FOREIGN KEY (`usuario_id`) REFERENCES `auth_user` (`id`) ON DELETE CASCADE',
                    'SELECT 1');
                PREPARE stmt FROM @add_new; EXECUTE stmt; DEALLOCATE PREPARE stmt;
            """,
            reverse_sql=r"""
                -- Quitar la FK nueva (si existe)
                SET @has_new := (
                    SELECT COUNT(*)
                    FROM information_schema.REFERENTIAL_CONSTRAINTS rc
                    WHERE rc.CONSTRAINT_SCHEMA = DATABASE()
                      AND rc.TABLE_NAME = 'movimientos_usuario'
                      AND rc.CONSTRAINT_NAME = 'fk_movimientos_usuario_auth_user'
                );
                SET @drop_new := IF(@has_new = 1,
                    'ALTER TABLE `movimientos_usuario` DROP FOREIGN KEY `fk_movimientos_usuario_auth_user`',
                    'SELECT 1');
                PREPARE stmt FROM @drop_new; EXECUTE stmt; DEALLOCATE PREPARE stmt;
            """,
        ),
    ]
