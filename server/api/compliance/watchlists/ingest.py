from __future__ import annotations

import hashlib
import logging
import urllib.request

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from api.compliance.models import (
    WatchlistListSlug,
    WatchlistRecord,
    WatchlistSnapshot,
    WatchlistSnapshotStatus,
)
from api.compliance.watchlists.catalog import (
    WatchlistSource,
    active_sources,
)
from api.compliance.watchlists.official_xml import (
    parse_canada_sema,
    parse_eu_fsf,
    parse_ofac_enhanced,
    parse_uk_sanctions,
)
from api.compliance.watchlists.sat_cff import SAT_SOURCES, parse_sat_csv
from api.compliance.watchlists.un_csnu import DEFAULT_SOURCE_URL, parse_un_consolidated

PARSERS = {
    "ofac": parse_ofac_enhanced,
    "uk": parse_uk_sanctions,
    "eu": parse_eu_fsf,
    "ca": parse_canada_sema,
}

logger = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 MasscerWatchlistIngest/1.0"


def download_url(url: str, timeout: int = 180) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def latest_succeeded_snapshot(list_slug: str) -> WatchlistSnapshot | None:
    return (
        WatchlistSnapshot.objects.filter(
            list_slug=list_slug,
            status=WatchlistSnapshotStatus.SUCCEEDED,
        )
        .order_by("-ingested_at")
        .first()
    )


def unchanged_if_same_hash(
    *, list_slug: str, file_bytes: bytes, force: bool
) -> dict | None:
    digest = hashlib.sha256(file_bytes).hexdigest()
    previous = latest_succeeded_snapshot(list_slug)
    if force or not previous or previous.file_sha256 != digest:
        return None
    logger.info("%s watchlist unchanged (%s)", list_slug, digest[:12])
    return {
        "status": "unchanged",
        "list_slug": list_slug,
        "snapshot_id": str(previous.id),
        "file_sha256": digest,
        "record_count": previous.record_count,
    }


def record_failed_snapshot(*, list_slug: str, source_url: str, file_bytes: bytes, error: str):
    WatchlistSnapshot.objects.create(
        list_slug=list_slug,
        source_url=source_url,
        file_sha256="",
        content_length=len(file_bytes) if file_bytes else 0,
        status=WatchlistSnapshotStatus.FAILED,
        is_current=False,
        error=error[:4000],
    )


def persist_watchlist_records(
    *,
    list_slug: str,
    source_url: str,
    file_bytes: bytes,
    parsed: dict,
    label: str = "watchlist",
) -> dict:
    digest = hashlib.sha256(file_bytes).hexdigest()
    records = parsed["records"]
    with transaction.atomic():
        snapshot = WatchlistSnapshot.objects.create(
            list_slug=list_slug,
            source_url=source_url,
            file_sha256=digest,
            content_length=len(file_bytes),
            date_generated=parsed.get("date_generated") or "",
            status=WatchlistSnapshotStatus.SUCCEEDED,
            is_current=False,
            record_count=len(records),
        )
        WatchlistRecord.objects.bulk_create(
            [
                WatchlistRecord(
                    snapshot=snapshot,
                    record_type=row["record_type"],
                    reference_number=row["reference_number"][:64],
                    data_id=row["data_id"][:32],
                    primary_name=row["primary_name"],
                    listed_on=row["listed_on"][:32],
                    names=row["names"],
                    dates_of_birth=row["dates_of_birth"],
                    document_numbers=row["document_numbers"],
                    nationalities=row["nationalities"],
                    search_document=row["search_document"],
                    raw=row["raw"],
                )
                for row in records
            ],
            batch_size=500,
        )
        WatchlistSnapshot.objects.filter(
            list_slug=list_slug,
            is_current=True,
        ).exclude(pk=snapshot.pk).update(is_current=False)
        snapshot.is_current = True
        snapshot.save(update_fields=["is_current"])

    logger.info(
        "Ingested %s watchlist %s (%s records, generated %s)",
        label,
        digest[:12],
        len(records),
        snapshot.date_generated,
    )
    return {
        "status": "updated",
        "list_slug": list_slug,
        "snapshot_id": str(snapshot.id),
        "file_sha256": digest,
        "record_count": len(records),
        "date_generated": snapshot.date_generated,
    }


def ingest_un_csnu(
    *,
    xml_bytes: bytes | None = None,
    force: bool = False,
    download=download_url,
) -> dict:
    source_url = getattr(settings, "WATCHLIST_UN_CSNU_URL", "") or DEFAULT_SOURCE_URL
    list_slug = WatchlistListSlug.ONU_CSNU
    file_bytes = b""
    try:
        if xml_bytes is None:
            xml_bytes = download(source_url)
        file_bytes = xml_bytes
        skipped = unchanged_if_same_hash(
            list_slug=list_slug, file_bytes=file_bytes, force=force
        )
        if skipped:
            return skipped
        parsed = parse_un_consolidated(file_bytes)
        return persist_watchlist_records(
            list_slug=list_slug,
            source_url=source_url,
            file_bytes=file_bytes,
            parsed=parsed,
            label="UN CSNU",
        )
    except Exception as exc:
        logger.exception("UN CSNU watchlist ingest failed")
        record_failed_snapshot(
            list_slug=list_slug,
            source_url=source_url,
            file_bytes=file_bytes,
            error=str(exc),
        )
        raise


def ingest_sat_list(
    list_slug: str,
    *,
    csv_bytes: bytes | None = None,
    force: bool = False,
    download=download_url,
) -> dict:
    source_url = SAT_SOURCES[list_slug]
    file_bytes = b""
    try:
        if csv_bytes is None:
            csv_bytes = download(source_url)
        file_bytes = csv_bytes
        skipped = unchanged_if_same_hash(
            list_slug=list_slug, file_bytes=file_bytes, force=force
        )
        if skipped:
            return skipped
        parsed = parse_sat_csv(file_bytes)
        return persist_watchlist_records(
            list_slug=list_slug,
            source_url=source_url,
            file_bytes=file_bytes,
            parsed=parsed,
            label=list_slug,
        )
    except Exception as exc:
        logger.exception("%s watchlist ingest failed", list_slug)
        record_failed_snapshot(
            list_slug=list_slug,
            source_url=source_url,
            file_bytes=file_bytes,
            error=str(exc),
        )
        raise


def _ingest_bytes(
    source: WatchlistSource,
    parse,
    *,
    file_bytes: bytes | None,
    force: bool,
    download,
) -> dict:
    payload = b""
    try:
        if file_bytes is None:
            file_bytes = download(source.url)
        payload = file_bytes
        skipped = unchanged_if_same_hash(
            list_slug=source.slug, file_bytes=payload, force=force
        )
        if skipped:
            return skipped
        parsed = parse(payload)
        return persist_watchlist_records(
            list_slug=source.slug,
            source_url=source.url,
            file_bytes=payload,
            parsed=parsed,
            label=source.slug,
        )
    except Exception as exc:
        logger.exception("%s watchlist ingest failed", source.slug)
        record_failed_snapshot(
            list_slug=source.slug,
            source_url=source.url,
            file_bytes=payload,
            error=str(exc),
        )
        raise


def ingest_fetch(
    source: WatchlistSource,
    *,
    file_bytes: bytes | None = None,
    force: bool = False,
    download=download_url,
) -> dict:
    if source.parser == "un":
        return ingest_un_csnu(xml_bytes=file_bytes, force=force, download=download)
    if source.parser == "sat":
        return ingest_sat_list(
            source.slug, csv_bytes=file_bytes, force=force, download=download
        )
    return _ingest_bytes(
        source,
        PARSERS[source.parser],
        file_bytes=file_bytes,
        force=force,
        download=download,
    )


def ingest_uploaded_file(source: WatchlistSource, file_bytes: bytes) -> dict:
    skipped = unchanged_if_same_hash(
        list_slug=source.slug, file_bytes=file_bytes, force=False
    )
    if skipped:
        return skipped
    if source.parser == "un":
        parsed = parse_un_consolidated(file_bytes)
    elif source.parser == "sat":
        parsed = parse_sat_csv(file_bytes)
    else:
        parsed = PARSERS[source.parser](file_bytes)
    return persist_watchlist_records(
        list_slug=source.slug,
        source_url=source.url,
        file_bytes=file_bytes,
        parsed=parsed,
        label=source.slug,
    )


def apply_watch_page(source: WatchlistSource, page_bytes: bytes) -> dict:
    digest = hashlib.sha256(page_bytes).hexdigest()
    current = WatchlistSnapshot.objects.filter(
        list_slug=source.slug, is_current=True
    ).first()
    now = timezone.now()
    if current is None:
        WatchlistSnapshot.objects.create(
            list_slug=source.slug,
            source_url=source.url,
            file_sha256=digest,
            content_length=len(page_bytes),
            status=WatchlistSnapshotStatus.SUCCEEDED,
            is_current=True,
            record_count=0,
        )
        return {
            "status": "unchanged",
            "list_slug": source.slug,
            "needs_download": False,
        }
    current.ingested_at = now
    current.error = ""
    if current.file_sha256 == digest:
        current.status = WatchlistSnapshotStatus.SUCCEEDED
        current.save(update_fields=["status", "error", "ingested_at"])
        return {
            "status": "unchanged",
            "list_slug": source.slug,
            "needs_download": False,
        }
    current.status = WatchlistSnapshotStatus.NEEDS_DOWNLOAD
    current.save(update_fields=["status", "error", "ingested_at"])
    return {
        "status": "needs_download",
        "list_slug": source.slug,
        "needs_download": True,
    }


def ingest_watch(
    source: WatchlistSource,
    *,
    page_bytes: bytes | None = None,
    download=download_url,
) -> dict:
    payload = b""
    try:
        if page_bytes is None:
            page_bytes = download(source.url)
        payload = page_bytes
        return apply_watch_page(source, payload)
    except Exception as exc:
        logger.exception("%s watchlist page check failed", source.slug)
        current = WatchlistSnapshot.objects.filter(
            list_slug=source.slug, is_current=True
        ).first()
        if current is None:
            record_failed_snapshot(
                list_slug=source.slug,
                source_url=source.url,
                file_bytes=payload,
                error=str(exc),
            )
        else:
            current.error = str(exc)[:4000]
            current.save(update_fields=["error"])
        raise


def ingest_all_watchlists(*, force: bool = False, download=download_url) -> dict:
    results = []
    errors = []
    for source in active_sources():
        try:
            if source.mode == "watch":
                results.append(ingest_watch(source, download=download))
            else:
                results.append(ingest_fetch(source, force=force, download=download))
        except Exception as exc:
            errors.append({"list_slug": source.slug, "error": str(exc)[:500]})
    if errors and not results:
        raise RuntimeError(f"All watchlist ingests failed: {errors}")
    return {"results": results, "errors": errors}
