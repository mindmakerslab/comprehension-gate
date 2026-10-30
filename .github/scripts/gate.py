#!/usr/bin/env python3
"""Comprehension gate: no se mergea lo que no se entiende.

Eventos:
  pull_request (opened, synchronize, reopened): genera 3 preguntas sobre el diff,
    las publica en la PR y deja el status `comprehension-gate` en pending.
  issue_comment (created): si quien comenta es el autor o tiene permiso de escritura,
    evalúa su respuesta contra las últimas preguntas del head SHA actual y pone
    el status en success o failure (con feedback y nuevas preguntas).

Solo usa la librería estándar. Proveedor de LLM, en este orden:
  CLAUDE_CODE_OAUTH_TOKEN -> CLI `claude -p` con la suscripción de Claude Code
  ANTHROPIC_API_KEY       -> API de Anthropic directa
  OPENROUTER_API_KEY      -> OpenRouter como alternativa
Modelo: variable GATE_MODEL (por defecto claude-sonnet-4-5).

GATE_MODE=bookmark (variante 2): en vez del diff de la PR, pregunta por todo lo que ha
cambiado desde el último commit que el autor demostró entender (su bookmark, guardado en la
rama huérfana `comprehension-bookmarks`). Al aprobar, mueve el bookmark al head de la PR.
"""
import subprocess
import base64
import json
import os
import re
import sys
import urllib.error
import urllib.request

CONTEXT = "comprehension-gate"
MARK_Q = "comprehension-gate:questions"
MARK_V = "comprehension-gate:verdict"
MAX_DIFF = 60_000

GH_API = os.environ.get("GITHUB_API_URL", "https://api.github.com")
REPO = os.environ["GITHUB_REPOSITORY"]
GH_TOKEN = os.environ["GITHUB_TOKEN"]
MODEL = os.environ.get("GATE_MODEL") or "claude-sonnet-4-5"
MODE = "pr"  # se resuelve por PR en resolve_mode()
BOOKMARK_BRANCH = "comprehension-bookmarks"


# ---------------------------------------------------------------- GitHub

def gh(method, path, body=None, accept="application/vnd.github+json"):
    url = path if path.startswith("http") else f"{GH_API}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {GH_TOKEN}",
        "Accept": accept,
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read().decode()
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"GitHub {method} {path}: {e.code} {e.read().decode()[:500]}")
    if accept.endswith("diff"):
        return raw
    return json.loads(raw) if raw else None


def set_status(sha, state, description, target_url=None):
    body = {"state": state, "context": CONTEXT, "description": description[:140]}
    if target_url:
        body["target_url"] = target_url
    gh("POST", f"/repos/{REPO}/statuses/{sha}", body)


def comment(pr_number, text):
    return gh("POST", f"/repos/{REPO}/issues/{pr_number}/comments", {"body": text})


def list_comments(pr_number):
    out, page = [], 1
    while True:
        batch = gh("GET", f"/repos/{REPO}/issues/{pr_number}/comments?per_page=100&page={page}")
        out += batch
        if len(batch) < 100:
            return out
        page += 1


def can_answer(user, pr):
    if user == pr["user"]["login"]:
        return True
    try:
        perm = gh("GET", f"/repos/{REPO}/collaborators/{user}/permission")
        return perm.get("permission") in ("admin", "write") or perm.get("role_name") in ("maintain", "write", "admin")
    except RuntimeError:
        return False


# ------------------------------------------------------------------- LLM

QUESTIONS_TOOL = {
    "name": "publicar_preguntas",
    "description": "Publica las preguntas de comprensión sobre el cambio.",
    "input_schema": {
        "type": "object",
        "properties": {
            "resumen": {"type": "string", "description": "Una frase neutra sobre qué toca la PR, sin revelar las respuestas."},
            # Campos planos en vez de un array: algunos proveedores serializan mal los arrays.
            "pregunta_1": {"type": "string", "description": "Qué hace el cambio y por qué de esa forma."},
            "pregunta_2": {"type": "string", "description": "Riesgos o efectos laterales."},
            "pregunta_3": {"type": "string", "description": "Escenario ¿qué pasaría si...? con un caso límite real."},
        },
        "required": ["resumen", "pregunta_1", "pregunta_2", "pregunta_3"],
    },
}

VERDICT_TOOL = {
    "name": "emitir_veredicto",
    "description": "Veredicto sobre si las respuestas demuestran comprensión del cambio.",
    "input_schema": {
        "type": "object",
        "properties": {
            "aprobado": {"type": "boolean"},
            "feedback": {"type": "string", "description": "Qué está bien y qué falta, pregunta por pregunta, breve."},
            "repregunta_1": {"type": "string", "description": "Si no aprueba: pregunta sobre lo que falló. Vacío si aprueba."},
            "repregunta_2": {"type": "string", "description": "Opcional. Vacío si no hace falta."},
            "repregunta_3": {"type": "string", "description": "Opcional. Vacío si no hace falta."},
        },
        "required": ["aprobado", "feedback", "repregunta_1"],
    },
}

SYSTEM = (
    "Eres un revisor sénior que protege a un equipo de la deuda cognitiva: nadie debe mergear "
    "código que no entiende, aunque lo haya escrito un agente. Escribes en español, con tildes "
    "correctas, tono directo, sin em-dash ni punto medio y sin negritas."
)


def call_llm(prompt, tool):
    if os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"):
        cmd = ["claude", "-p", "--output-format", "json", "--json-schema", json.dumps(tool["input_schema"]),
               "--system-prompt", SYSTEM, "--tools", "", "--model", MODEL, "--no-session-persistence"]
        r = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=300)
        if r.returncode != 0:
            raise RuntimeError(f"claude -p falló: {r.stderr[-500:]}")
        out = json.loads(r.stdout)
        if out.get("structured_output"):
            return out["structured_output"]
        m = re.search(r"\{.*\}", out.get("result") or "", re.S)
        if m:
            return json.loads(m.group(0))
        raise RuntimeError(f"claude -p sin JSON: {out.get('result')}")

    if os.environ.get("ANTHROPIC_API_KEY"):
        body = {
            "model": MODEL, "max_tokens": 2000, "system": SYSTEM,
            "messages": [{"role": "user", "content": prompt}],
            "tools": [tool], "tool_choice": {"type": "tool", "name": tool["name"]},
        }
        req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=json.dumps(body).encode(), headers={
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        })
        with urllib.request.urlopen(req, timeout=180) as r:
            resp = json.load(r)
        for block in resp["content"]:
            if block.get("type") == "tool_use":
                return block["input"]
        raise RuntimeError(f"Respuesta sin tool_use: {resp}")

    if os.environ.get("OPENROUTER_API_KEY"):
        model = MODEL if "/" in MODEL else "anthropic/" + re.sub(r"(\d)-(\d)$", r"\1.\2", MODEL)
        body = {
            "model": model, "max_tokens": 2000,
            "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}],
            "tools": [{"type": "function", "function": {
                "name": tool["name"], "description": tool["description"], "parameters": tool["input_schema"]}}],
            "tool_choice": {"type": "function", "function": {"name": tool["name"]}},
        }
        req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", data=json.dumps(body).encode(), headers={
            "Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}",
            "Content-Type": "application/json",
            "X-Title": "pr-comprehension-gate",
        })
        with urllib.request.urlopen(req, timeout=180) as r:
            resp = json.load(r)
        msg = resp["choices"][0]["message"]
        if msg.get("tool_calls"):
            return json.loads(msg["tool_calls"][0]["function"]["arguments"])
        m = re.search(r"\{.*\}", msg.get("content") or "", re.S)
        if m:
            return json.loads(m.group(0))
        raise RuntimeError(f"Respuesta sin JSON: {resp}")

    raise RuntimeError("Falta CLAUDE_CODE_OAUTH_TOKEN, ANTHROPIC_API_KEY u OPENROUTER_API_KEY en los secrets del repo.")


# --------------------------------------------------------------- Marcas

def encode(data):
    return base64.b64encode(json.dumps(data, ensure_ascii=False).encode()).decode()


def marker(kind, sha, data):
    return f"<!-- {kind} sha={sha} data={encode(data)} -->"


MARK_RE = re.compile(r"<!-- (comprehension-gate:\w+) sha=([0-9a-f]+) data=([A-Za-z0-9+/=]+) -->")


def latest_state(comments, sha, user):
    """(preguntas, aprobado, base) para `user` en este SHA.

    Aprobado si alguien ya aprobó este SHA. Preguntas: las últimas dirigidas a `user`
    o, si no hay, las últimas para cualquiera ('*').
    """
    mine, anyone, approved = None, None, False
    for c in comments:
        for kind, s, data in MARK_RE.findall(c.get("body") or ""):
            if s != sha:
                continue
            payload = json.loads(base64.b64decode(data))
            if kind == MARK_Q:
                para = payload.get("para", "*")
                if para == user:
                    mine = payload
                elif para == "*":
                    anyone = payload
            elif kind == MARK_V and payload.get("aprobado"):
                approved = True
    q = mine or anyone
    return (q["preguntas"], approved, q.get("base")) if q else (None, approved, None)


def as_list(value):
    """Algunos modelos devuelven el array como string JSON o como texto con saltos de línea."""
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str):
        try:
            return as_list(json.loads(value))
        except ValueError:
            return [re.sub(r"^\s*\d+[.)]\s*", "", l).strip() for l in value.splitlines() if l.strip()]
    return []


def fields(out, prefix):
    return [str(out[k]).strip() for k in (f"{prefix}_{i}" for i in (1, 2, 3)) if str(out.get(k) or "").strip()]


def numbered(qs):
    return "\n".join(f"{i}. {q}" for i, q in enumerate(qs, 1))


# --------------------------------------------------------------- Flujos

def read_bookmark(login):
    try:
        f = gh("GET", f"/repos/{REPO}/contents/bookmarks/{login}.json?ref={BOOKMARK_BRANCH}")
    except RuntimeError:
        return None, None
    return json.loads(base64.b64decode(f["content"])), f["sha"]


def write_bookmark(login, sha, pr_number):
    data = {"login": login, "sha": sha, "pr": pr_number, "fecha": __import__("datetime").datetime.utcnow().isoformat() + "Z"}
    _, blob = read_bookmark(login)
    body = {"message": f"bookmark: {login} entiende {sha[:7]} (PR #{pr_number})", "branch": BOOKMARK_BRANCH,
            "content": base64.b64encode((json.dumps(data, indent=2) + "\n").encode()).decode()}
    if blob:
        body["sha"] = blob
    gh("PUT", f"/repos/{REPO}/contents/bookmarks/{login}.json", body)


def pr_diff(pr, base=None):
    if base:
        diff = gh("GET", f"/repos/{REPO}/compare/{base}...{pr['head']['sha']}", accept="application/vnd.github.v3.diff")
    else:
        diff = gh("GET", f"/repos/{REPO}/pulls/{pr['number']}", accept="application/vnd.github.v3.diff")
    # Ni los ficheros del propio gate ni la documentación cuentan como código a entender.
    ignore = [x for x in (os.environ.get("GATE_IGNORE") or ".github/,*.md").split(",") if x]

    def ignored(path):
        return any(path.endswith(x[1:]) if x.startswith("*") else path.startswith(x) for x in ignore)

    parts = re.split(r"(?m)^(?=diff --git )", diff)
    diff = "".join(p for p in parts
                   if not (m := re.match(r"diff --git a/(\S+)", p)) or not ignored(m.group(1)))
    if len(diff) > MAX_DIFF:
        diff = diff[:MAX_DIFF] + "\n\n[diff truncado]"
    return diff


def resolve_mode(pr):
    """GATE_MODE manda. Si no está, las PRs contra la rama `bookmark` usan la variante 2."""
    global MODE
    bases = (os.environ.get("GATE_BOOKMARK_BASES") or "bookmark").split(",")
    MODE = os.environ.get("GATE_MODE") or ("bookmark" if pr["base"]["ref"] in bases else "pr")
    print(f"Modo: {MODE}")


def target():
    """A quién se examina. author: quien abre la PR. merger: cualquiera con permiso write."""
    return os.environ.get("GATE_TARGET") or ("merger" if MODE == "bookmark" else "author")


def diff_range(pr, login):
    """Devuelve (base, descripción) del rango sobre el que se pregunta a `login`."""
    if MODE == "bookmark":
        bm, _ = read_bookmark(login)
        if bm:
            de = f" (PR #{bm['pr']})" if bm.get("pr") else ""
            return bm["sha"], f"desde el bookmark de @{login} `{bm['sha'][:7]}`{de}"
        return pr["base"]["sha"], f"@{login} no tiene bookmark: desde la base de la PR"
    return pr["base"]["sha"], "diff de la PR"


def ask(pr, login):
    """Genera y publica preguntas. login='*' significa que vale para cualquiera."""
    sha, num = pr["head"]["sha"], pr["number"]
    set_status(sha, "pending", "Generando preguntas sobre el cambio...")
    base, scope = diff_range(pr, login)
    diff = pr_diff(pr, base if MODE == "bookmark" else None)
    if not diff.strip():
        body = (f"### Comprehension gate: aprobado\n\nNo hay código nuevo que entender para @{login} "
                f"entre `{base[:7]}` y `{sha[:7]}`.\n\n" + marker(MARK_V, sha, {"aprobado": True, "para": login}))
        c = comment(num, body)
        return set_status(sha, "success", "Nada nuevo que entender", c["html_url"])
    extra = ""
    if MODE == "bookmark":
        extra = ("\nEl diff no es solo esta PR: es todo lo que ha cambiado en el código desde el último commit "
                 "que esta persona demostró entender, incluidos cambios de otras personas. Reparte las preguntas "
                 "entre las partes más importantes de ese cambio acumulado, no solo las de esta PR.\n")
    prompt = f"""Título de la PR: {pr['title']}
Descripción: {pr.get('body') or '(sin descripción)'}
{extra}
Diff:
```diff
{diff}
```

Escribe exactamente 3 preguntas concretas sobre ESTE cambio que solo pueda contestar bien
alguien que lo ha leído y entendido. Cubre: qué hace y por qué de esa forma, riesgos o efectos
laterales, y un escenario "¿qué pasaría si...?" con un caso límite real del diff. Cita nombres de
funciones, ficheros o valores concretos. Nada de preguntas genéricas ni de sí/no. No des pistas
de la respuesta."""
    for _ in range(3):
        out = call_llm(prompt, QUESTIONS_TOOL)
        qs = fields(out, "pregunta") or as_list(out.get("preguntas"))
        if len(qs) >= 3:
            break
    else:
        raise RuntimeError(f"El modelo no devolvió 3 preguntas: {out}")
    qs = qs[:3]
    quien = "Antes de mergear, contesta" if login == "*" else f"@{login}, antes de mergear contesta"
    body = (
        f"### Comprehension gate\n\n{out['resumen']}\n\n"
        f"{quien} en un comentario a estas preguntas con tus palabras:\n\n{numbered(qs)}\n\n"
        f"Commit evaluado: `{sha[:7]}`, {scope}. Un nuevo push invalida la aprobación y genera preguntas nuevas.\n\n"
        + marker(MARK_Q, sha, {"preguntas": qs, "base": base, "para": login})
    )
    c = comment(num, body)
    set_status(sha, "pending", "Esperando respuestas", c["html_url"])


def on_pull_request(event):
    pr = event["pull_request"]
    resolve_mode(pr)
    if MODE == "bookmark" and target() == "merger":
        # Cada persona tiene su bookmark: las preguntas se generan cuando alguien se ofrece a aprobar.
        sha = pr["head"]["sha"]
        c = comment(pr["number"], "### Comprehension gate\n\nPara aprobar esta PR, cualquier persona con permiso "
                    "de escritura puede comentar (por ejemplo, `quiero aprobar`). Recibirá 3 preguntas sobre todo lo "
                    "que ha cambiado desde su último bookmark. El check pasa cuando al menos una persona demuestra "
                    f"que entiende el cambio. Commit: `{sha[:7]}`.")
        return set_status(sha, "pending", "Esperando a que alguien con permiso write lo entienda", c["html_url"])
    ask(pr, pr["user"]["login"] if MODE == "bookmark" else "*")


def on_issue_comment(event):
    issue, cmt = event["issue"], event["comment"]
    if "pull_request" not in issue:
        return print("No es una PR.")
    if cmt["user"]["type"] == "Bot" or MARK_RE.search(cmt.get("body") or ""):
        return print("Comentario del bot, se ignora.")
    num = issue["number"]
    pr = gh("GET", f"/repos/{REPO}/pulls/{num}")
    if pr["state"] != "open":
        return print("PR cerrada.")
    resolve_mode(pr)
    user = cmt["user"]["login"]
    if target() == "author" and user != pr["user"]["login"]:
        return print(f"GATE_TARGET=author: solo cuenta el autor de la PR, no {user}.")
    if target() == "merger" and not can_answer(user, pr):
        return print(f"GATE_TARGET=merger: {user} no tiene permiso de escritura.")
    sha = pr["head"]["sha"]
    questions, approved, base = latest_state(list_comments(num), sha, user)
    if approved:
        return print("Ya aprobado para este SHA.")
    if not questions:
        if MODE == "bookmark" and target() == "merger":
            return ask(pr, user)
        return print("No hay preguntas para el head SHA actual (puede que aún se estén generando).")

    set_status(sha, "pending", f"Evaluando la respuesta de {user}...")
    prompt = f"""Diff sobre el que se preguntó:
```diff
{pr_diff(pr, base if MODE == "bookmark" else None)}
```

Preguntas planteadas:
{numbered(questions)}

Respuesta de @{user}:
\"\"\"
{cmt['body']}
\"\"\"

Decide si la respuesta demuestra que entiende el cambio. Exige que conteste a todas las
preguntas, que sea correcta según el diff y que muestre el porqué, no solo el qué. No exijas
redacción perfecta ni longitud: una respuesta breve y correcta aprueba; una vaga, evasiva,
incorrecta o que no responde a alguna pregunta, no.

Si no aprueba: el feedback dice, pregunta por pregunta, si va bien o mal encaminada y qué tipo
de cosa falta (por ejemplo "no explicas el porqué" o "revisa en qué momento se compara con el
umbral"), pero NUNCA revela la respuesta correcta, ni valores, ni nombres de variables o líneas que
la contengan. Si revelas la respuesta, el gate deja de servir. Las nuevas preguntas atacan lo
mismo desde otro ángulo, sin pistas. Si aprueba, el feedback es una o dos frases."""
    v = call_llm(prompt, VERDICT_TOOL)
    if v.get("aprobado") in (True, "true", "True"):
        body = (f"### Comprehension gate: aprobado\n\n@{user} {v['feedback']}\n\n"
                f"Check `{CONTEXT}` en verde para `{sha[:7]}`.\n\n"
                + marker(MARK_V, sha, {"aprobado": True}))
        c = comment(num, body)
        if MODE == "bookmark":
            write_bookmark(user, sha, num)
        set_status(sha, "success", f"{user} demuestra que entiende el cambio", c["html_url"])
    else:
        nq = (fields(v, "repregunta") or questions)[:3]
        body = (f"### Comprehension gate: todavía no\n\n@{user} {v['feedback']}\n\n"
                f"Contesta de nuevo en otro comentario:\n\n{numbered(nq)}\n\n"
                + marker(MARK_V, sha, {"aprobado": False})
                + "\n" + marker(MARK_Q, sha, {"preguntas": nq, "base": base, "para": user}))
        c = comment(num, body)
        set_status(sha, "failure", "La respuesta no demuestra comprensión del cambio", c["html_url"])


def main():
    with open(os.environ["GITHUB_EVENT_PATH"]) as f:
        event = json.load(f)
    name = os.environ["GITHUB_EVENT_NAME"]
    try:
        if name == "pull_request":
            on_pull_request(event)
        elif name == "issue_comment":
            on_issue_comment(event)
    except Exception as e:  # deja rastro visible en la PR
        sha = (event.get("pull_request") or {}).get("head", {}).get("sha")
        if not sha and "issue" in event and "pull_request" in event["issue"]:
            sha = gh("GET", f"/repos/{REPO}/pulls/{event['issue']['number']}")["head"]["sha"]
        if sha:
            set_status(sha, "error", f"Error del gate: {str(e)[:100]}")
        raise


if __name__ == "__main__":
    sys.exit(main())
