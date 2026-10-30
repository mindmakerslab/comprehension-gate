#!/usr/bin/env python3
"""Comprehension gate: no se mergea lo que no se entiende.

Eventos:
  pull_request (opened, synchronize, reopened): genera 3 preguntas sobre el diff,
    las publica en la PR y deja el status `comprehension-gate` en pending.
  issue_comment (created): si quien comenta es el autor o tiene permiso de escritura,
    evalúa su respuesta contra las últimas preguntas del head SHA actual y pone
    el status en success o failure (con feedback y nuevas preguntas).

Solo usa la librería estándar. Proveedor de LLM:
  ANTHROPIC_API_KEY  -> API de Anthropic directa (preferido)
  OPENROUTER_API_KEY -> OpenRouter como alternativa
Modelo: variable GATE_MODEL (por defecto claude-sonnet-4-5).
"""
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
            "preguntas": {"type": "array", "items": {"type": "string"}, "minItems": 3, "maxItems": 3},
        },
        "required": ["resumen", "preguntas"],
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
            "nuevas_preguntas": {
                "type": "array", "items": {"type": "string"},
                "description": "Si no aprueba: 1 a 3 preguntas para repreguntar sobre lo que falló. Vacío si aprueba.",
            },
        },
        "required": ["aprobado", "feedback", "nuevas_preguntas"],
    },
}

SYSTEM = (
    "Eres un revisor sénior que protege a un equipo de la deuda cognitiva: nadie debe mergear "
    "código que no entiende, aunque lo haya escrito un agente. Escribes en español, con tildes "
    "correctas, tono directo, sin em-dash ni punto medio y sin negritas."
)


def call_llm(prompt, tool):
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

    raise RuntimeError("Falta ANTHROPIC_API_KEY (o OPENROUTER_API_KEY) en los secrets del repo.")


# --------------------------------------------------------------- Marcas

def encode(data):
    return base64.b64encode(json.dumps(data, ensure_ascii=False).encode()).decode()


def marker(kind, sha, data):
    return f"<!-- {kind} sha={sha} data={encode(data)} -->"


MARK_RE = re.compile(r"<!-- (comprehension-gate:\w+) sha=([0-9a-f]+) data=([A-Za-z0-9+/=]+) -->")


def latest_state(comments, sha):
    """Devuelve (preguntas, aprobado) según el último comentario del bot para este SHA."""
    questions, approved = None, False
    for c in comments:
        for kind, s, data in MARK_RE.findall(c.get("body") or ""):
            if s != sha:
                continue
            payload = json.loads(base64.b64decode(data))
            if kind == MARK_Q:
                questions, approved = payload["preguntas"], False
            elif kind == MARK_V and payload.get("aprobado"):
                approved = True
    return questions, approved


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


def numbered(qs):
    return "\n".join(f"{i}. {q}" for i, q in enumerate(qs, 1))


# --------------------------------------------------------------- Flujos

def pr_diff(pr_number):
    diff = gh("GET", f"/repos/{REPO}/pulls/{pr_number}", accept="application/vnd.github.v3.diff")
    if len(diff) > MAX_DIFF:
        diff = diff[:MAX_DIFF] + "\n\n[diff truncado]"
    return diff


def on_pull_request(event):
    pr = event["pull_request"]
    sha, num = pr["head"]["sha"], pr["number"]
    set_status(sha, "pending", "Generando preguntas sobre el cambio...")
    diff = pr_diff(num)
    prompt = f"""Título de la PR: {pr['title']}
Descripción: {pr.get('body') or '(sin descripción)'}

Diff:
```diff
{diff}
```

Escribe exactamente 3 preguntas concretas sobre ESTE cambio que solo pueda contestar bien
alguien que lo ha leído y entendido. Cubre: qué hace y por qué de esa forma, riesgos o efectos
laterales, y un escenario "¿qué pasaría si...?" con un caso límite real del diff. Cita nombres de
funciones, ficheros o valores concretos. Nada de preguntas genéricas ni de sí/no. No des pistas
de la respuesta."""
    out = call_llm(prompt, QUESTIONS_TOOL)
    qs = as_list(out.get("preguntas"))[:3]
    if len(qs) < 3:
        raise RuntimeError(f"El modelo no devolvió 3 preguntas: {out}")
    body = (
        f"### Comprehension gate\n\n{out['resumen']}\n\n"
        f"Antes de mergear, contesta en un comentario a estas preguntas con tus palabras:\n\n{numbered(qs)}\n\n"
        f"Commit evaluado: `{sha[:7]}`. Un nuevo push invalida la aprobación y genera preguntas nuevas.\n\n"
        + marker(MARK_Q, sha, {"preguntas": qs})
    )
    c = comment(num, body)
    set_status(sha, "pending", "Esperando respuestas del autor", c["html_url"])


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
    user = cmt["user"]["login"]
    if not can_answer(user, pr):
        return print(f"{user} no es el autor ni tiene permiso de escritura; se ignora.")
    sha = pr["head"]["sha"]
    questions, approved = latest_state(list_comments(num), sha)
    if approved:
        return print("Ya aprobado para este SHA.")
    if not questions:
        return print("No hay preguntas para el head SHA actual (puede que aún se estén generando).")

    set_status(sha, "pending", f"Evaluando la respuesta de {user}...")
    prompt = f"""Diff de la PR:
```diff
{pr_diff(num)}
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
incorrecta o que no responde a alguna pregunta, no. Si no aprueba, explica qué falta sin dar
la respuesta y repregunta solo sobre lo que falló."""
    v = call_llm(prompt, VERDICT_TOOL)
    if v.get("aprobado") in (True, "true", "True"):
        body = (f"### Comprehension gate: aprobado\n\n@{user} {v['feedback']}\n\n"
                f"Check `{CONTEXT}` en verde para `{sha[:7]}`.\n\n"
                + marker(MARK_V, sha, {"aprobado": True}))
        c = comment(num, body)
        set_status(sha, "success", f"{user} demuestra que entiende el cambio", c["html_url"])
    else:
        nq = (as_list(v.get("nuevas_preguntas")) or questions)[:3]
        body = (f"### Comprehension gate: todavía no\n\n@{user} {v['feedback']}\n\n"
                f"Contesta de nuevo en otro comentario:\n\n{numbered(nq)}\n\n"
                + marker(MARK_V, sha, {"aprobado": False}) + "\n" + marker(MARK_Q, sha, {"preguntas": nq}))
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
