Detta dokument sammanfattar hur Registrering (personalens klickvy) fungerar i legacy Kommun, och vilka constraints Unified måste följa.

- Roll & scope: personal per avdelning/dag/måltid.
- Vad vyn visar: Lista kosttyper (normalkost implicit, specialkosttyper), antal per typ, boendeantal, status “Registrerad/Ej registrerad”, Alt2 som kontext.
- Actions: Toggla antal upp/ner per kosttyp, markera måltid som klar, varningar vid mismatch (t.ex. totals ≠ boende).
- Data/beräkningar: `registreringar` per kosttyp/dag/måltid; normalkost = boende − summa specialkost; validering mot boendeantal.

Constraints
- Per-typ toggling och validering är obligatoriska; statuslogik måste matcha legacy.
- Payloads ska följa legacy-kontrakt; inga “smarta” avvikelser.
