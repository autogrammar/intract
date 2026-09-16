# Commands Reference

## `scan`

Skanuje pliki i wypisuje znalezione kontrakty inline.

```bash
python -m intract scan .
python -m intract scan . --json
```

## `validate`

Waliduje kontrakty inline i manifest.

```bash
python -m intract validate .
python -m intract validate . --manifest intract.yaml
python -m intract validate . --json
python -m intract validate . --planfile
```

## `check`

Tryb policy-aware pod CI/pre-commit.

```bash
python -m intract check .
python -m intract check --staged
python -m intract check --changed --base main
python -m intract check . --format sarif --output intract.sarif
```

Status procesu zależy od policy `fail_on` / `warn_on`.

## `check-manifest`

Waliduje manifest względem schematu.

```bash
python -m intract check-manifest intract.yaml
python -m intract check-manifest intract.yaml --json
```

## `coverage`

Pokazuje pokrycie plików kontraktami.

```bash
python -m intract coverage .
python -m intract coverage . --json
```

## `duplicates`

Wyszukuje duplikaty / podobieństwa intencji.

```bash
python -m intract duplicates .
python -m intract duplicates . --threshold 0.84
python -m intract duplicates . --json
```

## `graph`

Buduje graf zależności kontraktów `contract -> require`.

```bash
python -m intract graph .
python -m intract graph . --format json
python -m intract graph . --format mermaid
python -m intract graph . --format mermaid --output graph.mmd
```

## `watch`

Obserwuje folder i waliduje po zmianach.

```bash
python -m intract watch .
python -m intract watch . --interval 0.5
python -m intract watch . --planfile
python -m intract watch . --once
```

## `tickets`

Generuje tickety z błędów, braków i naruszeń.

```bash
python -m intract tickets .
```

Tworzy:

```text
.intract/planfile-tickets.yaml
.intract/planfile-tickets.json
.intract/TODO.intract.md
```

## `artifact`

Waliduje artefakty inne niż kod.

```bash
python -m intract artifact Dockerfile
python -m intract artifact openapi.yaml
python -m intract artifact .github/workflows/ci.yml
python -m intract artifact k8s/deployment.yaml
```

## `engine`

Silnik analizy codebase.

```bash
python -m intract engine suggest .
python -m intract engine drift .
python -m intract engine run .
python -m intract engine run . --planfile
python -m intract engine run . --json
```

## Wspólne schematy komend (`wellmanifest/dsl`)

Część powierzchni CLI odpowiada wspólnym schematom komend publikowanym przez
`wellmanifest/dsl` (`schemas/commands/*.schema.json`). Powiązanie jest
deklaratywne — manifest DSL przypięte jest do `wellmanifest/dsl@5f40ad5`
przez `standardsLock` w `dsl-manifest.json`.

| Komenda CLI | Wspólny schemat | Mapowanie |
| --- | --- | --- |
| `intract validate <path>` | `VALIDATE` | `{verb: VALIDATE, path}` |
| `intract coverage <path>`, `duplicates`, `graph`, `scan` | `QUERY` | `{verb: QUERY, target: <path>, format?}` |

Nieadoptowane:

- `GENERATE` — `propose`/`engine suggest` przyjmują plik lub ustrukturyzowane
  wejście, nie `text` wymagany przez schemat.
- `PATCH` — intract nie aplikuje patchy na cele (pfix wycofany, ticket-004).
- `RESOLVE` — brak rezolucji tekstu naturalnego (`llm.mode: none`).
