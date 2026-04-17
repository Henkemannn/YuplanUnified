🎯 Syfte

Yuplan ska representera menyer som strukturerad data, inte text, för att möjliggöra:

stabil planering
receptkoppling
inköp
AI
skalbar arkitektur
🧠 Kärnprincip

Menyn är inte text
Menyn är referenser till komponenter

🧱 Domänmodell
MenuComponent
component_id (PK, stabil)
canonical_name
tags[]
category (optional)
status
MenuDetail
menu_id
day
meal_slot

component_ref_type   # component | unresolved
component_id         # nullable
unresolved_text      # nullable

free_text_note
🔐 Kritisk invariant

En menyrad måste vara:

component_id != null
OR
unresolved_text != null

Aldrig båda tomma.

🔄 Import & resolution
resolve_component(text)
normalize
alias lookup
fuzzy match (high confidence only)
fallback → unresolved
Alias model
component_alias:
  alias_text
  alias_norm
  component_id
  confidence
🔁 Datans livscykel
Import → resolved/unresolved
Manuell mapping → alias skapas
Stabilisering → component-driven system
🔗 Koppling till Planera 2.0

Planera 2.0:

👉 räknar behov (antal)

Component layer:

👉 säger vad som produceras

Flöde
MenuDetail → Component → (future) Recipe → Ingredients
🧠 Arkitektur
Engine: untouched
Adapter: MenuAdapter
Context: component_id + semantics
Feature flags styr aktivering
🧩 Feature flags
components_enabled = false
recipes_enabled = false
🏗 Menybyggare (framtid)
component library
drag & drop
veckovy
koppling till recept/prep
🔑 Beslut att låsa
component_id = systemets kärna
resolved/unresolved-regeln
alias-baserad inlärning
ingen gissning
🔮 Möjliggör
recept
prep
inköp
AI
kostnad
svinnoptimering
🚀 Min slutsats

Du har just definierat:

👉 det lager som gör Yuplan till en plattform

Inte Planera 2.0 i sig – utan det som gör att 2.0 kan växa.

🧭 Nästa steg (viktigt)

Nu när detta är låst:

👉 nästa naturliga steg är:

Component Composition

Alltså:

Meal = flera component_id

ex:

meatballs
potatoes
gravy