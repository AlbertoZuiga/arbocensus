from django.db import migrations


def reconcile_status_from_visited(apps, schema_editor):
    # El admin deja editar `visited` y `status` por separado, así que una fila
    # puede haber quedado con la visita registrada solo en el booleano. Un
    # `skipped` con visited=True no se toca: omitir es siempre una acción
    # posterior y deliberada, la API impide omitir una parada ya visitada.
    RouteStop = apps.get_model("routes", "RouteStop")
    RouteStop.objects.filter(visited=True, status="pending").update(status="visited")


def restore_visited_from_status(apps, schema_editor):
    # Al revertir, `RemoveField` repone la columna con default=False para todas
    # las filas: sin esto la marcha atrás borraría el avance del censo.
    RouteStop = apps.get_model("routes", "RouteStop")
    RouteStop.objects.filter(status="visited").update(visited=True)


class Migration(migrations.Migration):
    dependencies = [
        ("routes", "0004_treeobservation_source"),
    ]

    operations = [
        migrations.RunPython(
            reconcile_status_from_visited, restore_visited_from_status
        ),
        migrations.RemoveField(
            model_name="routestop",
            name="visited",
        ),
    ]
