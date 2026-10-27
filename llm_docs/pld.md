# PLD runs

Rules for PLD files (`server/api/compliance`) that the code doesn't make obvious.

## Who goes first

The organization can complete its own PLD at any time: before, during, or after its clients and suppliers. Nothing waits on counterparties.

## Runs and history

- A `PLDExpedient` is one run for one `PLDEntity`. Each new analysis adds a run with the next `version`. Old runs are never edited or deleted.
- An entity can have only one open run, meaning a run that is not signed or delivered. The database enforces this.
- Always get the current run with `entity.current_expedient()`, which returns the highest version. Never use `expedients.first()` or order by `created_at`.
- A new run starts by hand, any time the current run is finished. There is no schedule, because official papers (deeds, powers, partner changes) can change at any moment.
- Both sides can start one: the organization from the compliance page (`POST /v1/compliance/entities/<id>/expedients/`), and the client or supplier from their own page (`start_new_run` action). Both are refused while the current run is open.
- "Reset" only works on an unfinished run, so it can never erase history.
- A new run asks for new documents. Identification data on the entity is kept as a starting point. The per-run answers (truthfulness consent, risk declarations, notice invoices) are cleared so the person answers them again.
- When the organization starts a new run for a client or supplier, it also emails them an invite link.

## Frozen data

Identification data lives on `PLDEntity.metadata`, which the next run overwrites. So when a run is signed, `mark_expedient_signed` copies the metadata and matrix score into `PLDExpedient.entity_snapshot` and sets `completed_at`. Runs that finished before this existed are frozen when the next run starts.

## Who sees history

The organization sees every run of every entity, with documents and ZIP downloads. A client or supplier sees their own past runs and can download each signed PDF.

## Known Gaps

- The organization isn't told when a client or supplier starts a new run on their own.
