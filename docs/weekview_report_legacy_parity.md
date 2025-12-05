Detta dokument sammanfattar hur Veckorapporten fungerar i legacy Kommun, och vilka constraints Unified måste följa.

- Roll & scope: viewer/admin/cook/unit_portal; site+vecka över alla avdelningar.
- Vad vyn visar: Per avdelning × dag × måltid: boendeantal, specialkost per kosttyp, normalkost (härledd), samt totalsummeringar per avdelning och globalt.
- Actions: Rent läsläge; export/utskrift kan förekomma, men inga skrivvägar.
- Data/beräkningar: `registreringar`, `boende_antal`, kosttyper; normalkost = total boende − summa specialkost; Alt2 är kontext.

Constraints
- Rapporten får inte ha write-endpoints; endast GET är tillåtet.
- UI måste visa spec/norm-kolumner och totals, samt varna vid saknad meny/boende/registreringar.
