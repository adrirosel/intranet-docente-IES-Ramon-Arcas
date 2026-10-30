# Contrato API — Intranet Docente

Fuente canónica machine-readable: [openapi/openapi.yaml](../openapi/openapi.yaml).

Prefijo funcional: **`/api/v1`**.  
Health: sin prefijo de versión (`/health`, `/health/ready`).

Autenticación por defecto: header `Authorization: Bearer <access_token>`, salvo endpoints públicos y refresh (cookie).

## Convenciones de respuesta (norma del repo)

Alineadas a los apuntes del profesorado (FastAPI + diseño REST):

| Caso | Formato |
|------|--------|
| Error | `{"detail": "..."}` o lista de errores de validación 422 |
| Listados paginados | `{ "items": [...], "page": 1, "limit": 10, "total": N }` |
| Listados filtrados (excepción) | Array JSON directo — ver [Excepciones de paginación](#excepciones-de-paginación) |
| Detalle / recurso | Objeto JSON del recurso |
| POST creado | `201` + cuerpo del recurso + cabecera `Location: /api/v1/.../{id}` |
| Mutación OK | Recurso actualizado (sin wrapper `{code, msg}`) |

Códigos habituales: `200`, `201`, `204`, `400`, `401`, `403`, `404`, `409`, `422`, `503`.

Paginación (cuando aplica): `page` (default 1), `limit` (default 10, máx. 50).

Identificadores: `string` (ObjectId de MongoDB en hex). El cliente **nunca** envía el `id` en el alta; lo asigna el servidor.

### Excepciones de paginación

Estos listados devuelven un **array** (no el wrapper paginado), porque se consultan por filtro acotado:

| Endpoint | Motivo |
|----------|--------|
| `GET /api/v1/anuncios` | Feed del tablón (vigentes, segmentados) |
| `GET /api/v1/tickets` | Cola filtrada por `tipo` / `estado` |
| `GET /api/v1/guardias` | Cuadrante por `fecha` / `franja` |
| `POST /api/v1/guardias/asignar` | Resultado de la ejecución (array de `Guardia`) |

Usuarios, retrasos, notificaciones y auditoría sí usan `{ items, page, limit, total }`.

## Auth

| Método | Endpoint | Auth | Roles | Descripción |
|--------|----------|------|-------|-------------|
| POST | `/api/v1/auth/google` | Público | — | Body `{ "id_token" }` → access JWT + cookie HttpOnly refresh |
| POST | `/api/v1/auth/refresh` | Cookie refresh | — | Renueva access; no usa Bearer |
| POST | `/api/v1/auth/logout` | Auth | — | Invalida refresh en Redis y borra cookie |
| GET | `/api/v1/auth/me` | Auth | — | Usuario autenticado, roles y estado |

- Access token: header Bearer.
- Refresh token: cookie HttpOnly `refresh_token` (path `/api/v1/auth`), almacenada en Redis.
- Sin restricción de dominio Google. Alta OAuth deja al usuario en estado `pendiente` hasta aprobación admin.

## Usuarios

| Método | Endpoint | Auth | Roles / regla | Descripción |
|--------|----------|------|---------------|-------------|
| GET | `/api/v1/usuarios` | Auth | `admin` | Listado paginado (`?departamento=&estado=&rol=&page=&limit=`) |
| POST | `/api/v1/usuarios` | Auth | `admin` | Alta manual; `201` + `Location` |
| GET | `/api/v1/usuarios/me` | Auth | — | Perfil propio |
| PATCH | `/api/v1/usuarios/me` | Auth | — | Rectificar datos propios (RGPD): `name`, `dni`, `telefono` |
| GET | `/api/v1/usuarios/me/datos` | Auth | — | Exportar datos personales propios (RGPD) |
| GET | `/api/v1/usuarios/me/horario` | Auth | — | Horario semanal propio |
| GET | `/api/v1/usuarios/{id}` | Auth | `admin` o propio | Detalle |
| GET | `/api/v1/usuarios/{id}/horario` | Auth | `admin` o propio | Horario de un docente |
| PATCH | `/api/v1/usuarios/{id}` | Auth | `admin` | Parcial (aprobar, roles, departamento…) |
| PUT | `/api/v1/usuarios/{id}/roles` | Auth | `admin` | Sustituir lista de roles; `409` si se elimina el último admin |

## Anuncios

| Método | Endpoint | Auth | Roles | Descripción |
|--------|----------|------|-------|-------------|
| GET | `/api/v1/anuncios` | Auth | — | Feed segmentado por departamento (array) |
| POST | `/api/v1/anuncios` | Auth | `admin`, `directiva` | Publicar; `201` + `Location` |
| PATCH | `/api/v1/anuncios/{id}/fijar` | Auth | `admin` | Fijar / desfijar |

## Guardias

| Método | Endpoint | Auth | Roles | Descripción |
|--------|----------|------|-------|-------------|
| GET | `/api/v1/guardias` | Auth | — | Cuadrante (`?fecha=&franja=`) → array |
| POST | `/api/v1/guardias/asignar` | Auth | `jefatura` | Asignación por rondas → array de `Guardia` |
| PATCH | `/api/v1/guardias/{id}` | Auth | `jefatura` | Cambiar `cubre_id` / estado → `Guardia` |

### Modelo y regla de asignación

Cada `Guardia` distingue:

| Campo | Significado |
|-------|-------------|
| `asignado_id` | Docente al que corresponde la guardia por ronda/contador |
| `cubre_id` | Docente que finalmente realiza la guardia |
| `ausente_id` | Docente cuya ausencia genera el hueco |

Regla (cerrada; runtime en Fase 3):

1. En cada hueco puede haber más de un docente disponible.
2. Contador de guardias realizadas **por docente y por hueco horario concreto**.
3. Empate en contador entre disponibles del hueco → selección aleatoria.
4. La comparación del contador es solo entre disponibles de ese hueco, nunca contra todo el claustro.
5. Si el `asignado_id` no puede asistir, otro disponible cubre (`cubre_id`); en rondas siguientes se prioriza a quien tenga menos.
6. `asignado_id` y `cubre_id` pueden diferir.

## Ausencias

| Método | Endpoint | Auth | Roles / propiedad | Descripción |
|--------|----------|------|-------------------|-------------|
| POST | `/api/v1/ausencias` | Auth | — | Registro; `201` + cuerpo `Ausencia` + `Location` |
| GET | `/api/v1/ausencias/{id}` | Auth | dueño / `admin` / `jefatura` | Detalle |
| POST | `/api/v1/ausencias/{id}/justificante` | Auth | dueño | Subida de justificante |
| GET | `/api/v1/ausencias/{id}/pdf` | Auth | dueño | PDF autocompletado |
| POST | `/api/v1/ausencias/{id}/firma` | Auth | dueño | Firma; body `FirmaRequest` → `Ausencia` |

### Firma (decisión cerrada)

| Campo | Valor |
|-------|--------|
| `proveedor` | `manuscrita` (objetivo garantizado) o `autofirma` (mejor esfuerzo) |
| `firma_base64` | Imagen PNG/JPEG en base64 (captura en pantalla o payload del cliente) |

AutoFirma depende de certificado e instalación en el equipo del usuario; no bloquea la evaluación si la vía manuscrita funciona.

Estados de ausencia: `registrada` → `pendiente_justificante` (si genérica) → `pendiente_firma` → `firmada`.

## Tickets

| Método | Endpoint | Auth | Roles / propiedad | Descripción |
|--------|----------|------|-------------------|-------------|
| GET | `/api/v1/tickets` | Auth | — | Listado (`?tipo=&estado=`) → array |
| POST | `/api/v1/tickets` | Auth | — | Creación; `201` + `Location` |
| PATCH | `/api/v1/tickets/{id}` | Auth | `responsable_ticket` / `admin` | Transición de estado |
| GET | `/api/v1/tickets/{id}/comentarios` | Auth | involucrados | Hilo de comentarios |
| POST | `/api/v1/tickets/{id}/comentarios` | Auth | involucrados | Nuevo comentario; `201` + `Location` |

### Máquina de estados de tickets

```
abierto → en_proceso → resuelto → cerrado
```

- Solo se aceptan transiciones válidas.
- Transición inválida → `422` con `{"detail": "..."}`.

## FEM (Formación en Empresas Murcia)

| Método | Endpoint | Auth | Roles | Descripción |
|--------|----------|------|-------|-------------|
| GET | `/api/v1/fem/alumnos` | Auth | `tutor`, `admin` | Alumnado asignado |
| PATCH | `/api/v1/fem/alumnos/{id}/horas` | Auth | `tutor`, `admin` | Actualizar horas cursadas |

## Dashboard

| Método | Endpoint | Auth | Roles | Descripción |
|--------|----------|------|-------|-------------|
| GET | `/api/v1/dashboard/kpis` | Auth | `directiva`, `admin` | Indicadores del centro |

## Retrasos

| Método | Endpoint | Auth | Roles | Descripción |
|--------|----------|------|-------|-------------|
| POST | `/api/v1/retrasos` | Auth | `docente`, `admin` | Registrar retraso; `201` + `Location` |
| GET | `/api/v1/retrasos/{id}` | Auth | `docente`, `admin` | Detalle |
| GET | `/api/v1/alumnos/{id}/retrasos` | Auth | `docente`, `admin` | Histórico paginado (`?curso_escolar=&page=&limit=`) |

## Notificaciones

| Método | Endpoint | Auth | Roles / regla | Descripción |
|--------|----------|------|---------------|-------------|
| GET | `/api/v1/notificaciones` | Auth | solo propias | Bandeja paginada (`?leida=&page=&limit=`) + `no_leidas` |
| PATCH | `/api/v1/notificaciones/{id}` | Auth | destinatario | Marcar leída / no leída |
| POST | `/api/v1/notificaciones/suscripciones` | Auth | — | Registrar Web Push (`201` o `200` si ya existía) |
| DELETE | `/api/v1/notificaciones/suscripciones/{id}` | Auth | dueño | Eliminar suscripción (`204`) |

Las notificaciones **no se crean desde la API**: las generan los servicios ante eventos de negocio.

## Auditoría

| Método | Endpoint | Auth | Roles | Descripción |
|--------|----------|------|-------|-------------|
| GET | `/api/v1/auditoria` | Auth | `admin`, `directiva` | Registro paginado (solo lectura) |

Filtros: `usuario_id`, `accion`, `recurso_tipo`, `recurso_id`, `desde`, `hasta` (ISO 8601), `page`, `limit` (default 10). Intervalo inválido (`desde` > `hasta`) → 422.

Acciones runtime: `auth.login_google`, `auth.login_failed`, `auth.logout`, `usuarios.create`, `usuarios.patch`, `usuarios.put_roles`.  
En `patch` / `put_roles` el `detalle` incluye `antes` y `despues`. Las mutaciones de usuarios exigen persistir la traza (503 si falla Mongo); login/logout usan best-effort con log.

## Health

| Método | Endpoint | Auth | Descripción |
|--------|----------|------|-------------|
| GET | `/health` | Público | Liveness (proceso vivo) |
| GET | `/health/ready` | Público | Readiness (Mongo, Redis) |

## Decisiones cerradas

- `POST /auth/google`: body `{ "id_token": "..." }`; sin whitelist de dominio.
- Refresh token: cookie HttpOnly (no body JSON).
- Errores y mutaciones: norma FastAPI / recurso (sin `{code, msg}`).
- Guardias: `asignado_id` vs `cubre_id` + regla de rondas (arriba).
- Firma: `FirmaRequest` con `proveedor` (`manuscrita` \| `autofirma`) + `firma_base64`.
- Perfil PDF: `UsuarioMePatch` admite `name`, `dni`, `telefono`.

## Fuera de este contrato (fases posteriores)

Módulos de la memoria del proyecto **sin endpoints** en este OpenAPI (se definirán al abordar su fase):

| Módulo memoria | Notas |
|----------------|-------|
| Emplazamiento de alumnado en el aula | Diseños de aula configurables |
| Aula de convivencia | Alta por jefatura; vínculo con guardias de destino |
| Comparador de horarios | Intersección de huecos libres entre docentes |
| Repositorio documental | Docs por departamento / proyecto |
| Reserva de espacios y recursos | Con detección de solapamientos |
| Comisiones de servicio | Reutilizará flujo de PDF/firma de ausencias |
| Onboarding / primeros pasos | Guía de bienvenida (contenido, no solo `pendiente→activo`) |
| Mapa FEM / empresas | Geolocalización (Leaflet + Nominatim) |
| Generación IA borrador RRSS | Entrada al ticket `tipo=rrss`; no publica en redes |
| Google Calendar | Sincronización de horarios/ausencias |

## Pendiente de decisión (módulos posteriores)

- Librerías concretas de PDF, email y Web Push (VAPID).
- Si el autor puede corregir o borrar un retraso mal registrado, y en qué plazo.
- Preferencias de canal de notificación y plazo de conservación de notificaciones/auditoría.
- Fuente canónica de alumnado (`alumno_id`) compartida con FEM/retrasos.
