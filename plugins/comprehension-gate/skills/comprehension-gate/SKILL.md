---
name: comprehension-gate
description: Examina al usuario sobre un cambio de código antes de mergearlo o aprobarlo. Úsala cuando pida "examíname", "¿entiendo esta PR?", "comprehension gate", "quiz me" o antes de aprobar una PR escrita por un agente.
---

# Comprehension gate

Objetivo: que nadie mergee un cambio que no entiende. Tú preguntas, el usuario responde. Nunca des las respuestas.

## 1. Obtener el diff

- PR: `gh pr diff <número>` (y `gh pr view <número>` para título y descripción).
- Rama local: `git diff $(git merge-base origin/main HEAD)...HEAD` (cambia `main` por la rama base si es otra).
- Ignora ficheros generados, lockfiles, documentación (`*.md`) y los del propio gate.

## 2. Tres preguntas

Lee el diff y el código de alrededor que haga falta. Escribe un resumen de una línea del cambio y tres preguntas:

1. Qué hace el cambio y por qué de esa forma.
2. Riesgos o efectos laterales.
3. Un escenario "¿qué pasaría si...?" con un caso límite real del código.

Las preguntas tienen que poder contestarse entendiendo el cambio, no memorizándolo. Nada de preguntas de nombres de variables ni de líneas concretas.

## 3. Evaluar

Haz las tres preguntas juntas y espera la respuesta. Evalúa pregunta por pregunta:

- Aprobado si las respuestas muestran que entiende el comportamiento y los riesgos, aunque no use las palabras exactas.
- Si no aprueba: di qué está bien y qué falta, sin revelar la respuesta, y repregunta solo sobre lo que falló.
- Repite hasta que apruebe o el usuario lo deje.

## 4. Resultado

Termina con `APROBADO` o `NO APROBADO` y el resumen del cambio. No mergees ni apruebes la PR tú: eso lo hace el usuario.

## Ejemplo

> Usuario: examíname de la PR 12 antes de mergear

Resumen: el cupón BF15 descuenta un 15 % sobre el total con IVA.

1. ¿Qué hace el cambio y por qué se aplica en ese punto del cálculo?
2. ¿Qué le pasa a la base imponible y al IVA del pedido con este cupón?
3. Un carrito de 200 € con otro cupón del 20 %: ¿qué descuento total sale y se respeta el tope del 30 %?

> Usuario: 1) añade un cupón del 15 %... 2) baja todo igual... 3) un 35 %, se pasa del tope

Feedback: la 1 y la 3 bien. En la 2 falta algo: mira qué se descuenta y sobre qué importe se calcula el IVA. Repregunta: después de aplicar BF15, ¿el total sigue siendo base más IVA?

> Usuario: no, la base y el IVA no bajan, solo el total

APROBADO. El cupón rompe la igualdad total = base + IVA y se salta el tope.

## Instalar el gate en un repo (CI)

Si el usuario quiere que el examen bloquee el merge en GitHub, hazlo tú paso a paso y confirma cada cambio en su repo:

1. Copia `.github/workflows/comprehension-gate.yml` y `.github/scripts/gate.py` de `mindmakerslab/comprehension-gate`:
   ```bash
   gh api repos/mindmakerslab/comprehension-gate/contents/.github/workflows/comprehension-gate.yml --jq .content | base64 -d > .github/workflows/comprehension-gate.yml
   gh api repos/mindmakerslab/comprehension-gate/contents/.github/scripts/gate.py --jq .content | base64 -d > .github/scripts/gate.py
   ```
2. Secret del modelo. Pide al usuario que lo ponga él, sin pegarlo en el chat: `gh secret set OPENROUTER_API_KEY` (o `CLAUDE_CODE_OAUTH_TOKEN` para usar su suscripción, sacado con `claude setup-token`).
3. Variables: `gh variable set GATE_USERS --body "login1,login2"` (quién activa el gate). Opcionales: `GATE_TARGET` (`author` o `merger`) y `GATE_MODEL`.
4. Commit y push de los dos ficheros en una rama, y PR.
5. Haz obligatorio el check `comprehension-gate` en la rama principal (Settings, Rules, Rulesets, Require status checks). En repos privados hace falta GitHub Pro o Team; en el plan gratuito solo funciona en públicos.
6. Prueba: abre una PR pequeña y comprueba que el gate comenta tres preguntas.

En CI la entrevista va por comentarios de la PR: el gate publica las preguntas, el usuario contesta con otro comentario, el gate evalúa y pone el check en verde o en rojo con feedback y repreguntas.
