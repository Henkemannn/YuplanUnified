Detta dokument sammanfattar hur Planera (Kockvy) fungerar i legacy Kommun, och vilka constraints Unified måste följa.

- Roll & scope: kock/enhetschef/admin; avdelning per dag och vecka.
- Vad vyn visar: Meny Alt1/Alt2, Alt2-markering, boendeantal, specialkostaggregat från registreringar; beräkningar för normalkost och dag/veckosummeringar.
- Actions: Alt1/Alt2-val och boendeantal-ändringar; ingen specialkostregistrering i Planera (den sker i registreringsvyn).
- Data/beräkningar: `veckomeny`, `alt2_markering`, `boende_antal`, `registreringar`; normalkost = boende − specialkost; ETag-krav vid mutationer.

Constraints
- Mutationer ska gå via Weekview/Planera API med ETag (412 vid stale).
- Planera får inte introducera specialkost-skrivningar; UI ska visa varningar/mismatch enligt legacy.
