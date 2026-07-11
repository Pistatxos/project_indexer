# project_indexer

![Logo project indexer](./logo.jpg)

Script en Python (`project_index.py`) que recorre una o varias raíces a
**profundidad 2** (`categoria/proyecto`), lee los archivos `.project.yml`, deriva
tags automáticos del contenido de cada carpeta y genera **tablas Markdown**
(principal + sandbox, más un resumen) que inserta en un README entre marcadores.
Las tablas son Markdown estándar (se ven bien en GitLab/GitHub y en Obsidian).
Corre igual en local que en el **NAS (Synology)**, a mano o por cron.

Pero antes que la herramienta, va el **método** que implementa — porque la
herramienta sin el método no sirve de mucho.

## El método: dos niveles, por finalidad

La convención es deliberadamente simple:

- **Las carpetas representan la _finalidad_ del proyecto, no la tecnología ni el
  propietario.** Nada de "una carpeta para todo lo de Python" o "una por cliente":
  se agrupa por *para qué sirve*. Lo que relaciona cosas por lenguaje o
  plataforma son los `tags`, no las carpetas.
- **Máximo dos niveles de profundidad**: `categoria/proyecto`. Si algo no se
  encuentra en dos carpetas, la estructura ha fallado. Dos niveles caben en la
  cabeza; tres ya no.

Cinco categorías de primer nivel, con un ciclo de vida natural:

```
sandbox → tools → products
                → services
```

| Categoría | Para qué |
|---|---|
| `products/` | Genera ingresos (software propio o de cliente). |
| `services/` | Gratuito pero en uso activo (algo que mantienes tú). |
| `tools/` | Herramientas reutilizables que automatizan tu día a día. |
| `learning/` | Formación: cursos, ejercicios, laboratorios. |
| `sandbox/` | I+D: pruebas y prototipos que quizá nunca se toquen más — y está bien. |

Mover un proyecto de categoría es la excepción: solo cuando cambia su naturaleza
real (p. ej. algo gratis que empieza a monetizarse), **nunca** por cambiar de
lenguaje o framework.

**¿Esto entra en la taxonomía?** El test rápido: *¿alguna vez le harías
`git init`?* Si sí, es un proyecto y lleva su `.project.yml`. Si no (libros,
cursos sin código propio, assets, logos…), es material de referencia y vive
fuera, sin metadatos ni categoría.

Cada proyecto se marca con un `.project.yml` en su raíz, que guarda **solo lo que
no se puede inferir** (para qué sirve y en qué estado está). Todo lo demás —Git,
docs, lenguaje, fechas— lo deduce esta herramienta, que además mantiene un índice
navegable. Eso es lo que hace `project_index.py`.

## Instalación

Solo necesita Python 3 y **PyYAML**:

```bash
python3 -m pip install pyyaml
```

En Synology (DSM): instala el paquete **Python 3** desde el Centro de paquetes y
luego `python3 -m pip install --user pyyaml` desde SSH.

## Configuración (`.env`)

Los ajustes viven en un archivo **`.env`** junto al script, para que **sobrevivan
a las actualizaciones** (cuando sobrescribes `project_index.py` no pierdes tu
config). El `.env` **no se versiona** (está en `.gitignore`); se sube solo
`.env.example` como plantilla:

```bash
cp .env.example .env      # y edita .env con tus rutas
```

```dotenv
ROOTS=/volume1/proyectos                # raíces a escanear (varias con comas)
README=/volume1/proyectos/README.md      # README a actualizar (vacío = a consola)
EXCLUDE=                                  # carpetas extra a excluir (comas)
TIMEZONE=Europe/Madrid                    # zona horaria de la fecha
INIT=true                                 # crear .project.yml que falten
```

**Precedencia por ajuste: argumentos de CLI  >  `.env`  >  valores por defecto**
del bloque `CONFIG` del script (que solo actúan como último recurso si no hay
`.env` ni argumentos). Así dejas el NAS configurado en su `.env` y puedes lanzar
una pasada puntual con otras rutas vía `--root`/`--readme`. Con `--env RUTA`
puedes apuntar a un `.env` en otra ubicación.

## Uso

```bash
# Sin argumentos: usa todo lo del bloque CONFIG
python3 project_index.py

# Indexar y actualizar el README índice
python3 project_index.py --root ~/projects --readme INDICE.md

# En el NAS, con la ruta real de los proyectos
python3 project_index.py --root /volume1/proyectos --readme /volume1/proyectos/INDICE.md

# Varias raíces (local + NAS montado) en una sola pasada
python3 project_index.py --root ~/projects --root /volume1/proyectos --readme INDICE.md

# Vista previa por consola, sin tocar ningún archivo
python3 project_index.py --root ~/projects

# Crear .project.yml plantilla en las carpetas de nivel 2 que aún no tengan
python3 project_index.py --root /volume1/proyectos --init

# Excluir carpetas por nombre o patrón glob (repetible)
python3 project_index.py --root ~/projects --exclude _borrar --exclude "*_old" --readme INDICE.md
```

### Opciones

| Opción | Descripción |
|---|---|
| `--root RUTA` | Raíz a escanear (`categoria/proyecto`). **Repetible.** Anula `ROOTS` del `.env`. |
| `--readme RUTA` | README a actualizar entre marcadores. Sin ella (ni `README` en `.env`), imprime a consola. |
| `--exclude PATRÓN` | Nombre exacto o patrón glob de carpeta a ignorar (nivel 1 o 2). Repetible. Anula `EXCLUDE`. |
| `--timezone TZ` | Zona horaria de la fecha, p. ej. `Europe/Madrid`. Anula `TIMEZONE`. |
| `--env RUTA` | Ruta a un `.env` alternativo (por defecto, `.env` junto al script). |
| `--init` | Crea un `.project.yml` plantilla en las carpetas de nivel 2 que no tengan uno. Activo por defecto vía `CONFIG["init"]`. |
| `--fix-sandbox-status` | One-shot: pasa a `archived` los `.project.yml` de `sandbox/` que estén en `active` (preservando el resto). Úsalo una vez para corregir los ya creados. |

`--init` (y `CONFIG["init"]`) es **seguro e idempotente**: solo crea los que
faltan, nunca sobrescribe ni borra los existentes. Por eso viene activo: cada
pasada da de alta las carpetas nuevas sola. **Ojo:** con init activo, borrar un
`.project.yml` no oculta el proyecto (la carpeta sigue ahí y se le vuelve a
crear). Para quitar algo de las tablas: borra la carpeta, exclúyela
(`--exclude`) o dale un `type` fuera de la taxonomía.

Exclusiones aplicadas siempre (además de `--exclude`): `.git`, `node_modules`,
`__pycache__`, `venv`, `.venv`, `.obsidian`, `@eaDir` (basura de Synology),
`.DS_Store`.

## El archivo `.project.yml`

Un proyecto se reconoce porque **contiene** un `.project.yml` en su carpeta de
nivel 2. Campos:

```yaml
name: mi-proyecto          # opcional; por defecto, el nombre de la carpeta
type: services             # products | services | tools | learning | sandbox
status: active             # active | paused | archived | deprecated
description: "Qué hace"
tags: [interno, cron]      # tags manuales; los automáticos se añaden sin duplicar
created: 2025-03-01        # informativo
```

Solo `name`, `type`, `status`, `description`, `tags` y `created` se leen. Todo lo
demás se ignora. (Si en vez de `created` usas `date`, también se acepta.)

**Descripción**: manda la del `.project.yml`. Si está vacía, se saca del primer
párrafo real del `README.md` del proyecto (saltando título, badges, bloques de
código y HTML), recortada a ~200 caracteres. Así la tabla se rellena sola aunque
no hayas puesto `description` a mano.

## Info de Git

En cada proyecto que sea repo (`.git/`) el script ejecuta `git status` y saca:

- **Estado Git** (columna *Git*): `✅ limpio` (todo commiteado y pusheado) ·
  `🟠 pendiente` (cambios sin commitear o commits sin pushear) · `—` (no es repo).
- **Actualizado**: fecha del **último commit** (`git log -1 --format=%cs`). Si la
  carpeta no es repo, se usa la fecha de modificación más reciente de su primer
  nivel.
- El **remoto** (`github`/`gitlab`/`gitea`) y la marca `git` van como tags.

## Auto-tagging

A los tags manuales se les añaden estos **sin duplicar** (según el contenido de
la carpeta del proyecto):

Por **extensión** de archivo: `.py`→`python` · `.sh`→`bash` · `.js`→`javascript`
· `.ts`→`typescript` · `.tf`→`terraform` · `.go`→`go` · `.rs`→`rust` ·
`.php`→`php`.

Por **archivo-marcador**: `Dockerfile`/`docker-compose.*`/`compose.*`→`docker` ·
`package.json`→`node` · `go.mod`→`go` · `Cargo.toml`→`rust` ·
`composer.json`→`php` · `pyproject.toml`→`python`.

De **Git**: remoto `origin` en github/gitlab/gitea → `github`/`gitlab`/`gitea`.
Si el repo es local (sin remoto) → `git` a secas. Con remoto **no** se añade
`git` además del host (evita el `git gitea` redundante).

Los tags automáticos **no se escriben** al `.project.yml`: se recalculan en cada
pasada (es como un `init` continuo), así que siempre reflejan el estado real de
la carpeta.

## Columna Docs

`Docs` = ✅ si el proyecto tiene un `README` en su raíz, ❌ si no. Sirve para
cumplir tu regla de mantenimiento (*todo proyecto debe tener un `README.md`
mínimo*) y localizar de un vistazo los que faltan (también salen contados en el
Resumen).

## Bloque Resumen

Si el README destino tiene el par `<!-- INICIO RESUMEN -->` / `<!-- FIN RESUMEN -->`,
el script inserta ahí una mini-tabla con: total de proyectos, desglose por tipo,
cuántos con git pendiente y cuántos sin README. La plantilla ya lo trae; si tu
hub actual no lo tiene, pega esos dos marcadores donde quieras el resumen.

## Validaciones (avisos, no bloquean)

Al final se imprime un resumen con el nº de proyectos indexados y los avisos:

- `type` no coincide con la carpeta de nivel 1 real.
- `status` vacío o fuera de `[active, paused, archived, deprecated]` → se trata
  con el **valor por defecto según el tipo**: `active` en general, pero
  **`archived` para `sandbox`** (los experimentos no arrancan como activos; solo
  pasan a `active` si lo pones tú a mano). Ese defecto de sandbox se controla con
  la constante `SANDBOX_DEFAULT_STATUS`.
- `type` desconocido (fuera de products/services/tools/learning/sandbox) → el
  proyecto no aparece en ninguna tabla.

## Salida: las tablas y los marcadores

El README destino debe contener estos tres pares de marcadores. El script
reescribe **solo** lo que hay entre cada par; el resto del archivo no se toca. Si
falta un par, se avisa y ese bloque no se inserta.

```markdown
**Última actualización:** <!-- INICIO FECHA -->
<!-- FIN FECHA -->

<!-- INICIO RESUMEN -->
<!-- FIN RESUMEN -->

<!-- INICIO TABLA PRINCIPAL -->
<!-- FIN TABLA PRINCIPAL -->

<!-- INICIO TABLA SANDBOX -->
<!-- FIN TABLA SANDBOX -->
```

Tienes una plantilla lista en [`plantilla_indice.md`](plantilla_indice.md).
**Si el README destino no existe, el script lo crea automáticamente a partir de
esa plantilla** (y luego rellena las tablas); en las siguientes pasadas ya solo
actualiza los bloques. Así, en el NAS, basta con lanzarlo la primera vez y el
`README.md` de la raíz aparece solo.

- **Tabla principal**: proyectos con `type` en `products, services, tools,
  learning`, **agrupados por type**, columnas `Nombre | Estado | Git | Docs |
  Actualizado | Tags | Descripción | Ruta`. Dentro de cada grupo, `active`
  primero y luego alfabético.
- **Tabla sandbox**: solo `type: sandbox`, mismas columnas y orden.

La columna **Ruta** es un botón 📁 (`file://…`) que abre la carpeta del proyecto.

La fecha se genera con el formato `%Y-%m-%d %H:%M` (sin nombre de zona) en la
zona horaria configurada (`Europe/Madrid` por defecto), vía `zoneinfo`.

En el Python del Synology (DSM suele traer **Python 3.8**, sin `zoneinfo`) el
script cae a la **hora local del sistema** y avisa. Si el NAS ya está en hora de
Madrid, esa hora es la correcta y puedes ignorar el aviso. Para forzar la zona
exacta desde el propio script instala el backport en tu venv:

```bash
pip install "backports.zoneinfo[tzdata]"
```

## Automatizar en el NAS (cron)

Con el **Programador de tareas** de DSM (tarea programada → script definido por
el usuario), o por crontab:

Deja las rutas en el `.env` junto al script y el cron queda mínimo:

```cron
# Cada día a las 03:00 regenera el índice (rutas tomadas de CONFIG)
0 3 * * * /usr/local/bin/python3 /volume1/tools/project_indexer/project_index.py >> /volume1/tools/project_indexer/index.log 2>&1
```

O pásalo todo por argumentos si prefieres no tocar el script:

```cron
0 3 * * * /usr/local/bin/python3 /volume1/tools/project_indexer/project_index.py \
    --root /volume1/proyectos --readme /volume1/proyectos/INDICE.md >> /volume1/tools/project_indexer/index.log 2>&1
```

## Licencia

MIT — úsalo, modifícalo, adáptalo a tu propio sistema de carpetas sin pedir permiso.