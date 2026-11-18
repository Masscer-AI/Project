from __future__ import annotations

from dataclasses import dataclass

from api.compliance.models import (
    WatchlistListSlug,
    WatchlistSnapshot,
    WatchlistSnapshotStatus,
)
from api.compliance.watchlists.sat_cff import SAT_SOURCES

FETCH = "fetch"
WATCH = "watch"
OFF = "off"


@dataclass(frozen=True)
class WatchlistSource:
    slug: str
    url: str
    mode: str
    parser: str = ""


SOURCES: tuple[WatchlistSource, ...] = (
    WatchlistSource(
        WatchlistListSlug.ONU_CSNU,
        "https://scsanctions.un.org/resources/xml/en/consolidated.xml",
        FETCH,
        "un",
    ),
    *(
        WatchlistSource(slug, url, FETCH, "sat")
        for slug, url in SAT_SOURCES.items()
    ),
    WatchlistSource(
        WatchlistListSlug.OFAC_SDN,
        "https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/SDN_ENHANCED.XML",
        FETCH,
        "ofac",
    ),
    WatchlistSource(
        WatchlistListSlug.OFAC_CONS,
        "https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/CONS_ENHANCED.XML",
        FETCH,
        "ofac",
    ),
    WatchlistSource(
        WatchlistListSlug.UK_UKSL,
        "https://sanctionslist.fcdo.gov.uk/docs/UK-Sanctions-List.xml",
        FETCH,
        "uk",
    ),
    WatchlistSource(
        WatchlistListSlug.EU_FSF,
        "https://webgate.ec.europa.eu/fsd/fsf/public/files/xmlFullSanctionsList_1_1/content?token=dG9rZW4tMjAxNw",
        FETCH,
        "eu",
    ),
    WatchlistSource(
        WatchlistListSlug.CA_SEMA,
        "https://www.international.gc.ca/world-monde/assets/office_docs/international_relations-relations_internationales/sanctions/sema-lmes.xml",
        FETCH,
        "ca",
    ),
    WatchlistSource(
        WatchlistListSlug.MX_49BIS,
        "https://dof.gob.mx/nota_detalle.php?codigo=5797381&fecha=28/08/2026",
        WATCH,
    ),
    WatchlistSource(
        WatchlistListSlug.FATF_HIGH,
        "https://www.fatf-gafi.org/en/publications/High-risk-and-other-monitored-jurisdictions/call-for-action-october-2026.html",
        WATCH,
    ),
    WatchlistSource(
        WatchlistListSlug.FATF_GREY,
        "https://www.fatf-gafi.org/en/publications/High-risk-and-other-monitored-jurisdictions/increased-monitoring-october-2026.html",
        WATCH,
    ),
    WatchlistSource(
        WatchlistListSlug.EU_AML,
        "https://finance.ec.europa.eu/financial-crime/anti-money-laundering-and-countering-financing-terrorism-international-level_en",
        WATCH,
    ),
    WatchlistSource(
        WatchlistListSlug.EU_TAX,
        "https://www.consilium.europa.eu/en/policies/eu-list-of-non-cooperative-jurisdictions/",
        WATCH,
    ),
    WatchlistSource(
        WatchlistListSlug.US_FINCEN,
        "https://www.fincen.gov/resources/statutes-and-regulations/311-special-measures",
        WATCH,
    ),
    WatchlistSource(
        WatchlistListSlug.US_FTO,
        "https://www.state.gov/foreign-terrorist-organizations/",
        WATCH,
    ),
    WatchlistSource(
        WatchlistListSlug.MX_UIF,
        "https://www.gob.mx/uif/archivo/prensa?idiom=es",
        WATCH,
    ),
    WatchlistSource(
        WatchlistListSlug.EU_MAP,
        "https://sanctionsmap.eu/",
        WATCH,
    ),
    WatchlistSource(
        WatchlistListSlug.MX_LPB,
        "https://websitipld.cnbv.gob.mx/",
        OFF,
    ),
    WatchlistSource(
        WatchlistListSlug.INTERPOL_RN,
        "https://www.interpol.int/How-we-work/Notices/View-Red-Notices",
        OFF,
    ),
    WatchlistSource(
        WatchlistListSlug.MX_PEP,
        "https://www.gob.mx/shcp/documentos/uif-marco-juridico-personas-politicamente-expuestas-nacionales",
        OFF,
    ),
    WatchlistSource(
        WatchlistListSlug.MX_SABG,
        "https://directoriosancionados.buengobierno.gob.mx/",
        OFF,
    ),
    WatchlistSource(
        WatchlistListSlug.PL_MSWIA,
        "https://www.gov.pl/web/mswia/lista-osob-i-podmiotow-objetych-sankcjami",
        OFF,
    ),
)

SOURCE_BY_SLUG = {source.slug: source for source in SOURCES}


def active_sources() -> list[WatchlistSource]:
    return [source for source in SOURCES if source.mode != OFF]


def _failure_text(source: WatchlistSource, current, latest, status: str) -> str:
    if status != "failed":
        return ""
    row = latest
    if source.mode == WATCH and current is not None and current.error:
        row = current
    return row.error[:500]


def _status(source: WatchlistSource, current, latest) -> str:
    if source.mode == OFF:
        return "not_loaded"
    if source.mode == WATCH:
        if current is None:
            if latest and latest.status == WatchlistSnapshotStatus.FAILED:
                return "failed"
            return "not_loaded"
        if current.status == WatchlistSnapshotStatus.NEEDS_DOWNLOAD:
            return "needs_download"
        if current.error:
            return "failed"
        return "unchanged"
    if (
        latest
        and latest.status == WatchlistSnapshotStatus.FAILED
        and (current is None or latest.ingested_at > current.ingested_at)
    ):
        return "failed"
    if current and current.status == WatchlistSnapshotStatus.SUCCEEDED:
        return "loaded"
    return "not_loaded"


def catalog_rows() -> list[dict]:
    current = {
        row.list_slug: row
        for row in WatchlistSnapshot.objects.filter(is_current=True)
    }
    latest = {}
    for row in WatchlistSnapshot.objects.order_by("-ingested_at"):
        latest.setdefault(row.list_slug, row)
    rows = []
    for source in SOURCES:
        snap = current.get(source.slug)
        last = latest.get(source.slug)
        when = snap.ingested_at if snap else None
        status = _status(source, snap, last)
        rows.append(
            {
                "list_slug": source.slug,
                "mode": source.mode,
                "status": status,
                "error": _failure_text(source, snap, last, status),
                "source_url": source.url,
                "record_count": snap.record_count if snap and source.mode == FETCH else 0,
                "date_generated": snap.date_generated if snap and source.mode == FETCH else "",
                "ingested_at": when.isoformat() if when else None,
            }
        )
    return rows
