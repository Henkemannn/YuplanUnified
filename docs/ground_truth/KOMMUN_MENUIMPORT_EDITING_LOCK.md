Status: LOCKED
Last reviewed: 2026-10-07

# Kommun Menyimport — Editing & Action Ownership Lock

## Purpose

This document prevents duplicate Builder/editor/search implementations while Kommun Menyimport is closed for pilot.

## Canonical ownership

Builder/domain owns:
- Components
- Dishes/Compositions
- composition library
- canonical composition identity
- shared Dish editor
- shared Component editor
- canonical composition search semantics

Kommun week/menu UI owns:
- week context
- day
- meal slot
- menu placement
- user action context

The week surface must not become another Builder.

## Resolved row action contract

For a resolved Dish:

**Direct Dish-name click**
-> existing shared Dish editor

**⋯ -> Öppna rätt**
-> exact same existing shared Dish editor

**⋯ -> Byt rätt**
-> Rättbibliotek selector
-> returns another canonical `composition_id`

**⋯ -> Ta bort från menyn**
-> removes only the canonical menu placement
-> does not delete Dish, Component or library records

These operations are not modes of one ambiguous action.

## Unresolved imported text

Unresolved imported menu text:
- is shown as ordinary menu text
- must not expose technical labels such as `Ej kopplad`
- may prefill Rättbibliotek search with the imported text
- guaranteed user path to resolve is `⋯ -> Byt rätt`

## Rättbibliotek

Rättbibliotek is a selector over canonical Builder data.

It may have a presentation adapted to the menu context, but it must not own:
- another Dish model
- another composition store
- another search matcher
- another editor

Resolved `Byt rätt` starts with an empty query and may show subtle current-Dish context.

Empty resolved search must not dump the full library by default.

`+ Skapa ny rätt` must reuse the shared canonical Dish create flow.

## Search runtime

`static/js/builder_composition_search.js` is the shared canonical composition-search runtime.

Builder and Rättbibliotek must use the same runtime.

Current canonical behavior is name/id search.

Tag / hashtag search is deferred until implemented once in the canonical Builder search runtime.

No picker-specific matcher is allowed.

## Slot bind contract

The selector returns:
- `composition_id`

The caller/week slot owns and supplies:
- `day`
- `meal_slot`

A bind must never make the picker responsible for week-slot context.

## Existing-Dish editor integration

Historical accepted integration reference:

`dd7ffac54593ac114975d78a49b2f4c586caf4f0`
`feat(kommun): edit menu dishes in shared builder overlay`

Architecture:

Menyimport parent
-> frosted overlay
-> isolated editor host
-> `/builder-editor-host?composition_id=<id>`
-> shared Dish editor

Later accepted shared-editor improvements through `bda732af...` must remain.

Do not mount the full Builder workspace/runtime into the week App Shell merely to open a Dish.

## User-facing terminology

“Builder” is internal terminology.

Normal user-facing menu operations should use language such as:
- Redigera meny
- Rättbibliotek
- Öppna rätt
- Byt rätt

Do not expose implementation terms such as:
- Builder
- unresolved
- match
- canonical id

unless in admin/developer diagnostics.

## Scope guard

During Kommun 1.1 closure:
- no new full menu-builder workspace
- no duplicate Dish modal
- no duplicate Component modal
- no duplicate search runtime
- no Offshore migration as a side effect of a Kommun action fix
- no broad legacy cleanup

If a fix appears to require more than a small integration seam, stop and audit before implementation.
