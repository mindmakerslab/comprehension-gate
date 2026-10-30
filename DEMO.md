# Demo en directo

Antes de empezar: ten abierta la pestaña del repo con sesión iniciada como `double-thinker`. Todo se puede hacer desde la web o con `gh`.

## 1. Gate por PR (main)

La rama `demo/black-friday` añade un cupón BF15 "15 % sobre el precio final". Parece inocente, pero se aplica sobre el total con IVA: la base imponible y el IVA del pedido no bajan, el total ya no es base más IVA y el cupón se salta el tope del 30 %.

```bash
gh pr create -R mindmakerslab/comprehension-gate --base main --head demo/black-friday \
  --title "Cupón BF15 de Black Friday" --body "Nuevo cupón BF15: 15 % sobre el precio final, acumulable."
```

1. En unos 30 segundos aparece el comentario con 3 preguntas y el check `comprehension-gate` en pending. El botón de merge está bloqueado.
2. Contesta mal a propósito (por ejemplo "aplica un 15 % y ya"). El gate responde con feedback sin darte la respuesta, repregunta y el check pasa a failure.
3. Contesta bien. El check pasa a success y ya se puede mergear. Si haces un push, vuelve a pending con preguntas nuevas.

Al acabar, cierra la PR sin mergear para poder repetir.

## 2. Bookmark de entendimiento (rama bookmark)

Tu bookmark está en el commit anterior a un cambio de Lucía (el umbral de envío gratis pasa a mirarse antes de cupones). La rama `demo/iva-envio-prorrata` es tu cambio: el IVA del envío sigue al de lo que transporta.

```bash
gh pr create -R mindmakerslab/comprehension-gate --base bookmark --head demo/iva-envio-prorrata \
  --title "IVA del envío según lo que transporta" --body "El envío lleva el IVA de los productos que transporta, prorrateado por línea."
```

1. Como en esta rama el modo es `merger`, el gate pide que comente quien quiera aprobar. Comenta `quiero aprobar`.
2. Las preguntas cubren tu cambio y también el de Lucía: es tu deuda cognitiva acumulada desde tu bookmark.
3. Al aprobar, mira `bookmarks/double-thinker.json` en la rama `comprehension-bookmarks`: el bookmark se ha movido al head de la PR.

Para repetir, cierra la PR y devuelve el bookmark al punto de partida:

```bash
R=mindmakerslab/comprehension-gate
START=$(gh api repos/$R/commits/bookmark -q ".parents[0].sha")   # commit anterior al de Lucía
BLOB=$(gh api "repos/$R/contents/bookmarks/double-thinker.json?ref=comprehension-bookmarks" -q .sha)
C=$(printf '{"login":"double-thinker","sha":"%s","pr":null}\n' "$START" | base64 -w0)
gh api -X PUT repos/$R/contents/bookmarks/double-thinker.json -f message="bookmark: reinicio" \
  -f branch=comprehension-bookmarks -f sha="$BLOB" -f content="$C"
```

## 3. Un agente abre la PR (modo merger)

El issue "Envío gratis para pedidos de solo libros desde 30 euros" está preparado y sin etiquetar.

1. Ponle la etiqueta `agent`. Claude Code lo implementa en un runner, pasa los tests y abre una PR como `github-actions[bot]`. Tarda unos 3 o 4 minutos; enséñalo en Actions mientras tanto.
2. El gate publica las preguntas dirigidas a quien vaya a mergear: el autor es un bot, así que el examinado eres tú.
3. Contesta. Nadie mergea código de un agente sin demostrar que lo entiende.
