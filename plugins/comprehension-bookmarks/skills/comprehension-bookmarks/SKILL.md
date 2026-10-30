---
name: comprehension-bookmarks
description: Marcador de entendimiento sobre la historia de git. Úsala cuando el usuario pregunte "¿qué me he perdido?", "¿hasta dónde entiendo este repo?", "ponme al día", "mueve mi bookmark" o quiera examinarse de lo que han cambiado otros (personas o agentes) desde la última vez.
---

# Comprehension bookmarks

Cada persona tiene un bookmark: el último commit que entiende. Todo lo que hay entre su bookmark y `HEAD` es su deuda cognitiva, incluido lo que han escrito otros o los agentes.

## Dónde se guarda

En la rama `comprehension-bookmarks`, un fichero por persona en `bookmarks/<login>.json`, el mismo formato que usa la Action:

```json
{ "login": "ana", "sha": "<commit>", "pr": null, "fecha": "2026-10-30T15:20:00Z" }
```

- Login: `gh api user --jq .login`, o `git config user.email` si no hay `gh`.
- Leer: `git fetch origin comprehension-bookmarks && git show origin/comprehension-bookmarks:bookmarks/<login>.json`.
- Si la rama no existe, créala huérfana con un README. Si no hay bookmark, pregunta al usuario desde qué commit quiere empezar (por defecto, el de hace dos semanas).

## Ver la deuda

```bash
git log --oneline <sha>..HEAD
git diff --stat <sha>..HEAD
```

Cuéntale cuántos commits y de quién, y qué zonas del código se han movido. Sin juzgar.

## Examen

1. Lee `git diff <sha>..HEAD` (ignora lockfiles, generados y `*.md`).
2. Tres preguntas: qué ha cambiado y por qué, riesgos o efectos laterales, y un "¿qué pasaría si...?" con un caso límite real. Cubre también los cambios de otros, no solo los del usuario.
3. Evalúa sin revelar respuestas. Si falla, di qué falta y repregunta solo eso.

## Mover el bookmark

Solo si aprueba, y confirmándolo con el usuario:

```bash
git worktree add /tmp/cb origin/comprehension-bookmarks
# escribir bookmarks/<login>.json con el sha de HEAD y la fecha actual
git -C /tmp/cb add -A && git -C /tmp/cb commit -m "bookmark: <login> entiende <sha corto>"
git -C /tmp/cb push origin HEAD:comprehension-bookmarks
git worktree remove /tmp/cb
```

Nunca muevas el bookmark de otra persona.

## Ejemplo

> Usuario: ¿qué me he perdido en este repo?

Tu bookmark está en `b120422` (hace 9 días). Desde ahí hay 2 commits: uno de Lucía, que mira el umbral de envío gratis antes de cupones, y uno tuyo, que prorratea el IVA del envío por línea. Se han movido `checkout/envio.py` y `checkout/iva.py`. ¿Te examino?

1. ¿Qué cambia en el envío gratis desde el commit de Lucía y por qué importa el orden respecto a los cupones?
2. ¿Qué riesgo tiene prorratear el IVA del envío entre líneas con tipos distintos?
3. Un carrito de 48 € con un cupón de 10 € y umbral de 40 €: ¿paga envío?

Si aprueba: "¿Muevo tu bookmark a `2ba2420`?" y solo con un sí lo escribes.

## Instalar los bookmarks en CI

Para que el gate pregunte en las PRs por todo lo cambiado desde el bookmark de quien mergea:

1. Instala primero el gate (skill `comprehension-gate`, sección de instalación).
2. `gh variable set GATE_MODE --body bookmark`. Así todas las PRs usan el modo bookmark y examinan a quien quiera mergear (`merger`), no solo al autor.
3. Crea la rama de bookmarks si no existe:
   ```bash
   git switch --orphan comprehension-bookmarks
   mkdir -p bookmarks && echo "# Bookmarks de comprensión" > README.md
   git add README.md && git commit -m "bookmarks: punto de partida" && git push origin comprehension-bookmarks
   git switch -
   ```
4. Para mergear, quien vaya a aprobar comenta `quiero aprobar` en la PR. El gate le pregunta, y si aprueba, mueve su bookmark al commit mergeado.
