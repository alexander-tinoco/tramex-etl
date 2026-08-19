# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

**Operators at the Tramex agency.** A small team that manages immigration
tramites on behalf of their clients: US visas, Global Entry, passports, and
Canada tramites (IRCC account).

The heavy lifting happens **on desktop computers, at the office**, with the
system open for the whole workday while clients are being helped. But there's
a second, confirmed and frequent, usage scene: **looking things up from the
phone outside the office** — in the consulate line, accompanying a client to
an appointment, checking a detail on the spot. In that situation what's needed
is finding a person and reading their data, including their account
credential, not capturing new records.

There are two real roles:

- **`operador`** — handles tramites: creating, viewing, editing, and archiving
  records, and looking up clients' account credentials.
- **`admin`** — additionally manages users, reviews the audit log, and runs
  the retention policy.

## Product Purpose

Replace the shared spreadsheet the agency used to run on.

That file held clients' records and, in plain-text cells next to the name and
passport number, **the passwords for those people's consular accounts** —
because the agency needs to log into those accounts to manage the tramites on
their behalf.

The system succeeds when an operator finds a person and their whole record in
seconds, gets the credential they need to log into the right portal, and all
of it gets logged without them having to do anything extra to make that happen.

## Positioning

What sets the system apart isn't the CRUD, it's **the auditable custody of
someone else's credentials**:

- Client credentials are **encrypted reversibly** (Fernet), not hashed,
  because the job is to recover and use them. A hash would make them useless.
- Because the data is recoverable, the control is access-based rather than
  cryptographic: every decryption is logged with user, date, IP, and record,
  and the system hands back to whoever looked it up the audit-entry number it
  just generated.
- Ingesting the operational file is **idempotent**: reconciling the same
  Excel file doesn't duplicate or overwrite anything.

## Operating Context

- **Data origin:** a `TRAMEX.xlsx` file maintained by hand for years, with
  four heterogeneous sheets (`Master Tramex`, `Global entry`, `Pasaportes`,
  `Canada`). The main sheet carries four title rows before the real header;
  there are filler rows and unlabeled total rows; some entries for the same
  person are duplicated with different spacing; the date column mixes real
  dates with free text (`"MARZO"`, `"pendiente"`); phone numbers come in
  inconsistent formats.
- **External portals:** the operator switches between this system and the
  consular portals (CGI/USVISA, Global Entry, IRCC), copying credentials from
  one to the other. That handoff is the day's biggest point of friction.
- **Workday:** the system stays open for hours; it isn't a tool for quick,
  occasional visits.

## Capabilities and Constraints

**Confirmed capabilities**

- Excel ingestion with identity resolution: four unrelated sheets are
  consolidated into unique people.
- CRUD for the four tramite types, always hanging off a client.
- Audited lookup of encrypted credentials.
- Reversible soft delete and a retention policy with permanent purging.
- Authentication with an `httpOnly` cookie session, two roles, and
  brute-force lockout.
- A queryable, filterable audit log.

**Constraints**

- **Scale: hundreds of clients** (between 100 and 1,000 people), with a
  handful of new tramites a day. Simple name search is enough; there's no
  need for combined filters or cursor-based pagination. Decisions shouldn't
  block growth, but shouldn't pay for complexity nobody uses today either.
- The mobile scene is for **reading and searching**, not data entry.

**Domain terminology** (used by the team and present in the data)

`trámite`, `cita`, `expediente`, `Master Tramex`, `Global Entry`, `IRCC`,
`cuenta`, `pasaporte`. The interface uses the team's vocabulary, not generic
translations.

**Explicitly undecided**

- Encryption key rotation (today it requires re-encrypting the database by hand).
- Assisted merging of namesakes that ended up split apart.
- Scheduled execution of the retention purge.
- There is no publicly deployed environment.

## Brand Commitments

**Tramex is a real agency and the logo provided is the definitive one.** The
identity must be respected as-is; no claims, services, locations, figures, or
testimonials should be invented.

- **Name:** Tramex.
- **Logo:** `Logo tramex.png` — a globe with a passport, a key, and a plane,
  in petroleum green and sage, with the name in small caps under the mark.
- **Palette extracted from the logo** (measured from the file, not estimated):

  | Role | Hex | Presence in the logo |
  |---|---|---|
  | Deep petroleum green | `#003C48` | 37% — dominant color: passport, globe outline |
  | Sage green | `#84C0A8` | 23% — globe fill |
  | Steel blue | `#185868` | «TRAMEX» wordmark |
  | Gold | `#C8B060` | passport stripe; minimal accent (42 px) |

- **Voice:** sober and direct. The system handles personal data and
  third-party credentials; the tone allows for neither corporate jargon nor
  informality.

## Evidence on Hand

- **Official logo:** `/home/alexander-tinoco/Descargas/Logo tramex.png`
  (500×500 PNG). It's the only brand asset that exists.
- **Synthetic data:** `docs/generar_datos_demo.py` generates a file with the
  structure and quirks of the real one. **No real client data — names,
  phone numbers, emails, passport numbers, or credentials — exists or should
  ever exist in the repository.**
- **No additional brand material exists** — and none should be fabricated:
  team photos, client testimonials, figures on tramites resolved, office
  locations, certifications, or agreements with any immigration authority.

## Product Principles

1. **The credential is the center of gravity.** The whole system exists so an
   operator can get someone else's password quickly and traceably. That
   operation deserves the most careful visual and interaction treatment, not
   the treatment of just another button in the row.
2. **The trail isn't requested, it happens.** Auditing can never depend on
   someone remembering to turn it on, and whoever looks something up must see
   that it was logged.
3. **Messy data is preserved, not discarded.** A date written as `"MARZO"` is
   information the operator knows how to interpret; the system keeps it
   instead of losing it during normalization.
4. **One person, one record.** The value over the spreadsheet is that
   someone's four tramites stop being four unrelated rows.
5. **Nothing gets destroyed by accident.** With personal data, every removal
   is reversible and audited; destruction is a separate, explicit operation.

## Accessibility & Inclusion

- **English-language interface**, using the team's vocabulary.
- **Extended use:** the system stays open for the whole workday, which makes
  sustained contrast and reading-distance legibility a higher priority than
  first-impression impact.
- **Real mobile scene:** searching and reading must work on a phone, standing
  up and with one hand.
- **High-precision data:** passport numbers, phone numbers, and credentials
  get transcribed by hand into other portals. Distinguishing `l` from `I` and
  `0` from `O` isn't a typographic nicety, it's error prevention.
