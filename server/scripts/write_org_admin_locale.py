"""Generate `server/locale/es/LC_MESSAGES/django.{po,mo}` for Organization Management admin.

GNU `msguniq` / `msgfmt` are not required: this script writes a valid .po and compiles it
with `polib` (dev dependency). Regenerate after changing translatable strings:

  uv run --project server --group dev python server/scripts/write_org_admin_locale.py

If you install GNU gettext, you can use `makemessages` / `compilemessages` instead.
"""
from __future__ import annotations

import pathlib


def esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def write_msg(f, msgid: str, msgstr: str) -> None:
    f.write(f'msgid "{esc(msgid)}"\n')
    f.write(f'msgstr "{esc(msgstr)}"\n\n')


def write_plural(f, msgid: str, msgid_plural: str, s0: str, s1: str) -> None:
    f.write(f'msgid "{esc(msgid)}"\n')
    f.write(f'msgid_plural "{esc(msgid_plural)}"\n')
    f.write(f'msgstr[0] "{esc(s0)}"\n')
    f.write(f'msgstr[1] "{esc(s1)}"\n\n')


def main() -> None:
    root = pathlib.Path(__file__).resolve().parents[1]
    out = root / "locale" / "es" / "LC_MESSAGES" / "django.po"
    out.parent.mkdir(parents=True, exist_ok=True)

    pairs: list[tuple[str, str]] = [
        ("Language", "Idioma"),
        ("Change language", "Cambiar idioma"),
        ("System Management", "Gestión del sistema"),
        ("Language Settings", "Configuración de idioma"),
        ("Admin language", "Idioma del admin"),
        (
            "Choose the admin language. Your choice is stored in the session cookie and applies to the Django admin and the System Management pages.",
            "Elige el idioma del admin. Tu elección se guarda en la cookie de sesión y aplica al admin de Django y a las páginas de Gestión del sistema.",
        ),
        ("Home", "Inicio"),
        ("Organizations Management", "Gestión de organizaciones"),
        (
            "Search organizations by name or owner email. Open billing to manage manual enterprise deals, wallet, and feature flags.",
            "Busca organizaciones por nombre o correo del propietario. Abre Facturación para gestionar acuerdos enterprise manuales, monedero y feature flags.",
        ),
        ("Search", "Buscar"),
        ("Clear", "Limpiar"),
        ("Organization", "Organización"),
        ("Owner", "Propietario"),
        ("Members", "Miembros"),
        ("Subscription", "Suscripción"),
        ("Wallet (USD)", "Monedero (USD)"),
        ("Flags", "Indicadores"),
        ("ends", "termina"),
        ("none", "ninguno"),
        ("no wallet", "sin monedero"),
        ("Billing", "Facturación"),
        ("No organizations found.", "No se encontraron organizaciones."),
        ("Back to Organizations Management", "Volver a Gestión de organizaciones"),
        ("How billing works in Masscer", "Cómo funciona la facturación en Masscer"),
        ("Usage and access", "Uso y acceso"),
        ("use the", "usan la"),
        ("latest", "última"),
        (
            "subscription row (by creation time): its status, end date, and wallet balance decide whether the org can spend credits.",
            "fila de suscripción (por fecha de creación): su estado, fecha de fin y saldo del monedero determinan si la org puede gastar créditos.",
        ),
        ("Stripe", "Stripe"),
        (
            "is separate: if a row still has a Stripe subscription id, Stripe may keep charging until you cancel it from that same subscription row here, or the customer cancels in the",
            "es independiente: si una fila sigue teniendo un id de suscripción de Stripe, Stripe puede seguir cobrando hasta que la canceles desde esa misma fila de suscripción aquí, o el cliente cancele en el",
        ),
        ("Stripe Customer Portal", "Portal de clientes de Stripe"),
        (
            "from the in-app billing page. Adding a manual row on top does",
            "desde la página de facturación de la app. Añadir una fila manual encima",
        ),
        ("not", "no"),
        ("automatically stop an older Stripe subscription.", "detiene automáticamente una suscripción antigua de Stripe."),
        ("At a glance", "Resumen"),
        (
            "Active Masscer subscriptions (in this summary and for wallet recharge) are subscription rows where the organization can still use plan benefits: status is trial or active, and the Masscer end date (if set) has not passed yet—including subscriptions that are about to expire. Stripe may already show canceled; billing there is separate from access here.",
            "En este resumen y para la recarga del monedero, las suscripciones Masscer activas son filas en las que la organización aún puede usar los beneficios del plan: estado en prueba o activo, y la fecha de fin en Masscer (si existe) aún no ha pasado—incluidas las que están por vencer. En Stripe puede figurar ya como cancelada; el cobro allí es independiente del acceso aquí.",
        ),
        ("Metric", "Métrica"),
        ("Value", "Valor"),
        ("Wallet total balance", "Saldo total en monedero"),
        ("USD", "USD"),
        ("Members", "Miembros"),
        ("No subscriptions", "Sin suscripciones"),
        ("Stripe subscriptions", "Suscripciones de Stripe"),
        ("Active Masscer subscriptions", "Suscripciones activas en Masscer"),
        ("Masscer subscriptions", "Suscripciones Masscer"),
        (
            "All subscription rows stored in Masscer for this organization (manual and Stripe-linked). Usage follows the latest row by creation time; open a row below to edit it in the payments admin. For rows that include a Stripe subscription id, this same card also shows live Stripe status and cancellation actions.",
            "Todas las filas de suscripción guardadas en Masscer para esta organización (manuales y enlazadas a Stripe). El uso sigue la fila más reciente por fecha de creación; abre una fila abajo para editarla en el admin de pagos. Para filas que incluyen un id de suscripción de Stripe, esta misma tarjeta también muestra el estado en vivo en Stripe y acciones de cancelación.",
        ),
        (
            "Rows grouped as active below include both currently active and expired rows, so you can quickly find subscriptions that can be reactivated.",
            "Las filas agrupadas como activas abajo incluyen tanto activas actuales como expiradas, para que puedas encontrar rápido las suscripciones que se pueden reactivar.",
        ),
        ("Active + expired rows", "Filas activas + expiradas"),
        ("Inactive rows", "Filas inactivas"),
        (
            "No active or expired Masscer subscription rows.",
            "No hay filas de suscripción Masscer activas o expiradas.",
        ),
        (
            "No inactive Masscer subscription rows.",
            "No hay filas de suscripción Masscer inactivas.",
        ),
        ("Created at", "Creada el"),
        ("Active in Stripe", "Activas en Stripe"),
        ("Past subscriptions", "Suscripciones pasadas"),
        (
            "No active Stripe subscriptions to cancel here.",
            "Aquí no hay suscripciones activas de Stripe para cancelar.",
        ),
        ("No past Stripe subscriptions on file.", "No hay suscripciones pasadas de Stripe registradas."),
        (
            "No Stripe subscription ids on file for this organization.",
            "No hay ids de suscripción de Stripe registrados para esta organización.",
        ),
        ("Masscer subscription", "Suscripción Masscer"),
        ("Edit subscription", "Editar suscripción"),
        ("Latest row (access)", "Fila más reciente (acceso)"),
        ("Plan", "Plan"),
        ("Payment method on row", "Método de pago en la fila"),
        ("Stripe subscription id", "Id de suscripción de Stripe"),
        ("Stripe customer id", "Id de cliente de Stripe"),
        ("Stripe lookup", "Consulta Stripe"),
        ("Field", "Campo"),
        ("Value", "Valor"),
        ("Stripe status", "Estado en Stripe"),
        ("Current period end (Stripe)", "Fin del periodo actual (Stripe)"),
        ("Cancel at (Stripe)", "Cancelación en (Stripe)"),
        ("Cancel at period end", "Cancelar al final del periodo"),
        (
            "Both actions call the Stripe API. Check the confirmation box on each form before submitting.",
            "Ambas acciones llaman a la API de Stripe. Marca la casilla de confirmación en cada formulario antes de enviar.",
        ),
        ("Cancel this subscription in Stripe", "Cancelar esta suscripción en Stripe"),
        ("Manual renewal", "Renovación manual"),
        (
            "Renews this subscription from admin. Active rows extend from their current end date; expired rows restart from now. This action also recharges wallet credits and records a manual payment using contract price (or plan fallback).",
            "Renueva esta suscripción desde admin. Las filas activas extienden desde su fecha de fin actual; las expiradas reinician desde ahora. Esta acción también recarga créditos del monedero y registra un pago manual usando precio contractual (o fallback del plan).",
        ),
        ("I confirm manual renewal", "Confirmo esta renovación manual"),
        ("Renew subscription", "Renovar suscripción"),
        ("Masscer status", "Estado en Masscer"),
        ("Masscer access: active", "Acceso Masscer: activo"),
        ("Masscer access: inactive", "Acceso Masscer: inactivo"),
        ("None", "Ninguna"),
        (
            "Cancel this Stripe subscription at the end of the current billing period?",
            "¿Cancelar esta suscripción de Stripe al final del periodo de facturación actual?",
        ),
        ("I confirm this Stripe change", "Confirmo este cambio en Stripe"),
        ("Cancel at period end (Stripe)", "Cancelar al final del periodo (Stripe)"),
        (
            "Cancel this Stripe subscription IMMEDIATELY? This cannot be undone in Masscer.",
            "¿Cancelar esta suscripción de Stripe de INMEDIATO? Esto no se puede deshacer en Masscer.",
        ),
        ("Cancel immediately (Stripe)", "Cancelar de inmediato (Stripe)"),
        ("Status", "Estado"),
        ("Payment method (on this row)", "Método de pago (en esta fila)"),
        ("Display price (USD)", "Precio mostrado (USD)"),
        ("Billing interval (deal / display)", "Intervalo de facturación (acuerdo / visualización)"),
        ("End date (Masscer)", "Fecha de fin (Masscer)"),
        ("Credit limit override (USD)", "Límite de crédito (USD, anulación)"),
        ("Contract price (USD)", "Precio contractual (USD)"),
        ("Wallet", "Monedero"),
        (
            "Organization usage draws from this balance (compute units). Top up here for one-off credits without changing the subscription row.",
            "El uso de la organización se descuenta de este saldo (unidades de cómputo). Recarga aquí créditos puntuales sin cambiar la fila de suscripción.",
        ),
        ("Balance", "Saldo"),
        ("USD at 1 USD =", "USD a 1 USD ="),
        ("No organization wallet.", "No hay monedero de organización."),
        (
            "Wallet recharge is disabled until the organization has at least one active Masscer subscription (trial or active, not past its end date).",
            "La recarga del monedero está deshabilitada hasta que la organización tenga al menos una suscripción Masscer activa (prueba o activa, sin superar su fecha de fin).",
        ),
        ("Manual credit (USD)", "Crédito manual (USD)"),
        ("Balance before (compute units)", "Saldo antes (unidades de cómputo)"),
        ("Credit added (compute units)", "Crédito añadido (unidades de cómputo)"),
        ("Balance after (compute units, estimated)", "Saldo después (unidades de cómputo, estimado)"),
        ("Approximate USD equivalent (before → after)", "Equivalente USD aproximado (antes → después)"),
        ("Enter a valid positive USD amount.", "Introduce un importe USD válido y positivo."),
        (
            "Compute Unit rate is missing; cannot estimate the new balance.",
            "Falta la tasa de Unidad de cómputo; no se puede estimar el nuevo saldo.",
        ),
        ("Confirm wallet recharge", "Confirmar recarga del monedero"),
        (
            "This is an estimate from the current balance and the Compute Unit conversion; the saved amount is the USD you entered.",
            "Es una estimación a partir del saldo actual y la conversión a Unidad de cómputo; el importe guardado es el USD que introdujiste.",
        ),
        ("Confirm recharge", "Confirmar recarga"),
        ("Cancel", "Cancelar"),
        ("Amount (USD)", "Importe (USD)"),
        ("e.g. 100", "p. ej. 100"),
        (
            "Whole or decimal USD amount credited to the org wallet using the same conversion as plan credits (Compute Unit currency must exist).",
            "Importe en USD (entero o decimal) acreditado al monedero de la org con la misma conversión que los créditos del plan (debe existir la moneda Unidad de cómputo).",
        ),
        (
            "Register this recharge as a payment",
            "Registrar esta recarga como pago",
        ),
        (
            "Creates a completed manual payment on the newest active Masscer subscription for the same USD amount.",
            "Crea un pago manual completado en la suscripción Masscer activa más reciente por el mismo importe USD.",
        ),
        (
            "Requires an active Masscer subscription before registering wallet recharges as payments.",
            "Requiere una suscripción Masscer activa antes de registrar recargas del monedero como pagos.",
        ),
        ("Payment note", "Nota del pago"),
        (
            "Required when registering this recharge as a payment.",
            "Obligatoria al registrar esta recarga como pago.",
        ),
        ("Recharge wallet", "Recargar monedero"),
        ("Manual subscription (enterprise)", "Suscripción manual (enterprise)"),
        (
            "Create a new bank-transfer / enterprise manual subscription. Saving will mark every existing Masscer subscription row for this organization as cancelled, then add one new manual row. This does not call Stripe; cancel billing in Stripe separately if needed.",
            "Crea una suscripción manual nueva (transferencia / enterprise). Al guardar se marcarán como canceladas todas las filas de suscripción Masscer existentes de la organización y luego se añadirá una fila manual nueva. No llama a Stripe; cancela el cobro en Stripe aparte si hace falta.",
        ),
        ("Create subscription", "Crear suscripción"),
        (
            "Warning: submitting this form will immediately mark all previous Masscer subscription rows as cancelled (including Stripe-linked rows in Masscer only) and then create one new manual subscription. Stripe may continue charging until you cancel from the corresponding subscription row below.",
            "Aviso: al enviar este formulario se marcarán de inmediato como canceladas todas las filas de suscripción Masscer anteriores (solo en Masscer, incluidas las enlazadas a Stripe) y luego se creará una suscripción manual nueva. Stripe puede seguir cobrando hasta que canceles desde la fila de suscripción correspondiente más abajo.",
        ),
        (
            "I understand that all existing Masscer subscription rows for this organization will be marked cancelled and one new manual subscription will be created.",
            "Entiendo que se marcarán como canceladas todas las filas de suscripción Masscer existentes de esta organización y se creará una suscripción manual nueva.",
        ),
        ("Create manual subscription", "Crear suscripción manual"),
        (
            "The custom subscription plan is missing. Run sync_subscription_plans (or your usual deploy startup) to seed catalog plans.",
            "Falta el plan de suscripción «custom». Ejecuta sync_subscription_plans (o el arranque habitual del despliegue) para sembrar los planes del catálogo.",
        ),
        (
            "This flow always uses the Custom catalog plan for admin-created enterprise deals. It is not tied to Stripe product prices for organization or free trial. Set contract price and credit overrides on this row as needed.",
            "Este flujo siempre usa el plan de catálogo Custom para acuerdos enterprise creados desde el admin. No está ligado a los precios de producto Stripe de organization ni de prueba gratuita. Ajusta precio contractual y anulaciones de crédito en esta fila según convenga.",
        ),
        ("Registered payments", "Pagos registrados"),
        (
            "SubscriptionPayment records linked to this organization's subscriptions (most recent first).",
            "Registros SubscriptionPayment vinculados a las suscripciones de esta organización (más recientes primero).",
        ),
        (
            "No subscription payments recorded for this organization.",
            "No hay pagos de suscripción registrados para esta organización.",
        ),
        ("Date", "Fecha"),
        ("Method", "Método"),
        ("Notes", "Notas"),
        ("Active", "Activo"),
        ("or", "o"),
        ("Trial", "Prueba"),
        (
            "allows usage (subject to end date). Use",
            "permite uso (sujeto a fecha de fin). Usa",
        ),
        ("Expired", "Caducado"),
        ("Cancelled", "Cancelado"),
        ("to block access from this row.", "para bloquear el acceso desde esta fila."),
        ("Billing interval", "Intervalo de facturación"),
        (
            "For documentation and negotiations; Stripe renewals are controlled in Stripe, not by this field.",
            "Para documentación y negociación; las renovaciones de Stripe se controlan en Stripe, no con este campo.",
        ),
        ("End date (optional)", "Fecha de fin (opcional)"),
        ("Calculate from now", "Calcular desde ahora"),
        (
            "When this manual deal ends in Masscer (end of chosen day, UTC). Leave empty for no fixed end on this row.",
            "Cuando termina este acuerdo manual en Masscer (fin del día elegido, UTC). Déjalo vacío para sin fin fijo en esta fila.",
        ),
        ("Credit budget (USD)", "Presupuesto de crédito (USD)"),
        (
            "Monthly (or per-recharge) USD budget for this deal; converted to compute units when you recharge from this subscription. Required for manual custom subscriptions.",
            "Presupuesto mensual (o por recarga) en USD de este acuerdo; se convierte a unidades de cómputo al recargar desde esta suscripción. Obligatorio para suscripciones manuales con plan custom.",
        ),
        ("Contract price (USD)", "Precio contractual (USD)"),
        (
            "Negotiated list price for reporting and owner UI. Does not change Stripe prices. Required for manual custom subscriptions.",
            "Precio de lista negociado para informes y la UI del propietario. No cambia precios en Stripe. Obligatorio para suscripciones manuales con plan custom.",
        ),
        ("Internal notes (admin only)", "Notas internas (solo admin)"),
        ("Not shown to organization owners in the product API.", "No se muestra a los propietarios de la org en la API del producto."),
        (
            "Recharge wallet with this subscription's credit budget now",
            "Recargar monedero ahora con el presupuesto de crédito de esta suscripción",
        ),
        (
            "When checked, after save we add compute units from the USD credit budget set above. Uncheck to only change metadata on the row.",
            "Si está marcado, tras guardar añadimos unidades de cómputo según el presupuesto de crédito en USD indicado arriba. Desmárcalo para solo cambiar metadatos de la fila.",
        ),
        ("Organization feature flags", "Feature flags de la organización"),
        ("Only flags marked", "Solo aparecen flags marcados como"),
        ("organization-only", "solo-organización"),
        (
            "in the Feature Flag admin appear here. Toggles apply to this organization only.",
            "en el admin de Feature Flag. Los interruptores aplican solo a esta organización.",
        ),
        (
            "No organization-only feature flags defined.",
            "No hay feature flags definidos como solo-organización.",
        ),
        ("Flag", "Flag"),
        ("Enabled", "Activado"),
        ("Action", "Acción"),
        ("Disable", "Desactivar"),
        ("Enable", "Activar"),
        # Python / admin messages
        ("Invalid decimal: %(value)s", "Decimal no válido: %(value)s"),
        ("Invalid end date", "Fecha de fin no válida"),
        ("No wallet", "Sin monedero"),
        ("Low balance", "Saldo bajo"),
        ("Inactive subscription", "Suscripción inactiva"),
        ("Pending payment", "Pago pendiente"),
        ("No subscription", "Sin suscripción"),
        ("No Stripe subscription id on this row.", "No hay id de suscripción de Stripe en esta fila."),
        ("STRIPE_SECRET_KEY is not configured.", "STRIPE_SECRET_KEY no está configurada."),
        ("Unknown action.", "Acción desconocida."),
        ("Stripe error: %(msg)s", "Error de Stripe: %(msg)s"),
        ("Billing: %(name)s", "Facturación: %(name)s"),
        ("Plan is required.", "El plan es obligatorio."),
        ("Invalid plan.", "Plan no válido."),
        (
            "Manual subscriptions from this page must use the custom catalog plan.",
            "Las suscripciones manuales desde esta página deben usar el plan de catálogo custom.",
        ),
        (
            "Credit budget (USD) is required for manual custom subscriptions.",
            "El presupuesto de crédito (USD) es obligatorio para suscripciones manuales con plan custom.",
        ),
        (
            "Contract price (USD) is required for manual custom subscriptions.",
            "El precio contractual (USD) es obligatorio para suscripciones manuales con plan custom.",
        ),
        ("Credit budget (USD) cannot be negative.", "El presupuesto de crédito (USD) no puede ser negativo."),
        ("Contract price (USD) cannot be negative.", "El precio contractual (USD) no puede ser negativo."),
        ("Invalid subscription status.", "Estado de suscripción no válido."),
        ("Invalid billing interval.", "Intervalo de facturación no válido."),
        (
            "Only monthly, quarterly, or yearly subscriptions can be renewed.",
            "Solo se pueden renovar suscripciones mensuales, trimestrales o anuales.",
        ),
        (
            'Check "I confirm manual renewal" before renewing this subscription.',
            'Marca «Confirmo esta renovación manual» antes de renovar esta suscripción.',
        ),
        (
            "This subscription interval is not renewable from admin.",
            "Este intervalo de suscripción no es renovable desde admin.",
        ),
        (
            "Only active or expired subscriptions can be renewed from admin.",
            "Solo se pueden renovar desde admin suscripciones activas o expiradas.",
        ),
        (
            "Could not recharge wallet from this subscription's USD credit budget.",
            "No se pudo recargar el monedero desde el presupuesto de crédito USD de esta suscripción.",
        ),
        (
            "Manual renewal in admin. Previous end: %(old)s. New end: %(new)s.",
            "Renovación manual en admin. Fin anterior: %(old)s. Nuevo fin: %(new)s.",
        ),
        (
            "Subscription renewed. End date extended, wallet recharged, and payment registered.",
            "Suscripción renovada. Se extendió la fecha de fin, se recargó el monedero y se registró el pago.",
        ),
        (
            "Check the box to confirm that all existing Masscer subscription rows for this organization will be marked cancelled before creating a new manual subscription.",
            "Marca la casilla para confirmar que se marcarán como canceladas todas las filas de suscripción Masscer existentes de esta organización antes de crear una suscripción manual nueva.",
        ),
        ("Created new manual subscription.", "Nueva suscripción manual creada."),
        ("Created manual subscription.", "Suscripción manual creada."),
        ("Wallet recharged from subscription credit budget.", "Monedero recargado desde el presupuesto de crédito de la suscripción."),
        (
            "Recharge skipped: no USD credit budget configured for this subscription.",
            "Recarga omitida: no hay presupuesto de crédito en USD configurado para esta suscripción.",
        ),
        ("Enter a positive amount_usd for wallet recharge.", "Introduce un amount_usd positivo para recargar el monedero."),
        ("Wallet credited with %(amount)s USD equivalent.", "Monedero acreditado con el equivalente a %(amount)s USD."),
        (
            "Wallet recharge requires at least one active Masscer subscription.",
            "La recarga del monedero requiere al menos una suscripción Masscer activa.",
        ),
        (
            "Use no more than two decimal places when registering a payment.",
            "Usa máximo dos decimales al registrar un pago.",
        ),
        (
            "Payment note is required when registering a payment.",
            "La nota del pago es obligatoria al registrar un pago.",
        ),
        (
            "Registered wallet recharge as a payment.",
            "Recarga del monedero registrada como pago.",
        ),
        ("Could not recharge wallet (Compute Unit currency missing?).", "No se pudo recargar el monedero (¿falta la moneda Unidad de cómputo?)."),
        ("Missing feature_flag_id.", "Falta feature_flag_id."),
        ("Invalid feature_flag_id.", "feature_flag_id no válido."),
        ("Invalid enabled value.", "Valor de «enabled» no válido."),
        ("Unknown or non-organization feature flag.", "Feature flag desconocido o no es solo-organización."),
        ("Feature flag '%(name)s' set to %(state)s.", "Feature flag «%(name)s» establecido en %(state)s."),
        ("On", "Activado"),
        ("Off", "Desactivado"),
        ("Invalid Masscer subscription id.", "Id de suscripción Masscer no válido."),
        ("Subscription not found for this organization.", "Suscripción no encontrada para esta organización."),
        ("That subscription row has no Stripe subscription id.", "Esa fila de suscripción no tiene id de suscripción de Stripe."),
        (
            'Check "I confirm this Stripe change" before cancelling in Stripe.',
            'Marca «Confirmo este cambio en Stripe» antes de cancelar en Stripe.',
        ),
        ("Stripe is not configured (STRIPE_SECRET_KEY).", "Stripe no está configurado (STRIPE_SECRET_KEY)."),
        (
            "Stripe will cancel this subscription at the end of the current billing period. The row in Masscer may stay active until Stripe webhooks run.",
            "Stripe cancelará esta suscripción al final del periodo de facturación actual. La fila en Masscer puede seguir activa hasta que corran los webhooks de Stripe.",
        ),
        (
            "Stripe subscription cancelled immediately. This Masscer subscription row was marked cancelled.",
            "Suscripción de Stripe cancelada de inmediato. La fila de suscripción de Masscer se marcó como cancelada.",
        ),
    ]

    with out.open("w", encoding="utf-8") as f:
        f.write(
            '# Spanish translations for Masscer admin (organization management).\n'
            'msgid ""\n'
            'msgstr ""\n'
            '"Project-Id-Version: Masscer\\n"\n'
            '"Language: es\\n"\n'
            '"MIME-Version: 1.0\\n"\n'
            '"Content-Type: text/plain; charset=UTF-8\\n"\n'
            '"Content-Transfer-Encoding: 8bit\\n"\n'
            '"Plural-Forms: nplurals=2; plural=(n != 1);\\n"\n\n'
        )

        for msgid, msgstr in pairs:
            write_msg(f, msgid, msgstr)

        # blocktrans from billing_detail (variable count)
        write_plural(
            f,
            "View %(count)s active subscription",
            "View %(count)s active subscriptions",
            "Ver %(count)s suscripción activa",
            "Ver %(count)s suscripciones activas",
        )
        write_plural(
            f,
            "View %(count)s past subscription",
            "View %(count)s past subscriptions",
            "Ver %(count)s suscripción pasada",
            "Ver %(count)s suscripciones pasadas",
        )
        write_plural(
            f,
            "View %(count)s active or expired Masscer subscription row",
            "View %(count)s active or expired Masscer subscription rows",
            "Ver %(count)s fila de suscripción Masscer activa o expirada",
            "Ver %(count)s filas de suscripción Masscer activas o expiradas",
        )
        write_plural(
            f,
            "View %(count)s inactive Masscer subscription row",
            "View %(count)s inactive Masscer subscription rows",
            "Ver %(count)s fila de suscripción Masscer inactiva",
            "Ver %(count)s filas de suscripción Masscer inactivas",
        )
        # blocktrans from language_settings.html
        write_msg(
            f,
            "Current language code: <code>%(current)s</code>.",
            "Código de idioma actual: <code>%(current)s</code>.",
        )

        write_plural(
            f,
            "Stripe reported missing subscription id(s); cleared stale stripe_subscription_id from one Masscer row.",
            "Stripe reported missing subscription id(s); cleared stale stripe_subscription_id from %(count)d Masscer rows.",
            "Stripe informó ids de suscripción faltantes; se limpió el stripe_subscription_id obsoleto de una fila de Masscer.",
            "Stripe informó ids de suscripción faltantes; se limpió el stripe_subscription_id obsoleto de %(count)d filas de Masscer.",
        )
        write_plural(
            f,
            "This Stripe subscription no longer exists (removed or expired). Cleared stale stripe_subscription_id from one Masscer row.",
            "This Stripe subscription no longer exists (removed or expired). Cleared stale stripe_subscription_id from %(count)d Masscer rows.",
            "Esta suscripción de Stripe ya no existe (eliminada o caducada). Se limpió el stripe_subscription_id obsoleto de una fila de Masscer.",
            "Esta suscripción de Stripe ya no existe (eliminada o caducada). Se limpió el stripe_subscription_id obsoleto de %(count)d filas de Masscer.",
        )

        write_plural(
            f,
            "Marked one previous Masscer subscription row as cancelled; created new manual subscription.",
            "Marked %(count)d previous Masscer subscription rows as cancelled; created new manual subscription.",
            "Se marcó una fila de suscripción Masscer anterior como cancelada; se creó una nueva suscripción manual.",
            "Se marcaron %(count)d filas de suscripción Masscer anteriores como canceladas; se creó una nueva suscripción manual.",
        )

    print(f"Wrote {out}")

    import polib

    po = polib.pofile(str(out))
    mo_path = out.with_suffix(".mo")
    po.save_as_mofile(str(mo_path))
    print(f"Wrote {mo_path}")


if __name__ == "__main__":
    main()
