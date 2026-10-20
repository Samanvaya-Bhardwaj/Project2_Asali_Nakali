# Running Asali / Nakali

How to start the system on one machine or across two, how to check it is behaving,
and what is known to be broken.

Last verified: 19 September 2026.

---

## 1. Running on one machine

```bash
python3 scripts/run_cluster.py --mode all
```

Both nodes start as background threads. Open <http://localhost:8011/index.html>.

To stop:

```bash
python3 scripts/run_cluster.py --stop
```

`Ctrl+C` also works, **but only if the launcher is running in the foreground of
that terminal**. A run started in the background (`... &`) is reparented to PID 1
and is unreachable from the terminal, which is why `--stop` exists. It matches
only this project's launcher and node modules, sends `SIGTERM`, then `SIGKILL` to
anything still alive.

Blunter alternatives if you need them:

```bash
pkill -f run_cluster.py
lsof -ti :8011 -ti :8012 | xargs kill
```

---

## 2. Running across two PCs

Both machines need the project folder. The second machine needs at least
`integration/`, `api/`, `scripts/`, `databases/` and `data/`. Both must be on the
same Wi-Fi network.

**On your friend's PC** — the regulatory node (DB3 registry, DB4 grievances, audit ledger):

```bash
python3 scripts/run_cluster.py --mode pc2
```

**On your PC** — the retail node (DB1 checkouts, DB2 distribution). This machine
also serves the website:

```bash
python3 scripts/run_cluster.py --mode pc1
```

Open <http://localhost:8011/index.html>.

**Point the site at your friend's machine.** Click the status chip in the nav bar,
set *Node PC2* to `http://<friend-ip>:8012`, and save. The setting is stored in
your browser and is shared by the Verify and Explorer pages.

Your friend finds their address with:

| Platform | Command |
| --- | --- |
| macOS | `ipconfig getifaddr en0` |
| Windows | `ipconfig` → IPv4 Address |
| Linux | `hostname -I` |

The nodes already bind to `0.0.0.0`, so they accept connections from the network.
macOS may show a firewall prompt the first time — allow it. If the friend's node
shows as unreachable, check the firewall before anything else.

Stop with `python3 scripts/run_cluster.py --stop` on **each** machine.

---

## 2b. Other layouts, including three machines

### What the design actually allows

A node is **not** separable from its data. Each node process reads and writes
SQLite files sitting next to it on disk (`DB_FILES` in
`integration/db_explorer.py`). There is no remote-data layer, so "run the backend
here, keep the databases there" is not a configuration — wherever a node runs is
where its data lives.

There are also exactly **two** node slots. `run_cluster.py` offers `pc1` and
`pc2` only, and the browser maps silos to them with a fixed rule: DB1 and DB2 go
to PC1, everything else (DB3, DB4, audit ledger) goes to PC2. A third machine has
no node role to fill without a code change.

The frontend, on the other hand, *is* separable. It is static files that talk to
the nodes over HTTP, and the nodes send `Access-Control-Allow-Origin: *`, so it
can be hosted anywhere.

### Layout A — you host the site, two friends hold the data (works today)

This is the closest fit to "the databases live on my friends' machines", and it
is the arrangement to use unless you are prepared to change code. Verified
working.

**Friend 1** — retail and distribution data (DB1, DB2):

```bash
python3 scripts/run_cluster.py --mode pc1
```

**Friend 2** — registry, grievances and the audit ledger (DB3, DB4, audit):

```bash
python3 scripts/run_cluster.py --mode pc2
```

**You** — host the site only. Any static server will do:

```bash
cd dashboard
python3 -m http.server 8080
```

Open <http://localhost:8080/index.html>, click the status chip in the nav, and
set:

- Node PC1 → `http://<friend-1-ip>:8011`
- Node PC2 → `http://<friend-2-ip>:8012`

Save. Both pages now query your friends' machines.

Two things to know:

- **The connection setting is per browser origin.** Serving the site from
  `:8080` is a different origin from `:8011`, so it keeps its own copy of the
  node addresses. Set them once on `:8080`.
- **Your PC runs no backend in this layout.** The query engines run on your
  friends' machines, beside their data. If your PC must run backend code, use
  Layout B or C.

### Layout B — you run a node too (three machines, two of them holding data)

If you want your own machine to do real work rather than only serve files, take
one of the two node roles yourself:

- **You**: `python3 scripts/run_cluster.py --mode pc1` — serves the site *and*
  holds DB1/DB2.
- **Friend 1**: `python3 scripts/run_cluster.py --mode pc2` — holds DB3/DB4/audit.
- **Friend 2**: no role in the current design.

Open <http://localhost:8011/index.html> and point Node PC2 at friend 1.

### Layout C — data genuinely split across two friends, backend on your PC

This is what you asked for literally, and it needs one of two things.

**C1. Share the database folders over the network.** Your friends export their
`databases/` directory (SMB on Windows, File Sharing on macOS, NFS on Linux), you
mount them, and you point `DB_FILES` at the mount paths. No application code
changes.

Be aware this is genuinely fragile: **SQLite over a network share is unreliable
for writes.** Its file locking does not work correctly over SMB or NFS, and
concurrent writes can corrupt the database. Reads are usually fine. If you go
this way, treat the mounted databases as read-only during the demo. I have not
tested this path.

**C2. Give each silo its own address.** The cleaner fix, and a modest change:

- `dashboard/assets/cluster.js` — `urlFor(dbHint)` currently returns one of two
  URLs. Extend the stored config from `{pc1, pc2}` to one entry per silo
  (`db1`, `db2`, `db3`, `db4`, `audit`) and return the matching one.
- The connection panel in the same file — show one address field per silo instead
  of two.
- `explorer.js` — `getTargetNodeUrl` mirrors the same two-way rule and needs the
  same treatment.

The nodes themselves need no change: each already answers for any silo it can
see on disk, so you would run a node on each machine and simply give it only the
database files it is meant to own.

Say the word if you want C2 implemented.

### Which to choose

| You want | Use |
| --- | --- |
| Data on both friends' machines, least effort | **Layout A** (tested) |
| Your machine doing real work, one friend holding the regulatory data | **Layout B** |
| Backend on your machine, data files elsewhere | **Layout C1**, read-only |
| Each silo on a machine you choose | **Layout C2**, needs the code change |

Whatever you pick, the sync caveat in section 4 still applies: nothing replicates
between machines.

---

## 3. Checking it is working

**Health of both nodes:**

```bash
python3 scripts/run_cluster.py --check-health
```

**Activity log.** Every operation against every silo is recorded: schema reads,
row browsing, searches, inserts, updates, deletes, federated verifications and
chain validations. Read it in the browser under *Explorer → Section 6, Activity
log*, or directly:

```bash
curl -s "http://127.0.0.1:8011/api/v1/explorer/activity?db=all&limit=20"
```

Each node returns only the rows it served, and the Explorer page merges both, so
running on two machines does not double-count. The *Clear log* button wipes both
nodes and records the clear itself, so the feed says the history was cleared
rather than appearing mysteriously empty.

**Audit chain integrity** — *Explorer → Section 7*, or:

```bash
curl -s "http://127.0.0.1:8012/api/v1/explorer/validate_chain"
```

**Row counts straight from the databases:**

```bash
sqlite3 databases/db1_purchase_registry.sqlite   "select count(*) from purchase_events;"
sqlite3 databases/db2_distributor_ledger.sqlite  "select count(*) from distribution_batches;"
sqlite3 databases/db3_manufacturer_registry.sqlite "select count(*) from products;"
```

Baseline for a clean checkout: 26 checkout events, 23 batches, 16 products.

**A verification end to end:**

```bash
curl -s -X POST http://127.0.0.1:8011/api/v1/explorer/operation \
  -H 'Content-Type: application/json' \
  -d '{"db_id":"all","operation":"FEDERATED_VIEW","table":"","data":{"item_code":"MED-ASALI-001"}}'
```

---

## 4. The databases do **not** sync between the two PCs

This is the most important thing to understand before demonstrating the system.

**There is no replication.** The backend makes no HTTP calls between nodes.
`DB_FILES` in `integration/db_explorer.py` resolves to local paths, so each
machine reads and writes its *own* complete set of all five databases.

The "distribution" is routing in the browser only: the frontend sends DB1/DB2
requests to PC1 and DB3/DB4/audit requests to PC2. Each node holds a full copy and
will answer for any silo, which is why the fallback path can silently serve
divergent data.

Measured by running a genuine second copy of the project as PC2:

| Action | Result |
| --- | --- |
| Insert a DB1 row via PC1 | PC1's file: 1 row. PC2's file: **0** |
| Ask PC2 to browse DB1 | It answers, from its own stale copy, missing the insert |
| Federated insert via PC2 | Wrote DB3 on PC2 only; PC1 saw nothing |

**What this means in practice.** A read-only demonstration across two machines
works and looks convincing. The moment either machine *writes*, the two diverge
and stay diverged. An insert your friend makes will never reach your PC.

**If you need writes to be consistent during a demo,** do all of them from one
machine, or keep both nodes on a single machine (`--mode all`) and use the second
PC only to view the site over the network.

---

## 5. Known issues

### 5.1 Federated insert writes only one of three silos

`FEDERATED_INSERT` is meant to register an item across DB3, DB2 and DB1 in one
step. It writes DB3 and then fails silently on the other two:

```json
{
  "success": true,
  "results": { "db3_mfg": true, "db2_logistics": false, "db1_pos": false },
  "message": "Successfully registered ... across DB3 (Mfg), DB2 (Logistics), and DB1 (Retail POS)"
}
```

Two separate faults:

1. **The writes fail.** The built-in payload in `_execute_federated_operation`
   violates the DB2 column constraints — it sends `transport_mode: "Refrigerated
   Van"` and `status: "DELIVERED"`, but both must be lowercase from a fixed list
   (`road`, `air`, `rail`, `courier`; `delivered`, `dispatched`, `in_transit`,
   `returned`, `lost`, `damaged`).
2. **The response lies about it.** `success` is `true` and the message claims all
   three silos were written, even though `results` records two failures. Read
   `results`, not `message`.

Status: **not fixed.**

### 5.2 Entity resolver certified fake serials as genuine — fixed

Unknown serials were being rewritten onto real ones and then reported with that
real product's clean verdict. `MED-TOTALLY-FAKE-9999` came back as **Asali, 100%
trust** — the exact failure the project exists to prevent. Only a string with no
resemblance at all (`ZZZZZZZZ`) was correctly rejected, which is what hid the
problem in casual testing.

A similarity threshold could not fix it. Measured on this catalogue, a genuine
OCR misread scores **0.888** while the invented `MED-FAKE-0001` scores **0.897** —
the fake scores higher than the real one, because every serial shares the
`MED-XXXXX-NNN` skeleton.

The fix, applied in both `integration/entity_resolver.py` and
`dashboard/assets/engines.js`:

- **Confusion folding.** Glyph pairs a scanner genuinely confuses (`O`/`0`,
  `I`/`L`/`1`, `S`/`5`, `B`/`8`, `Z`/`2`) are folded onto one shape. A real misread
  then matches *exactly*; every fake stays 2–12 edits away.
- **Name matching is gated.** Scoring a serial against product names is a category
  error and was how fakes matched a real product. It now runs only for input that
  reads like a name. A hyphenated drug name such as `Co-trimoxazole` still takes
  the name path.
- **No loose fallback.** Anything not matched by the deterministic or
  confusion-folded rules is left unlinked, which sends it to the phantom-serial
  veto. Refusing to guess is the only safe default here.

Current behaviour:

| Input | Verdict |
| --- | --- |
| `MED-ASALI-001` | Asali, 100 |
| `MED-ASAL1-OO1` (OCR misread) | Asali, 100 — resolves to `MED-ASALI-001` |
| `BATCH-A001` (batch bridge key) | Asali, 100 |
| `Novamox` / `Novamax` (name, typo) | matched |
| `MED-SYNC-XYZ` | Nakali, 0, phantom-serial veto |
| `MED-TOTALLY-FAKE-9999` | Nakali, 0, phantom-serial veto |
| `MED-FAKE-0001` | Nakali, 0, phantom-serial veto |
| `MED-ASALI-999` (real prefix, unknown number) | Nakali, 0, phantom-serial veto |

Status: **fixed**, both engines verified in agreement.

This is worth presenting rather than hiding: it demonstrates that naive string
similarity is unsafe for structured identifiers, with the 0.888-versus-0.897
measurement as evidence, and that confusion-aware normalisation is the principled
alternative.

### 5.3 `/api/v1/verify` does not exist

The project guide documents this endpoint, but neither node implements it; both
return 404. The real federated path is:

```
POST /api/v1/explorer/operation
{"db_id": "all", "operation": "FEDERATED_VIEW", "data": {"item_code": "..."}}
```

It returns the verdict, trust score, veto codes, lifecycle state and silo
coverage, but not the product or custody detail. The Verify page therefore
computes the **verdict** live from the cluster and reads the descriptive detail
from the stored dossier, and labels which is which on screen.

Status: **not fixed**, documented behaviour.

### 5.4 Nodes are single-threaded

Both use `HTTPServer`, not `ThreadingHTTPServer`, despite the guide describing a
threading mixin. Requests are served one at a time, so a slow request blocks
others. Fine for a demo; it will show up if several people load the site at once.

---

## 6. Ports and layout

| | Node PC1 | Node PC2 |
| --- | --- | --- |
| Port | 8011 | 8012 |
| Role | Retail and distribution | Regulator and ministry |
| Silos | DB1 checkouts, DB2 distribution | DB3 registry, DB4 grievances, audit ledger |
| Also serves | the website | the website |

Either node can serve the site; the site is served from whichever machine you
open. Conventionally that is PC1.
