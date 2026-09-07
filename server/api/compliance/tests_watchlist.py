from django.test import SimpleTestCase, TestCase

from api.compliance.models import WatchlistRecord, WatchlistSnapshot, WatchlistSnapshotStatus
from api.compliance.watchlists.ingest import ingest_sat_list, ingest_un_csnu
from api.compliance.watchlists.normalize import fold_text
from api.compliance.watchlists.search import search_watchlist_records
from api.compliance.watchlists.sat_cff import parse_sat_csv
from api.compliance.watchlists.un_csnu import parse_un_consolidated

SAMPLE_UN_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<CONSOLIDATED_LIST dateGenerated="2026-09-07T12:00:00-05:00">
  <INDIVIDUALS>
    <INDIVIDUAL>
      <DATAID>110111</DATAID>
      <FIRST_NAME>Qosa</FIRST_NAME>
      <SECOND_NAME>Abdullah</SECOND_NAME>
      <THIRD_NAME>Jose</THIRD_NAME>
      <UN_LIST_TYPE>Al-Qaida</UN_LIST_TYPE>
      <REFERENCE_NUMBER>QDi.001</REFERENCE_NUMBER>
      <LISTED_ON>2001-10-17</LISTED_ON>
      <COMMENTS1>Associated with Al-Qaida.</COMMENTS1>
      <NATIONALITY>
        <VALUE>Saudi Arabia</VALUE>
      </NATIONALITY>
      <INDIVIDUAL_ALIAS>
        <QUALITY>Good</QUALITY>
        <ALIAS_NAME>Abu Mohammed</ALIAS_NAME>
      </INDIVIDUAL_ALIAS>
      <INDIVIDUAL_DATE_OF_BIRTH>
        <TYPE_OF_DATE>EXACT</TYPE_OF_DATE>
        <DATE>1958-04-30</DATE>
      </INDIVIDUAL_DATE_OF_BIRTH>
      <INDIVIDUAL_DOCUMENT>
        <TYPE_OF_DOCUMENT>Passport</TYPE_OF_DOCUMENT>
        <NUMBER>A1234567</NUMBER>
      </INDIVIDUAL_DOCUMENT>
    </INDIVIDUAL>
    <INDIVIDUAL>
      <DATAID>220222</DATAID>
      <FIRST_NAME>Unrelated</FIRST_NAME>
      <SECOND_NAME>Person</SECOND_NAME>
      <REFERENCE_NUMBER>QDi.999</REFERENCE_NUMBER>
      <LISTED_ON>2010-01-01</LISTED_ON>
      <NATIONALITY>
        <VALUE>Mexico</VALUE>
      </NATIONALITY>
    </INDIVIDUAL>
  </INDIVIDUALS>
  <ENTITIES>
    <ENTITY>
      <DATAID>330333</DATAID>
      <FIRST_NAME>Eastern Turkistan Islamic Movement</FIRST_NAME>
      <UN_LIST_TYPE>Al-Qaida</UN_LIST_TYPE>
      <REFERENCE_NUMBER>QDe.088</REFERENCE_NUMBER>
      <LISTED_ON>2002-09-11</LISTED_ON>
      <ENTITY_ALIAS>
        <QUALITY>Good</QUALITY>
        <ALIAS_NAME>ETIM</ALIAS_NAME>
      </ENTITY_ALIAS>
    </ENTITY>
  </ENTITIES>
</CONSOLIDATED_LIST>
"""


class UnCsnuParserTests(SimpleTestCase):
    def test_parses_individuals_and_entities(self):
        parsed = parse_un_consolidated(SAMPLE_UN_XML)
        self.assertEqual(parsed["date_generated"], "2026-09-07T12:00:00-05:00")
        self.assertEqual(len(parsed["records"]), 3)
        by_ref = {row["reference_number"]: row for row in parsed["records"]}
        person = by_ref["QDi.001"]
        self.assertEqual(person["record_type"], "individual")
        self.assertEqual(person["primary_name"], "Qosa Abdullah Jose")
        self.assertIn("Abu Mohammed", person["names"])
        self.assertEqual(person["dates_of_birth"], ["1958-04-30"])
        self.assertEqual(person["document_numbers"], ["A1234567"])
        self.assertEqual(person["nationalities"], ["Saudi Arabia"])
        self.assertIn(fold_text("Jose"), person["search_document"])
        self.assertIn("a1234567", person["search_document"])
        entity = by_ref["QDe.088"]
        self.assertEqual(entity["record_type"], "entity")
        self.assertIn("ETIM", entity["names"])


class WatchlistIngestTests(TestCase):
    def test_ingest_skips_unchanged_hash(self):
        first = ingest_un_csnu(xml_bytes=SAMPLE_UN_XML)
        self.assertEqual(first["status"], "updated")
        self.assertEqual(first["record_count"], 3)
        self.assertEqual(WatchlistSnapshot.objects.filter(is_current=True).count(), 1)
        self.assertEqual(WatchlistRecord.objects.count(), 3)

        second = ingest_un_csnu(xml_bytes=SAMPLE_UN_XML)
        self.assertEqual(second["status"], "unchanged")
        self.assertEqual(second["snapshot_id"], first["snapshot_id"])
        self.assertEqual(WatchlistSnapshot.objects.count(), 1)

        forced = ingest_un_csnu(xml_bytes=SAMPLE_UN_XML, force=True)
        self.assertEqual(forced["status"], "updated")
        self.assertEqual(WatchlistSnapshot.objects.count(), 2)
        self.assertEqual(WatchlistSnapshot.objects.filter(is_current=True).count(), 1)
        current = WatchlistSnapshot.objects.get(is_current=True)
        self.assertEqual(str(current.id), forced["snapshot_id"])
        self.assertEqual(current.status, WatchlistSnapshotStatus.SUCCEEDED)

    def test_and_text_search(self):
        ingest_un_csnu(xml_bytes=SAMPLE_UN_XML)
        both = search_watchlist_records(query="qosa al-qaida")
        self.assertEqual(list(both.values_list("reference_number", flat=True)), ["QDi.001"])
        missing = search_watchlist_records("qosa", "mexico")
        self.assertEqual(missing.count(), 0)
        accent = search_watchlist_records(query="JOSE")
        self.assertEqual(accent.get().reference_number, "QDi.001")
        entity = search_watchlist_records(query="etim", record_type="entity")
        self.assertEqual(entity.get().reference_number, "QDe.088")


SAMPLE_SAT_69B_CSV = (
    "Información actualizada al 31 de julio de 2026; los listados.\n"
    "Listado completo de contribuyentes (Artículo 69-B del CFF)\n"
    "No,RFC,Nombre del Contribuyente,Situación del contribuyente,"
    "Publicación página SAT presuntos\n"
    '1,AAA080808HL8,"ASESORES EN AVALUOS Y ACTIVOS, S.A. DE C.V.",'
    "Sentencia Favorable,01/06/2018\n"
    "2,AAAA620217U54,AMADOR AQUINO JOSE AVENAMAR,Definitivo,01/06/2017\n"
    "3,AABL9902181Q7,ALCARAZ BARRERA LIZBETH ALEJANDRA,Presunto,05/06/2026\n"
).encode("cp1252")

SAMPLE_SAT_69_FIRMES_CSV = (
    "RFC,RAZON SOCIAL,TIPO PERSONA,SUPUESTO,FECHA DE PRIMERA PUBLICACION,ENTIDAD FEDERATIVA\n"
    "AAG090703QT6,APLICA AGUASCALIENTES SA DE CV,M,FIRMES,01/01/2014,CIUDAD DE MEXICO\n"
    "AAGL5405077Y7,JOSE LUIS ANDRADE GARCIA,F,FIRMES,01/01/2014,NUEVO LEON\n"
    "AAGL5405077Y7,JOSE LUIS ANDRADE GARCIA,F,FIRMES,01/01/2014,NUEVO LEON\n"
).encode("cp1252")


class SatCffParserTests(SimpleTestCase):
    def test_parses_69b_complete_csv(self):
        parsed = parse_sat_csv(SAMPLE_SAT_69B_CSV)
        self.assertEqual(parsed["date_generated"], "31 de julio de 2026")
        by_rfc = {row["reference_number"]: row for row in parsed["records"]}
        self.assertEqual(len(by_rfc), 3)
        entity = by_rfc["AAA080808HL8"]
        self.assertEqual(entity["record_type"], "entity")
        self.assertIn("ASESORES EN AVALUOS Y ACTIVOS, S.A. DE C.V.", entity["names"])
        self.assertEqual(entity["listed_on"], "01/06/2018")
        person = by_rfc["AAAA620217U54"]
        self.assertEqual(person["record_type"], "individual")
        self.assertIn("definitivo", person["search_document"])
        self.assertIn("aaaa620217u54", person["search_document"])

    def test_parses_art69_and_dedupes_rfc(self):
        parsed = parse_sat_csv(SAMPLE_SAT_69_FIRMES_CSV)
        self.assertEqual(len(parsed["records"]), 2)
        by_rfc = {row["reference_number"]: row for row in parsed["records"]}
        self.assertEqual(by_rfc["AAG090703QT6"]["record_type"], "entity")
        self.assertEqual(by_rfc["AAGL5405077Y7"]["record_type"], "individual")
        self.assertEqual(by_rfc["AAGL5405077Y7"]["nationalities"], ["NUEVO LEON"])


class SatWatchlistIngestTests(TestCase):
    def test_ingest_69b_and_and_search(self):
        first = ingest_sat_list("sat_69b", csv_bytes=SAMPLE_SAT_69B_CSV)
        self.assertEqual(first["status"], "updated")
        self.assertEqual(first["record_count"], 3)
        second = ingest_sat_list("sat_69b", csv_bytes=SAMPLE_SAT_69B_CSV)
        self.assertEqual(second["status"], "unchanged")
        hits = search_watchlist_records(
            query="amador definitivo",
            list_slug="sat_69b",
        )
        self.assertEqual(hits.get().reference_number, "AAAA620217U54")
        rfc_hit = search_watchlist_records(query="AAA080808HL8", list_slug="sat_69b")
        self.assertEqual(rfc_hit.get().primary_name, "ASESORES EN AVALUOS Y ACTIVOS, S.A. DE C.V.")


class WatchlistSearchToolTests(TestCase):
    def test_and_terms_and_rfc_routing(self):
        from api.compliance.screening.search_tool import search_watchlists_impl

        ingest_sat_list("sat_69b", csv_bytes=SAMPLE_SAT_69B_CSV)
        rfc = search_watchlists_impl(["AAA080808HL8"])
        self.assertTrue(any(hit.reference_number == "AAA080808HL8" for hit in rfc.hits))
        and_query = search_watchlists_impl(["amador", "definitivo"], list_slug="sat_69b")
        self.assertEqual(and_query.hits[0].reference_number, "AAAA620217U54")
        none = search_watchlists_impl(["amador", "xyznoexiste"], list_slug="sat_69b")
        self.assertEqual(none.hits, [])

