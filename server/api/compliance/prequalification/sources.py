"""Official sources the pre-qualification agent is allowed to apply.

We do not vendor the full statutes. The DOF / Camara de Diputados texts are the
authoritative publications; this module records what Masscer operationalizes.
"""

from __future__ import annotations

RULESET_VERSION = "2026.1"

# Public official publications (not stored verbatim in the repo).
LEGAL_SOURCES = [
    {
        "id": "lfpiorpi",
        "title": "Ley Federal para la Prevencion e Identificacion de Operaciones con Recursos de Procedencia Ilicita",
        "citation": "DOF 17-10-2012 y reformas, incluida la de 16-07-2025",
        "url": "https://www.diputados.gob.mx/LeyesBiblio/pdf/LFPIORPI.pdf",
        "use": "Obligacion de identificar a clientes o usuarios que realicen actividades vulnerables y de integrar expediente.",
    },
    {
        "id": "reglamento",
        "title": "Reglamento de la LFPIORPI",
        "citation": "DOF y reforma de marzo 2026",
        "url": "https://www.diputados.gob.mx/LeyesBiblio/regley.htm",
        "use": "Desarrolla identificacion, avisos y medidas de quien realiza actividades vulnerables.",
    },
    {
        "id": "rcg",
        "title": "Reglas de caracter general a que se refiere la LFPIORPI",
        "citation": "DOF 23-08-2013, reformas 24-07-2014, 30-11-2020 y Acuerdo 115/2026 DOF 07-08-2026",
        "url": "https://www.dof.gob.mx/nota_detalle.php?codigo=5795797&fecha=07/08/2026",
        "use": (
            "Anexos 3 (persona fisica mexicana o residente permanente) y 4 "
            "(persona moral): datos y documentos del expediente de identificacion. "
            "Art. 23 Quinquies: prelacion del beneficiario controlador (25% o mas, "
            "control por otros medios, o funcionario de mayor grado). "
            "Comprobante de domicilio con antiguedad no mayor a tres meses."
        ),
    },
    {
        "id": "uif-portal",
        "title": "Portal de prevencion de lavado de dinero (SAT/UIF)",
        "citation": "Material operativo y anexos vigentes publicados por la autoridad",
        "url": "https://sppld.sat.gob.mx",
        "use": "Formatos, anexos y criterios publicados por la autoridad administrativa.",
    },
]
