# 🌌 Personal Development & Business Hub

Este es mi ecosistema privado de desarrollo. Así gestiono mi propiedad intelectual, los servicios que monto, el trabajo con clientes y mi evolución técnica. Un máximo dos niveles de profundidad. Si no se encuentra en dos carpetas, la estructura ha fallado.

> **Las carpetas representan la finalidad del proyecto, no la tecnología.** 

**Última actualización:** <!-- INICIO FECHA --><!-- FIN FECHA -->

---

<!-- INICIO RESUMEN -->

<!-- FIN RESUMEN -->

---

### Vista Principal

<!-- INICIO TABLA PRINCIPAL -->

<!-- FIN TABLA PRINCIPAL -->


---

### Sandbox

<!-- INICIO TABLA SANDBOX -->

<!-- FIN TABLA SANDBOX -->


---

## 🔄 Ciclo de Vida

```
sandbox/ → tools/ → products/
                  → services/
```

1. **Sandbox**: investigación, pruebas y prototipos rápidos. Almacén de creaciones que quizá nunca se toquen más — y está bien.
2. **Tools**: herramientas que funcionan y automatizan el día a día, propias o reutilizables desde otros proyectos.
3. **Products / Services**: destino final según el propósito real del código, no según su origen.

Mover un proyecto de categoría es la excepción, no la norma, y solo ocurre cuando cambia su naturaleza real (por ejemplo, algo gratuito que empieza a monetizarse). Nunca por cambiar de lenguaje o framework.

---

## 📂 Project Structure

```text
~/projects/
├── products/          # GENERA INGRESOS
│   ├── producto_x/    # Software propio, a la venta.
│   └── cliente_x/     # Proyecto de cliente, facturado directamente.
│
├── services/          # GRATUITO, PERO EN USO ACTIVO
│   ├── service_1/     # Servicio 1, tipo repo en github.
│   └── weather/       # Servicio 2, tipo repo en gitlab.
│
├── tools/             # HERRAMIENTAS REUTILIZABLES
│   ├── tool_1/        # Scripts en Python, guardados por si acaso.
│   └── check_1/       # Script sh que testea disponibilidad de una app.
│
├── learning/          # FORMACIÓN CONTINUA
│   └── terraform/     # Cursos, ejercicios, certificaciones.
│
└── sandbox/           # LABORATORIO DE I+D
    └── prueba_1/      # Pruebas sin compromiso de futuro.
```

Dentro de cada proyecto no hay estructura obligatoria — cada tecnología usa la que le venga mejor. Lo único fijo es el archivo de metadatos `.project.yml` en la raíz.

---

## 🗂️ ¿Dónde va cada cosa?

| Tipo de proyecto | Carpeta | Status típico |
|---|---|---|
| Software vendible, o de cliente facturado | `products/` | active |
| Servicio que mantienes tú, gratuito pero en uso real | `services/` | active |
| Herramienta reutilizable, o script que sigue corriendo | `tools/` | active / archived |
| Curso, certificación, laboratorio de aprendizaje | `learning/` | active / archived |
| Prueba rápida sin compromiso de futuro | `sandbox/` | active / archived |

**¿Y si no encaja en ninguna?** Aplica el test: **¿alguna vez le harías `git init` a esto?**

- Si sí → es un proyecto real. Si ya sabes su destino final, entra directo en su categoría;
  si no, `sandbox/` mientras lo decides.
- Si no → es material de referencia (libros, cursos, assets, logos) cualquier cosa `sin código propio` lo pondremos fuera de `~/projects/`, sin metadatos ni categoría.
---

## 🏷️ Relacionar sin crear carpetas de más

Cuando varias cosas están relacionadas por plataforma o tecnología **no se crea una carpeta agrupadora** — eso sería organizar por tecnología, justo lo que evitamos. Se usa el campo `tags` de `.project.yml`. La tabla automática permite filtrar/agrupar por tag sin que la carpeta tenga que decir nada.

---

## 📄 Archivo `.project.yml`

Cada proyecto incluye un archivo oculto `.project.yml` con metadatos manuales:

```yaml
name: aemet
type: tools              # products | services | tools | learning | sandbox
status: active           # active | paused | archived | deprecated
description: "Consulta metereológica en la api de aemet."
tags:
  - python
created: 2026-07-04
```

- **`type`** debe coincidir con la carpeta de primer nivel donde vive el proyecto.
- **`status`** usa un enum cerrado para poder filtrar de forma consistente.
- Toda la información técnica (Git, commits, lenguaje, Docker...) se obtiene automáticamente con herramientas externas — aquí solo va lo que nadie más puede inferir: para qué sirve y en qué estado está.

---

## ⚙️ Cómo se automatiza la tabla

Un script recorre local y NAS, lee cada `.project.yml`, actualiza la fecha de arriba y genera dos tablas: **Principal** (products, services, tools, learning agrupados por type) y **Sandbox** (aparte, para no mezclar volumen con lo importante). Añade tags automáticos por convención (lenguaje, Docker, Git) sin pisar los manuales, y avisa por consola si algo no cuadra (`type`/carpeta o `status` inválido). 

---

## 🛠️ Tech Stack

- **Languages**: Python (principal), Bash/Zsh
- **Automation**: n8n (workflows), Docker (containerización)
- **Git**:
  - GitHub → proyectos públicos y open source
  - GitLab → proyectos privados, propios y de cliente
  - Gitea → mirroring y backup local

---

## 📝 Reglas de Mantenimiento

- **Clean Sandbox**: lo que creas ahí y no le ves futuro se queda como almacén y si sirve, se mueve a su categoría definitiva.
- **Aislamiento por proyecto**: cada proyecto de cliente en `products/` tiene su propio `.env` y dependencias aisladas — nunca compartidas entre proyectos.
- **Documentation**: todo proyecto debe tener un `README.md` mínimo en su raíz, además de su `.project.yml`.
- **Repo y buenas prácticas**: commits atómicos y descriptivos. `.gitignore` desde el primer commit (entornos, `.env`, `__pycache__`, `node_modules`...). Nunca credenciales ni claves en el repo, ni en el historial — si se cuela una, se rota, no basta con borrarla del último commit.

---

###### By 🚀 Pistatxos