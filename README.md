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
- `hooks` (pendiente, solo diseño): la misma idea sin GitHub Actions. Un `git understand` local (o un hook pre-push) calcula el diff entre tu bookmark y `HEAD`, genera las preguntas con `claude -p` usando tu suscripción de Claude Code, te las hace en la terminal y, si apruebas, guarda el bookmark en `refs/notes/comprehension` o en la rama `comprehension-bookmarks`. Útil para trabajo en solitario o repos sin Actions.

Además, [`agent-pr.yml`](.github/workflows/agent-pr.yml) cierra el círculo: al etiquetar un issue con `agent`, Claude Code lo implementa en un runner y abre la PR como `github-actions[bot]`. Como el autor es un bot, el gate examina a quien vaya a mergear.

Los pasos para enseñarlo en directo están en [DEMO.md](DEMO.md).

Para que `agent-pr.yml` pueda abrir PRs, activa en Settings > Actions > General "Allow GitHub Actions to create and approve pull requests", o:

```bash
gh api -X PUT repos/mi-org/mi-repo/actions/permissions/workflow -f default_workflow_permissions=read -F can_approve_pull_request_reviews=true
```

## Usar la plantilla

```bash
gh repo create mi-org/mi-repo --private --template mindmakerslab/comprehension-gate
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
- A quién se examina lo decide la variable `GATE_TARGET`. Con `author` (por defecto en main) solo cuenta el autor de la PR, útil cuando la ha generado un agente que él lanzó. Con `merger` (por defecto en la rama `bookmark`) cualquiera con permiso write contesta por su cuenta y el check pasa en cuanto uno demuestra que entiende el cambio.
- El gate solo actúa en PRs de las personas de `GATE_USERS` (lista separada por comas, por defecto `double-thinker`) y solo atiende comentarios de esa lista. En un repo público evita que cualquiera gaste tu API. Cámbiala con `gh variable set GATE_USERS -R mi-org/mi-repo --body "ana,luis"`.
- Permisos del workflow: `pull-requests: write`, `statuses: write` y `contents: write`. Este último solo lo necesita la variante bookmark; si solo usas el gate por PR, ponlo en `read`.

## Código de ejemplo

`src/checkout` es un servicio de checkout pequeño pero realista, para que la demo tenga algo con miga que cambiar: cupones que se acumulan con tope, importes fijos prorrateados entre líneas, IVA por país y categoría (Canarias sin IVA), redondeo con `Decimal` y envío por peso y zona.

```bash
pip install pytest && pytest -q
PYTHONPATH=src python3 -m checkout ejemplos/pedido.json
```

## Skills para Claude Code

El repo es también un marketplace de plugins:

```
/plugin marketplace add mindmakerslab/comprehension-gate
/plugin install comprehension-gate@mindmakerslab
/plugin install comprehension-bookmarks@mindmakerslab
```

- `comprehension-gate`: Claude te examina sobre una PR o rama antes de mergear.
- `comprehension-bookmarks`: tu marcador de entendimiento; te examina de todo lo que ha cambiado desde tu bookmark y lo mueve si apruebas.
