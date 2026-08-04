# Jenkins SS12000 pipeline

Pipelinen har tio stages och hämtar först `persons`, därefter `activities`.
Resultatet blir två källfiler och fem Canvas SIS-kompatibla CSV-filer i `output/`.

Activities-anropet skickar dessa query-parametrar (de två `expand`-värdena
skickas som två separata parametrar):

```text
expandReferenceNames=true
expandplacement=true
expand=groups
expand=teachers
```

## Jenkins-konfiguration

Skapa ett **Secret text**-credential med ID `ss12000-secret`. Jobbet ska använda
`Pipeline script from SCM`, grenen `main` och Script Path `Jenkinsfile`.

Installera Jenkins-pluginet **SSH Agent** och skapa ett credential av typen
**SSH Username with private key** med ID `sftp-private-key`. Ange SFTP-användaren
`root` och den privata nyckel som SchoolSoft har godkänt.

Lägg även SchoolSoft-serverns verifierade publika host key i filen `known_hosts`
i repositoryts rot. Hämta nyckeln och visa dess fingeravtryck med:

```bash
ssh-keyscan -p 2222 sms-int1.schoolsoft.se > known_hosts
ssh-keygen -lf known_hosts
```

Jämför fingeravtrycket med ett värde från SchoolSoft innan filen checkas in.
Pipelinen använder strikt host key-kontroll och avbryter om nyckeln inte stämmer.
SFTP-kommandot ignorerar agentanvändarens övriga SSH-konfiguration (`-F
/dev/null`), använder endast repositoryts `known_hosts` och kräver en ED25519-
nyckel för exakt host/port-kombination. Före anslutningen kopieras filen till en
tillfällig sökväg utan mellanslag, eftersom OpenSSH annars tolkar mellanslag i
`UserKnownHostsFile` som avgränsare mellan flera filer.

SFTP-steget flyttar först föregående version av filerna till
`/home/larande_test/gamla`. En äldre fil med samma namn i `gamla` ersätts.
Därefter laddas exakt dessa nya filer upp till `/home/larande_test`:

```text
users_filtered.csv
user_observers.csv
sections.csv
enrollments.csv
courses.csv
```

## Viktiga mappningsantaganden

CSV-filerna följer de uttryckliga mappningarna för integrationen och tolererar
flera vanliga SS12000-representationer:

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

`users_filtered.csv` använder personens första `eduPersonPrincipalNames` som
både `user_id` och `login_id`. `personStatus=Aktiv` ger `active`; alla andra
värden ger `suspended`. Elever med `_embedded.placements.schoolType=FS` eller
`enrolments.schoolType=YH` utelämnas. Alla andra personer behålls och samtliga
fält skrivs inom dubbla citattecken.

`sections.csv` skapar en rad per referens i `Activity.groups`. Gruppens
`displayName` hämtas från motsvarande objekt i `_embedded.groups`, medan
`course_id`, `start_date` och `end_date` hämtas från aktivitetens toppnivå.
Status är alltid `active` och samtliga fält skrivs inom dubbla citattecken.

`enrollments.csv` följer den särskilda SchoolSoft-mappningen: varje lärare i
`Activity._embedded.teachers` och varje elev i
`Activity._embedded.groups.groupMemberships` ger en rad. `course_id` är
aktivitetens ID, `section_id` är gruppens ID och `user_id` är personens första
`eduPersonPrincipalNames`-värde efter uppslag i Persons. En passerad
`Activity.endDate` ger status `completed`; annars blir status `active`. Samtliga
fält i filen skrivs inom dubbla citattecken. Eftersom toppnivåns `teachers` i
det verkliga API-svaret endast innehåller en duty-referens hämtas lärarens
`person.id` från den expanderade listan `_embedded.teachers`.

`courses.csv` traverserar varje Activity en gång per expanderad grupp. För
grundskolan används `_embedded.syllabus.subjectName`. För gymnasiet består `short_name` av
gruppernas `displayName` följt av `syllabus.displayName`, medan `long_name` tas
från `_embedded.syllabus.courseName`. `account_id` slås upp från organisationens
`displayName`, och gruppens `startDate` skapar ett läsårs-ID på formen
`25*26*10`. Endast helt identiska rader tas bort och samtliga fält citeras.

`user_observers.csv` tar endast med personer där ett objekt i
`externalIdentifiers` har `context=studentguid`. Varje objekt i elevens
`responsibles` med `relationType=Vårdnadshavare` ger en rad. Både
`observer_id` och `student_id` är första EPPN-värdet efter uppslag i Persons.
Elevens `personStatus=Aktiv` ger `active`; alla andra värden ger `inactive`.
Relationer där någon av identifierarna blir tom utelämnas. Samtliga fält skrivs
inom dubbla citattecken.

Om SchoolSoft-svaret använder andra fältnamn behöver endast funktionerna i
`ss12000_common.py`, `create_users_filtered.py`, `create_user_observers.py` och
`create_enrollments.py`
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
