import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { listFemAlumnos, patchFemHoras, type FemAlumno } from '../services/api'

type Props = {
  roles: string[]
}

function progresoPct(alumno: FemAlumno): number {
  const total = alumno.horas_totales > 0 ? alumno.horas_totales : 500
  const pct = (alumno.horas_cursadas / total) * 100
  return Math.max(0, Math.min(100, Math.round(pct)))
}

/** Seguimiento FEM: listado + % horas (API existente; sin mapa aún). */
export function FemPage({ roles }: Props) {
  const canAccess = roles.includes('tutor') || roles.includes('admin')

  const [items, setItems] = useState<FemAlumno[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [okMsg, setOkMsg] = useState<string | null>(null)
  const [filtroEstado, setFiltroEstado] = useState('')
  const [horasDraft, setHorasDraft] = useState<Record<string, string>>({})
  const [savingId, setSavingId] = useState<string | null>(null)

  const load = useCallback(async () => {
    if (!canAccess) return
    setLoading(true)
    setError(null)
    try {
      const data = await listFemAlumnos(filtroEstado.trim() || undefined)
      setItems(data)
      const drafts: Record<string, string> = {}
      for (const a of data) {
        drafts[a.id] = String(a.horas_cursadas)
      }
      setHorasDraft(drafts)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo cargar el alumnado FEM')
    } finally {
      setLoading(false)
    }
  }, [canAccess, filtroEstado])

  useEffect(() => {
    void load()
  }, [load])

  if (!canAccess) return null

  const onSaveHoras = async (alumno: FemAlumno, e: FormEvent) => {
    e.preventDefault()
    const raw = horasDraft[alumno.id] ?? ''
    const value = Number(raw)
    if (Number.isNaN(value) || value < 0 || value > 500) {
      setError('Las horas deben ser un número entre 0 y 500.')
      return
    }
    setSavingId(alumno.id)
    setError(null)
    setOkMsg(null)
    try {
      await patchFemHoras(alumno.id, value)
      setOkMsg(`Horas actualizadas para ${alumno.nombre}.`)
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudieron guardar las horas')
    } finally {
      setSavingId(null)
    }
  }

  return (
    <section className="card">
      <h2>Formación en Empresas (FEM)</h2>
      <p className="hint">
        Alumnado en prácticas y progreso respecto a 500 h. Visible para tutor y admin. El mapa
        geográfico queda pendiente (la API aún no expone coordenadas).
      </p>

      <div className="toolbar fem-filters">
        <label>
          Estado
          <input
            value={filtroEstado}
            onChange={(e) => setFiltroEstado(e.target.value)}
            placeholder="p. ej. activo"
          />
        </label>
        <button type="button" onClick={() => void load()}>
          Actualizar
        </button>
      </div>

      {error && <p className="error">{error}</p>}
      {okMsg && <p className="ok">{okMsg}</p>}

      {loading && <p>Cargando alumnado FEM…</p>}
      {!loading && items.length === 0 && (
        <p className="muted">No hay alumnos FEM con ese filtro.</p>
      )}

      <ul className="fem-list">
        {items.map((a) => {
          const pct = progresoPct(a)
          return (
            <li key={a.id} className="fem-item">
              <div className="row">
                <h3>{a.nombre}</h3>
                {a.estado && (
                  <span className="badge badge-fem-estado">{a.estado}</span>
                )}
              </div>
              <p className="fem-meta muted">
                Empresa: {a.empresa || '—'}
                {a.tutor_id ? ` · Tutor: ${a.tutor_id}` : ''}
              </p>
              <div className="fem-progress-block">
                <div className="row">
                  <span>
                    {a.horas_cursadas} / {a.horas_totales} h
                  </span>
                  <span className="badge badge-rol">{pct}%</span>
                </div>
                <div
                  className="fem-progress"
                  role="progressbar"
                  aria-valuenow={pct}
                  aria-valuemin={0}
                  aria-valuemax={100}
                >
                  <div className="fem-progress-bar" style={{ width: `${pct}%` }} />
                </div>
              </div>
              <form className="fem-horas-form" onSubmit={(e) => void onSaveHoras(a, e)}>
                <label>
                  Horas cursadas
                  <input
                    type="number"
                    min={0}
                    max={500}
                    step={1}
                    value={horasDraft[a.id] ?? ''}
                    onChange={(e) =>
                      setHorasDraft((prev) => ({ ...prev, [a.id]: e.target.value }))
                    }
                    required
                  />
                </label>
                <button type="submit" disabled={savingId === a.id}>
                  {savingId === a.id ? 'Guardando…' : 'Guardar horas'}
                </button>
              </form>
            </li>
          )
        })}
      </ul>
    </section>
  )
}
