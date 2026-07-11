#!/usr/bin/env python3
"""
project_index.py — Indexa proyectos (.project.yml) en tablas Markdown.

Recorre una o varias raíces a profundidad 2 (categoria/proyecto), busca los
archivos .project.yml, aplica auto-tagging según el contenido de cada carpeta,
valida los metadatos y genera dos tablas Markdown (principal + sandbox) que
inserta en un README entre marcadores. Pensado para correr igual en local que
en el NAS (Synology), a mano o por cron.

Uso típico:
    python3 project_index.py --root ~/projects --readme INDICE.md
    python3 project_index.py --root /volume1/Developer --readme /volume1/Developer/INDICE.md
    python3 project_index.py --root ~/projects            # sin --readme: imprime a stdout
    python3 project_index.py --root ~/projects --init      # crea .project.yml que falten

Requiere PyYAML:  python3 -m pip install pyyaml
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from fnmatch import fnmatch
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
except ImportError:  # Python < 3.9 (p. ej. el Python de Synology DSM)
    try:
        from backports.zoneinfo import ZoneInfo  # pip install "backports.zoneinfo[tzdata]"
    except ImportError:
        ZoneInfo = None

try:
    import yaml  # PyYAML
except ImportError:  # pragma: no cover
    sys.exit("Falta PyYAML. Instálalo con:  python3 -m pip install pyyaml")


# ============================ CONFIGURACIÓN ================================
# La configuración real vive en un archivo .env junto al script (NO versionado;
# ver .env.example). Precedencia: argumentos de CLI > .env > estos valores.
# Estos son solo el último recurso si no hay .env ni argumentos.
CONFIG = {
    # Raíces a escanear (categoria/proyecto). Admiten "~".
    "roots": ["~/projects"],
    # README a actualizar entre marcadores. None = imprime por consola.
    "readme": None,
    # Carpetas extra a excluir (además de DEFAULT_EXCLUDE). Nombres o globs.
    "exclude": [],
    # Zona horaria de la fecha de actualización.
    "timezone": "Europe/Madrid",
    # Crear .project.yml plantilla donde falte, en cada pasada.
    "init": True,
}
# Claves del .env que mapean a cada ajuste (para el mensaje de ayuda/errores).
ENV_KEYS = {"roots": "ROOTS", "readme": "README", "exclude": "EXCLUDE",
            "timezone": "TIMEZONE", "init": "INIT"}
# ===========================================================================


# --- Constantes -------------------------------------------------------------

PROJECT_FILE = ".project.yml"

VALID_STATUS = ("active", "paused", "archived", "deprecated")
DEFAULT_STATUS = "active"
# Los proyectos de sandbox NO se consideran activos por defecto (son almacén de
# experimentos); solo pasan a "active" si lo pones tú a mano.
SANDBOX_DEFAULT_STATUS = "archived"

MAIN_TYPES = ("products", "services", "tools", "learning")
SANDBOX_TYPE = "sandbox"
KNOWN_TYPES = (*MAIN_TYPES, SANDBOX_TYPE)

# Carpetas que se ignoran siempre (además de las que pases con --exclude).
# @eaDir es basura que crea Synology en cada carpeta.
DEFAULT_EXCLUDE = [
    ".git", "node_modules", "__pycache__", "venv", ".venv",
    ".obsidian", "@eaDir", ".DS_Store",
]

# Marcadores del README. Cada par delimita un bloque que se regenera entero.
MARKERS = {
    "fecha": ("<!-- INICIO FECHA -->", "<!-- FIN FECHA -->"),
    "resumen": ("<!-- INICIO RESUMEN -->", "<!-- FIN RESUMEN -->"),
    "principal": ("<!-- INICIO TABLA PRINCIPAL -->", "<!-- FIN TABLA PRINCIPAL -->"),
    "sandbox": ("<!-- INICIO TABLA SANDBOX -->", "<!-- FIN TABLA SANDBOX -->"),
}

# Tags automáticos por extensión de archivo y por archivo-marcador.
EXT_TAGS = {
    ".py": "python", ".sh": "bash", ".js": "javascript", ".ts": "typescript",
    ".tf": "terraform", ".go": "go", ".rs": "rust", ".php": "php",
}
MARKER_TAGS = {
    "Dockerfile": "docker", "docker-compose.yml": "docker",
    "docker-compose.yaml": "docker", "compose.yml": "docker",
    "compose.yaml": "docker", "package.json": "node", "go.mod": "go",
    "Cargo.toml": "rust", "composer.json": "php", "pyproject.toml": "python",
}
# Orden estable y legible de los tags automáticos en la tabla.
TAG_ORDER = ("python", "javascript", "typescript", "bash", "go", "rust",
             "php", "terraform", "node", "docker")

README_NAMES = ("README.md", "readme.md", "Readme.md", "README.MD", "README")

STATUS_LABEL = {
    "active": "✅ active",
    "paused": "⏸️ paused",
    "archived": "📦 archived",
    "deprecated": "⚠️ deprecated",
}

GIT_STATUS_LABEL = {"clean": "✅ limpio", "pending": "🟠 pendiente", "none": "—"}

TABLE_HEADER = (
    "| Nombre | Estado | Git | Docs | Actualizado | Tags | Descripción | Ruta |\n"
    "|---|:---:|:---:|:---:|:---:|---|---|:---:|"
)


# --- Modelo -----------------------------------------------------------------

@dataclass
class Project:
    name: str
    type: str                 # type del .project.yml (fuente para agrupar)
    status: str               # normalizado a minúsculas / DEFAULT_STATUS
    description: str
    tags: list[str]           # manuales + auto (sin duplicar)
    created: str
    category: str             # nombre REAL de la carpeta de nivel 1
    path: Path
    git_status: str = "none"  # clean | pending | none (sin git)
    last_updated: str = ""    # fecha último commit, o mtime de la carpeta
    has_docs: bool = False    # tiene README(.md) en su raíz
    warnings: list[str] = field(default_factory=list)


# --- Utilidades -------------------------------------------------------------

def is_excluded(name: str, patterns: list[str]) -> bool:
    return any(fnmatch(name, pat) for pat in patterns)


def _safe_iterdir(path: Path) -> list[Path]:
    try:
        return sorted(path.iterdir(), key=lambda p: p.name.lower())
    except OSError:
        return []


def formatted_now(tz_name: str) -> tuple[str, str | None]:
    """(fecha 'YYYY-MM-DD HH:MM' en la zona pedida, aviso|None si hubo fallback)."""
    fmt = "%Y-%m-%d %H:%M"
    if ZoneInfo is not None:
        try:
            return datetime.now(ZoneInfo(tz_name)).strftime(fmt), None
        except Exception:
            return (datetime.now().strftime(fmt),
                    f"zona horaria '{tz_name}' no disponible (¿falta tzdata?); "
                    f"usada la hora local del sistema")
    return (datetime.now().strftime(fmt),
            "zoneinfo no disponible (Python < 3.9): usada la hora local del sistema "
            "(correcta si el NAS ya está en Europe/Madrid). Para forzar la zona: "
            "pip install \"backports.zoneinfo[tzdata]\"")


def default_status_for(ptype: str) -> str:
    """Status por defecto según el tipo (sandbox no arranca como activo)."""
    return SANDBOX_DEFAULT_STATUS if ptype == SANDBOX_TYPE else DEFAULT_STATUS


def dir_mtime_date(path: Path) -> str:
    """Fecha (YYYY-MM-DD) de modificación más reciente en el primer nivel."""
    latest = 0.0
    try:
        latest = path.stat().st_mtime
    except OSError:
        pass
    try:
        for entry in path.iterdir():
            try:
                m = entry.stat().st_mtime
                if m > latest:
                    latest = m
            except OSError:
                continue
    except OSError:
        pass
    if latest <= 0:
        return ""
    return datetime.fromtimestamp(latest).strftime("%Y-%m-%d")


def as_str(value) -> str:
    """Convierte a str limpio (fechas de PyYAML -> ISO, None -> '')."""
    if value is None:
        return ""
    return str(value).strip()


def as_tag_list(value) -> list[str]:
    """Normaliza el campo tags a lista de strings."""
    if value is None:
        return []
    if isinstance(value, str):
        # Admite "a, b" o "a b" escritos a mano.
        parts = [t.strip() for t in value.replace(",", " ").split()]
        return [t for t in parts if t]
    if isinstance(value, (list, tuple)):
        return [as_str(v) for v in value if as_str(v)]
    return [as_str(value)]


# --- Descubrimiento (profundidad 2) ----------------------------------------

def iter_project_dirs(root: Path, excludes: list[str]):
    """Genera (category_name, project_dir) para cada carpeta de nivel 2."""
    for cat in _safe_iterdir(root):
        if not cat.is_dir() or is_excluded(cat.name, excludes):
            continue
        for proj in _safe_iterdir(cat):
            if not proj.is_dir() or is_excluded(proj.name, excludes):
                continue
            yield cat.name, proj


# --- Git --------------------------------------------------------------------

_GIT_TIMEOUT = 10  # segundos por comando git


def run_git(args: list[str], cwd: Path) -> str | None:
    """Ejecuta 'git <args>' en cwd. Devuelve stdout o None si falla.

    Pasa safe.directory=* para que git no se niegue por 'dubious ownership'
    (típico en el NAS, donde los repos pueden ser de otro usuario)."""
    try:
        res = subprocess.run(
            ["git", "-c", "safe.directory=*", *args], cwd=str(cwd),
            capture_output=True, text=True, timeout=_GIT_TIMEOUT,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return res.stdout if res.returncode == 0 else None


def classify_remote(url: str | None) -> str | None:
    """github|gitlab|gitea según el dominio del remoto, o None."""
    if not url:
        return None
    u = url.lower()
    if "github" in u:
        return "github"
    if "gitlab" in u:
        return "gitlab"
    if "gitea" in u:
        return "gitea"
    return None


def get_git_info(project_dir: Path) -> dict:
    """{'is_git', 'remote_host', 'git_status'(clean|pending|none), 'last_commit'}."""
    if not (project_dir / ".git").is_dir():
        return {"is_git": False, "remote_host": None, "git_status": "none", "last_commit": None}

    remote = classify_remote((run_git(["config", "--get", "remote.origin.url"], project_dir) or "").strip())

    porcelain = run_git(["status", "--porcelain"], project_dir)
    sb = run_git(["status", "-sb"], project_dir)
    if porcelain is None and sb is None:
        status = "none"  # hay .git pero git falla (permisos, repo roto…)
    else:
        branch_line = sb.splitlines()[0] if sb else ""
        if (porcelain and porcelain.strip()) or "ahead" in branch_line:
            status = "pending"   # cambios sin commitear o commits sin pushear
        else:
            status = "clean"

    out = run_git(["log", "-1", "--format=%cs"], project_dir)  # fecha del último commit
    last_commit = out.strip() if out and out.strip() else None
    return {"is_git": True, "remote_host": remote, "git_status": status, "last_commit": last_commit}


# --- Auto-tagging y docs ----------------------------------------------------

def find_readme(project_dir: Path) -> Path | None:
    """Devuelve el README de la raíz del proyecto, o None."""
    for name in README_NAMES:
        p = project_dir / name
        if p.is_file():
            return p
    return None


def _is_readme_noise(line: str) -> bool:
    """Líneas que NO cuentan como descripción (título, badges, código, HTML…)."""
    s = line.strip()
    if not s:
        return True
    return s.startswith((
        "#", "![", "[![", "<!--", "```", "~~~", "---", "===", ">", "|",
    )) or (s.startswith("<") and s.endswith(">"))


def extract_readme_description(readme_path: Path, max_lines: int = 2,
                               max_chars: int = 200) -> str:
    """Primer párrafo real del README (salta título/badges/código/vacías)."""
    try:
        text = readme_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    collected: list[str] = []
    for raw in text.splitlines():
        if _is_readme_noise(raw):
            if collected:      # ya empezamos el párrafo y llegó ruido/vacío → fin
                break
            continue           # aún no hemos empezado: seguir saltando
        collected.append(raw.strip())
        if len(collected) >= max_lines:
            break
    desc = " ".join(collected).strip()
    if len(desc) > max_chars:
        desc = desc[:max_chars].rstrip() + "…"
    return desc


def detect_auto_tags(project_dir: Path, excludes: list[str]) -> list[str]:
    """Tags por contenido: lenguaje (por extensión) y stack (por archivo-marcador)."""
    tags: set[str] = set()
    for dirpath, dirnames, filenames in os.walk(project_dir):
        dirnames[:] = [d for d in dirnames
                       if d != ".git" and not is_excluded(d, excludes)]
        for fn in filenames:
            if fn in MARKER_TAGS:
                tags.add(MARKER_TAGS[fn])
            ext = os.path.splitext(fn)[1].lower()
            if ext in EXT_TAGS:
                tags.add(EXT_TAGS[ext])

    ordered = [t for t in TAG_ORDER if t in tags]
    ordered += sorted(t for t in tags if t not in TAG_ORDER)
    return ordered


def merge_tags(manual: list[str], auto: list[str]) -> list[str]:
    """Manuales primero; añade autos que no estén ya (sin duplicar, ci)."""
    out = list(manual)
    seen = {t.lower() for t in manual}
    for t in auto:
        if t.lower() not in seen:
            out.append(t)
            seen.add(t.lower())
    return out


# --- Construcción del proyecto ---------------------------------------------

def load_yaml(path: Path) -> dict:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def build_project(category: str, project_dir: Path, excludes: list[str]) -> Project:
    raw = load_yaml(project_dir / PROJECT_FILE)

    name = as_str(raw.get("name")) or project_dir.name
    ptype = as_str(raw.get("type")) or category
    description = as_str(raw.get("description"))
    created = as_str(raw.get("created")) or as_str(raw.get("date"))
    manual_tags = as_tag_list(raw.get("tags"))

    # La description del .project.yml manda; si está vacía, se saca del README.
    readme_path = find_readme(project_dir)
    if not description and readme_path is not None:
        description = extract_readme_description(readme_path)

    proj = Project(
        name=name, type=ptype, status="", description=description,
        tags=[], created=created, category=category, path=project_dir,
    )

    # Validación de status (no bloqueante). El defecto depende del tipo.
    default_status = default_status_for(ptype)
    raw_status = as_str(raw.get("status")).lower()
    if not raw_status:
        proj.warnings.append(f"{category}/{project_dir.name}: status vacío → tratado como '{default_status}'")
        proj.status = default_status
    elif raw_status not in VALID_STATUS:
        proj.warnings.append(
            f"{category}/{project_dir.name}: status '{raw_status}' no válido "
            f"(usa {', '.join(VALID_STATUS)}) → tratado como '{default_status}'"
        )
        proj.status = default_status
    else:
        proj.status = raw_status

    # Validación type vs carpeta de nivel 1.
    if proj.type != category:
        proj.warnings.append(
            f"{category}/{project_dir.name}: type '{proj.type}' no coincide "
            f"con la carpeta de nivel 1 '{category}'"
        )

    # Aviso si el type no encaja en ninguna tabla.
    if proj.type not in KNOWN_TYPES:
        proj.warnings.append(
            f"{category}/{project_dir.name}: type '{proj.type}' desconocido "
            f"→ no aparece en ninguna tabla"
        )

    # Git + auto-tagging (los tags de git salen de la misma info).
    gi = get_git_info(project_dir)
    auto = detect_auto_tags(project_dir, excludes)
    if gi["is_git"]:
        # El host ya implica git; solo etiquetamos "git" a secas si es repo local
        # sin remoto (para no repetir, p. ej. "git gitea").
        auto.append(gi["remote_host"] or "git")
    proj.tags = merge_tags(manual_tags, auto)
    proj.git_status = gi["git_status"]
    proj.last_updated = gi["last_commit"] or dir_mtime_date(project_dir)
    proj.has_docs = readme_path is not None
    return proj


# --- Render de tablas -------------------------------------------------------

def _cell(v) -> str:
    return str(v).replace("|", "\\|").replace("\n", " ").replace("\r", " ").strip()


def _tags_cell(tags: list[str]) -> str:
    if not tags:
        return "—"
    return " ".join(f"`{_cell(t)}`" for t in tags)


def _folder_link(path: Path) -> str:
    """Botón 📁 que abre la carpeta del proyecto (file:// con espacios escapados)."""
    url = str(path).replace(" ", "%20")
    return f"[📁](file://{url})"


def _row(p: Project) -> str:
    cols = [
        f"**{_cell(p.name)}**",
        STATUS_LABEL.get(p.status, _cell(p.status)),
        GIT_STATUS_LABEL.get(p.git_status, "—"),
        "✅" if p.has_docs else "❌",
        _cell(p.last_updated) or "—",
        _tags_cell(p.tags),
        _cell(p.description) or "—",
        _folder_link(p.path),
    ]
    return "| " + " | ".join(cols) + " |"


def render_resumen(projects: list[Project]) -> str:
    """Tabla de estadísticas para el bloque RESUMEN del hub."""
    total = len(projects)
    pending = sum(1 for p in projects if p.git_status == "pending")
    undocumented = sum(1 for p in projects if not p.has_docs)

    by_type: dict[str, int] = {}
    for p in projects:
        by_type[p.type] = by_type.get(p.type, 0) + 1
    order = [*MAIN_TYPES, SANDBOX_TYPE]
    parts = [f"{t}: {by_type[t]}" for t in order if t in by_type]
    parts += [f"{t}: {n}" for t, n in sorted(by_type.items()) if t not in order]
    by_type_str = " · ".join(parts) or "—"

    return (
        "| 📊 Resumen | |\n"
        "|---|---|\n"
        f"| 🗂️ Total | **{total}** proyectos |\n"
        f"| 🏷️ Por tipo | {_cell(by_type_str)} |\n"
        f"| 🟠 Git pendiente | {pending} |\n"
        f"| 📄 Sin README | {undocumented} |\n"
    )


def _sort_key(p: Project):
    # "active" primero, luego alfabético por nombre.
    return (0 if p.status == "active" else 1, p.name.lower())


def render_main_table(projects: list[Project]) -> str:
    groups: dict[str, list[Project]] = {t: [] for t in MAIN_TYPES}
    for p in projects:
        if p.type in groups:
            groups[p.type].append(p)

    parts: list[str] = []
    for t in MAIN_TYPES:
        rows = sorted(groups[t], key=_sort_key)
        if not rows:
            continue
        body = "\n".join(_row(p) for p in rows)
        parts.append(f"### {t.capitalize()}\n\n{TABLE_HEADER}\n{body}")

    return "\n\n".join(parts) if parts else "_Sin proyectos indexados._"


def render_sandbox_table(projects: list[Project]) -> str:
    rows = sorted((p for p in projects if p.type == SANDBOX_TYPE), key=_sort_key)
    if not rows:
        return "_Sin proyectos en sandbox._"
    body = "\n".join(_row(p) for p in rows)
    return f"{TABLE_HEADER}\n{body}"


# --- Inserción en el README -------------------------------------------------

def replace_block(text: str, start: str, end: str, content: str) -> tuple[str, bool]:
    """Reemplaza lo que hay entre start y end (marcadores incluidos, preservados)."""
    s = text.find(start)
    if s == -1:
        return text, False
    e = text.find(end, s + len(start))
    if e == -1:
        return text, False
    new = f"{start}\n{content}\n{end}"
    return text[:s] + new + text[e + len(end):], True


def _seed_template() -> str:
    """Contenido inicial del README destino: la plantilla junto al script,
    o un esqueleto mínimo con los tres pares de marcadores si no está."""
    plantilla = Path(__file__).resolve().parent / "plantilla_indice.md"
    try:
        return plantilla.read_text(encoding="utf-8")
    except OSError:
        f_i, f_f = MARKERS["fecha"]
        r_i, r_f = MARKERS["resumen"]
        p_i, p_f = MARKERS["principal"]
        s_i, s_f = MARKERS["sandbox"]
        return (
            "# 📇 Índice de proyectos\n\n"
            f"**Última actualización:** {f_i}\n—\n{f_f}\n\n"
            f"{r_i}\n\n{r_f}\n\n"
            f"## Proyectos\n\n{p_i}\n\n{p_f}\n\n"
            f"## Sandbox\n\n{s_i}\n\n{s_f}\n"
        )


def update_readme(path: Path, blocks: dict[str, str]) -> list[str]:
    """Inserta cada bloque en su par de marcadores. `blocks` = {clave: contenido}."""
    warnings: list[str] = []
    if not path.exists():
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(_seed_template(), encoding="utf-8")
            print(f"  ℹ README '{path}' no existía; creado desde la plantilla.")
        except OSError as exc:
            return [f"No se pudo crear el README '{path}': {exc}"]
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return [f"No se pudo leer el README '{path}': {exc}"]

    for key, content in blocks.items():
        start, end = MARKERS[key]
        text, ok = replace_block(text, start, end, content)
        if not ok:
            warnings.append(f"README sin marcadores {start} … {end}: bloque '{key}' no insertado")

    try:
        path.write_text(text, encoding="utf-8")
    except OSError as exc:
        return warnings + [f"No se pudo escribir el README '{path}': {exc}"]
    return warnings


# --- Init: crear .project.yml que falten -----------------------------------

INIT_TEMPLATE = (
    "name: {name}\n"
    "type: {type}\n"
    "status: {status}\n"
    "description: \"\"\n"
    "tags: []\n"
    "created: {created}\n"
)


def init_missing(roots: list[Path], excludes: list[str], today: str) -> tuple[int, list[str]]:
    created_count = 0
    notices: list[str] = []
    for root in roots:
        for category, project_dir in iter_project_dirs(root, excludes):
            yml = project_dir / PROJECT_FILE
            if yml.exists():
                continue
            try:
                yml.write_text(
                    INIT_TEMPLATE.format(
                        name=project_dir.name, type=category,
                        status=default_status_for(category), created=today,
                    ),
                    encoding="utf-8",
                )
                created_count += 1
                notices.append(f"creado {category}/{project_dir.name}/{PROJECT_FILE}")
            except OSError as exc:
                notices.append(f"✗ no se pudo crear en {category}/{project_dir.name}: {exc}")
    return created_count, notices


# Cambia SOLO la línea 'status:' de active -> archived, preservando el resto.
_STATUS_ACTIVE_RE = re.compile(r'(?m)^(status:[ \t]*)(["\']?)active\2[ \t]*$')


def fix_sandbox_status(roots: list[Path], excludes: list[str]) -> tuple[int, list[str]]:
    """One-shot: pasa a 'archived' los .project.yml de sandbox que estén en 'active'."""
    changed = 0
    notices: list[str] = []
    for root in roots:
        for category, project_dir in iter_project_dirs(root, excludes):
            if category != SANDBOX_TYPE:
                continue
            yml = project_dir / PROJECT_FILE
            if not yml.is_file():
                continue
            try:
                text = yml.read_text(encoding="utf-8")
                new = _STATUS_ACTIVE_RE.sub(rf"\g<1>{SANDBOX_DEFAULT_STATUS}", text, count=1)
                if new != text:
                    yml.write_text(new, encoding="utf-8")
                    changed += 1
                    notices.append(f"sandbox/{project_dir.name}: active → {SANDBOX_DEFAULT_STATUS}")
            except OSError as exc:
                notices.append(f"✗ no se pudo tocar sandbox/{project_dir.name}: {exc}")
    return changed, notices


# --- .env (ajustes que sobreviven a las actualizaciones del script) --------

def load_env(path: Path) -> dict[str, str]:
    """Parsea un .env sencillo (KEY=VALUE, # comentarios, comillas opcionales)."""
    data: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return data
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        key, _, val = s.partition("=")
        key, val = key.strip(), val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            val = val[1:-1]
        if key:
            data[key] = val
    return data


def _env_list(env: dict, key: str) -> list[str] | None:
    if key not in env:
        return None
    return [x.strip() for x in env[key].split(",") if x.strip()]


def _env_bool(env: dict, key: str) -> bool | None:
    if key not in env:
        return None
    return env[key].strip().lower() in ("1", "true", "yes", "y", "on", "si", "sí")


# --- CLI --------------------------------------------------------------------

def parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Indexa proyectos (.project.yml) en tablas Markdown para un README. "
                    "Los argumentos anulan los valores por defecto del bloque CONFIG del script.",
    )
    p.add_argument("--root", action="append", metavar="RUTA", default=None,
                   help="Raíz a escanear (categoria/proyecto). Repetible. Anula CONFIG['roots'].")
    p.add_argument("--readme", metavar="RUTA", default=None,
                   help="README.md a actualizar entre marcadores. Sin él (ni CONFIG), imprime a stdout.")
    p.add_argument("--exclude", action="append", metavar="PATRÓN", default=None,
                   help="Nombre o glob de carpeta a excluir (nivel 1 o 2). Repetible. Anula CONFIG['exclude'].")
    p.add_argument("--timezone", metavar="TZ", default=None,
                   help="Zona horaria de la fecha (ej. Europe/Madrid). Anula CONFIG['timezone'].")
    p.add_argument("--env", metavar="RUTA", default=None,
                   help="Ruta al archivo .env con los ajustes (por defecto, .env junto al script).")
    p.add_argument("--init", action="store_true",
                   help="Crea un .project.yml plantilla en las carpetas de nivel 2 que no tengan.")
    p.add_argument("--fix-sandbox-status", action="store_true",
                   help=f"One-shot: pasa a '{SANDBOX_DEFAULT_STATUS}' los .project.yml de sandbox "
                        f"que estén en 'active'. Úsalo una vez para corregir los ya creados.")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    # Ajustes desde .env (junto al script salvo que se pase --env).
    env_path = Path(args.env).expanduser() if args.env else Path(__file__).resolve().parent / ".env"
    env = load_env(env_path)

    # Precedencia por ajuste: argumento de CLI > .env > CONFIG (defecto).
    roots_raw = args.root if args.root is not None else (_env_list(env, "ROOTS") or CONFIG["roots"])
    if args.readme is not None:
        readme_arg = args.readme
    elif "README" in env:
        readme_arg = env["README"] or None      # README= vacío → consola
    else:
        readme_arg = CONFIG["readme"]
    exclude_extra = args.exclude if args.exclude is not None else (
        _env_list(env, "EXCLUDE") if "EXCLUDE" in env else CONFIG["exclude"])
    tz_name = args.timezone if args.timezone is not None else (env.get("TIMEZONE") or CONFIG["timezone"])
    env_init = _env_bool(env, "INIT")
    do_init = args.init or (env_init if env_init is not None else CONFIG["init"])

    roots: list[Path] = []
    for r in roots_raw:
        path = Path(r).expanduser().resolve()
        if not path.is_dir():
            print(f"AVISO: raíz inexistente, se omite: {path}", file=sys.stderr)
            continue
        roots.append(path)
    if not roots:
        print("ERROR: ninguna raíz válida (usa --root o CONFIG['roots']).", file=sys.stderr)
        return 2

    excludes = DEFAULT_EXCLUDE + list(exclude_extra)

    fecha, tz_warning = formatted_now(tz_name)

    if args.fix_sandbox_status:
        n, notices = fix_sandbox_status(roots, excludes)
        for note in notices:
            print(f"  {note}")
        print(f"\n[fix-sandbox] {n} .project.yml de sandbox pasados a '{SANDBOX_DEFAULT_STATUS}'.\n")

    if do_init:
        n, notices = init_missing(roots, excludes, fecha[:10])
        for note in notices:
            print(f"  {note}")
        print(f"\n[init] {n} archivo(s) {PROJECT_FILE} creado(s).\n")

    # Descubrir y construir proyectos.
    projects: list[Project] = []
    for root in roots:
        for category, project_dir in iter_project_dirs(root, excludes):
            if (project_dir / PROJECT_FILE).is_file():
                projects.append(build_project(category, project_dir, excludes))

    blocks = {
        "fecha": fecha,
        "resumen": render_resumen(projects),
        "principal": render_main_table(projects),
        "sandbox": render_sandbox_table(projects),
    }

    # Salida.
    if readme_arg:
        readme_path = Path(readme_arg).expanduser()
        write_warnings = update_readme(readme_path, blocks)
    else:
        write_warnings = []
        for key, content in blocks.items():
            print(f"<!-- {key.upper()} -->\n{content}\n")

    # Resumen + warnings.
    warnings = [w for p in projects for w in p.warnings] + write_warnings
    if tz_warning:
        warnings.insert(0, tz_warning)
    print("=" * 60)
    print(f"Proyectos indexados: {len(projects)}   ·   Fecha: {fecha} ({tz_name})")
    if readme_arg:
        print(f"README actualizado : {Path(readme_arg).expanduser()}")
    if warnings:
        print(f"\nAvisos ({len(warnings)}):")
        for w in warnings:
            print(f"  ⚠ {w}")
    else:
        print("\nSin avisos. ✅")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
