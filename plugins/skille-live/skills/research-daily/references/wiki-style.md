# Wiki tematyczna — playbook (`wiki/`)

To serce skilla. Wikipedia użytkownika dla danego tematu. Pisana DLA CZŁOWIEKA, który chce zrozumieć temat.

## Zasady

**Jeden plik = jeden dział = jeden mini-artykuł.** Nie monolit. Działy to obszary wiedzy w temacie. Master sam identyfikuje działy z focus + pierwszych findingów.

**Nazwy plików: kebab-case bez numerów** (`platnosci.md`, `bezpieczenstwo.md`, `wybor-technologii.md`).

**`wiki/README.md` to spis treści.** Lista działów z 1-zdaniowym opisem.

## Anatomia działu

```markdown
# [Nazwa działu]

[2-3 zdania wprowadzenia — dla kogoś kto nie zna tematu.]

[Główne opcje, podejścia, narzędzia. Pełnymi zdaniami z kontekstem. NIE listujesz — wyjaśniasz.]

[Konkretne przykłady z liczbami i nazwiskami. "Calorify (indie dev z Turcji) zbudował X w 11 dni, robi $4K MRR, stack: Y."]

[Pułapki. Pisane jak ostrzeżenie do kolegi przy kawie.]

[Rekomendacja gdy istnieje konsensus, z uzasadnieniem.]

---
*Źródła: 4 wideo YT, 3 wątki Reddit, raport Perplexity. Ostatni update: 2026-04-28.*
```

## Style guide pisania

- **Polski język ZAWSZE.** Cytaty po angielsku → tłumacz w tekście.
- **Pełne zdania, nie bullety jak telegram.** Bullety tylko gdy realnie listujesz porównywalne elementy.
- **Liczby i nazwiska > ogólniki.**
- **Wpleć kontekst w zdanie**, nie używaj mikro-nagłówków. ZAKAZANE: `Implikacja:`, `Signal:`, `Note:`, `Action:`, `Why hot:`, `Rationale:`.
- **Counter źródeł na KOŃCU działu**, jednym zdaniem kursywą. ZAKAZANE inline: `[yt×4, reddit×3]`. ZALECANE: *Źródła: 4 wideo YT, 3 wątki Reddit, raport Perplexity.*
- **Max 1 emoji per dział.**
- **Bez statusów** typu 🆕 ⬆️ ✅ ❌ ⚠️ przy bulletach.
- **Pisz jakbyś tłumaczył koledze przy kawie.**
- **Backlinki Obsidian-style.** `[[wiki/inny-dzial]]` zamiast linków markdown. Pierwsza wzmianka tematu = link, kolejne w tym samym akapicie bez.
