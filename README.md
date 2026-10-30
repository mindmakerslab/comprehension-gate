# comprehension-gate

No mergeas lo que no entiendes.

Con agentes escribiendo buena parte del código, el cuello de botella ya no es teclear sino entender. Cada PR que se mergea sin que nadie la comprenda es deuda cognitiva: el código funciona hoy, pero el equipo ya no sabe por qué, y el día que falla nadie puede razonar sobre él.

Este repo es una plantilla que convierte esa idea en un check de GitHub:

1. Al abrir o actualizar una PR, un agente lee el diff y publica 3 preguntas concretas sobre el cambio: qué hace y por qué, qué riesgos o efectos laterales tiene, y qué pasaría en un caso límite.
2. El status `comprehension-gate` queda en pending. Con la protección de rama activa, la PR no se puede mergear.
3. El autor (o alguien con permiso de escritura) contesta en un comentario. El agente evalúa si la respuesta demuestra comprensión.
4. Si no convence, responde con feedback, repregunta y pone el status en failure. Si convence, lo pone en success.
5. Un nuevo push invalida la aprobación y vuelve a preguntar sobre el código nuevo.

No sustituye a la code review. Es la parte que un agente no puede hacer por ti: entender lo que vas a firmar.

## Variantes

Cada variante vive en una rama de este repo:

- [`main`](../../tree/main): gate por PR. Pregunta por el diff de la PR. Es esta.
- [`bookmark`](../../tree/bookmark): bookmark de entendimiento. Cada persona tiene guardado el último commit que demostró entender, y el gate pregunta por todo lo que ha cambiado desde ahí, incluidos los cambios de otros. Mide tu deuda cognitiva acumulada, no solo la de tu PR.
- [`hooks`](../../tree/hooks): la misma idea sin GitHub Actions, como comando local de git que usa `claude -p` con tu suscripción.

Los pasos para enseñarlo en directo están en [DEMO.md](DEMO.md).

## Usar la plantilla

```bash
gh repo create mi-org/mi-repo --private --template double-thinker/comprehension-gate
```

O copia a un repo existente estos dos ficheros:

- `.github/workflows/comprehension-gate.yml`
- `.github/scripts/gate.py` (Python estándar, sin dependencias)

## Configurar el modelo

El gate acepta tres credenciales y usa la primera que encuentre:

1. `CLAUDE_CODE_OAUTH_TOKEN`: tu suscripción de Claude Code, sin pagar API aparte. El workflow instala el CLI en el runner y llama a `claude -p`.

   ```bash
   claude setup-token        # abre el navegador y devuelve un token sk-ant-oat...
   gh secret set CLAUDE_CODE_OAUTH_TOKEN -R mi-org/mi-repo   # pega el token cuando lo pida
   ```

2. `ANTHROPIC_API_KEY`: la API de Anthropic directa.

   ```bash
   gh secret set ANTHROPIC_API_KEY -R mi-org/mi-repo
   ```

3. `OPENROUTER_API_KEY`: OpenRouter, por si es lo que tienes a mano.

El modelo se elige con la variable `GATE_MODEL` (por defecto `claude-sonnet-4-5`):

```bash
gh variable set GATE_MODEL -R mi-org/mi-repo --body claude-sonnet-4-5
```

Las PRs desde forks no reciben secrets, así que el gate pondrá el status en error. Para equipos que trabajan con ramas en el mismo repo no hay problema.

## Exigir el check para mergear

Sin esto el gate solo avisa. Hace falta un repo público o un plan Pro, Team o Enterprise (en repos privados de cuentas Free GitHub no aplica reglas de rama).

```bash
gh api -X POST repos/mi-org/mi-repo/rulesets --input - <<'JSON'
{
  "name": "comprehension-gate",
  "target": "branch",
  "enforcement": "active",
  "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
  "rules": [
    {"type": "required_status_checks",
     "parameters": {"strict_required_status_checks_policy": false,
                    "required_status_checks": [{"context": "comprehension-gate"}]}}
  ]
}
JSON
```

## Cómo funciona por dentro

- Usa commit statuses y no check runs: así el job que se dispara con `issue_comment` puede marcar el head SHA de la PR.
- Las preguntas viajan en un comentario oculto (`<!-- comprehension-gate:questions sha=... -->`) dentro del comentario del bot. Al evaluar, se usan las últimas preguntas publicadas para el head SHA actual; por eso un push nuevo deja la aprobación anterior sin efecto.
- Solo cuenta la respuesta del autor de la PR o de alguien con permiso write. Los comentarios de otros y del bot se ignoran.
- Permisos del workflow: `contents: read`, `pull-requests: write`, `statuses: write`.

## Código de ejemplo

`src/carrito.py` y `tests/test_carrito.py` están para tener algo que cambiar en la demo:

```bash
python3 -m unittest discover -s tests -v
```
