# Jenkins SS12000 pipeline

Pipelinen har exakt nio stages och hämtar först `persons`, därefter `activities`.
Resultatet blir två källfiler och fem Canvas SIS-kompatibla CSV-filer i `output/`.

## Jenkins-konfiguration

Skapa ett **Secret text**-credential med ID `ss12000-secret`. Jobbet ska använda
`Pipeline script from SCM`, grenen `main` och Script Path `Jenkinsfile`.

## Viktiga mappningsantaganden

Den tidigare konversationen definierade bara users-mappningen fullständigt. Övriga
filer använder därför Canvas SIS standardkolumner och tolererar flera vanliga
SS12000-representationer:

- En aktivitet blir en section (`Activity.id`).
- Course ID tas i ordning från `parentActivity`, `course`, `syllabus`, `subject`
  och till sist aktivitetens eget ID.
- Deltagare kan ligga direkt i aktivitetens `students`, `members`, `participants`
  eller `teachers`, i inbäddade gruppmedlemskap eller som aktivitetsmedlemskap på
  personen.
- Observerrelationer kan vara studentcentrerade (`responsiblePersons`, `guardians`,
  `parents`, `contacts`) eller observercentrerade (`responsibleFor`, `students`,
  `children`). Båda personerna måste finnas i persons-exporten.
- Status normaliseras till Canvas `active`/`deleted`.
- CSV skrivs som UTF-8 med BOM för säker visning av svenska tecken i Excel.

Om SchoolSoft-svaret använder andra fältnamn behöver endast funktionerna i
`ss12000_common.py`, `create_user_observers.py` och `create_enrollments.py`
justeras. Käll-JSON arkiveras alltid för att göra detta verifierbart.

## Lokal kontroll

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
SS12000_SECRET='...' .venv/bin/python ss12000_export.py \
  --base-url 'https://example/ss12000/v2' --org-id 0 --output-dir output
```

Kör därefter CSV-scripten med samma argument som visas i `Jenkinsfile` och avsluta
med `python3 validate_outputs.py --output-dir output`.

