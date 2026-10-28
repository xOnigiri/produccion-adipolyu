# Recorrido – Parte 8: publicación en GitHub

Explicación en lenguaje sencillo de lo que se agregó para publicar el proyecto: README, licencia y capturas, y las protecciones que impiden subir datos del taller.
Aprobada el 28/10/2026.

## La idea general: publicar el código, nunca los datos

El repositorio tiene dos tipos de contenido, como un taller que muestra sus moldes pero no sus libros de pedidos:

```
Se sube a GitHub                         Se queda solo en la computadora
─────────────────────────────            ──────────────────────────────────
código (.py, templates, static)          produccion.db (registros reales)
pruebas automáticas (tests/)             produccion_prueba.db
docs/ (recorridos y capturas)            respaldos/ y copias de la base
README.md, LICENSE, logo                 .venv/ (entorno de Python)
```

Esta parte casi no tiene código nuevo: agrega documentación y confirma que la separación funciona.

---

## 1. [README.md](../README.md): la portada del repositorio

Es lo primero que se ve en GitHub. Sus secciones:

- **Qué hace**: cada pantalla explicada en una línea, con ejemplos del taller.
- **Capturas** dentro del texto, para entender la app sin instalarla.
- **Instalación y uso en Windows**: crear el entorno virtual, instalar `requirements.txt`, crear la base con `crear_base.py` y abrir la app con doble clic.
- **Cómo se guardan los datos**: qué se guarda, qué se calcula al mostrar y la regla de redondeo.
- **Estructura**: una tabla con el trabajo de cada archivo.
- **Pruebas**: cómo correrlas y qué cubren.
- **Cómo se desarrolló**: la app se hizo con asistencia de IA (Claude), con requisitos, pruebas y aprobación a cargo del responsable del proyecto.

## 2. [LICENSE](../LICENSE): qué se puede reutilizar

- **El código** está bajo licencia MIT: cualquiera puede reutilizarlo, siempre que conserve el aviso de autoría.
- **El logo y el nombre "Adipolyu"** quedan fuera de esa licencia y pertenecen a Adipolyu E.I.R.L. con todos los derechos reservados. La exclusión nombra los archivos concretos (`logo-adipolyu.png`, `static/icono.png` y las capturas) para que no haya dudas.

## 3. [docs/capturas/](capturas/): imágenes solo con datos de ejemplo

Son 6 capturas: registrar, error de validación con lona, historial, informe PDF, listas y vista de celular.

- **Base aparte.** Se tomaron con el modo prueba, pero sobre una base de ejemplo nueva creada en una carpeta temporal. La app no abrió `produccion.db` ni `produccion_prueba.db`. La misma función del modo prueba se niega a trabajar si la ruta apunta a la base real.
- **Navegador automático.** Edge en modo sin ventana (`--headless`) tomó todas las capturas con el mismo tamaño, así que se pueden repetir igual después de un cambio de diseño.
- **Error de validación.** Se envió un pedido con sobrante mayor que lo recibido. La app lo rechazó y no guardó nada: las tarjetas de la semana siguieron con el mismo número de pedidos.
- **Celular.** La página se mostró dentro de un marco de 390 px de ancho, que es el de un teléfono, para que se active el diseño con botón "Menú".
- **Informe.** La primera página del PDF se convirtió a imagen; lleva la marca de agua "DATOS DE EJEMPLO".
- **Imágenes limpias.** Se guardaron sin metadatos ocultos. La pantalla Respaldo no tiene captura, porque muestra rutas de la computadora.

Las herramientas de captura se usaron solo en una carpeta temporal: no se agregaron a `requirements.txt` ni al proyecto.

## 4. [.gitignore](../.gitignore): lo que Git nunca sube

```
*.db
respaldos*/
.venv/
.env
```

- **`*.db`** cubre la base real, la de prueba y cualquier copia.
- **`respaldos*/`** cubre las carpetas de respaldo locales.
- **`.env`** queda reservado por si algún día hay claves.

En GitHub se comprobó que el repositorio tiene exactamente los mismos archivos que Git controla en la computadora, y ninguna base de datos.

## 5. Revisión antes de cada commit

Antes de cada commit y de cada subida se revisa automáticamente:

| Qué se revisa | Cómo |
|---|---|
| Datos personales o rutas de la computadora | Búsqueda de texto en todos los archivos de todos los commits y en todos los mensajes |
| Claves o contraseñas | Búsqueda de patrones típicos (`token`, `password`, prefijos de claves) |
| Bases y respaldos | Confirmar que Git los sigue ignorando |
| La base real | Huella SHA-256 igual antes y después |
| La app | Las 204 pruebas automáticas pasan |

El resultado se muestra antes de hacer el commit.

## 6. Cambios futuros: commit + push

```
probar y aprobar  →  revisión (punto 5)  →  git commit  →  git push
```

- El repositorio se creó **privado**. Hacerlo público es una decisión aparte, desde la configuración de GitHub.
- Una vez subido, el historial **no se reescribe** (nunca `git push --force`). Un error se corrige con un commit nuevo, así el historial siempre muestra lo que pasó.

---

## Decisiones técnicas destacadas

1. **Separación entre código y datos.** Las bases y los respaldos nunca entran al repositorio. Se garantiza con `.gitignore` y se comprueba en cada revisión.
2. **Capturas reproducibles y seguras.** Se toman con un navegador automático sobre una base de ejemplo temporal, sin tocar ninguna base existente, con tamaños fijos y sin metadatos.
3. **Licencia con exclusión de marca.** El código es libre (MIT); el logo y el nombre de la empresa quedan protegidos y se nombran los archivos concretos.
4. **Revisión antes de cada commit.** Datos personales, claves, archivos ignorados, huella de la base real y pruebas automáticas.
5. **Historial que no se reescribe.** Después de publicar, todo arreglo es un commit nuevo y nunca se fuerza la subida.
6. **Transparencia.** El README declara que el código se escribió con asistencia de IA y quién definió, probó y aprobó cada parte.
