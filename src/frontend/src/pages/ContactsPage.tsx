import { useState, useMemo } from 'react'
import { useContacts, useCreateContact, useUpdateContact, useDeleteContact } from '../api/contacts'
import { Modal } from '../components/Modal'
import { Badge } from '../components/Badge'
import { Plus, Search, Pencil, Trash2 } from 'lucide-react'
import type { Contact, ContactCreate, NumberType } from '../api/types'

const typeLabel: Record<NumberType, string> = {
  private: 'Privat',
  business: 'Geschäftlich',
  mobile: 'Mobil',
}

interface FormState {
  number: string
  name: string
  number_type: NumberType
  tags: string
  notes: string
  spam_score: string
}

function emptyForm(): FormState {
  return { number: '', name: '', number_type: 'private', tags: '', notes: '', spam_score: '0' }
}

function contactToForm(c: Contact): FormState {
  return {
    number: c.number,
    name: c.name,
    number_type: c.number_type,
    tags: c.tags.join(', '),
    notes: c.notes ?? '',
    spam_score: String(c.spam_score),
  }
}

export function ContactsPage() {
  const { data: contacts = [], isLoading } = useContacts()
  const createMut = useCreateContact()
  const updateMut = useUpdateContact()
  const deleteMut = useDeleteContact()

  const [search, setSearch] = useState('')
  const [modal, setModal] = useState<null | 'create' | Contact>(null)
  const [form, setForm] = useState<FormState>(emptyForm())

  const filtered = useMemo(
    () => contacts.filter((c) => !search || c.number.includes(search) || c.name.toLowerCase().includes(search.toLowerCase())),
    [contacts, search],
  )

  function openCreate() {
    setForm(emptyForm())
    setModal('create')
  }

  function openEdit(c: Contact) {
    setForm(contactToForm(c))
    setModal(c)
  }

  function field(key: keyof FormState) {
    return {
      value: form[key],
      onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
        setForm((f) => ({ ...f, [key]: e.target.value })),
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const payload: ContactCreate = {
      number: form.number,
      name: form.name,
      number_type: form.number_type,
      tags: form.tags ? form.tags.split(',').map((t) => t.trim()).filter(Boolean) : [],
      notes: form.notes || undefined,
      spam_score: Number(form.spam_score),
    }
    if (modal === 'create') {
      await createMut.mutateAsync(payload)
    } else if (modal && typeof modal === 'object') {
      await updateMut.mutateAsync({ number: modal.number, data: payload })
    }
    setModal(null)
  }

  const inputCls = 'w-full bg-ha-bg border border-ha-border rounded px-3 py-1.5 text-sm text-white focus:outline-none focus:border-ha-accent'

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <h1 className="text-xl font-semibold text-white">Kontakte</h1>
        <div className="flex gap-2">
          <div className="relative">
            <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-ha-muted" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Suche…"
              className="bg-ha-surface border border-ha-border rounded px-3 py-1.5 pl-8 text-sm text-white placeholder-ha-muted focus:outline-none focus:border-ha-accent w-44"
            />
          </div>
          <button
            onClick={openCreate}
            className="flex items-center gap-1.5 bg-ha-accent hover:bg-blue-600 text-white rounded px-3 py-1.5 text-sm transition-colors"
          >
            <Plus size={14} />
            Neu
          </button>
        </div>
      </div>

      {isLoading ? (
        <p className="text-ha-muted">Lade…</p>
      ) : (
        <div className="bg-ha-surface border border-ha-border rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-ha-border text-ha-muted">
                <th className="text-left px-4 py-2">Nummer</th>
                <th className="text-left px-4 py-2">Name</th>
                <th className="text-left px-4 py-2">Typ</th>
                <th className="text-left px-4 py-2">Spam</th>
                <th className="text-left px-4 py-2">Tags</th>
                <th className="px-4 py-2" />
              </tr>
            </thead>
            <tbody>
              {filtered.map((c) => (
                <tr key={c.number} className="border-b border-ha-border last:border-0 hover:bg-ha-border/20">
                  <td className="px-4 py-2 text-ha-muted font-mono">{c.number}</td>
                  <td className="px-4 py-2 text-white">{c.name}</td>
                  <td className="px-4 py-2"><Badge>{typeLabel[c.number_type]}</Badge></td>
                  <td className="px-4 py-2">
                    {c.spam_score > 0 && <Badge variant={c.spam_score >= 7 ? 'danger' : 'warning'}>{c.spam_score}</Badge>}
                  </td>
                  <td className="px-4 py-2 text-ha-muted">{c.tags.join(', ') || '—'}</td>
                  <td className="px-4 py-2">
                    <div className="flex gap-2 justify-end">
                      <button onClick={() => openEdit(c)} className="text-ha-muted hover:text-white transition-colors"><Pencil size={14} /></button>
                      <button
                        onClick={() => { if (confirm(`${c.name} löschen?`)) deleteMut.mutate(c.number) }}
                        className="text-ha-muted hover:text-red-400 transition-colors"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr><td colSpan={6} className="px-4 py-8 text-center text-ha-muted">Keine Kontakte</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {modal !== null && (
        <Modal title={modal === 'create' ? 'Neuer Kontakt' : `Kontakt bearbeiten`} onClose={() => setModal(null)}>
          <form onSubmit={handleSubmit} className="space-y-3">
            <div>
              <label className="block text-xs text-ha-muted mb-1">Nummer</label>
              <input {...field('number')} disabled={modal !== 'create'} required className={inputCls} placeholder="+49..." />
            </div>
            <div>
              <label className="block text-xs text-ha-muted mb-1">Name</label>
              <input {...field('name')} required className={inputCls} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs text-ha-muted mb-1">Typ</label>
                <select {...field('number_type')} className={inputCls}>
                  <option value="private">Privat</option>
                  <option value="business">Geschäftlich</option>
                  <option value="mobile">Mobil</option>
                </select>
              </div>
              <div>
                <label className="block text-xs text-ha-muted mb-1">Spam-Score</label>
                <input {...field('spam_score')} type="number" min="0" max="10" className={inputCls} />
              </div>
            </div>
            <div>
              <label className="block text-xs text-ha-muted mb-1">Tags (kommagetrennt)</label>
              <input {...field('tags')} className={inputCls} placeholder="tag1, tag2" />
            </div>
            <div>
              <label className="block text-xs text-ha-muted mb-1">Notizen</label>
              <textarea {...field('notes')} rows={2} className={inputCls} />
            </div>
            <div className="flex justify-end gap-2 pt-1">
              <button type="button" onClick={() => setModal(null)} className="px-4 py-1.5 text-sm text-ha-muted hover:text-white transition-colors">
                Abbrechen
              </button>
              <button type="submit" className="px-4 py-1.5 text-sm bg-ha-accent hover:bg-blue-600 text-white rounded transition-colors">
                Speichern
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  )
}
